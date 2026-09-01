from pathlib import Path

import pytest

from nsg_price.adb_xiaohongshu import AdbClient, AndroidDevice, find_adb, parse_adb_devices


def test_parse_adb_devices_reads_xiaomi8_metadata():
    output = """List of devices attached
emulator-5554 device product:sdk_phone model:sdk_phone device:generic transport_id:1
emulator-5554 offline transport_id:2
"""

    devices = parse_adb_devices(output)

    assert devices == [
        AndroidDevice(serial="emulator-5554", state="device", model="sdk_phone", product="sdk_phone"),
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
    client = AdbClient(tmp_path / "adb.exe", serial="emulator-5554")
    expected = AndroidDevice(serial="emulator-5554", state="device", model="sdk_phone")
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


def test_remove_remote_dir_is_scoped_to_project_phone_directory(tmp_path: Path):
    class Client(AdbClient):
        def __init__(self) -> None:
            super().__init__(tmp_path / "adb.exe")
            self.commands = []

        def shell(self, *args: str, timeout: float | None = None) -> str:
            self.commands.append(args)
            return ""

    client = Client()
    client.remove_remote_dir("/sdcard/Pictures/NintendoGamePrice/2026-06-27")

    assert client.commands == [("rm", "-rf", "/sdcard/Pictures/NintendoGamePrice/2026-06-27")]
    with pytest.raises(RuntimeError, match="refusing to remove"):
        client.remove_remote_dir("/sdcard/Pictures")


def test_android_publish_workflow_is_complete_and_selectors_are_not_corrupted():
    source = Path("nsg_price/adb_xiaohongshu.py").read_text(encoding="utf-8")

    assert "return AdbPublishResult(" in source
    assert "client.remove_remote_dir(remote_dir)" in source
    assert "remote_deleted = True" in source
    assert "_open_image_picker(device, profile)" in source
    assert "_open_dedicated_album(device, profile, session_name)" in source
    assert "_select_newest_images(device, len(images), profile)" in source
    assert ".click(" not in source
    assert "set_text" not in source
    assert "????" not in source

def test_root_status_detects_magisk_but_reports_pending_authorization(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    client = AdbClient(tmp_path / "adb.exe", serial="emulator-5554")

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
    client = AdbClient(tmp_path / "adb.exe", serial="emulator-5554")
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

def test_final_publish_button_accepts_send_note_text(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    calls = []

    def fake_click_any(device, selectors, timeout=1.5):
        calls.append(selectors)
        return len(calls) == 2

    monkeypatch.setattr(module, "_click_any", fake_click_any)
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    assert module._click_final_publish_button(object(), module.Xiaomi8TapProfile()) is True
    assert calls[0] == [{"text": "完成"}, {"description": "完成"}]
    assert any("发笔记" in str(selector) for selector in calls[1])

def test_final_publish_button_falls_back_to_top_right_tap(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    points = []
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: False)
    monkeypatch.setattr(module, "_relative_click", lambda device, point: points.append(point))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    profile = module.Xiaomi8TapProfile()
    assert module._click_final_publish_button(object(), profile) is True
    assert points == [profile.next_button]

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


def test_replace_latest_note_images_pushes_appends_deletes_old_images_and_cleans_phone_album(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from nsg_price import adb_xiaohongshu as module

    pack_dir = tmp_path / "publish" / "2026-06-27"
    pack_dir.mkdir(parents=True)
    first = pack_dir / "01.png"
    second = pack_dir / "02.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    (pack_dir / "caption.txt").write_text("title\nbody", encoding="utf-8")
    output_dir = tmp_path / "screens"
    events = []

    class Client:
        def wake_and_dismiss_keyguard(self) -> None:
            events.append("wake")

        def push_images(self, images, remote_dir: str):
            events.append(("push", [Path(image).name for image in images], remote_dir))
            return [f"{remote_dir}/{Path(image).name}" for image in images]

        def remove_remote_dir(self, remote_dir: str) -> None:
            events.append(("remove", remote_dir))

    class Device:
        def screen_on(self) -> None:
            events.append("screen_on")

        def screenshot(self, path: str) -> None:
            events.append(("screenshot", Path(path).name))
            Path(path).write_bytes(b"png")

    client = Client()
    device = Device()
    monkeypatch.setattr(module, "find_adb", lambda adb_path=None: Path(adb_path or "adb.exe"))
    monkeypatch.setattr(
        module,
        "choose_device",
        lambda adb_path, serial=None: (client, AndroidDevice(serial=serial or "emulator-5554", state="device")),
    )
    monkeypatch.setattr(module, "_prepare_xhs_home", lambda device: events.append("home"))
    monkeypatch.setattr(module, "_open_profile_latest_note", lambda device, profile, note_hint=None: events.append(("profile_latest", note_hint)))
    monkeypatch.setattr(module, "_open_note_edit_from_detail", lambda device, profile: events.append("edit_detail"))
    monkeypatch.setattr(
        module,
        "_replace_note_images_from_album",
        lambda device, profile, album_name, new_image_count, old_image_count: events.append(
            ("replace", album_name, new_image_count, old_image_count)
        ),
    )
    monkeypatch.setattr(module, "_save_note_edit", lambda device, profile: events.append("save"))

    result = module.replace_latest_note_images_via_adb(
        pack_dir,
        adb_path="adb.exe",
        serial="emulator-5554",
        output_dir=output_dir,
        submit=True,
        device_factory=lambda serial: device,
    )

    expected_remote_dir = f"{module.DEFAULT_REMOTE_ROOT}/publish-2026-06-27"
    assert events == [
        "wake",
        ("push", ["01.png", "02.png"], expected_remote_dir),
        "screen_on",
        "home",
        ("profile_latest", "2026-06-27"),
        "edit_detail",
        ("replace", "publish-2026-06-27", 2, 2),
        "save",
        ("screenshot", "xhs_adb_replace_after_submit.png"),
        ("remove", expected_remote_dir),
    ]
    assert result.status == "submitted"
    assert result.serial == "emulator-5554"
    assert result.image_count == 2
    assert result.old_image_count == 2
    assert result.remote_deleted is True
    assert result.screenshot == output_dir / "xhs_adb_replace_after_submit.png"


def test_replace_latest_note_images_keeps_phone_album_until_submitted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from nsg_price import adb_xiaohongshu as module

    pack_dir = tmp_path / "publish" / "2026-06-27"
    pack_dir.mkdir(parents=True)
    (pack_dir / "01.png").write_bytes(b"first")
    (pack_dir / "caption.txt").write_text("title\nbody", encoding="utf-8")
    events = []

    class Client:
        def wake_and_dismiss_keyguard(self) -> None:
            events.append("wake")

        def push_images(self, images, remote_dir: str):
            events.append(("push", remote_dir))
            return [f"{remote_dir}/{Path(image).name}" for image in images]

        def remove_remote_dir(self, remote_dir: str) -> None:
            events.append(("remove", remote_dir))

    class Device:
        def screen_on(self) -> None:
            events.append("screen_on")

        def screenshot(self, path: str) -> None:
            events.append(("screenshot", Path(path).name))
            Path(path).write_bytes(b"png")

    client = Client()
    device = Device()
    monkeypatch.setattr(module, "find_adb", lambda adb_path=None: Path(adb_path or "adb.exe"))
    monkeypatch.setattr(module, "choose_device", lambda adb_path, serial=None: (client, AndroidDevice(serial="emulator-5554", state="device")))
    monkeypatch.setattr(module, "_prepare_xhs_home", lambda device: None)
    monkeypatch.setattr(module, "_open_profile_latest_note", lambda device, profile, note_hint=None: None)
    monkeypatch.setattr(module, "_open_note_edit_from_detail", lambda device, profile, note_hint=None: None)
    monkeypatch.setattr(module, "_replace_note_images_from_album", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_save_note_edit", lambda device, profile: events.append("save"))

    result = module.replace_latest_note_images_via_adb(
        pack_dir,
        adb_path="adb.exe",
        submit=False,
        old_image_count=3,
        device_factory=lambda serial: device,
    )

    assert result.status == "ready"
    assert result.old_image_count == 3
    assert result.remote_deleted is False
    assert ("remove", f"{module.DEFAULT_REMOTE_ROOT}/publish-2026-06-27") not in events
    assert "save" not in events


def test_profile_latest_note_scrolls_past_sales_cards_before_opening_first_note(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    class Device:
        def __init__(self) -> None:
            self.swipes = []

        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

        @staticmethod
        def app_current() -> dict[str, str]:
            return {"activity": "com.xingin.capa.v2.feature.imageedit3.editpage.ImageEditActivity3"}

        def swipe(self, *args, **kwargs) -> None:
            self.swipes.append((args, kwargs))

    device = Device()
    points = []
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "_relative_click", lambda device, point: points.append(point))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._open_profile_latest_note(device, module.Xiaomi8TapProfile())

    assert device.swipes
    assert points == [module.Xiaomi8TapProfile().first_profile_note]


def test_profile_latest_note_prefers_matching_note_hint(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    class Element:
        def __init__(self, exists: bool) -> None:
            self.exists = exists
            self.info = {"bounds": {"left": 96, "top": 1577, "right": 534, "bottom": 2080}}

    class Device:
        def __init__(self) -> None:
            self.swipes = []

        def __call__(self, **selector):
            return Element(selector == {"descriptionContains": "2026-06-27"})

        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

        def swipe(self, *args, **kwargs) -> None:
            self.swipes.append((args, kwargs))

    device = Device()
    points = []
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "_relative_click", lambda device, point: points.append(point))
    monkeypatch.setattr(module, "_human_tap_element", lambda device, element: points.append(element.info["bounds"]))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._open_profile_latest_note(device, module.Xiaomi8TapProfile(), note_hint="2026-06-27")

    assert device.swipes
    assert points == [{"left": 96, "top": 1577, "right": 534, "bottom": 2080}]


def test_append_new_images_uses_material_selector_from_image_editor(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    class Device:
        def __init__(self) -> None:
            self.swipes = []
            self.state = "com.xingin.capa.v2.feature.imageedit3.editpage.ImageEditActivity3"

        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

        def app_current(self) -> dict[str, str]:
            return {"activity": self.state}

        def dump_hierarchy(self) -> str:
            return """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.xingin.xhs" content-desc="" clickable="false" enabled="true" focusable="false" bounds="[0,0][1080,2248]">
    <node index="0" text="" resource-id="" class="androidx.recyclerview.widget.RecyclerView" package="com.xingin.xhs" content-desc="" clickable="false" enabled="true" focusable="true" bounds="[44,1890][1080,2006]">
      <node index="0" text="" resource-id="" class="android.view.ViewGroup" package="com.xingin.xhs" content-desc="" clickable="true" long-clickable="true" enabled="true" focusable="true" bounds="[44,1890][182,2006]" />
      <node index="1" text="" resource-id="" class="android.view.ViewGroup" package="com.xingin.xhs" content-desc="" clickable="true" long-clickable="true" enabled="true" focusable="true" bounds="[182,1890][320,2006]" />
      <node index="2" text="" resource-id="" class="android.view.ViewGroup" package="com.xingin.xhs" content-desc="" clickable="true" long-clickable="true" enabled="true" focusable="true" bounds="[320,1890][458,2006]" />
      <node index="3" text="" resource-id="" class="android.view.ViewGroup" package="com.xingin.xhs" content-desc="" clickable="true" long-clickable="true" enabled="true" focusable="true" bounds="[458,1890][596,2006]" />
      <node index="4" text="" resource-id="" class="android.view.ViewGroup" package="com.xingin.xhs" content-desc="" clickable="true" long-clickable="true" enabled="true" focusable="true" bounds="[596,1890][734,2006]" />
      <node index="5" text="" resource-id="" class="android.view.ViewGroup" package="com.xingin.xhs" content-desc="" clickable="true" long-clickable="true" enabled="true" focusable="true" bounds="[734,1890][872,2006]" />
    </node>
  </node>
</hierarchy>"""

        def swipe(self, *args, **kwargs) -> None:
            self.swipes.append((args, kwargs))

    events = []
    device = Device()
    monkeypatch.setattr(module, "_wait_for_activity", lambda device, expected, timeout=8.0: events.append(("wait", expected)))
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: False)
    def fake_click_add(device, profile):
        events.append(("click_add", profile.image_editor_add))
        device.state = "com.xingin.ugc.publish.activity.MaterialSelectActivity"
        return True
    monkeypatch.setattr(module, "_click_image_editor_add_tile", fake_click_add)
    monkeypatch.setattr(module, "_open_dedicated_material_album", lambda device, album_name: events.append(("album", album_name)), raising=False)
    monkeypatch.setattr(module, "_select_material_album_images", lambda device, count: events.append(("select", count)), raising=False)
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._append_new_images_from_album(device, module.Xiaomi8TapProfile(), "publish-2026-06-27", 8)

    assert ("wait", "ImageEditActivity3") in events
    assert device.swipes
    assert ("click_add", module.Xiaomi8TapProfile().image_editor_add) in events
    assert ("wait", "MaterialSelectActivity") in events
    assert ("album", "publish-2026-06-27") in events
    assert ("select", 8) in events


def test_material_album_selection_scrolls_to_top_before_selecting(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    events = []

    class Device:
        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

    monkeypatch.setattr(module, "_scroll_material_album_to_top", lambda device: events.append("top"))
    monkeypatch.setattr(
        module,
        "_material_selection_bounds",
        lambda device: [{"left": 216, "top": 210, "right": 354, "bottom": 348}],
    )
    monkeypatch.setattr(module, "_human_tap", lambda device, bounds=None, point=None: events.append(("tap", bounds)))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "_wait_for_activity", lambda *args, **kwargs: events.append("wait"))

    module._select_material_album_images(Device(), 1)

    assert events[0] == "top"
    assert events[1] == ("tap", {"left": 216, "top": 210, "right": 354, "bottom": 348})


def test_replace_note_images_deletes_old_images_from_preview_after_next(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    events = []
    monkeypatch.setattr(module, "_open_first_image_editor", lambda device, profile: events.append("open"))
    monkeypatch.setattr(module, "_delete_images_from_image_editor", lambda device, profile, count: events.append(("delete_editor", count)))
    monkeypatch.setattr(module, "_append_new_images_from_album", lambda device, profile, album, count: events.append(("append", album, count)))
    monkeypatch.setattr(module, "_finish_image_editor", lambda device, profile: events.append("next"))
    monkeypatch.setattr(
        module,
        "_delete_front_images_from_preview_counted",
        lambda device, profile, count, total_image_count: events.append(("delete_preview", count, total_image_count)),
    )

    module._replace_note_images_from_album(object(), module.Xiaomi8TapProfile(), "publish-2026-06-27", 8, 8)

    assert events == [
        "open",
        ("delete_editor", 7),
        ("append", "publish-2026-06-27", 8),
        "next",
        ("delete_preview", 1, 9),
    ]


def test_delete_images_from_image_editor_uses_long_press_and_delete(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    events = []

    class Device:
        def __init__(self) -> None:
            self.touch = self

        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

        @staticmethod
        def dump_hierarchy() -> str:
            return """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" class="androidx.recyclerview.widget.RecyclerView" clickable="false" bounds="[44,1890][1080,2006]">
    <node index="0" text="" class="android.view.ViewGroup" clickable="true" long-clickable="true" bounds="[44,1890][182,2006]" />
    <node index="1" text="" class="android.view.ViewGroup" clickable="true" long-clickable="true" bounds="[182,1890][320,2006]" />
  </node>
</hierarchy>"""

        def down(self, x: int, y: int) -> None:
            events.append(("down", x, y))

        def up(self, x: int, y: int) -> None:
            events.append(("up", x, y))

    monkeypatch.setattr(module, "_wait_for_activity", lambda *args, **kwargs: events.append("wait"))
    monkeypatch.setattr(module, "_swipe_image_editor_to_start", lambda device, swipes: events.append(("start", swipes)))
    monkeypatch.setattr(module, "_human_long_press", lambda device, point: events.append(("long_press", point)))
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: False)
    monkeypatch.setattr(module, "_relative_click", lambda device, point: events.append(("delete", point)))
    monkeypatch.setattr(module.random, "triangular", lambda minimum, maximum, mode: mode)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._delete_images_from_image_editor(Device(), module.Xiaomi8TapProfile(), 2)

    assert events[0] == "wait"
    assert events[1] == ("start", 2)
    assert events.count(("down", 113, 1948)) == 2
    assert events.count(("delete", module.Xiaomi8TapProfile().image_editor_longpress_delete)) == 2


def test_delete_front_images_from_preview_rewinds_before_deleting(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    events = []

    class Device:
        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

        def swipe(self, *args, **kwargs) -> None:
            events.append("swipe")

    monkeypatch.setattr(module, "_wait_for_activity", lambda *args, **kwargs: events.append("wait"))
    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: False)
    monkeypatch.setattr(module, "_relative_click", lambda device, point: events.append(("delete", point)))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)

    module._delete_front_images_from_preview(Device(), module.Xiaomi8TapProfile(), 2, total_image_count=6)

    assert events[0] == "wait"
    assert events[1:6] == ["swipe", "swipe", "swipe", "swipe", "swipe"]
    assert events.count(("delete", module.Xiaomi8TapProfile().preview_delete)) == 2


def test_delete_front_images_from_preview_does_not_overswipe_when_already_first(monkeypatch: pytest.MonkeyPatch):
    from nsg_price import adb_xiaohongshu as module

    events = []

    class Device:
        @staticmethod
        def window_size() -> tuple[int, int]:
            return 1080, 2248

        def swipe(self, *args, **kwargs) -> None:
            events.append("swipe")

        def dump_hierarchy(self) -> str:
            return '<node text="1/8" class="android.widget.TextView" />'

    monkeypatch.setattr(module, "_click_any", lambda *args, **kwargs: False)
    monkeypatch.setattr(module, "_relative_click", lambda device, point: events.append(("delete", point)))
    monkeypatch.setattr(module, "_human_pause", lambda *args: None)
    monkeypatch.setattr(module, "_wait_for_activity", lambda *args, **kwargs: events.append("wait"))

    module._delete_front_images_from_preview(Device(), module.Xiaomi8TapProfile(), 1)

    assert events[0] == "wait"
    assert "swipe" not in events
    assert events.count(("delete", module.Xiaomi8TapProfile().preview_delete)) == 1
