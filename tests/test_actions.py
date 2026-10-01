"""Unit tests for the computer use toolset members and their helpers.

conftest.py stubs mss, pyautogui and pyperclip: tools run against a recorder,
so these check which input calls a tool would make without making any.
"""

import pytest

from conftest import monitor
from winuse_mcp import server


def tool(name):
    obj = getattr(server, name)
    return getattr(obj, "fn", obj)


@pytest.fixture
def clock(monkeypatch):
    """Fake time: sleep advances monotonic instead of waiting."""
    now = [0.0]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(server.time, "sleep", sleep)
    monkeypatch.setattr(server.time, "monotonic", lambda: now[0])
    return slept


# ------------------------------------------------------------------ _point


def test_point_none_means_cursor(screen):
    assert server._point(None) == (None, None)


def test_point_converts_like_to_native(screen):
    assert server._point([686, 443]) == (960, 620)


@pytest.mark.parametrize("bad", [[1], [1, 2, 3], []])
def test_point_rejects_wrong_length(screen, bad):
    with pytest.raises(ValueError, match="coordinate"):
        server._point(bad)


# ------------------------------------------------------------------ _zoom_rect


def test_zoom_rect_scales_to_native():
    mon = monitor(0, 0, 1920, 1080)
    # 1920 / 1372 per screenshot pixel: [686, 443] lands on (960, 620).
    assert server._zoom_rect(mon, [0, 0, 686, 443]) == {
        "left": 0,
        "top": 0,
        "width": 960,
        "height": 620,
    }


def test_zoom_rect_offsets_by_monitor_origin():
    mon = monitor(1920, 200, 1920, 1080)
    rect = server._zoom_rect(mon, [686, 443, 1372, 772])
    assert rect == {"left": 1920 + 960, "top": 200 + 620, "width": 960, "height": 460}


def test_zoom_rect_no_scaling_below_cap():
    mon = monitor(0, 0, 1280, 720)
    assert server._zoom_rect(mon, [100, 50, 300, 250]) == {
        "left": 100,
        "top": 50,
        "width": 200,
        "height": 200,
    }


def test_zoom_rect_clamps_to_monitor():
    mon = monitor(0, 0, 1280, 720)
    assert server._zoom_rect(mon, [-50, -50, 5000, 5000]) == {
        "left": 0,
        "top": 0,
        "width": 1280,
        "height": 720,
    }


@pytest.mark.parametrize(
    "region",
    [
        [10, 10, 10, 50],  # zero width
        [10, 50, 50, 10],  # inverted
        [10, 10, 50],  # too short
        [2000, 2000, 3000, 3000],  # entirely off screen
    ],
)
def test_zoom_rect_rejects_bad_regions(region):
    with pytest.raises(ValueError):
        server._zoom_rect(monitor(0, 0, 1280, 720), region)


# ------------------------------------------------------------------ _fit


@pytest.mark.parametrize(
    "size, box, want",
    [
        ((400, 300), (1372, 772), (400, 300)),  # already fits: never upscaled
        ((1920, 1080), (1372, 772), (1372, 772)),  # whole screen: same as a screenshot
        ((1920, 400), (1372, 772), (1372, 286)),  # wide strip: width-bound
        ((400, 1080), (1372, 772), (286, 772)),  # tall strip: height-bound
        ((5000, 1), (1372, 772), (1372, 1)),  # never collapses to zero
    ],
)
def test_fit(size, box, want):
    assert server._fit(*size, *box) == want


# ------------------------------------------------------------------ _modifiers and _keys


@pytest.mark.parametrize(
    "text, want",
    [
        (None, []),
        ("", []),
        ("shift", ["shift"]),
        ("ctrl+shift", ["ctrl", "shift"]),
        ("super", ["win"]),
        ("Alt", ["alt"]),
    ],
)
def test_modifiers(text, want):
    assert server._modifiers(text) == want


def test_modifiers_rejects_non_modifiers():
    with pytest.raises(ValueError, match="modifier"):
        server._modifiers("ctrl+a")


def test_keys_maps_super_and_lowercases():
    assert server._keys("super+Tab") == ["win", "tab"]
    assert server._keys("Return") == ["return"]


def test_keys_rejects_unknown_and_empty():
    with pytest.raises(ValueError, match="unknown"):
        server._keys("nosuchkey")
    with pytest.raises(ValueError, match="empty"):
        server._keys("  ")


# ------------------------------------------------------------------ clicks


def test_click_without_coordinate_clicks_at_cursor(screen, inputs):
    out = tool("left_click")()
    assert inputs.calls == [("click", (), {"x": None, "y": None, "clicks": 1, "button": "left"})]
    assert out == "left click x1 at the cursor"


def test_click_holds_modifiers_around_the_click(screen, inputs):
    tool("right_click")([686, 443], "ctrl+shift")
    assert [c[0] for c in inputs.calls] == ["keyDown", "keyDown", "click", "keyUp", "keyUp"]
    assert [c[1][0] for c in inputs.calls if c[0] in ("keyDown", "keyUp")] == [
        "ctrl",
        "shift",
        "shift",
        "ctrl",
    ]
    assert inputs.calls[2][2] == {"x": 960, "y": 620, "clicks": 1, "button": "right"}


def test_click_bad_modifier_sends_nothing(screen, inputs):
    with pytest.raises(ValueError):
        tool("left_click")([10, 10], "ctrl+q")
    assert inputs.calls == []


@pytest.mark.parametrize(
    "name, clicks, button",
    [("double_click", 2, "left"), ("triple_click", 3, "left"), ("middle_click", 1, "middle")],
)
def test_click_variants(screen, inputs, name, clicks, button):
    tool(name)([686, 443])
    assert inputs.calls == [("click", (), {"x": 960, "y": 620, "clicks": clicks, "button": button})]


# ------------------------------------------------------------------ drag and mouse buttons


def test_drag_uses_start_coordinate_and_coordinate(screen, inputs):
    tool("left_click_drag")([0, 0], [686, 443], "shift")
    assert [c[0] for c in inputs.calls] == ["moveTo", "keyDown", "dragTo", "mouseUp", "keyUp"]
    assert inputs.calls[0][1] == (1, 1)
    assert inputs.calls[2][1] == (960, 620)


def test_mouse_down_and_up_act_at_cursor(inputs):
    tool("left_mouse_down")()
    tool("left_mouse_up")()
    assert inputs.calls == [
        ("mouseDown", (), {"button": "left"}),
        ("mouseUp", (), {"button": "left"}),
    ]


# ------------------------------------------------------------------ scroll


def test_scroll_at_cursor_does_not_move(screen, inputs):
    tool("scroll")("down", 3)
    assert inputs.calls == [("scroll", (-3,), {})]


def test_scroll_horizontal_holds_shift_once(screen, inputs):
    tool("scroll")("left", 2, [686, 443], "shift+ctrl")
    downs = [c[1][0] for c in inputs.calls if c[0] == "keyDown"]
    assert downs == ["shift", "ctrl"]
    assert ("scroll", (2,), {}) in inputs.calls


def test_scroll_amount_is_capped(screen, inputs):
    tool("scroll")("up", 500)
    assert inputs.calls == [("scroll", (server.MAX_SCROLL_AMOUNT,), {})]


def test_scroll_rejects_bad_direction(screen, inputs):
    with pytest.raises(ValueError, match="scroll_direction"):
        tool("scroll")("sideways", 1)


# ------------------------------------------------------------------ key, hold_key, wait


def test_key_repeat(inputs):
    tool("key")("tab", 3)
    assert inputs.calls == [("press", ("tab",), {})] * 3


def test_key_chord_repeat(inputs):
    tool("key")("alt+Tab", 2)
    assert inputs.calls == [("hotkey", ("alt", "tab"), {})] * 2


@pytest.mark.parametrize("repeat", [0, 101])
def test_key_repeat_out_of_range(inputs, repeat):
    with pytest.raises(ValueError, match="repeat"):
        tool("key")("tab", repeat)
    assert inputs.calls == []


def test_hold_key_presses_polls_and_releases(inputs, clock):
    out = tool("hold_key")("ctrl+shift", 0.2)
    kinds = [c[0] for c in inputs.calls]
    assert kinds[:2] == ["keyDown", "keyDown"]
    assert kinds[-2:] == ["keyUp", "keyUp"]
    # Polled every 50ms, so the kill switch is never more than one slice away.
    assert kinds.count("failSafeCheck") == 4
    assert max(clock) <= 0.05
    assert out == "held ctrl+shift for 0.2s"


def test_hold_key_duration_is_capped(inputs, clock):
    out = tool("hold_key")("a", 10_000)
    assert out == f"held a for {server.MAX_HOLD_SECONDS:.1f}s"
    assert sum(clock) == pytest.approx(server.MAX_HOLD_SECONDS)


def test_wait_takes_duration(clock):
    assert tool("wait")(duration=60) == f"waited {server.MAX_WAIT_SECONDS:.1f}s"
    assert clock == [server.MAX_WAIT_SECONDS]


# ------------------------------------------------------------------ through MCP


def test_mcp_dispatch_uses_anthropic_argument_names(screen, inputs):
    # Goes through the server's own argument validation, as a client call would.
    import asyncio

    asyncio.run(server.mcp.call_tool("left_click", {"coordinate": [686, 443], "text": "shift"}))
    assert ("click", (), {"x": 960, "y": 620, "clicks": 1, "button": "left"}) in inputs.calls
    assert [c[0] for c in inputs.calls] == ["keyDown", "click", "keyUp"]


@pytest.mark.parametrize("text", ["+", "shift++", "ctrl+!"])
def test_hold_key_refuses_keys_with_implicit_modifiers(inputs, clock, text):
    # pyautogui would press and release shift around these, dropping a held one.
    with pytest.raises(ValueError, match="unshifted"):
        tool("hold_key")(text, 1)
    assert inputs.calls == []


def test_hold_key_accepts_explicit_shift_with_base_key(inputs, clock):
    tool("hold_key")("shift+=", 0.05)
    assert [c[1][0] for c in inputs.calls if c[0] == "keyDown"] == ["shift", "="]
