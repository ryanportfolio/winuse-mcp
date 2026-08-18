"""Computer use for Claude Code on Windows.

Exposes screenshot capture and input control as MCP tools, mirroring the
action set of Anthropic's computer use tool (macOS-only in the Claude Code
CLI). All coordinates the model passes in are in the pixel space of the
downscaled screenshot; this module rescales them to native screen pixels.
"""

import ctypes
import io
import time

# Opt out of DPI virtualization before any screen-metric call, otherwise
# capture size and click coordinates disagree whenever display scaling
# is not 100%.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
except Exception:  # pragma: no cover - pre-Win8.1 fallback
    ctypes.windll.user32.SetProcessDPIAware()

import mss
import pyautogui
import pyperclip
from mcp.server.mcpserver import Image, MCPServer
from PIL import Image as PILImage

# Moving the mouse into a screen corner aborts the current action
# (pyautogui.FailSafeException): manual kill switch while the model drives.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

MAX_LONG_EDGE = 1372
MAX_RECORD_SECONDS = 15.0
MAX_RECORD_FRAMES = 8
MAX_WAIT_SECONDS = 10.0

mcp = MCPServer("winuse")


def _primary_monitor() -> dict:
    with mss.mss() as sct:
        monitors = sct.monitors[1:]
    for mon in monitors:
        if mon.get("is_primary") or (mon["left"] == 0 and mon["top"] == 0):
            return mon
    return monitors[0]


def _scale() -> float:
    mon = _primary_monitor()
    return min(1.0, MAX_LONG_EDGE / max(mon["width"], mon["height"]))


def _to_native(x: float, y: float) -> tuple[int, int]:
    mon = _primary_monitor()
    scale = min(1.0, MAX_LONG_EDGE / max(mon["width"], mon["height"]))
    nx = mon["left"] + round(x / scale)
    ny = mon["top"] + round(y / scale)
    nx = max(mon["left"], min(nx, mon["left"] + mon["width"] - 1))
    ny = max(mon["top"], min(ny, mon["top"] + mon["height"] - 1))
    return nx, ny


def _grab_frame() -> PILImage.Image:
    with mss.mss() as sct:
        mon = _primary_monitor()
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


def _click(x: float, y: float, button: str = "left", clicks: int = 1) -> str:
    nx, ny = _to_native(x, y)
    pyautogui.click(x=nx, y=ny, clicks=clicks, button=button)
    return f"{button} click x{clicks} at ({x}, {y})"


@mcp.tool()
def screenshot() -> Image:
    """Take a screenshot of the primary monitor.

    Returns a downscaled PNG. All coordinates passed to the other tools
    must be in this downscaled image's pixel space.
    """
    return _png(_grab_frame())


@mcp.tool()
def left_click(x: int, y: int) -> str:
    """Left-click at (x, y) in screenshot coordinates."""
    return _click(x, y)


@mcp.tool()
def double_click(x: int, y: int) -> str:
    """Double left-click at (x, y) in screenshot coordinates."""
    return _click(x, y, clicks=2)


@mcp.tool()
def triple_click(x: int, y: int) -> str:
    """Triple left-click (select line/paragraph) at (x, y) in screenshot coordinates."""
    return _click(x, y, clicks=3)


@mcp.tool()
def right_click(x: int, y: int) -> str:
    """Right-click (context menu) at (x, y) in screenshot coordinates."""
    return _click(x, y, button="right")


@mcp.tool()
def middle_click(x: int, y: int) -> str:
    """Middle-click at (x, y) in screenshot coordinates."""
    return _click(x, y, button="middle")


@mcp.tool()
def mouse_move(x: int, y: int) -> str:
    """Move the mouse to (x, y) in screenshot coordinates without clicking."""
    nx, ny = _to_native(x, y)
    pyautogui.moveTo(nx, ny)
    return f"moved to ({x}, {y})"


@mcp.tool()
def left_click_drag(start_x: int, start_y: int, end_x: int, end_y: int) -> str:
    """Hold left button at start and drag to end, in screenshot coordinates."""
    sx, sy = _to_native(start_x, start_y)
    ex, ey = _to_native(end_x, end_y)
    pyautogui.moveTo(sx, sy)
    pyautogui.dragTo(ex, ey, duration=0.4, button="left")
    return f"dragged ({start_x}, {start_y}) -> ({end_x}, {end_y})"


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
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        if previous is not None:
            pyperclip.copy(previous)
    return f"typed {len(text)} characters"


@mcp.tool()
def key(combo: str) -> str:
    """Press a key or chord, e.g. 'enter', 'ctrl+s', 'alt+f4', 'ctrl+shift+t'.

    Key names follow pyautogui: enter, esc, tab, space, backspace, delete,
    up/down/left/right, home, end, pageup, pagedown, f1-f24, win, ctrl,
    alt, shift, printscreen, and single characters.
    """
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty key combo")
    invalid = [p for p in parts if p not in pyautogui.KEYBOARD_KEYS]
    if invalid:
        raise ValueError(f"unknown key(s): {invalid}")
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)
    return f"pressed {combo}"


@mcp.tool()
def scroll(x: int, y: int, direction: str = "down", amount: int = 3) -> str:
    """Scroll at (x, y) in screenshot coordinates.

    direction: up, down, left, or right. amount is in wheel clicks.
    Horizontal scrolling is sent as shift+wheel.
    """
    if direction not in ("up", "down", "left", "right"):
        raise ValueError("direction must be up, down, left, or right")
    amount = max(1, min(int(amount), 20))
    nx, ny = _to_native(x, y)
    pyautogui.moveTo(nx, ny)
    vertical = direction in ("up", "down")
    clicks = amount if direction in ("up", "left") else -amount
    if vertical:
        pyautogui.scroll(clicks)
    else:
        pyautogui.keyDown("shift")
        try:
            pyautogui.scroll(clicks)
        finally:
            pyautogui.keyUp("shift")
    return f"scrolled {direction} {amount} at ({x}, {y})"


@mcp.tool()
def cursor_position() -> str:
    """Current mouse position in screenshot coordinates."""
    pos = pyautogui.position()
    mon = _primary_monitor()
    scale = min(1.0, MAX_LONG_EDGE / max(mon["width"], mon["height"]))
    x = round((pos.x - mon["left"]) * scale)
    y = round((pos.y - mon["top"]) * scale)
    return f"({x}, {y})"


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
def wait(seconds: float = 1.0) -> str:
    """Wait before the next action, e.g. for a window or page to settle. Capped at 10s."""
    seconds = max(0.1, min(float(seconds), MAX_WAIT_SECONDS))
    time.sleep(seconds)
    return f"waited {seconds:.1f}s"


def main() -> None:
    mcp.run()
