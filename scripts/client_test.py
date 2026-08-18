import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command="uv", args=["run", "winuse-mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("tools:", names)

            result = await session.call_tool("screenshot", {})
            block = result.content[0]
            print("screenshot block type:", block.type, "mime:", getattr(block, "mimeType", None), "b64 len:", len(getattr(block, "data", "")))

            result = await session.call_tool("cursor_position", {})
            print("cursor_position:", result.content[0].text)

            result = await session.call_tool("mouse_move", {"x": 100, "y": 100})
            print("mouse_move:", result.content[0].text)

            result = await session.call_tool("cursor_position", {})
            print("cursor_position after move:", result.content[0].text)

            result = await session.call_tool("record", {"duration_seconds": 2, "max_frames": 3})
            print("record frames:", len(result.content), "types:", {b.type for b in result.content})

            result = await session.call_tool("key", {"combo": "nosuchkey"})
            print("bad key isError:", result.is_error)


asyncio.run(main())
