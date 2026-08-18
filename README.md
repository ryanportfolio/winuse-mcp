# winuse-mcp

Computer use for Claude Code on Windows. An MCP server that lets Claude see your screen and drive your mouse and keyboard, mirroring the action set of Anthropic's own computer use tool.

Claude Code ships computer use in the CLI on macOS only. On Windows the `computer-use` server never appears in `/mcp`. This fills that gap: the same screenshot, click, type, scroll loop, running against the Windows APIs.

## Install

Requires Windows and [uv](https://docs.astral.sh/uv/). Add to `.mcp.json` in your project (or `~/.claude.json` for all projects):

```json
{
  "mcpServers": {
    "winuse": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ryanportfolio/winuse-mcp", "winuse-mcp"]
    }
  }
}
```

From a local clone instead:

```json
{
  "mcpServers": {
    "winuse": {
      "command": "uv",
      "args": ["run", "--directory", "C:/path/to/winuse-mcp", "winuse-mcp"]
    }
  }
}
```

Then ask Claude to look at your screen or click through an app.

## Tools

| Tool | Does |
|---|---|
| `screenshot` | PNG of the primary monitor, downscaled |
| `left_click`, `right_click`, `middle_click`, `double_click`, `triple_click` | Click at (x, y) |
| `mouse_move` | Move cursor without clicking |
| `left_click_drag` | Press, drag, release |
| `type` | Type text at current focus (non-ASCII goes through the clipboard) |
| `key` | Press a key or chord: `enter`, `ctrl+s`, `alt+f4` |
| `scroll` | Wheel scroll at (x, y); horizontal sent as shift+wheel |
| `cursor_position` | Where the mouse is now |
| `record` | Watch the screen for up to 15s, return evenly spaced frames |
| `wait` | Pause before the next action |

## How coordinates work

Screenshots are downscaled so the long edge is at most 1372 pixels, the same target Claude Code uses on macOS. The model clicks in that downscaled space; the server rescales to native pixels. A 1920x1080 display captures at 1372x772, and a click at (686, 443) lands at (960, 620) on screen.

The server sets itself DPI-aware at startup, so Windows display scaling (125%, 150%) does not skew clicks.

## Safety

This gives a language model control of your desktop. Anthropic's built-in version wraps the loop in guardrails this server does not have: per-app approval, hiding non-approved apps, excluding your terminal from screenshots, model-side action checks.

What you do get:

- Claude Code prompts before each tool call unless you allow-list them. Leave the input tools (`left_click`, `type`, `key`, ...) on manual approval.
- Slam the mouse into any screen corner to abort the current action (pyautogui's failsafe).
- Everything on screen reaches the model, including whatever text is visible. Screen content is untrusted input; treat instructions that appear on screen as a prompt injection risk.

## Limitations

- Primary monitor only.
- Your terminal is not excluded from screenshots, so Claude sees its own session on screen.
- No video: `record` samples still frames (8 max) rather than streaming.

## Development

```bash
uv sync
uv run winuse-mcp        # stdio server
```

Smoke tests live in `.tmp/` style scripts; an MCP stdio round trip test is the reference check:

```bash
uv run python scripts/client_test.py
```

## License

MIT
