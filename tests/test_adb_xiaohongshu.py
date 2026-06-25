from pathlib import Path

import pytest

from nsg_price.adb_xiaohongshu import AdbClient, AndroidDevice, find_adb, parse_adb_devices


def test_parse_adb_devices_reads_xiaomi8_metadata():
    output = """List of devices attached
2527b8b device product:dipper model:MI_8 device:dipper transport_id:1
emulator-5554 offline transport_id:2
"""

    devices = parse_adb_devices(output)

    assert devices == [
        AndroidDevice(serial="2527b8b", state="device", model="MI_8", product="dipper"),
        AndroidDevice(serial="emulator-5554", state="offline"),
    ]


def test_find_adb_accepts_explicit_path(tmp_path: Path):
    adb = tmp_path / "adb.exe"
    adb.write_bytes(b"")

    assert find_adb(adb) == adb.resolve()


def test_select_device_requires_unambiguous_usable_device(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    client = AdbClient(tmp_path / "adb.exe")
    monkeypatch.setattr(
        client,
        "devices",
        lambda: [
            AndroidDevice(serial="one", state="device"),
            AndroidDevice(serial="two", state="device"),
        ],
    )

    with pytest.raises(RuntimeError, match="pass --device"):
        client.select_device()


def test_select_device_uses_requested_serial(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    client = AdbClient(tmp_path / "adb.exe", serial="2527b8b")
    expected = AndroidDevice(serial="2527b8b", state="device", model="MI_8")
    monkeypatch.setattr(client, "devices", lambda: [expected])

    assert client.select_device() == expected


def test_push_images_resets_remote_dir_and_preserves_picker_order(tmp_path: Path):
    class Client(AdbClient):
        def __init__(self) -> None:
            super().__init__(tmp_path / "adb.exe")
            self.commands = []

        def run(self, *args: str, include_serial: bool = True, timeout: float | None = None) -> str:
            self.commands.append(("run", args))
            return ""

        def shell(self, *args: str, timeout: float | None = None) -> str:
            self.commands.append(("shell", args))
            return ""

    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    client = Client()
    remote_files = client.push_images([first, second], "/sdcard/Pictures/NintendoGamePrice/2026-06-25-am")

    assert remote_files == [
        "/sdcard/Pictures/NintendoGamePrice/2026-06-25-am/01_first.png",
        "/sdcard/Pictures/NintendoGamePrice/2026-06-25-am/02_second.png",
    ]
    assert client.commands[0] == ("shell", ("mkdir", "-p", "/sdcard/Pictures/NintendoGamePrice/2026-06-25-am"))
    assert client.commands[1] == ("shell", ("rm", "-f", "/sdcard/Pictures/NintendoGamePrice/2026-06-25-am/*"))

    touch_commands = [args for kind, args in client.commands if kind == "shell" and args[:2] == ("touch", "-t")]
    assert len(touch_commands) == 2
    assert touch_commands[0][2] > touch_commands[1][2]
    assert touch_commands[0][3].endswith("/01_first.png")
    assert touch_commands[1][3].endswith("/02_second.png")


def test_android_publish_workflow_is_complete_and_selectors_are_not_corrupted():
    source = Path("nsg_price/adb_xiaohongshu.py").read_text(encoding="utf-8")

    assert "return AdbPublishResult(" in source
    assert "_open_image_picker(device, profile)" in source
    assert "_open_dedicated_album(device, profile, session_name)" in source
    assert "_select_newest_images(device, len(images), profile)" in source
    assert ".click(" not in source
    assert "set_text" not in source
    assert "????" not in source

def test_root_status_detects_magisk_but_reports_pending_authorization(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    client = AdbClient(tmp_path / "adb.exe", serial="2527b8b")

    def fake_shell(*args: str, timeout: float | None = None) -> str:
        if args == ("which", "su"):
            return "/sbin/su"
        raise __import__("subprocess").TimeoutExpired("su", timeout or 5)

    monkeypatch.setattr(client, "shell", fake_shell)

    assert client.root_status() == {
        "installed": True,
        "authorized": False,
        "su_path": "/sbin/su",
        "detail": "Magisk authorization timed out; unlock the phone and grant shell root",
    }


def test_root_status_detects_authorized_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    client = AdbClient(tmp_path / "adb.exe", serial="2527b8b")
    monkeypatch.setattr(
        client,
        "shell",
        lambda *args, **kwargs: "/sbin/su" if args == ("which", "su") else "uid=0(root) gid=0(root)",
    )

    status = client.root_status()

    assert status["installed"] is True
    assert status["authorized"] is True
    assert "uid=0(root)" in status["detail"]

def test_human_tap_randomizes_position_and_hold(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    events = []

    class Touch:
        def down(self, x: int, y: int) -> None:
            events.append(("down", x, y))

        def up(self, x: int, y: int) -> None:
            events.append(("up", x, y))

    class Device:
        touch = Touch()

        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

    waits = []
    monkeypatch.setattr(module.random, "triangular", lambda minimum, maximum, mode: mode)
    monkeypatch.setattr(module.time, "sleep", waits.append)

    x, y, hold = module._human_tap(
        Device(),
        bounds={"left": 100, "top": 200, "right": 300, "bottom": 400},
    )

    assert 100 < x < 300
    assert 200 < y < 400
    assert events == [("down", x, y), ("up", x, y)]
    assert hold == pytest.approx(0.075)
    assert waits == [pytest.approx(0.1888), pytest.approx(0.075), pytest.approx(0.44)]

def test_clickable_topics_use_only_coordinate_touches(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    class BodyField:
        info = {"bounds": {"bottom": 778}}

        def set_text(self, value: str) -> None:
            raise AssertionError("topic input must not call set_text")

    class Device:
        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

    points = []
    keyboard_points = []
    monkeypatch.setattr(module, "_relative_click", lambda device, point: points.append(point))
    monkeypatch.setattr(module, "_keyboard_tap", lambda device, point: keyboard_points.append(point))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._select_clickable_topics(Device(), BodyField(), ["\u4efb\u5929\u5802Switch"])

    assert points[0] == module.TOPIC_BUTTON_POINT
    assert module.KEYBOARD_LETTERS["r"] in keyboard_points
    assert module.IME_CANDIDATE_POINT in points
    assert module.IME_LANGUAGE_POINT in points
    assert points[-1] == pytest.approx((0.28, 828 / 2248))

def test_paste_via_touch_never_writes_the_field_directly(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    class Field:
        def set_text(self, value: str) -> None:
            raise AssertionError("paste flow must not call set_text")

    class Device:
        def __init__(self) -> None:
            self.clipboard = None

        def set_clipboard(self, text: str, label: str | None = None) -> None:
            self.clipboard = (text, label)

    device = Device()
    actions = []
    monkeypatch.setattr(module, "_human_tap_element", lambda device, field: actions.append("tap"))
    monkeypatch.setattr(module, "_human_long_press_element", lambda device, field: actions.append("long_press"))
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: actions.append("paste") or True)
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._paste_via_touch(device, Field(), "正文")

    assert device.clipboard == ("正文", "NintendoGamePrice")
    assert actions == ["tap", "long_press", "paste"]

def test_dedicated_album_is_opened_by_exact_album_name(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    class Element:
        def __init__(self, exists: bool) -> None:
            self.exists = exists
            self.info = {"bounds": {"left": 120, "top": 320, "right": 620, "bottom": 400}}

    class Device:
        def __call__(self, **selector):
            return Element(selector in ({"text": "2026-06-19-pm"}, {"textContains": "2026-06-19-pm"}))

    profile = module.Xiaomi8TapProfile()
    points = []
    tapped = []
    monkeypatch.setattr(module, "_relative_click", lambda device, point: points.append(point))
    monkeypatch.setattr(module, "_human_tap_element", lambda device, element: tapped.append(element.info["bounds"]))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._open_dedicated_album(Device(), profile, "2026-06-19-pm")

    assert points == [profile.album_selector]
    assert tapped == [{"left": 120, "top": 320, "right": 620, "bottom": 400}]


def test_dedicated_album_fails_instead_of_clicking_wrong_date(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    class Element:
        exists = False
        info = {"bounds": {"left": 120, "top": 320, "right": 620, "bottom": 400}}

    class Device:
        def __init__(self) -> None:
            self.swipes = 0

        def __call__(self, **selector):
            return Element()

        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

        def swipe(self, *args, **kwargs) -> None:
            self.swipes += 1

    profile = module.Xiaomi8TapProfile()
    points = []
    device = Device()
    monkeypatch.setattr(module, "_relative_click", lambda device, point: points.append(point))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    with pytest.raises(RuntimeError, match="dedicated album was not found"):
        module._open_dedicated_album(device, profile, "2026-06-19-pm")

    assert points == [profile.album_selector]
    assert device.swipes == 6
