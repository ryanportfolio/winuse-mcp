"""Headless stand-ins for the libraries that touch the real desktop.

server.py imports mss, pyautogui and pyperclip at module load. These tests
replace all three in sys.modules before that import, so nothing here can
capture the screen, move the mouse, send a key or read the clipboard, and the
suite runs on a CI machine with no desktop at all.
"""

import sys
import types

import pytest


class _Recorder(types.ModuleType):
    """Fake pyautogui: records every call instead of sending input."""

    class FailSafeException(Exception):
        pass

    def __init__(self):
        super().__init__("pyautogui")
        self.FAILSAFE = True
        self.FAILSAFE_POINTS = [(0, 0)]
        self.PAUSE = 0.0
        self.KEYBOARD_KEYS = [
            "+", "a", "s", "t", "enter", "return", "tab", "esc", "ctrl", "alt",
            "shift", "win", "f4", "space", "backspace", "=", "!",
        ]
        self.calls = []
        self.cursor = types.SimpleNamespace(x=0, y=0)

    def position(self):
        return self.cursor

    @staticmethod
    def isShiftCharacter(character):
        # Same rule as pyautogui's own.
        return character.isupper() or character in set('~!@#$%^&*()_+{}|:"<>?')

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return call


class _FakeMSS:
    """Fake mss.mss(): exposes a monitor list the tests can set."""

    monitors = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


fake_pyautogui = _Recorder()
fake_mss = types.ModuleType("mss")
fake_mss.mss = _FakeMSS
fake_mss.base = types.SimpleNamespace(MSSBase=_FakeMSS)
fake_pyperclip = types.ModuleType("pyperclip")
fake_pyperclip.PyperclipException = Exception
fake_pyperclip.paste = lambda: ""
fake_pyperclip.copy = lambda text: None

sys.modules["pyautogui"] = fake_pyautogui
sys.modules["mss"] = fake_mss
sys.modules["pyperclip"] = fake_pyperclip


def monitor(left, top, width, height, primary=False):
    mon = {"left": left, "top": top, "width": width, "height": height}
    if primary:
        mon["is_primary"] = True
    return mon


@pytest.fixture
def screen():
    """Set the fake desktop. Index 0 is mss's union of all monitors."""

    def set_monitors(*mons):
        union = monitor(0, 0, 0, 0)
        _FakeMSS.monitors = [union, *mons]

    set_monitors(monitor(0, 0, 1920, 1080, primary=True))
    yield set_monitors
    _FakeMSS.monitors = []


@pytest.fixture
def inputs():
    """The fake pyautogui, cleared before each test."""
    fake_pyautogui.calls.clear()
    fake_pyautogui.cursor = types.SimpleNamespace(x=0, y=0)
    return fake_pyautogui
