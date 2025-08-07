#!/usr/bin/env python3
"""
Pytest configuration for Claude MCP wrapper server unit tests.
Optimized for fast execution with unit tests only.
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_server_functions():
    """Provide mocked server functions for unit tests."""
    with patch('server.handle_task_tool') as mock_task, \
         patch('server.handle_list_tools') as mock_list, \
         patch('server.handle_call_tool') as mock_call:
        
        # Default mock responses
        mock_task.return_value = asyncio.coroutine(lambda: CallToolResult(
            content=[TextContent(type="text", text="Mocked task response")]
        ))()
        
        mock_list.return_value = asyncio.coroutine(lambda: [
            Tool(name="Task", description="Mocked task tool", inputSchema={})
        ])()
        
        mock_call.return_value = asyncio.coroutine(lambda: CallToolResult(
            content=[TextContent(type="text", text="Mocked call response")]
        ))()
        
        yield {
            'task': mock_task,
            'list': mock_list, 
            'call': mock_call
        }


@pytest.fixture(autouse=True)
def setup_unit_test_environment():
    """Setup unit test environment with mocking and fast execution."""
    # Set test-specific environment variables for unit tests
    os.environ.setdefault("CLAUDE_BYPASS_PERMISSIONS", "false")
    os.environ.setdefault("DEBUG", "false")
    os.environ.setdefault("PROGRESS_NOTIFICATIONS", "false")
    os.environ.setdefault("SKIP_INTEGRATION_TESTS", "true")
    os.environ.setdefault("SKIP_SLOW_TESTS", "true")
    
    yield
    
    # Cleanup after test
    pass


def pytest_configure(config):
    """Configure pytest with custom markers for unit tests."""
    config.addinivalue_line(
        "markers", "unit: mark test as fast unit test with mocking"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (disabled by default)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running (disabled by default)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to optimize for unit tests."""
    skip_integration = pytest.mark.skip(reason="Integration tests disabled for unit test suite")
    skip_slow = pytest.mark.skip(reason="Slow tests disabled for unit test suite")
    
    for item in items:
        # Skip any tests marked as integration
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
        
        # Skip any tests marked as slow
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
        
        # Mark all remaining tests as unit tests
        if "integration" not in item.keywords and "slow" not in item.keywords:
            item.add_marker(pytest.mark.unit)
        
        # Skip tests with server/connection patterns (likely integration tests)
        if any(keyword in item.name for keyword in ["server", "connection", "delegation"]):
            if "mock" not in item.name.lower():
                item.add_marker(skip_integration)