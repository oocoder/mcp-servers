#!/usr/bin/env python3
"""
Test client for the task executor MCP server.
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest


@pytest.mark.asyncio
async def test_task_executor():
    """Test the task executor server."""
    server_params = StdioServerParameters(
        command="python3",
        args=["/Users/alexmaldonado/projects/mcp-servers/claude/task_executor_server.py"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()
                
                # List available tools
                tools = await session.list_tools()
                print("Available tools:", [tool.name for tool in tools.tools])
                print()
                
                # Test execute_task_file
                print("Testing execute_task_file...")
                result = await session.call_tool(
                    "execute_task_file",
                    {
                        "file_path": "/Users/alexmaldonado/projects/mcp-servers/claude/test_hello.md",
                        "working_directory": "/Users/alexmaldonado/projects/mcp-servers/claude"
                    }
                )
                print("Result:", result.content[0].text)
                print()
                
                # Test execute_dev_cycle
                print("Testing execute_dev_cycle...")
                result = await session.call_tool(
                    "execute_dev_cycle",
                    {
                        "instructions": "Create a simple calculator Python script that can add two numbers",
                        "working_directory": "/Users/alexmaldonado/projects/mcp-servers/claude"
                    }
                )
                print("Result:", result.content[0].text)
                
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_task_executor())