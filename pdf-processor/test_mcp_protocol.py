#!/usr/bin/env python3
"""Test MCP server protocol communication via stdio"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

async def test_mcp_initialization():
    """Test that the server responds to initialize request"""

    # MCP initialize request
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }

    # Get absolute path to server script
    server_path = Path(__file__).parent / "src" / "mcp_pdf_server.py"
    venv_python = Path(__file__).parent / "test_env" / "bin" / "python3"

    if not venv_python.exists():
        print("✗ ERROR: Virtual environment not found. Run setup first.")
        return False

    try:
        # Start the server process
        process = await asyncio.create_subprocess_exec(
            str(venv_python),
            str(server_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Send initialize request
        request_json = json.dumps(initialize_request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()

        # Wait for response with timeout
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)

            if not response_line:
                stderr = await process.stderr.read()
                print(f"✗ ERROR: No response from server. Stderr: {stderr.decode()}")
                process.kill()
                return False

            # Parse response
            response = json.loads(response_line.decode())

            # Verify response structure
            if "jsonrpc" not in response or response["jsonrpc"] != "2.0":
                print(f"✗ ERROR: Invalid JSON-RPC response: {response}")
                process.kill()
                return False

            if "id" not in response or response["id"] != 1:
                print(f"✗ ERROR: Response ID mismatch: {response}")
                process.kill()
                return False

            if "result" not in response:
                print(f"✗ ERROR: No result in response: {response}")
                process.kill()
                return False

            result = response["result"]

            # Check for required fields in result
            if "protocolVersion" not in result:
                print(f"✗ ERROR: Missing protocolVersion in result: {result}")
                process.kill()
                return False

            if "capabilities" not in result:
                print(f"✗ ERROR: Missing capabilities in result: {result}")
                process.kill()
                return False

            if "serverInfo" not in result:
                print(f"✗ ERROR: Missing serverInfo in result: {result}")
                process.kill()
                return False

            print(f"✓ Server initialized successfully")
            print(f"  Protocol version: {result['protocolVersion']}")
            print(f"  Server name: {result['serverInfo'].get('name', 'unknown')}")
            print(f"  Capabilities: {list(result['capabilities'].keys())}")

            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            notification_json = json.dumps(initialized_notification) + "\n"
            process.stdin.write(notification_json.encode())
            await process.stdin.drain()

            # Test tools/list request
            tools_list_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }

            tools_request_json = json.dumps(tools_list_request) + "\n"
            process.stdin.write(tools_request_json.encode())
            await process.stdin.drain()

            # Read tools response
            tools_response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
            tools_response = json.loads(tools_response_line.decode())

            if "result" not in tools_response:
                print(f"✗ ERROR: No result in tools response: {tools_response}")
                process.kill()
                return False

            tools_result = tools_response["result"]
            if "tools" not in tools_result:
                print(f"✗ ERROR: No tools in tools response: {tools_result}")
                process.kill()
                return False

            tools = tools_result["tools"]
            print(f"✓ Server responded to tools/list with {len(tools)} tools")

            for tool in tools[:3]:  # Show first 3 tools
                print(f"  - {tool['name']}: {tool.get('description', 'No description')[:50]}...")

            # Clean up
            process.kill()
            await process.wait()

            return True

        except asyncio.TimeoutError:
            stderr = await process.stderr.read()
            print(f"✗ ERROR: Server response timeout. Stderr: {stderr.decode()}")
            process.kill()
            return False

    except Exception as e:
        print(f"✗ ERROR: Exception during protocol test: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run protocol tests"""
    print("=" * 60)
    print("PDF Processor MCP Server - Protocol Communication Test")
    print("=" * 60)
    print()

    print("Test: MCP Initialize and Tools List")
    result = await test_mcp_initialization()

    print("\n" + "=" * 60)
    if result:
        print("🎉 Protocol test passed! Server can communicate via MCP protocol.")
        return 0
    else:
        print("❌ Protocol test failed. Server cannot communicate properly.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
