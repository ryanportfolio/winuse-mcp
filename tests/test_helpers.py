"""Unit tests for the pure helpers in server.py.

conftest.py stubs mss, pyautogui and pyperclip, so these never touch the
real screen, mouse, keyboard or clipboard.
"""

import pytest

from conftest import monitor
from winuse_mcp import server


# ------------------------------------------------------------------ _scale


@pytest.mark.parametrize(
    "width, height, want",
    [
        (1920, 1080, 1372 / 1920),
        (1080, 1920, 1372 / 1920),  # portrait: the long edge is the height
        (3840, 2160, 1372 / 3840),
        (1372, 800, 1.0),  # exactly the cap: no downscale
        (1280, 720, 1.0),  # smaller than the cap: never upscaled
    ],
)
def test_scale(width, height, want):
    assert server._scale(monitor(0, 0, width, height)) == pytest.approx(want)


def test_scale_is_long_edge_cap():
    assert server.MAX_LONG_EDGE == 1372


# ------------------------------------------------------------------ _primary_monitor


def test_primary_monitor_uses_flag(screen):
    # Windows puts the primary monitor at the desktop origin, so the flagged
    # monitor is listed after one to its left here.
    flagged = monitor(1920, 0, 2560, 1440, primary=True)
    screen(monitor(-1920, 0, 1920, 1080), flagged)
    assert server._primary_monitor() is flagged


def test_primary_monitor_falls_back_to_origin(screen):
    origin = monitor(0, 0, 1920, 1080)
    screen(monitor(-2560, 0, 2560, 1440), origin)
    assert server._primary_monitor() is origin


def test_primary_monitor_falls_back_to_first(screen):
    first = monitor(-2560, 0, 2560, 1440)
    screen(first, monitor(100, 100, 1920, 1080))
    assert server._primary_monitor() is first


# ------------------------------------------------------------------ _to_native


def test_to_native_readme_example(screen):
    # The worked example on the README: 1920x1080 captured at 1372x772.
    assert server._to_native(686, 443) == (960, 620)


def test_to_native_identity_below_cap(screen):
    screen(monitor(0, 0, 1280, 720, primary=True))
    assert server._to_native(640, 360) == (640, 360)


def test_to_native_clamps_off_failsafe_point(screen):
    # (0, 0) is pyautogui's failsafe point; landing there wedges later calls.
    assert server._to_native(0, 0) == (1, 1)
    assert server._to_native(0, 0) != server.FAILSAFE_POINT


def test_to_native_clamps_inside_monitor(screen):
    assert server._to_native(-50, -50) == (1, 1)
    assert server._to_native(10_000, 10_000) == (1919, 1079)


def test_to_native_offsets_by_monitor_origin(screen):
    # A primary monitor that does not sit at the desktop origin.
    screen(monitor(1920, 200, 1920, 1080, primary=True))
    assert server._to_native(686, 443) == (1920 + 960, 200 + 620)


# ------------------------------------------------------------------ cursor_position


def test_cursor_position_round_trips(screen, inputs):
    fn = getattr(server.cursor_position, "fn", server.cursor_position)
    inputs.cursor.x, inputs.cursor.y = server._to_native(686, 443)
    assert fn() == "(686, 443)"


# ------------------------------------------------------------------ _split_combo


@pytest.mark.parametrize(
    "combo, want",
    [
        ("ctrl+s", ["ctrl", "s"]),
        ("CTRL+Shift+T", ["ctrl", "shift", "t"]),
        (" alt + f4 ", ["alt", "f4"]),
        ("enter", ["enter"]),
        ("ctrl++", ["ctrl", "+"]),
        ("+", ["+"]),
        ("", []),
        ("ctrl+", ["ctrl", "+"]),
    ],
)
def test_split_combo(combo, want):
    assert server._split_combo(combo) == want


def test_helpers_send_no_input(screen, inputs):
    server._to_native(10, 10)
    server._split_combo("ctrl+s")
    server._scale(monitor(0, 0, 1920, 1080))
    assert inputs.calls == []


def test_server_uses_the_stand_ins(inputs):
    # Guards the guard: if the stubs stop applying, every other test here
    # would run against the real mouse and keyboard.
    import sys

    assert server.pyautogui is inputs
    assert server.mss is sys.modules["mss"]
    assert server.pyperclip is sys.modules["pyperclip"]
    assert not hasattr(server.mss, "__file__")
