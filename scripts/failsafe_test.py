"""Regression checks for the failsafe cleanup paths.

These are the paths a user hits while aborting, so they are checked without a
real abort: pyautogui is stubbed and the calls it received are recorded.
"""

import sys
import types

import pyautogui

from winuse_mcp import server


class Recorder:
    """Stands in for the pyautogui calls a tool makes."""

    def __init__(self, raise_on):
        self.calls = []
        self.armed = {}
        self.raise_on = raise_on
        self.FAILSAFE = True
        self.KEYBOARD_KEYS = pyautogui.KEYBOARD_KEYS
        self.FailSafeException = pyautogui.FailSafeException

    def __getattr__(self, name):
        def call(*args, **kwargs):
            # Recording the flag proves the release ran with the failsafe
            # suppressed, which is what stops it raising a second time.
            self.calls.append(name)
            self.armed[name] = self.FAILSAFE
            if name == self.raise_on:
                # pyautogui raises this from inside the tween loop, and again
                # from any later call, until the FAILSAFE flag is cleared.
                if self.FAILSAFE:
                    raise pyautogui.FailSafeException("fail-safe triggered")
            return None

        return call


def run(name, raise_on, tool, *args, expect):
    rec = Recorder(raise_on)
    server.pyautogui = rec
    try:
        tool(*args)
    except pyautogui.FailSafeException:
        pass
    finally:
        server.pyautogui = pyautogui
    ok = expect in rec.calls and rec.armed.get(expect) is False
    print(
        f"{'ok  ' if ok else 'FAIL'} {name}: calls={rec.calls}, "
        f"failsafe during {expect}={rec.armed.get(expect)}"
    )
    return ok


bad = 0

# An abort mid-drag must still release the button, or the desktop keeps
# dragging whatever was grabbed.
if not run(
    "drag aborted mid-tween still releases the button",
    "dragTo",
    server.left_click_drag.fn if hasattr(server.left_click_drag, "fn") else server.left_click_drag,
    10,
    10,
    200,
    200,
    expect="mouseUp",
):
    bad += 1

# An abort during a horizontal scroll must still release shift.
if not run(
    "horizontal scroll aborted still releases shift",
    "scroll",
    server.scroll.fn if hasattr(server.scroll, "fn") else server.scroll,
    10,
    10,
    "right",
    3,
    expect="keyUp",
):
    bad += 1

# Chord parsing: a trailing plus is a key, not a separator.
cases = {
    "ctrl+s": ["ctrl", "s"],
    "ctrl++": ["ctrl", "+"],
    "+": ["+"],
    "CTRL+Shift+T": ["ctrl", "shift", "t"],
    "enter": ["enter"],
}
for combo, want in cases.items():
    got = server._split_combo(combo)
    ok = got == want
    print(f"{'ok  ' if ok else 'FAIL'} split {combo!r} -> {got}")
    if not ok:
        bad += 1

# Clicks stay one pixel clear of the failsafe point, so a click at the model's
# origin cannot wedge every later input call.
nx, ny = server._to_native(0, 0)
ok = (nx, ny) != server.FAILSAFE_POINT
print(f"{'ok  ' if ok else 'FAIL'} model (0, 0) -> native {(nx, ny)}, failsafe point is {server.FAILSAFE_POINT}")
if not ok:
    bad += 1

sys.exit(1 if bad else 0)
