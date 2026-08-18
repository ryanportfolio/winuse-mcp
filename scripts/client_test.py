"""End-to-end check: speak MCP over stdio to the server and exercise it.

This drives the real screen, so the mouse moves while it runs. It exits
non-zero on the first failed check.
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

failures = []


def check(name, ok, detail=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{f': {detail}' if detail else ''}")
    if not ok:
        failures.append(name)


async def main():
    params = StdioServerParameters(command="uv", args=["run", "winuse-mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = {t.name for t in (await session.list_tools()).tools}
            expected = {
                "screenshot",
                "left_click",
                "double_click",
                "triple_click",
                "right_click",
                "middle_click",
                "mouse_move",
                "left_click_drag",
                "type",
                "key",
                "scroll",
                "cursor_position",
                "record",
                "wait",
            }
            check("every tool is exposed", tools == expected, f"missing {expected - tools}, extra {tools - expected}")

            shot = (await session.call_tool("screenshot", {})).content[0]
            check(
                "screenshot returns an image block",
                shot.type == "image" and len(getattr(shot, "data", "")) > 1000,
                f"type={shot.type}, {len(getattr(shot, 'data', ''))} base64 chars",
            )

            await session.call_tool("mouse_move", {"x": 100, "y": 100})
            pos = (await session.call_tool("cursor_position", {})).content[0].text
            x, y = (int(v) for v in pos.strip("()").split(","))
            # A pixel of rounding is expected: the round trip crosses the
            # downscale and back.
            check("the cursor lands where it was sent", abs(x - 100) <= 1 and abs(y - 100) <= 1, f"asked 100, 100 and read {pos}")

            frames = (await session.call_tool("record", {"duration_seconds": 2, "max_frames": 3})).content
            check(
                "record returns the frames it was asked for",
                len(frames) == 3 and all(f.type == "image" for f in frames),
                f"{len(frames)} blocks, types {[f.type for f in frames]}",
            )

            bad = await session.call_tool("key", {"combo": "nosuchkey"})
            check("an unknown key reports an error", bad.is_error is True, f"is_error={bad.is_error}")

            plus = await session.call_tool("key", {"combo": "ctrl++"})
            check("a chord ending in plus is accepted", plus.is_error is not True, f"is_error={plus.is_error}")


asyncio.run(main())
if failures:
    print(f"\n{len(failures)} failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall checks passed")
