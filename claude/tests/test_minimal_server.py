#!/usr/bin/env python3
"""
Comprehensive tests for minimal MCP server with Task and TodoWrite tools.
Tests functionality, error handling, and best practices implementation.
"""

import asyncio
import json
import sys
import traceback
from typing import Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest


class ServerTestResults:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
    
    def add_result(self, test_name: str, passed: bool, error: str = None):
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            self.tests_failed += 1
            self.failures.append((test_name, error))
            print(f"❌ {test_name}: {error}")
    
    def summary(self):
        print(f"\n📊 Test Summary:")
        print(f"   Total: {self.tests_run}")
        print(f"   Passed: {self.tests_passed}")
        print(f"   Failed: {self.tests_failed}")
        
        if self.failures:
            print(f"\n❌ Failures:")
            for test_name, error in self.failures:
                print(f"   {test_name}: {error}")
        
        return self.tests_failed == 0


@pytest.mark.asyncio
async def test_server_discovery():
    """Test that server can be discovered and lists correct tools."""
    results = ServerTestResults()
    
    server_params = StdioServerParameters(
        command="python3",
        args=["/Users/alexmaldonado/projects/mcp-servers/claude/src/mcp_compliant_server.py"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Test 1: Server initialization
                try:
                    await session.initialize()
                    results.add_result("Server initialization", True)
                except Exception as e:
                    results.add_result("Server initialization", False, str(e))
                    return results
                
                # Test 2: Tool discovery
                try:
                    tools = await session.list_tools()
                    tool_names = [tool.name for tool in tools.tools]
                    
                    expected_tools = ["Task", "TodoWrite"]
                    if set(tool_names) == set(expected_tools):
                        results.add_result("Tool discovery - correct tools", True)
                    else:
                        results.add_result("Tool discovery - correct tools", False, 
                                         f"Expected {expected_tools}, got {tool_names}")
                    
                    # Verify only expected tools (no extras)
                    if len(tool_names) == 2:
                        results.add_result("Tool discovery - no extra tools", True)
                    else:
                        results.add_result("Tool discovery - no extra tools", False,
                                         f"Expected 2 tools, got {len(tool_names)}")
                    
                except Exception as e:
                    results.add_result("Tool discovery", False, str(e))
                
                # Test 3: Tool descriptions
                try:
                    tools = await session.list_tools()
                    for tool in tools.tools:
                        if tool.name == "Task":
                            if "complex, multi-step tasks" in tool.description:
                                results.add_result("Task tool description", True)
                            else:
                                results.add_result("Task tool description", False,
                                                 "Description doesn't mention multi-step tasks")
                        elif tool.name == "TodoWrite":
                            if "structured task lists" in tool.description:
                                results.add_result("TodoWrite tool description", True)
                            else:
                                results.add_result("TodoWrite tool description", False,
                                                 "Description doesn't mention task lists")
                except Exception as e:
                    results.add_result("Tool descriptions", False, str(e))
    
    except Exception as e:
        results.add_result("Server connection", False, str(e))
    
    return results


@pytest.mark.asyncio
async def test_todowrite_functionality():
    """Test TodoWrite tool functionality and validation."""
    results = ServerTestResults()
    
    server_params = StdioServerParameters(
        command="python3",
        args=["/Users/alexmaldonado/projects/mcp-servers/claude/src/mcp_compliant_server.py"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Test 1: Valid todo creation
                try:
                    result = await session.call_tool("TodoWrite", {
                        "todos": [
                            {"id": "1", "content": "Test task 1", "status": "pending"},
                            {"id": "2", "content": "Test task 2", "status": "in_progress"}
                        ]
                    })
                    
                    response_text = result.content[0].text
                    if "Todo List Updated" in response_text and "2 total tasks" in response_text:
                        results.add_result("TodoWrite - valid todo creation", True)
                    else:
                        results.add_result("TodoWrite - valid todo creation", False,
                                         "Response doesn't contain expected content")
                except Exception as e:
                    results.add_result("TodoWrite - valid todo creation", False, str(e))
                
                # Test 2: Empty content validation
                try:
                    result = await session.call_tool("TodoWrite", {
                        "todos": [
                            {"id": "1", "content": "", "status": "pending"}
                        ]
                    })
                    
                    response_text = result.content[0].text
                    if "content cannot be empty" in response_text:
                        results.add_result("TodoWrite - empty content validation", True)
                    else:
                        results.add_result("TodoWrite - empty content validation", False,
                                         "Should reject empty content")
                except Exception as e:
                    results.add_result("TodoWrite - empty content validation", False, str(e))
                
                # Test 3: Invalid status validation
                try:
                    result = await session.call_tool("TodoWrite", {
                        "todos": [
                            {"id": "1", "content": "Test", "status": "invalid_status"}
                        ]
                    })
                    
                    response_text = result.content[0].text
                    if "invalid status" in response_text:
                        results.add_result("TodoWrite - invalid status validation", True)
                    else:
                        results.add_result("TodoWrite - invalid status validation", False,
                                         "Should reject invalid status")
                except Exception as e:
                    results.add_result("TodoWrite - invalid status validation", False, str(e))
                
                # Test 4: Missing required fields
                try:
                    result = await session.call_tool("TodoWrite", {
                        "todos": [
                            {"id": "1", "content": "Test"}  # Missing status
                        ]
                    })
                    
                    response_text = result.content[0].text
                    if "missing required field" in response_text:
                        results.add_result("TodoWrite - missing field validation", True)
                    else:
                        results.add_result("TodoWrite - missing field validation", False,
                                         "Should reject missing required fields")
                except Exception as e:
                    results.add_result("TodoWrite - missing field validation", False, str(e))
                
                # Test 5: Best practices warning (multiple in_progress)
                try:
                    result = await session.call_tool("TodoWrite", {
                        "todos": [
                            {"id": "1", "content": "Task 1", "status": "in_progress"},
                            {"id": "2", "content": "Task 2", "status": "in_progress"}
                        ]
                    })
                    
                    response_text = result.content[0].text
                    if "Best Practice Warning" in response_text and "Multiple tasks in progress" in response_text:
                        results.add_result("TodoWrite - best practice warning", True)
                    else:
                        results.add_result("TodoWrite - best practice warning", False,
                                         "Should warn about multiple tasks in progress")
                except Exception as e:
                    results.add_result("TodoWrite - best practice warning", False, str(e))
                
                # Test 6: Completion celebration
                try:
                    result = await session.call_tool("TodoWrite", {
                        "todos": [
                            {"id": "1", "content": "Task 1", "status": "completed"},
                            {"id": "2", "content": "Task 2", "status": "completed"}
                        ]
                    })
                    
                    response_text = result.content[0].text
                    if "All tasks completed!" in response_text:
                        results.add_result("TodoWrite - completion celebration", True)
                    else:
                        results.add_result("TodoWrite - completion celebration", False,
                                         "Should celebrate when all tasks completed")
                except Exception as e:
                    results.add_result("TodoWrite - completion celebration", False, str(e))
    
    except Exception as e:
        results.add_result("TodoWrite server connection", False, str(e))
    
    return results


@pytest.mark.asyncio
async def test_task_functionality():
    """Test Task tool functionality and validation."""
    results = ServerTestResults()
    
    server_params = StdioServerParameters(
        command="python3",
        args=["/Users/alexmaldonado/projects/mcp-servers/claude/src/mcp_compliant_server.py"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Test 1: Valid task execution
                try:
                    result = await session.call_tool("Task", {
                        "prompt": "Create a simple Python script that prints 'Hello, World!'"
                    })
                    
                    response_text = result.content[0].text
                    if "Task Agent" in response_text and "Task Interpretation" in response_text:
                        results.add_result("Task - valid task execution", True)
                    else:
                        results.add_result("Task - valid task execution", False,
                                         "Response doesn't contain expected task execution format")
                except Exception as e:
                    results.add_result("Task - valid task execution", False, str(e))
                
                # Test 2: Missing prompt validation
                try:
                    result = await session.call_tool("Task", {})
                    
                    response_text = result.content[0].text
                    if "prompt' parameter is required" in response_text:
                        results.add_result("Task - missing prompt validation", True)
                    else:
                        results.add_result("Task - missing prompt validation", False,
                                         "Should require prompt parameter")
                except Exception as e:
                    results.add_result("Task - missing prompt validation", False, str(e))
                
                # Test 3: Working directory handling
                try:
                    result = await session.call_tool("Task", {
                        "prompt": "List files in current directory",
                        "working_directory": "/nonexistent/directory"
                    })
                    
                    response_text = result.content[0].text
                    if "Working directory does not exist" in response_text:
                        results.add_result("Task - invalid working directory warning", True)
                    else:
                        results.add_result("Task - invalid working directory warning", False,
                                         "Should warn about nonexistent directory")
                except Exception as e:
                    results.add_result("Task - invalid working directory warning", False, str(e))
                
                # Test 4: Task ID generation
                try:
                    result = await session.call_tool("Task", {
                        "prompt": "Simple test task"
                    })
                    
                    response_text = result.content[0].text
                    if "Task Agent [" in response_text and "]" in response_text:
                        results.add_result("Task - ID generation", True)
                    else:
                        results.add_result("Task - ID generation", False,
                                         "Should generate task ID")
                except Exception as e:
                    results.add_result("Task - ID generation", False, str(e))
                
                # Test 5: Implementation notes
                try:
                    result = await session.call_tool("Task", {
                        "prompt": "Test task for implementation notes"
                    })
                    
                    response_text = result.content[0].text
                    if "simulated task execution" in response_text and "In a real implementation" in response_text:
                        results.add_result("Task - implementation notes", True)
                    else:
                        results.add_result("Task - implementation notes", False,
                                         "Should include implementation notes")
                except Exception as e:
                    results.add_result("Task - implementation notes", False, str(e))
    
    except Exception as e:
        results.add_result("Task server connection", False, str(e))
    
    return results


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling for invalid tool calls."""
    results = ServerTestResults()
    
    server_params = StdioServerParameters(
        command="python3",
        args=["/Users/alexmaldonado/projects/mcp-servers/claude/src/mcp_compliant_server.py"]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Test 1: Unknown tool
                try:
                    result = await session.call_tool("UnknownTool", {})
                    
                    response_text = result.content[0].text
                    if "Unknown tool 'UnknownTool'" in response_text and "Available tools: Task, TodoWrite" in response_text:
                        results.add_result("Error handling - unknown tool", True)
                    else:
                        results.add_result("Error handling - unknown tool", False,
                                         "Should handle unknown tool gracefully")
                except Exception as e:
                    results.add_result("Error handling - unknown tool", False, str(e))
                
                # Test 2: Invalid arguments type
                try:
                    result = await session.call_tool("TodoWrite", {
                        "todos": "not an array"
                    })
                    
                    response_text = result.content[0].text
                    if "'todos' must be an array" in response_text:
                        results.add_result("Error handling - invalid argument type", True)
                    else:
                        results.add_result("Error handling - invalid argument type", False,
                                         "Should handle invalid argument types")
                except Exception as e:
                    results.add_result("Error handling - invalid argument type", False, str(e))
    
    except Exception as e:
        results.add_result("Error handling server connection", False, str(e))
    
    return results


async def run_all_tests():
    """Run all tests and return overall results."""
    print("🧪 Testing Minimal Claude MCP Server")
    print("=" * 50)
    
    all_results = TestResults()
    
    # Test 1: Server Discovery
    print("\n📡 Testing Server Discovery...")
    discovery_results = await test_server_discovery()
    all_results.tests_run += discovery_results.tests_run
    all_results.tests_passed += discovery_results.tests_passed  
    all_results.tests_failed += discovery_results.tests_failed
    all_results.failures.extend(discovery_results.failures)
    
    # Test 2: TodoWrite Functionality
    print("\n📝 Testing TodoWrite Functionality...")
    todowrite_results = await test_todowrite_functionality()
    all_results.tests_run += todowrite_results.tests_run
    all_results.tests_passed += todowrite_results.tests_passed
    all_results.tests_failed += todowrite_results.tests_failed
    all_results.failures.extend(todowrite_results.failures)
    
    # Test 3: Task Functionality  
    print("\n🤖 Testing Task Functionality...")
    task_results = await test_task_functionality()
    all_results.tests_run += task_results.tests_run
    all_results.tests_passed += task_results.tests_passed
    all_results.tests_failed += task_results.tests_failed
    all_results.failures.extend(task_results.failures)
    
    # Test 4: Error Handling
    print("\n❌ Testing Error Handling...")
    error_results = await test_error_handling()
    all_results.tests_run += error_results.tests_run
    all_results.tests_passed += error_results.tests_passed
    all_results.tests_failed += error_results.tests_failed
    all_results.failures.extend(error_results.failures)
    
    # Final Summary
    print("\n" + "=" * 50)
    success = all_results.summary()
    
    if success:
        print("\n🎉 All tests passed! The minimal server is working correctly.")
    else:
        print(f"\n💥 {all_results.tests_failed} tests failed. Please review and fix issues.")
    
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Test runner crashed: {e}")
        traceback.print_exc()
        sys.exit(1)