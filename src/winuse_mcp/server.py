"""Computer use for Claude Code on Windows.

Exposes screenshot capture and input control as MCP tools, mirroring the
member tools of Anthropic's computer use toolset (computer_toolset_20260801):
same tool names, same argument names. All coordinates the model passes in are
in the pixel space of the downscaled screenshot; this module rescales them to
native screen pixels.
"""

import contextlib
import ctypes
import io
import sys
import time

# Opt out of DPI virtualization before any screen-metric call, otherwise
# capture size and click coordinates disagree whenever display scaling
# is not 100%.
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:  # pragma: no cover - pre-Win8.1 fallback
        ctypes.windll.user32.SetProcessDPIAware()

import mss
import pyautogui
import pyperclip
from mcp.server.mcpserver import Image, MCPServer
from PIL import Image as PILImage

# Parking the mouse at the top-left corner aborts the action in flight
# (pyautogui.FailSafeException): manual kill switch while the model drives.
# pyautogui only watches (0, 0), so _to_native keeps clicks one pixel clear of
# it; landing the cursor there would wedge every later input call.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05
FAILSAFE_POINT = (0, 0)
# Pin the watched point rather than inheriting whatever this pyautogui version
# defaults to: older versions watch all four corners, and _to_native's clamp is
# written against exactly one.
pyautogui.FAILSAFE_POINTS = [FAILSAFE_POINT]

MAX_LONG_EDGE = 1372
MAX_RECORD_SECONDS = 15.0
MAX_RECORD_FRAMES = 8
MAX_WAIT_SECONDS = 10.0
MAX_HOLD_SECONDS = 10.0
MAX_SCROLL_AMOUNT = 20
MAX_KEY_REPEAT = 100

# Modifier names a click, drag or scroll may hold, mapped to pyautogui keys.
# "super" is Anthropic's name for the Windows key.
MODIFIERS = {"shift": "shift", "ctrl": "ctrl", "alt": "alt", "super": "win", "win": "win"}
KEY_ALIASES = {"super": "win"}

mcp = MCPServer("winuse")


@contextlib.contextmanager
def _cleanup():
    """Run a release call with the failsafe suppressed.

    pyautogui re-checks the failsafe inside mouseUp and keyUp, so cleanup
    issued after an abort would raise again and leave the button or key held
    down. The abort itself still propagates; only the release is exempt.
    """
    previous = pyautogui.FAILSAFE
    pyautogui.FAILSAFE = False
    try:
        yield
    finally:
        pyautogui.FAILSAFE = previous


@contextlib.contextmanager
def _holding(keys: list[str]):
    """Hold keys down for the body, then release them in reverse order.

    Only keys that actually went down are released, and the release runs with
    the failsafe suppressed so an abort cannot leave a modifier stuck.
    """
    held = []
    try:
        for k in keys:
            pyautogui.keyDown(k)
            held.append(k)
        yield
    finally:
        with _cleanup():
            for k in reversed(held):
                pyautogui.keyUp(k)


def _primary_monitor(sct: "mss.base.MSSBase | None" = None) -> dict:
    if sct is None:
        with mss.mss() as own:
            return _primary_monitor(own)
    monitors = sct.monitors[1:]
    for mon in monitors:
        if mon.get("is_primary") or (mon["left"] == 0 and mon["top"] == 0):
            return mon
    return monitors[0]


def _scale(mon: dict) -> float:
    return min(1.0, MAX_LONG_EDGE / max(mon["width"], mon["height"]))


def _to_native(x: float, y: float) -> tuple[int, int]:
    mon = _primary_monitor()
    scale = _scale(mon)
    nx = mon["left"] + round(x / scale)
    ny = mon["top"] + round(y / scale)
    # One pixel in from the edges: the top-left pixel is pyautogui's failsafe
    # point, and parking the cursor there makes every later call abort.
    nx = max(mon["left"] + 1, min(nx, mon["left"] + mon["width"] - 1))
    ny = max(mon["top"] + 1, min(ny, mon["top"] + mon["height"] - 1))
    return nx, ny


def _point(coordinate: list[int] | None) -> tuple[int | None, int | None]:
    """Native pixels for a [x, y] screenshot coordinate; None means 'where the cursor is'."""
    if coordinate is None:
        return None, None
    if len(coordinate) != 2:
        raise ValueError(f"coordinate must be [x, y], got {coordinate}")
    return _to_native(*coordinate)


def _zoom_rect(mon: dict, region: list[int]) -> dict:
    """Native capture rectangle for a [x0, y0, x1, y1] screenshot-space region."""
    if len(region) != 4:
        raise ValueError(f"region must be [x0, y0, x1, y1], got {region}")
    x0, y0, x1, y1 = region
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"region needs x1 > x0 and y1 > y0, got {region}")
    scale = _scale(mon)
    right = mon["left"] + mon["width"]
    bottom = mon["top"] + mon["height"]
    left = max(mon["left"], min(mon["left"] + round(x0 / scale), right))
    top = max(mon["top"], min(mon["top"] + round(y0 / scale), bottom))
    nx1 = max(mon["left"], min(mon["left"] + round(x1 / scale), right))
    ny1 = max(mon["top"], min(mon["top"] + round(y1 / scale), bottom))
    if nx1 <= left or ny1 <= top:
        raise ValueError(f"region {region} lies outside the screen")
    return {"left": left, "top": top, "width": nx1 - left, "height": ny1 - top}


def _fit(width: int, height: int, box_w: int, box_h: int) -> tuple[int, int]:
    """Largest size within box_w x box_h that keeps the aspect ratio; never upscales."""
    f = min(1.0, box_w / width, box_h / height)
    return max(1, round(width * f)), max(1, round(height * f))


def _grab_frame() -> PILImage.Image:
    with mss.mss() as sct:
        mon = _primary_monitor(sct)
        shot = sct.grab(mon)
        img = PILImage.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    scale = min(1.0, MAX_LONG_EDGE / max(img.size))
    if scale < 1.0:
        img = img.resize(
            (round(img.width * scale), round(img.height * scale)),
            PILImage.Resampling.LANCZOS,
        )
    return img


def _png(img: PILImage.Image) -> Image:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return Image(data=buf.getvalue(), format="png")


def _split_combo(combo: str) -> list[str]:
    """Split a chord on "+", treating a trailing "+" as the plus key itself.

    Without this, "ctrl++" parses to ["ctrl"] and presses Ctrl on its own while
    reporting success.
    """
    text = combo.strip()
    if text == "+":
        return ["+"]
    if text.endswith("+"):
        return [p.strip().lower() for p in text[:-1].split("+") if p.strip()] + ["+"]
    return [p.strip().lower() for p in text.split("+") if p.strip()]


def _keys(combo: str) -> list[str]:
    """pyautogui key names for a key or chord, or ValueError naming the bad parts."""
    parts = [KEY_ALIASES.get(p, p) for p in _split_combo(combo)]
    if not parts:
        raise ValueError("empty key combo")
    invalid = [p for p in parts if p not in pyautogui.KEYBOARD_KEYS]
    if invalid:
        raise ValueError(f"unknown key(s): {invalid}")
    return parts


def _modifiers(text: str | None) -> list[str]:
    """pyautogui keys for a click or scroll's modifier text, e.g. 'ctrl+shift'."""
    if not text:
        return []
    parts = _split_combo(text)
    invalid = [p for p in parts if p not in MODIFIERS]
    if invalid:
        raise ValueError(f"not modifier key(s): {invalid}; use shift, ctrl, alt or super")
    return [MODIFIERS[p] for p in parts]


def _where(coordinate: list[int] | None) -> str:
    return "the cursor" if coordinate is None else f"({coordinate[0]}, {coordinate[1]})"


def _with(text: str | None) -> str:
    return f" with {text}" if text else ""


def _click(coordinate: list[int] | None, text: str | None, button: str = "left", clicks: int = 1) -> str:
    nx, ny = _point(coordinate)
    with _holding(_modifiers(text)):
        pyautogui.click(x=nx, y=ny, clicks=clicks, button=button)
    return f"{button} click x{clicks} at {_where(coordinate)}{_with(text)}"


@mcp.tool()
def screenshot() -> Image:
    """Take a screenshot of the primary monitor.

    Returns a downscaled PNG. All coordinates passed to the other tools
    must be in this downscaled image's pixel space.
    """
    return _png(_grab_frame())


@mcp.tool()
def zoom(region: list[int]) -> Image:
    """Capture region [x0, y0, x1, y1] (screenshot coordinates) at full resolution.

    Use to read small text or dense UI. The image is scaled down only as far
    as needed to fit the usual screenshot size. Coordinates passed to other
    tools stay in the full screenshot's space, never the zoomed image's.
    """
    with mss.mss() as sct:
        mon = _primary_monitor(sct)
        shot = sct.grab(_zoom_rect(mon, region))
        img = PILImage.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    scale = _scale(mon)
    size = _fit(img.width, img.height, round(mon["width"] * scale), round(mon["height"] * scale))
    if size != img.size:
        img = img.resize(size, PILImage.Resampling.LANCZOS)
    return _png(img)


@mcp.tool()
def left_click(coordinate: list[int] | None = None, text: str | None = None) -> str:
    """Left-click at coordinate [x, y], or at the cursor when omitted.

    text: modifier keys to hold during the click: shift, ctrl, alt, super
    (the Windows key), or a '+'-joined combination such as 'ctrl+shift'.
    """
    return _click(coordinate, text)


@mcp.tool()
def double_click(coordinate: list[int] | None = None, text: str | None = None) -> str:
    """Double left-click at coordinate [x, y], or at the cursor. text: modifiers, as in left_click."""
    return _click(coordinate, text, clicks=2)


@mcp.tool()
def triple_click(coordinate: list[int] | None = None, text: str | None = None) -> str:
    """Triple left-click (select line/paragraph) at coordinate [x, y], or at the cursor. text: modifiers."""
    return _click(coordinate, text, clicks=3)


@mcp.tool()
def right_click(coordinate: list[int] | None = None, text: str | None = None) -> str:
    """Right-click (context menu) at coordinate [x, y], or at the cursor. text: modifiers."""
    return _click(coordinate, text, button="right")


@mcp.tool()
def middle_click(coordinate: list[int] | None = None, text: str | None = None) -> str:
    """Middle-click at coordinate [x, y], or at the cursor. text: modifiers."""
    return _click(coordinate, text, button="middle")


@mcp.tool()
def mouse_move(coordinate: list[int]) -> str:
    """Move the mouse to coordinate [x, y] without clicking, e.g. to hover."""
    nx, ny = _point(coordinate)
    pyautogui.moveTo(nx, ny)
    return f"moved to {_where(coordinate)}"


@mcp.tool()
def left_click_drag(start_coordinate: list[int], coordinate: list[int], text: str | None = None) -> str:
    """Press the left button at start_coordinate, drag to coordinate, and release.

    text: modifier keys to hold for the whole drag, as in left_click.
    """
    sx, sy = _point(start_coordinate)
    ex, ey = _point(coordinate)
    mods = _modifiers(text)
    pyautogui.moveTo(sx, sy)
    with _holding(mods):
        try:
            pyautogui.dragTo(ex, ey, duration=0.4, button="left")
        finally:
            # dragTo checks the failsafe inside its tween loop and skips its own
            # trailing mouseUp when that fires, so an abort mid-drag would leave the
            # button held and the desktop dragging whatever was grabbed.
            with _cleanup():
                pyautogui.mouseUp(button="left")
    return f"dragged {_where(start_coordinate)} -> {_where(coordinate)}{_with(text)}"


@mcp.tool()
def left_mouse_down() -> str:
    """Press and hold the left button at the cursor, for drags left_click_drag can't express.

    Move the cursor with mouse_move first, and release with left_mouse_up.
    """
    pyautogui.mouseDown(button="left")
    return "left button down"


@mcp.tool()
def left_mouse_up() -> str:
    """Release the left button at the cursor."""
    # Releasing is always safe, so it runs even after a failsafe abort; otherwise
    # parking the mouse to stop a run would leave the button held down.
    with _cleanup():
        pyautogui.mouseUp(button="left")
    return "left button up"


@mcp.tool(name="type")
def type_text(text: str) -> str:
    """Type text at the current keyboard focus.

    ASCII is typed key by key; anything else is pasted via the clipboard
    (previous clipboard contents are restored afterwards).
    """
    if text.isascii():
        pyautogui.write(text, interval=0.01)
    else:
        previous = None
        try:
            previous = pyperclip.paste()
        except pyperclip.PyperclipException:
            pass
        pyperclip.copy(text)
        try:
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)
        finally:
            if previous is not None:
                pyperclip.copy(previous)
    return f"typed {len(text)} characters"


@mcp.tool()
def key(text: str, repeat: int = 1) -> str:
    """Press a key or chord repeat times (1-100), e.g. 'enter', 'ctrl+s', 'alt+Tab'.

    Key names follow pyautogui, case-insensitive: enter (or return), esc,
    tab, space, backspace, delete, up/down/left/right, home, end, pageup,
    pagedown, f1-f24, win (or super), ctrl, alt, shift, printscreen, and
    single characters.
    """
    parts = _keys(text)
    repeat = int(repeat)
    if not 1 <= repeat <= MAX_KEY_REPEAT:
        raise ValueError(f"repeat must be 1 to {MAX_KEY_REPEAT}, got {repeat}")
    for _ in range(repeat):
        if len(parts) == 1:
            pyautogui.press(parts[0])
        else:
            pyautogui.hotkey(*parts)
    return f"pressed {text}" + (f" x{repeat}" if repeat > 1 else "")


@mcp.tool()
def hold_key(text: str, duration: float) -> str:
    """Hold a key or chord down for duration seconds, then release it. Capped at 10s.

    Parking the mouse at the top-left pixel releases it early.
    """
    parts = _keys(text)
    seconds = max(0.0, min(float(duration), MAX_HOLD_SECONDS))
    with _holding(parts):
        end = time.monotonic() + seconds
        while (remaining := end - time.monotonic()) > 0:
            time.sleep(min(0.05, remaining))
            # A plain sleep never looks at the mouse, so poll the failsafe here
            # or the kill switch would wait out the whole hold.
            pyautogui.failSafeCheck()
    return f"held {text} for {seconds:.1f}s"


@mcp.tool()
def scroll(
    scroll_direction: str,
    scroll_amount: int,
    coordinate: list[int] | None = None,
    text: str | None = None,
) -> str:
    """Scroll at coordinate [x, y], or at the cursor when omitted.

    scroll_direction: up, down, left, or right. scroll_amount is in wheel
    clicks, 1 to 20. Horizontal scrolling is sent as shift+wheel.
    text: modifier keys to hold during the scroll, as in left_click.
    """
    if scroll_direction not in ("up", "down", "left", "right"):
        raise ValueError("scroll_direction must be up, down, left, or right")
    amount = max(1, min(int(scroll_amount), MAX_SCROLL_AMOUNT))
    mods = _modifiers(text)
    nx, ny = _point(coordinate)
    if coordinate is not None:
        pyautogui.moveTo(nx, ny)
    if scroll_direction in ("left", "right") and "shift" not in mods:
        mods.append("shift")
    clicks = amount if scroll_direction in ("up", "left") else -amount
    # keyUp re-runs the failsafe check, so _holding releases with it suppressed;
    # an abort mid-scroll would otherwise leave shift stuck down for the user.
    with _holding(mods):
        pyautogui.scroll(clicks)
    return f"scrolled {scroll_direction} {amount} at {_where(coordinate)}{_with(text)}"


@mcp.tool()
def cursor_position() -> str:
    """Current mouse position in screenshot coordinates, as 'X=512, Y=384'."""
    pos = pyautogui.position()
    mon = _primary_monitor()
    scale = _scale(mon)
    x = round((pos.x - mon["left"]) * scale)
    y = round((pos.y - mon["top"]) * scale)
    return f"X={x}, Y={y}"


@mcp.tool()
def record(duration_seconds: float = 5.0, max_frames: int = 6):
    """Watch the screen for a period and return evenly spaced frames.

    Use to observe animations, loading states, or anything that changes
    over time. duration_seconds is capped at 15, max_frames at 8.
    """
    duration = max(0.5, min(float(duration_seconds), MAX_RECORD_SECONDS))
    frames = max(2, min(int(max_frames), MAX_RECORD_FRAMES))
    interval = duration / (frames - 1)
    images = []
    start = time.monotonic()
    for i in range(frames):
        target = start + i * interval
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        images.append(_png(_grab_frame()))
    return images


@mcp.tool()
def wait(duration: float = 1.0) -> str:
    """Wait before the next action, e.g. for a window or page to settle. Capped at 10s."""
    seconds = max(0.1, min(float(duration), MAX_WAIT_SECONDS))
    time.sleep(seconds)
    return f"waited {seconds:.1f}s"


def main() -> None:
    mcp.run()
