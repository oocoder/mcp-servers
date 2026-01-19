#!/usr/bin/env python3
"""Final end-to-end test using the actual MCP config"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

async def test_with_actual_config():
    """Test server using the actual MCP config command"""

    # Read the MCP config
    config_path = Path(__file__).parent / "mcp-config.json"
    with open(config_path) as f:
        config = json.load(f)

    server_config = config["mcpServers"]["pdf-processor"]
    command = server_config["command"]
    args = server_config["args"]
    cwd = server_config["cwd"]
    env = server_config.get("env", {})

    print(f"Testing with command: {command}")
    print(f"Args: {args}")
    print(f"CWD: {cwd}")

    try:
        # Start the server
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env={**dict(os.environ), **env} if env else None
        )

        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }

        process.stdin.write((json.dumps(init_request) + "\n").encode())
        await process.stdin.drain()

        # Wait for response
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)

            if response_line:
                response = json.loads(response_line.decode())
                if "result" in response:
                    print("✓ Server initialized successfully!")
                    print(f"  Server: {response['result'].get('serverInfo', {}).get('name', 'unknown')}")
                    print(f"  Protocol: {response['result'].get('protocolVersion', 'unknown')}")

                    # Send initialized notification
                    process.stdin.write((json.dumps({
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized"
                    }) + "\n").encode())
                    await process.stdin.drain()

                    # Request tools list
                    process.stdin.write((json.dumps({
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list",
                        "params": {}
                    }) + "\n").encode())
                    await process.stdin.drain()

                    tools_response = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
                    if tools_response:
                        tools_data = json.loads(tools_response.decode())
                        if "result" in tools_data and "tools" in tools_data["result"]:
                            tools = tools_data["result"]["tools"]
                            print(f"✓ Server returned {len(tools)} tools")
                            print("\nAvailable tools:")
                            for tool in tools:
                                print(f"  - {tool['name']}")

                            process.kill()
                            await process.wait()
                            return True

            stderr = await process.stderr.read()
            print(f"✗ Unexpected response or error: {stderr.decode()}")
            process.kill()
            return False

        except asyncio.TimeoutError:
            stderr = await process.stderr.read()
            print(f"✗ Timeout waiting for server response")
            print(f"  Stderr: {stderr.decode()}")
            process.kill()
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

import os

async def main():
    print("=" * 60)
    print("Final MCP Server Test - Using Actual Config")
    print("=" * 60)
    print()

    success = await test_with_actual_config()

    print()
    print("=" * 60)
    if success:
        print("🎉 SUCCESS! Server is fully functional.")
        print()
        print("You can now use it with Claude Code:")
        print("  claude code --mcp-config mcp-config.json")
        return 0
    else:
        print("❌ Test failed")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
