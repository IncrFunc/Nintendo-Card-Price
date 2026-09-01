from __future__ import annotations

import importlib.util
import os
import random
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Any, Callable, Iterable

from .paths import runtime_root
from .xiaohongshu import body_text_before_tags, caption_parts, publish_pack_files, split_body_and_tags


XHS_PACKAGE = "com.xingin.xhs"
DEFAULT_REMOTE_ROOT = "/sdcard/Pictures/NintendoGamePrice"
KEYBOARD_LETTERS = {
    "q": (0.058, 0.680), "w": (0.156, 0.680), "e": (0.255, 0.680),
    "r": (0.353, 0.680), "t": (0.451, 0.680), "y": (0.550, 0.680),
    "u": (0.648, 0.680), "i": (0.745, 0.680), "o": (0.843, 0.680),
    "p": (0.942, 0.680), "a": (0.105, 0.752), "s": (0.205, 0.752),
    "d": (0.303, 0.752), "f": (0.402, 0.752), "g": (0.500, 0.752),
    "h": (0.598, 0.752), "j": (0.696, 0.752), "k": (0.795, 0.752),
    "l": (0.893, 0.752), "z": (0.205, 0.827), "x": (0.303, 0.827),
    "c": (0.402, 0.827), "v": (0.500, 0.827), "b": (0.598, 0.827),
    "n": (0.696, 0.827), "m": (0.795, 0.827),
}
TOPIC_BUTTON_POINT = (0.291, 0.565)
IME_CANDIDATE_POINT = (0.120, 0.619)
IME_LANGUAGE_POINT = (0.796, 0.898)
TOPIC_INPUT_SPECS = {
    "\u4efb\u5929\u5802Switch": (("zh", "rentiantang"), ("en", "switch")),
    "Switch\u5361\u5e26": (("en", "switch"), ("zh", "kadai")),
    "\u6e38\u620f\u56de\u6536": (("zh", "youxihuishou"),),
    "\u4e8c\u624b\u6e38\u620f": (("zh", "ershouyouxi"),),
    "\u4ef7\u683c\u8bb0\u5f55": (("zh", "jiagejilu"),),
}


class AdbPublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class AndroidDevice:
    serial: str
    state: str
    model: str | None = None
    product: str | None = None


@dataclass(frozen=True)
class AdbPublishResult:
    status: str
    serial: str
    title: str
    image_count: int
    remote_dir: str
    remote_deleted: bool
    screenshot: Path
    message: str


@dataclass(frozen=True)
class AdbImagePushResult:
    status: str
    serial: str
    image_count: int
    remote_dir: str
    remote_files: list[str]


@dataclass(frozen=True)
class AdbReplaceImagesResult:
    status: str
    serial: str
    image_count: int
    old_image_count: int
    remote_dir: str
    remote_deleted: bool
    screenshot: Path
    message: str


@dataclass(frozen=True)
class Xiaomi8TapProfile:
    create: tuple[float, float] = (0.50, 0.94)
    profile_tab: tuple[float, float] = (0.91, 0.94)
    first_profile_note: tuple[float, float] = (0.25, 0.48)
    note_more: tuple[float, float] = (0.93, 0.06)
    post_editor_first_image: tuple[float, float] = (0.14, 0.15)
    post_editor_edit_image: tuple[float, float] = (0.72, 0.72)
    image_editor_add: tuple[float, float] = (0.87, 0.846)
    image_editor_strip_add: tuple[float, float] = (0.47, 0.81)
    image_editor_album_add: tuple[float, float] = (0.22, 0.865)
    image_editor_first_thumbnail: tuple[float, float] = (0.16, 0.84)
    image_editor_delete: tuple[float, float] = (0.90, 0.08)
    image_editor_longpress_delete: tuple[float, float] = (0.11, 0.89)
    image_editor_done: tuple[float, float] = (0.90, 0.94)
    preview_delete: tuple[float, float] = (0.915, 0.715)
    note_save: tuple[float, float] = (0.88, 0.94)
    grid_columns: tuple[float, ...] = (0.282, 0.618, 0.950)
    grid_rows: tuple[float, ...] = (0.170, 0.330, 0.490, 0.650)
    next_button: tuple[float, float] = (0.90, 0.94)
    album_selector: tuple[float, float] = (0.247, 0.066)
    dedicated_album: tuple[float, float] = (0.350, 0.315)


def find_adb(explicit: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    for variable in ("ADB_PATH", "ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.getenv(variable)
        if not value:
            continue
        path = Path(value)
        candidates.append(path if path.name.lower() == "adb.exe" else path / "platform-tools/adb.exe")
    resolved = shutil.which("adb")
    if resolved:
        candidates.append(Path(resolved))
    candidates.extend(
        [
            Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("adb executable not found; pass --adb-path or set ADB_PATH")


def parse_adb_devices(output: str) -> list[AndroidDevice]:
    devices: list[AndroidDevice] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        values = {key: value for item in parts[2:] if ":" in item for key, value in [item.split(":", 1)]}
        devices.append(
            AndroidDevice(
                serial=parts[0],
                state=parts[1],
                model=values.get("model"),
                product=values.get("product"),
            )
        )
    return devices


class AdbClient:
    def __init__(self, adb_path: str | Path, serial: str | None = None, timeout: float = 30.0) -> None:
        self.adb_path = Path(adb_path)
        self.serial = serial
        self.timeout = timeout

    def _command(self, *args: str, include_serial: bool = True) -> list[str]:
        command = [str(self.adb_path)]
        if include_serial and self.serial:
            command.extend(["-s", self.serial])
        command.extend(args)
        return command

    def run(self, *args: str, include_serial: bool = True, timeout: float | None = None) -> str:
        completed = subprocess.run(
            self._command(*args, include_serial=include_serial),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or self.timeout,
            check=False,
        )
        output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        if completed.returncode != 0:
            raise AdbPublishError(f"adb command failed ({completed.returncode}): {output}")
        return output

    def shell(self, *args: str, timeout: float | None = None) -> str:
        return self.run("shell", *args, timeout=timeout)

    def devices(self) -> list[AndroidDevice]:
        return parse_adb_devices(self.run("devices", "-l", include_serial=False))

    def select_device(self) -> AndroidDevice:
        devices = self.devices()
        if self.serial:
            matches = [device for device in devices if device.serial == self.serial]
            if not matches:
                raise AdbPublishError(f"ADB device not found: {self.serial}")
            selected = matches[0]
        else:
            usable = [device for device in devices if device.state == "device"]
            if len(usable) != 1:
                raise AdbPublishError(f"expected one usable ADB device, found {len(usable)}; pass --device")
            selected = usable[0]
            self.serial = selected.serial
        if selected.state != "device":
            raise AdbPublishError(f"ADB device {selected.serial} is {selected.state}, not device")
        return selected

    def package_version(self, package: str = XHS_PACKAGE) -> str | None:
        output = self.shell("dumpsys", "package", package)
        match = re.search(r"versionName=([^\s]+)", output)
        return match.group(1) if match else None

    def root_status(self, timeout: float = 5.0) -> dict[str, Any]:
        try:
            su_path = self.shell("which", "su").strip()
        except AdbPublishError:
            su_path = ""
        if not su_path:
            return {"installed": False, "authorized": False, "su_path": None, "detail": "su not found"}
        try:
            identity = self.shell("su", "-c", "id", timeout=timeout)
        except subprocess.TimeoutExpired:
            return {
                "installed": True,
                "authorized": False,
                "su_path": su_path,
                "detail": "Magisk authorization timed out; unlock the phone and grant shell root",
            }
        except AdbPublishError as exc:
            return {"installed": True, "authorized": False, "su_path": su_path, "detail": str(exc)}
        authorized = "uid=0(root)" in identity
        return {"installed": True, "authorized": authorized, "su_path": su_path, "detail": identity.strip()}

    def is_locked(self) -> bool:
        output = self.shell("dumpsys", "window")
        return "mDreamingLockscreen=true" in output or "mShowingLockscreen=true" in output

    def wake_and_dismiss_keyguard(self) -> None:
        self.shell("input", "keyevent", "KEYCODE_WAKEUP")
        self.shell("wm", "dismiss-keyguard")
        self.shell("input", "swipe", "540", "1900", "540", "500", "350")
        time.sleep(1)
        if self.is_locked():
            raise AdbPublishError("device is protected by PIN/pattern; unlock it before publishing")

    def push_images(self, images: Iterable[Path], remote_dir: str) -> list[str]:
        self.shell("mkdir", "-p", remote_dir)
        self.shell("rm", "-f", f"{remote_dir}/*")
        remote_files: list[str] = []
        image_list = list(images)
        base_mtime = datetime.now() + timedelta(minutes=1)
        for index, image in enumerate(image_list, start=1):
            remote = f"{remote_dir}/{index:02d}_{image.name}"
            self.run("push", str(image.resolve()), remote)
            mtime = (base_mtime - timedelta(seconds=index)).strftime("%Y%m%d%H%M.%S")
            self.shell("touch", "-t", mtime, remote)
            self.shell(
                "am",
                "broadcast",
                "-a",
                "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d",
                f"file://{remote}",
            )
            remote_files.append(remote)
        return remote_files

    def remove_remote_dir(self, remote_dir: str) -> None:
        if not remote_dir.startswith(f"{DEFAULT_REMOTE_ROOT}/"):
            raise AdbPublishError(f"refusing to remove unexpected phone directory: {remote_dir}")
        self.shell("rm", "-rf", remote_dir)


def choose_device(adb_path: str | Path, serial: str | None = None) -> tuple[AdbClient, AndroidDevice]:
    client = AdbClient(adb_path, serial=serial)
    return client, client.select_device()


def _phone_album_name_for_pack(pack_path: Path) -> str:
    return "-".join(part for part in pack_path.parts[-2:] if part) or pack_path.name


def adb_device_report(adb_path: str | Path | None = None, serial: str | None = None) -> dict[str, Any]:
    resolved_adb = find_adb(adb_path)
    client, device = choose_device(resolved_adb, serial)
    root = client.root_status()
    return {
        "adb": str(resolved_adb),
        "serial": device.serial,
        "state": device.state,
        "model": device.model,
        "product": device.product,
        "android": client.shell("getprop", "ro.build.version.release").strip(),
        "xiaohongshu_package": XHS_PACKAGE,
        "xiaohongshu_version": client.package_version(),
"locked": client.is_locked(),
        "root_installed": root["installed"],
        "root_authorized": root["authorized"],
        "root_su_path": root["su_path"],
        "root_detail": root["detail"],
        "uiautomator2_installed": importlib.util.find_spec("uiautomator2") is not None,
    }


def _connect_uiautomator(serial: str) -> Any:
    try:
        import uiautomator2 as u2
    except ImportError as exc:
        raise AdbPublishError("uiautomator2 is required; run: pip install -r requirements.txt") from exc
    return u2.connect(serial)


def _human_pause(minimum: float = 0.35, maximum: float = 1.25) -> None:
    mode = minimum + (maximum - minimum) * 0.32
    time.sleep(random.triangular(minimum, maximum, mode))


def _maybe_hesitate(chance: float = 0.2, minimum: float = 0.9, maximum: float = 2.8) -> None:
    if random.random() < chance:
        _human_pause(minimum, maximum)


def _human_tap(
    device: Any,
    *,
    bounds: dict[str, int] | None = None,
    point: tuple[float, float] | None = None,
) -> tuple[int, int, float]:
    width, height = device.window_size()
    _human_pause(0.08, 0.42)
    if bounds:
        left, right = bounds["left"], bounds["right"]
        top, bottom = bounds["top"], bounds["bottom"]
        inset_x = min(max((right - left) * 0.18, 3), max((right - left) / 2 - 1, 0))
        inset_y = min(max((bottom - top) * 0.18, 3), max((bottom - top) / 2 - 1, 0))
        x = random.triangular(left + inset_x, right - inset_x, (left + right) / 2)
        y = random.triangular(top + inset_y, bottom - inset_y, (top + bottom) / 2)
    elif point:
        base_x, base_y = width * point[0], height * point[1]
        x = random.triangular(base_x - width * 0.012, base_x + width * 0.012, base_x)
        y = random.triangular(base_y - height * 0.008, base_y + height * 0.008, base_y)
    else:
        raise ValueError("bounds or point is required")
    x = int(max(1, min(width - 2, x)))
    y = int(max(1, min(height - 2, y)))
    hold = random.triangular(0.045, 0.185, 0.075)
    device.touch.down(x, y)
    time.sleep(hold)
    device.touch.up(x, y)
    _human_pause(0.20, 0.95)
    return x, y, hold


def _human_tap_element(device: Any, element: Any) -> tuple[int, int, float]:
    info = element.info
    bounds = info.get("bounds")
    if not bounds:
        raise AdbPublishError("UI element has no tappable bounds")
    return _human_tap(device, bounds=bounds)


def _click_any(device: Any, selectors: list[dict[str, str]], timeout: float = 1.5) -> bool:
    for selector in selectors:
        element = device(**selector)
        if element.exists(timeout=timeout):
            _human_tap_element(device, element)
            return True
    return False


def _relative_click(device: Any, point: tuple[float, float]) -> None:
    _human_tap(device, point=point)


def _element_exists(element: Any, timeout: float = 0.0) -> bool:
    exists = element.exists
    return bool(exists(timeout=timeout) if callable(exists) else exists)


def _prepare_xhs_home(device: Any) -> None:
    device.app_stop(XHS_PACKAGE)
    device.app_start(XHS_PACKAGE, stop=True)
    _human_pause(3.5, 7.0)
    save_draft = "\u5b58\u8349\u7a3f"
    if _click_any(device, [{"text": save_draft}], timeout=2):
        _human_pause(1.5, 3.5)
    activity = device.app_current().get("activity", "")
    if "IndexActivity" not in activity:
        raise AdbPublishError(f"Xiaohongshu is not on the home page: {activity}")


def _dismiss_optional_media_location_dialog(device: Any) -> None:
    deny = "\u62d2\u7edd"
    if _click_any(device, [{"text": deny}], timeout=1):
        _human_pause(0.8, 1.8)
    _human_pause(1.2, 3.0)


def _click_final_publish_button(device: Any, profile: Xiaomi8TapProfile) -> bool:
    if _click_any(device, [{"text": "\u5b8c\u6210"}, {"description": "\u5b8c\u6210"}], timeout=1):
        _human_pause(0.8, 1.6)
    publish_selectors = [
        {"textMatches": "^(\u53d1\u7b14\u8bb0|\u53d1\u5e03|\u53d1\u5e03\u7b14\u8bb0)$"},
        {"descriptionMatches": "^(\u53d1\u7b14\u8bb0|\u53d1\u5e03|\u53d1\u5e03\u7b14\u8bb0)$"},
        {"textContains": "\u53d1\u7b14\u8bb0"},
        {"descriptionContains": "\u53d1\u7b14\u8bb0"},
    ]
    if _click_any(device, publish_selectors, timeout=3):
        return True
    _relative_click(device, profile.next_button)
    return True


def _wait_for_activity(device: Any, expected: str, timeout: float = 8.0) -> str:
    deadline = time.monotonic() + timeout
    activity = ""
    while time.monotonic() < deadline:
        activity = device.app_current().get("activity", "")
        if expected in activity:
            return activity
        _human_pause(0.30, 0.70)
    raise AdbPublishError(f"Xiaohongshu page did not become {expected}: {activity}")


def _open_image_picker(device: Any, profile: Xiaomi8TapProfile) -> None:
    opened = _click_any(device, [{"description": "\u53d1\u5e03"}], timeout=2)
    if not opened:
        _relative_click(device, profile.create)
    _human_pause(0.8, 2.0)
    _click_any(
        device,
        [
            {"textMatches": ".*(\u4e0a\u4f20\u56fe\u6587|\u53d1\u56fe\u6587|\u4ece\u76f8\u518c\u9009\u62e9|\u76f8\u518c).*"},
            {"descriptionMatches": ".*(\u4e0a\u4f20\u56fe\u6587|\u53d1\u56fe\u6587|\u4ece\u76f8\u518c\u9009\u62e9|\u76f8\u518c).*"},
        ],
        timeout=2.5,
    )
    _human_pause(1.2, 3.0)
    _wait_for_activity(device, "CapaAlbumActivity")


def _album_candidate(device: Any, album_name: str, timeout: float = 0.4) -> Any | None:
    selectors = [
        {"text": album_name},
        {"description": album_name},
        {"textContains": album_name},
        {"descriptionContains": album_name},
    ]
    for selector in selectors:
        element = device(**selector)
        if _element_exists(element, timeout=timeout):
            return element
    return None


def _scroll_album_list(device: Any) -> None:
    width, height = device.window_size()
    device.swipe(
        int(width * 0.50),
        int(height * 0.80),
        int(width * 0.50),
        int(height * 0.24),
        duration=0.35,
    )
    _human_pause(0.55, 1.15)


def _open_dedicated_album(device: Any, profile: Xiaomi8TapProfile, album_name: str) -> None:
    _relative_click(device, profile.album_selector)
    _human_pause(0.75, 1.65)
    album = _album_candidate(device, album_name, timeout=1.0)
    for _ in range(6):
        if album is not None:
            _human_tap_element(device, album)
            break
        _scroll_album_list(device)
        album = _album_candidate(device, album_name, timeout=0.6)
    else:
        raise AdbPublishError(f"dedicated album was not found: {album_name}")
    _human_pause(1.0, 2.2)
    header = device(text=album_name)
    if not _element_exists(header, timeout=2):
        raise AdbPublishError(f"dedicated album did not open: {album_name}")

def _select_newest_images(
    device: Any,
    count: int,
    profile: Xiaomi8TapProfile,
    *,
    expected_activity: str | None = "CapaPost",
) -> None:
    if count < 1:
        raise AdbPublishError("publish pack has no images")
    capacity = len(profile.grid_columns) * len(profile.grid_rows)
    if count > capacity:
        raise AdbPublishError(f"ADB picker profile supports at most {capacity} images, got {count}")
    selected = 0
    for row in profile.grid_rows:
        for column in profile.grid_columns:
            if selected >= count:
                break
            _relative_click(device, (column, row))
            selected += 1
            _human_pause(0.18, 0.72)
            _maybe_hesitate(0.24, 0.9, 2.7)
        if selected >= count:
            break
    if not _click_any(device, [{"textMatches": ".*(\u4e0b\u4e00\u6b65|\u5b8c\u6210).*"}], timeout=2):
        _relative_click(device, profile.next_button)
    _human_pause(2.5, 5.5)
    if _click_any(device, [{"textMatches": "^\u4e0b\u4e00\u6b65$"}], timeout=2):
        _human_pause(2.5, 5.5)
    if expected_activity:
        _wait_for_activity(device, expected_activity, timeout=10.0)


def _profile_note_candidate(device: Any, note_hint: str) -> Any | None:
    selectors = [
        {"descriptionContains": note_hint},
        {"textContains": note_hint},
        {"descriptionMatches": f".*{re.escape(note_hint)}.*"},
        {"textMatches": f".*{re.escape(note_hint)}.*"},
    ]
    for selector in selectors:
        element = device(**selector)
        if _element_exists(element, timeout=0.6):
            return element
    return None


def _open_profile_latest_note(device: Any, profile: Xiaomi8TapProfile, note_hint: str | None = None) -> None:
    if not _click_any(
        device,
        [
            {"text": "\u6211\u7684"},
            {"description": "\u6211\u7684"},
        ],
        timeout=2,
    ):
        _relative_click(device, profile.profile_tab)
    _human_pause(1.6, 3.5)
    width, height = device.window_size()
    device.swipe(
        int(width * 0.50),
        int(height * 0.78),
        int(width * 0.50),
        int(height * 0.36),
        duration=0.35,
    )
    _human_pause(0.9, 2.0)
    if note_hint:
        for _ in range(4):
            candidate = _profile_note_candidate(device, note_hint)
            if candidate is not None:
                _human_tap_element(device, candidate)
                _human_pause(2.0, 4.5)
                return
            device.swipe(
                int(width * 0.50),
                int(height * 0.66),
                int(width * 0.50),
                int(height * 0.28),
                duration=0.35,
            )
            _human_pause(0.9, 2.0)
    _relative_click(device, profile.first_profile_note)
    _human_pause(2.0, 4.5)
def _open_note_edit_from_detail(device: Any, profile: Xiaomi8TapProfile) -> None:
    if _click_any(
        device,
        [
            {"textMatches": ".*(编辑和权限设置|编辑与权限设置).*"},
            {"descriptionMatches": ".*(编辑和权限设置|编辑与权限设置).*"},
        ],
        timeout=2,
    ):
        _human_pause(0.8, 1.8)
        if _click_any(device, [{"text": "编辑"}, {"description": "编辑"}], timeout=2.5):
            _human_pause(2.0, 4.5)
            return
    if not _click_any(
        device,
        [
            {"textMatches": ".*(更多|更多操作|菜单).*"},
            {"descriptionMatches": ".*(更多|更多操作|菜单|more|More).*"},
        ],
        timeout=2,
    ):
        _relative_click(device, profile.note_more)
    _human_pause(0.8, 2.0)
    if not _click_any(
        device,
        [
            {"textMatches": ".*(编辑|编辑笔记|修改).*"},
            {"descriptionMatches": ".*(编辑|编辑笔记|修改).*"},
        ],
        timeout=4,
    ):
        raise AdbPublishError("latest note edit button was not found")
    _click_any(
        device,
        [
            {"textMatches": ".*(继续编辑|确认|确定|知道了).*"},
            {"descriptionMatches": ".*(继续编辑|确认|确定|知道了).*"},
        ],
        timeout=1.5,
    )
    _human_pause(2.0, 4.5)


def _open_first_image_editor(device: Any, profile: Xiaomi8TapProfile) -> None:
    _relative_click(device, profile.post_editor_first_image)
    _human_pause(0.7, 1.8)
    _wait_for_activity(device, "CapaNotePreview", timeout=30.0)
    if not _click_any(
        device,
        [
            {"textMatches": ".*(编辑图片|编辑照片|修图).*"},
            {"descriptionMatches": ".*(编辑图片|编辑照片|修图).*"},
        ],
        timeout=2,
    ):
        _relative_click(device, profile.post_editor_edit_image)
    _human_pause(1.1, 2.6)
    _wait_for_activity(device, "ImageEditActivity3", timeout=15.0)


def _swipe_image_editor_to_end(device: Any, swipes: int = 10) -> None:
    width, height = device.window_size()
    for _ in range(swipes):
        device.swipe(
            int(width * 0.93),
            int(height * 0.855),
            int(width * 0.08),
            int(height * 0.855),
            duration=0.45,
        )
        _human_pause(0.22, 0.58)


def _swipe_image_editor_to_start(device: Any, swipes: int = 10) -> None:
    width, height = device.window_size()
    for _ in range(swipes):
        device.swipe(
            int(width * 0.08),
            int(height * 0.855),
            int(width * 0.93),
            int(height * 0.855),
            duration=0.45,
        )
        _human_pause(0.22, 0.58)


def _image_editor_thumbnail_bounds(device: Any) -> list[dict[str, int]]:
    try:
        xml = device.dump_hierarchy()
    except Exception:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    width, height = device.window_size()
    lower_top = int(height * 0.82)
    lower_bottom = int(height * 0.90)
    bounds_list: list[dict[str, int]] = []
    for node in root.iter("node"):
        if node.attrib.get("clickable") != "true":
            continue
        bounds = node.attrib.get("bounds", "")
        nums = [int(x) for x in re.findall(r"\d+", bounds)]
        if len(nums) != 4:
            continue
        left, top, right, bottom = nums
        if top < lower_top or bottom > lower_bottom:
            continue
        if right - left < int(width * 0.08):
            continue
        bounds_list.append({"left": left, "top": top, "right": right, "bottom": bottom})
    return sorted(bounds_list, key=lambda bounds: bounds["left"])


def _human_long_press_bounds(device: Any, bounds: dict[str, int]) -> None:
    width, height = device.window_size()
    left, top, right, bottom = bounds["left"], bounds["top"], bounds["right"], bounds["bottom"]
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    x = int(random.triangular(center_x - 10, center_x + 10, center_x))
    y = int(random.triangular(center_y - 8, center_y + 8, center_y))
    x = max(1, min(width - 2, x))
    y = max(1, min(height - 2, y))
    _human_pause(0.18, 0.55)
    device.touch.down(x, y)
    time.sleep(random.triangular(0.62, 0.96, 0.74))
    device.touch.up(x, y)
    _human_pause(0.35, 0.85)


def _click_image_editor_add_tile(device: Any, profile: Xiaomi8TapProfile) -> bool:
    candidates = _image_editor_thumbnail_bounds(device)
    if candidates:
        _human_tap(device, bounds=candidates[-1])
        return True
    _relative_click(device, profile.image_editor_add)
    return True


def _append_new_images_from_album(
    device: Any,
    profile: Xiaomi8TapProfile,
    album_name: str,
    image_count: int,
) -> None:
    _wait_for_activity(device, "ImageEditActivity3", timeout=4.0)
    _swipe_image_editor_to_end(device, 8)
    _human_pause(0.9, 2.0)
    _click_image_editor_add_tile(device, profile)
    _human_pause(0.9, 2.0)
    if "ImageEditActivity3" in device.app_current().get("activity", ""):
        _swipe_image_editor_to_end(device, 4)
        _human_pause(0.8, 1.6)
        _click_image_editor_add_tile(device, profile)
        _human_pause(0.9, 2.0)
    _wait_for_activity(device, "MaterialSelectActivity", timeout=10.0)
    _open_dedicated_material_album(device, album_name)
    _select_material_album_images(device, image_count)
    _human_pause(1.6, 3.8)


def _material_album_selected(device: Any, album_name: str) -> bool:
    title = device(text=album_name)
    return _element_exists(title, timeout=0.6)


def _open_dedicated_material_album(device: Any, album_name: str) -> None:
    if _material_album_selected(device, album_name):
        return
    if not _click_any(
        device,
        [
            {"textMatches": ".*(全部|相册).*"},
            {"descriptionMatches": ".*(全部|相册).*"},
        ],
        timeout=2,
    ):
        _relative_click(device, (0.52, 0.065))
    _human_pause(0.8, 1.8)
    album = _album_candidate(device, album_name, timeout=1.0)
    for _ in range(6):
        if album is not None:
            _human_tap_element(device, album)
            _human_pause(0.9, 1.8)
            return
        _scroll_album_list(device)
        album = _album_candidate(device, album_name, timeout=0.6)
    raise AdbPublishError(f"dedicated material album was not found: {album_name}")


def _material_selection_bounds(device: Any) -> list[dict[str, int]]:
    hierarchy = device.dump_hierarchy()
    bounds: list[dict[str, int]] = []
    pattern = re.compile(
        r'class="android\.widget\.FrameLayout"[^>]*clickable="true"[^>]*'
        r'selected="false"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    )
    for match in pattern.finditer(hierarchy):
        left, top, right, bottom = [int(value) for value in match.groups()]
        width = right - left
        height = bottom - top
        if 80 <= width <= 180 and 80 <= height <= 180 and top > 180:
            bounds.append({"left": left, "top": top, "right": right, "bottom": bottom})
    bounds.sort(key=lambda item: (item["top"], item["left"]))
    return bounds


def _select_material_album_images(device: Any, count: int) -> None:
    _scroll_material_album_to_top(device)
    selected = 0
    while selected < count:
        candidates = _material_selection_bounds(device)
        if not candidates:
            raise AdbPublishError(f"no selectable images found in material album after selecting {selected}/{count}")
        for bounds in candidates:
            if selected >= count:
                break
            _human_tap(device, bounds=bounds)
            selected += 1
            _human_pause(0.18, 0.55)
        if selected < count:
            width, height = device.window_size()
            device.swipe(
                int(width * 0.50),
                int(height * 0.82),
                int(width * 0.50),
                int(height * 0.30),
                duration=0.35,
            )
            _human_pause(0.55, 1.15)
    if not _click_any(
        device,
        [
            {"textMatches": ".*下一步.*"},
            {"descriptionMatches": ".*下一步.*"},
        ],
        timeout=2,
    ):
        _relative_click(device, (0.82, 0.94))
    _human_pause(4.5, 8.0)
    _wait_for_activity(device, "ImageEditActivity3", timeout=12.0)


def _delete_images_from_image_editor(device: Any, profile: Xiaomi8TapProfile, count: int) -> None:
    if count < 0:
        raise AdbPublishError(f"old image count must not be negative: {count}")
    if count == 0:
        return
    _wait_for_activity(device, "ImageEditActivity3", timeout=12.0)
    _swipe_image_editor_to_start(device, min(count, 8))
    for _ in range(count):
        thumbnails = _image_editor_thumbnail_bounds(device)
        if thumbnails:
            _human_long_press_bounds(device, thumbnails[0])
        else:
            _human_long_press(device, profile.image_editor_first_thumbnail)
        _human_pause(0.6, 1.4)
        if not _click_any(
            device,
            [
                {"text": "\u5220\u9664"},
                {"textMatches": ".*(\u5220\u9664|\u79fb\u9664).*"},
                {"descriptionMatches": ".*(\u5220\u9664|\u79fb\u9664).*"},
            ],
            timeout=2.0,
        ):
            _relative_click(device, profile.image_editor_longpress_delete)
        _human_pause(0.8, 1.8)
    _human_pause(1.0, 2.5)


def _scroll_material_album_to_top(device: Any, swipes: int = 8) -> None:
    width, height = device.window_size()
    for _ in range(swipes):
        device.swipe(
            int(width * 0.50),
            int(height * 0.32),
            int(width * 0.50),
            int(height * 0.86),
            duration=0.35,
        )
        _human_pause(0.18, 0.42)


def _delete_front_images_from_preview(
    device: Any,
    profile: Xiaomi8TapProfile,
    count: int,
    *,
    total_image_count: int | None = None,
) -> None:
    if count < 0:
        raise AdbPublishError(f"old image count must not be negative: {count}")
    if count == 0:
        return
    _wait_for_activity(device, "CapaNotePreview", timeout=8.0)
    swipe_count = count
    if total_image_count is not None:
        swipe_count = max(swipe_count, total_image_count - 1)
    _swipe_preview_to_first_image(device, swipe_count)
    for _ in range(count):
        if not _click_any(
            device,
            [
                {"textMatches": ".*(删除|移除).*"},
                {"descriptionMatches": ".*(删除|移除).*"},
            ],
            timeout=1.5,
        ):
            _relative_click(device, profile.preview_delete)
        _click_any(
            device,
            [
                {"textMatches": "^(删除|确认|确定)$"},
                {"descriptionMatches": "^(删除|确认|确定)$"},
            ],
            timeout=2,
        )
        _human_pause(0.8, 1.8)


def _preview_page_position(device: Any) -> tuple[int, int] | None:
    try:
        hierarchy = device.dump_hierarchy()
    except AttributeError:
        return None
    match = re.search(r'(?:(?:text|content-desc)=")(\d+)/(\d+)"', hierarchy)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _delete_front_images_from_preview_counted(
    device: Any,
    profile: Xiaomi8TapProfile,
    count: int,
    *,
    total_image_count: int,
) -> None:
    target_total = max(total_image_count - count, 1)
    swipe_count = max(count, total_image_count - 1)
    deleted = 0
    while deleted < count:
        _swipe_preview_to_first_image(device, swipe_count)
        before = _preview_page_position(device)
        if before is not None and before[1] <= target_total:
            break
        if not _click_any(
            device,
            [
                {"text": "\u5220\u9664"},
                {"textMatches": ".*(\u5220\u9664|\u79fb\u9664).*"},
                {"descriptionMatches": ".*(\u5220\u9664|\u79fb\u9664).*"},
            ],
            timeout=1.5,
        ):
            _relative_click(device, profile.preview_delete)
        _click_any(
            device,
            [
                {"textMatches": "^(\u5220\u9664|\u786e\u8ba4|\u786e\u5b9a)$"},
                {"descriptionMatches": "^(\u5220\u9664|\u786e\u8ba4|\u786e\u5b9a)$"},
            ],
            timeout=2,
        )
        _human_pause(0.8, 1.8)
        deleted += 1
        after = _preview_page_position(device)
        if before is not None and after is not None and after[1] >= before[1]:
            raise AdbPublishError(f"preview image delete did not reduce image count: {before} -> {after}")
    final = _preview_page_position(device)
    if final is not None and final[1] != target_total:
        raise AdbPublishError(f"preview image count is {final[1]}, expected {target_total}")


def _swipe_preview_to_first_image(device: Any, swipes: int) -> None:
    width, height = device.window_size()
    position = _preview_page_position(device)
    if position is not None and position[0] == 1:
        return
    for _ in range(swipes):
        position = _preview_page_position(device)
        if position is not None and position[0] == 1:
            return
        device.swipe(
            int(width * 0.18),
            int(height * 0.46),
            int(width * 0.86),
            int(height * 0.46),
            duration=0.32,
        )
        _human_pause(0.18, 0.45)


def _finish_image_editor(device: Any, profile: Xiaomi8TapProfile) -> None:
    if not _click_any(
        device,
        [
            {"textMatches": "^(完成|保存|下一步)$"},
            {"descriptionMatches": "^(完成|保存|下一步)$"},
        ],
        timeout=2,
    ):
        _relative_click(device, profile.image_editor_done)
    _human_pause(1.2, 3.0)
    _wait_for_activity(device, "CapaNotePreview", timeout=10.0)


def _replace_note_images_from_album(
    device: Any,
    profile: Xiaomi8TapProfile,
    album_name: str,
    new_image_count: int,
    old_image_count: int,
) -> None:
    if new_image_count < 1:
        raise AdbPublishError("replacement publish pack has no images")
    _open_first_image_editor(device, profile)
    placeholder_count = 1 if old_image_count > 0 else 0
    old_images_to_remove_before_append = max(old_image_count - placeholder_count, 0)
    _delete_images_from_image_editor(device, profile, old_images_to_remove_before_append)
    _append_new_images_from_album(device, profile, album_name, new_image_count)
    _finish_image_editor(device, profile)
    if placeholder_count:
        _delete_front_images_from_preview_counted(
            device,
            profile,
            placeholder_count,
            total_image_count=placeholder_count + new_image_count,
        )


def _save_note_edit(device: Any, profile: Xiaomi8TapProfile) -> None:
    if not _click_any(
        device,
        [
            {"textMatches": "^(保存|发布|完成|更新|提交)$"},
            {"descriptionMatches": "^(保存|发布|完成|更新|提交)$"},
        ],
        timeout=3,
    ):
        _relative_click(device, profile.note_save)
    _click_any(
        device,
        [
            {"textMatches": ".*(确认|确定|继续|保存修改|发布修改).*"},
            {"descriptionMatches": ".*(确认|确定|继续|保存修改|发布修改).*"},
        ],
        timeout=2,
    )
    _human_pause(3.5, 7.0)


def _human_long_press_element(device: Any, element: Any) -> None:
    bounds = element.info.get("bounds")
    if not bounds:
        raise AdbPublishError("UI element has no long-press bounds")
    width, height = device.window_size()
    center_x = (bounds["left"] + bounds["right"]) / 2
    center_y = (bounds["top"] + bounds["bottom"]) / 2
    x = int(random.triangular(center_x - 18, center_x + 18, center_x))
    y = int(random.triangular(center_y - 10, center_y + 10, center_y))
    x = max(1, min(width - 2, x))
    y = max(1, min(height - 2, y))
    _human_pause(0.18, 0.55)
    device.touch.down(x, y)
    time.sleep(random.triangular(0.62, 0.96, 0.74))
    device.touch.up(x, y)
    _human_pause(0.35, 0.85)


def _human_long_press(device: Any, point: tuple[float, float]) -> None:
    width, height = device.window_size()
    base_x, base_y = width * point[0], height * point[1]
    x = int(random.triangular(base_x - width * 0.008, base_x + width * 0.008, base_x))
    y = int(random.triangular(base_y - height * 0.006, base_y + height * 0.006, base_y))
    x = max(1, min(width - 2, x))
    y = max(1, min(height - 2, y))
    _human_pause(0.18, 0.55)
    device.touch.down(x, y)
    time.sleep(random.triangular(0.62, 0.96, 0.74))
    device.touch.up(x, y)
    _human_pause(0.35, 0.85)


def _paste_via_touch(device: Any, field: Any, text: str) -> None:
    device.set_clipboard(text, label="NintendoGamePrice")
    _human_tap_element(device, field)
    _human_long_press_element(device, field)
    pasted = _click_any(
        device,
        [{"text": "\u7c98\u8d34"}, {"textMatches": ".*(\u7c98\u8d34|Paste).*"}],
        timeout=2.5,
    )
    if not pasted:
        raise AdbPublishError("paste menu did not appear after long press")
    _human_pause(0.55, 1.35)


def _keyboard_tap(device: Any, point: tuple[float, float]) -> None:
    width, height = device.window_size()
    base_x, base_y = width * point[0], height * point[1]
    x = int(random.triangular(base_x - width * 0.005, base_x + width * 0.005, base_x))
    y = int(random.triangular(base_y - height * 0.003, base_y + height * 0.003, base_y))
    _human_pause(0.018, 0.085)
    hold = random.triangular(0.042, 0.125, 0.064)
    device.touch.down(x, y)
    time.sleep(hold)
    device.touch.up(x, y)
    _human_pause(0.035, 0.18)

def _tap_keyboard_text(device: Any, text: str) -> None:
    for index, character in enumerate(text.lower()):
        point = KEYBOARD_LETTERS.get(character)
        if point is None:
            raise AdbPublishError(f"unsupported keyboard character: {character}")
        _keyboard_tap(device, point)
        if index > 1 and random.random() < 0.13:
            _human_pause(0.28, 0.95)


def _tap_first_topic_candidate(device: Any, body_field: Any) -> None:
    _, height = device.window_size()
    bottom = body_field.info["bounds"]["bottom"]
    candidate_y = min((bottom + 50) / height, 0.52)
    _relative_click(device, (0.28, candidate_y))


def _select_clickable_topics(device: Any, body_field: Any, tags: list[str]) -> None:
    keyboard_mode = "zh"
    for tag in tags:
        segments = TOPIC_INPUT_SPECS.get(tag)
        if segments is None:
            raise AdbPublishError(f"no coordinate keyboard plan for topic: {tag}")
        _relative_click(device, TOPIC_BUTTON_POINT)
        _human_pause(0.45, 1.05)
        for segment_mode, text in segments:
            if segment_mode != keyboard_mode:
                _relative_click(device, IME_LANGUAGE_POINT)
                keyboard_mode = segment_mode
                _human_pause(0.35, 0.85)
            _tap_keyboard_text(device, text)
            if segment_mode == "zh":
                _human_pause(0.35, 0.90)
                _relative_click(device, IME_CANDIDATE_POINT)
                _human_pause(0.45, 1.10)
        _human_pause(0.65, 1.35)
        _tap_first_topic_candidate(device, body_field)
        _human_pause(0.75, 1.65)

def _field_text(field: Any) -> str:
    try:
        return field.get_text() or ""
    except (AttributeError, RuntimeError):
        return str(field.info.get("text", ""))


def _wait_for_edit_fields(device: Any, timeout: float = 12.0) -> Any:
    deadline = time.monotonic() + timeout
    fields = device(className="android.widget.EditText")
    while fields.count < 1 and time.monotonic() < deadline:
        _human_pause(0.30, 0.75)
        fields = device(className="android.widget.EditText")
    if fields.count < 1:
        raise AdbPublishError("could not find Xiaohongshu title/body fields")
    return fields


def _fill_post(device: Any, title: str, body: str) -> None:
    main_body, tags = split_body_and_tags(body)
    fields = _wait_for_edit_fields(device)
    _paste_via_touch(device, fields[0], title)
    if fields.count >= 2:
        body_field = fields[1]
        _human_tap_element(device, body_field)
    else:
        if not _click_any(
            device,
            [
                {"textMatches": ".*(\u6dfb\u52a0\u6b63\u6587|\u8f93\u5165\u6b63\u6587|\u6b63\u6587).*"},
                {"descriptionMatches": ".*(\u6dfb\u52a0\u6b63\u6587|\u8f93\u5165\u6b63\u6587|\u6b63\u6587).*"},
            ],
            timeout=2,
        ):
            raise AdbPublishError("could not find Xiaohongshu body field")
        fields = device(className="android.widget.EditText")
        if fields.count < 2:
            raise AdbPublishError("Xiaohongshu body field did not become editable")
        body_field = fields[1]
    _human_pause(0.7, 2.1)
    _paste_via_touch(device, body_field, body_text_before_tags(main_body, tags))
    _select_clickable_topics(device, body_field, tags)
    _human_pause(0.9, 2.6)
    if _field_text(fields[0]).strip() != title.strip():
        raise AdbPublishError("Xiaohongshu title verification failed")
    body_text = _field_text(body_field).strip()
    if not body_text.startswith(main_body.strip()):
        raise AdbPublishError("Xiaohongshu body verification failed")
    missing_tags = [tag for tag in tags if tag.lower() not in body_text.lower()]
    if missing_tags:
        raise AdbPublishError(f"Xiaohongshu clickable topics missing: {missing_tags}")


def publish_pack_via_adb(
    pack_dir: str | Path,
    *,
    adb_path: str | Path | None = None,
    serial: str | None = None,
    publish: bool = False,
    output_dir: str | Path | None = None,
    device_factory: Callable[[str], Any] = _connect_uiautomator,
) -> AdbPublishResult:
    pack_path = Path(pack_dir)
    images, caption_path = publish_pack_files(pack_path)
    title, body = caption_parts(caption_path)
    resolved_adb = find_adb(adb_path)
    client, selected = choose_device(resolved_adb, serial)
    client.wake_and_dismiss_keyguard()

    session_name = _phone_album_name_for_pack(pack_path)
    remote_dir = f"{DEFAULT_REMOTE_ROOT}/{session_name}"
    client.push_images(images, remote_dir)

    device = device_factory(selected.serial)
    screenshot_dir = Path(output_dir) if output_dir else runtime_root() / "adb-xhs"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / "xhs_adb_ready.png"
    profile = Xiaomi8TapProfile()

    device.screen_on()
    _prepare_xhs_home(device)
    _open_image_picker(device, profile)
    _open_dedicated_album(device, profile, session_name)
    _select_newest_images(device, len(images), profile)
    _dismiss_optional_media_location_dialog(device)
    _fill_post(device, title, body)
    device.screenshot(str(screenshot_path))
    if publish:
        if not _click_final_publish_button(device, profile):
            raise AdbPublishError("final publish button was not found")
        _human_pause(3.5, 7.0)
        screenshot_path = screenshot_dir / "xhs_adb_after_publish.png"
        device.screenshot(str(screenshot_path))
        client.remove_remote_dir(remote_dir)
        status = "submitted"
        remote_deleted = True
        message = "final publish button clicked; phone images removed"
    else:
        status = "ready"
        remote_deleted = False
        message = "post filled and waiting for review; pass --publish to submit"

    return AdbPublishResult(
        status=status,
        serial=selected.serial,
        title=title,
        image_count=len(images),
        remote_dir=remote_dir,
        remote_deleted=remote_deleted,
        screenshot=screenshot_path,
        message=message,
    )


def replace_latest_note_images_via_adb(
    pack_dir: str | Path,
    *,
    adb_path: str | Path | None = None,
    serial: str | None = None,
    old_image_count: int | None = None,
    submit: bool = False,
    output_dir: str | Path | None = None,
    device_factory: Callable[[str], Any] = _connect_uiautomator,
) -> AdbReplaceImagesResult:
    pack_path = Path(pack_dir)
    images, _ = publish_pack_files(pack_path)
    resolved_adb = find_adb(adb_path)
    client, selected = choose_device(resolved_adb, serial)
    client.wake_and_dismiss_keyguard()

    album_name = _phone_album_name_for_pack(pack_path)
    remote_dir = f"{DEFAULT_REMOTE_ROOT}/{album_name}"
    client.push_images(images, remote_dir)

    replacement_old_count = old_image_count if old_image_count is not None else len(images)
    if replacement_old_count < 0:
        raise AdbPublishError(f"old image count must not be negative: {replacement_old_count}")

    device = device_factory(selected.serial)
    screenshot_dir = Path(output_dir) if output_dir else runtime_root() / "adb-xhs"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    profile = Xiaomi8TapProfile()

    device.screen_on()
    _prepare_xhs_home(device)
    _open_profile_latest_note(device, profile, note_hint=pack_path.name)
    _open_note_edit_from_detail(device, profile)
    _replace_note_images_from_album(
        device,
        profile,
        album_name,
        len(images),
        replacement_old_count,
    )

    if submit:
        _save_note_edit(device, profile)
        screenshot_path = screenshot_dir / "xhs_adb_replace_after_submit.png"
        device.screenshot(str(screenshot_path))
        client.remove_remote_dir(remote_dir)
        status = "submitted"
        remote_deleted = True
        message = "latest note images replaced and phone images removed"
    else:
        screenshot_path = screenshot_dir / "xhs_adb_replace_ready.png"
        device.screenshot(str(screenshot_path))
        status = "ready"
        remote_deleted = False
        message = "latest note images replaced in editor; pass --submit to save and remove phone images"

    return AdbReplaceImagesResult(
        status=status,
        serial=selected.serial,
        image_count=len(images),
        old_image_count=replacement_old_count,
        remote_dir=remote_dir,
        remote_deleted=remote_deleted,
        screenshot=screenshot_path,
        message=message,
    )


def push_publish_pack_images_via_adb(
    pack_dir: str | Path,
    *,
    adb_path: str | Path | None = None,
    serial: str | None = None,
) -> AdbImagePushResult:
    pack_path = Path(pack_dir)
    images, _ = publish_pack_files(pack_path)
    resolved_adb = find_adb(adb_path)
    client, selected = choose_device(resolved_adb, serial)
    session_name = _phone_album_name_for_pack(pack_path)
    remote_dir = f"{DEFAULT_REMOTE_ROOT}/{session_name}"
    remote_files = client.push_images(images, remote_dir)
    return AdbImagePushResult(
        status="pushed",
        serial=selected.serial,
        image_count=len(remote_files),
        remote_dir=remote_dir,
        remote_files=remote_files,
    )
