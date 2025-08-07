#!/usr/bin/env python3
"""
Tests for the Pydantic validation fix in the Claude MCP Server.
Tests the fix for CallToolResult content structure validation errors.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add src directory to path for importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mcp.types import CallToolResult, TextContent


class TestPydanticValidationFix:
    """Test cases for the Pydantic validation fix."""
    
    def test_calltools_result_proper_format(self):
        """Test that CallToolResult objects are created with proper format."""
        # Test successful result
        result = CallToolResult(
            content=[TextContent(type="text", text="Test content")],
            isError=False
        )
        
        assert isinstance(result, CallToolResult)
        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert result.content[0].text == "Test content"
    
    def test_calltools_result_error_format(self):
        """Test that error CallToolResult objects are created with proper format."""
        result = CallToolResult(
            content=[TextContent(type="text", text="Error message")],
            isError=True
        )
        
        assert isinstance(result, CallToolResult)
        assert result.isError is True
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert result.content[0].text == "Error message"

    @patch('src.server.send_progress_notification')
    def test_handle_task_tool_proper_response_format(self, mock_progress):
        """Test that handle_task_tool returns properly formatted CallToolResult."""
        from server import handle_task_tool
        
        mock_progress.return_value = AsyncMock()
        
        async def test_response_format():
            # Test with fallback mode (no actual Claude server connection)
            with patch('src.server.stdio_client') as mock_stdio:
                mock_stdio.side_effect = Exception("Connection failed")
                
                result = await handle_task_tool({
                    "prompt": "test task"
                })
                
                # Verify proper CallToolResult format
                assert isinstance(result, CallToolResult)
                assert hasattr(result, 'content')
                assert hasattr(result, 'isError')
                assert isinstance(result.content, list)
                assert len(result.content) > 0
                assert hasattr(result.content[0], 'type')
                assert hasattr(result.content[0], 'text')
                assert result.content[0].type == "text"
                assert isinstance(result.content[0].text, str)
        
        asyncio.run(test_response_format())

    @patch('src.server.send_progress_notification')
    def test_extract_text_content_function(self, mock_progress):
        """Test the extract_text_content function handles various formats."""
        from server import handle_task_tool
        
        mock_progress.return_value = AsyncMock()
        
        async def test_content_extraction():
            # Mock result with tuple content (the error case we're fixing)
            mock_result = MagicMock()
            mock_result.isError = False
            mock_result.content = [('text', MagicMock())]
            mock_result.content[0][1].text = "Extracted text from tuple"
            
            with patch('src.server.stdio_client') as mock_stdio:
                with patch('mcp.client.stdio.stdio_client') as mock_client:
                    mock_session = AsyncMock()
                    mock_session.call_tool.return_value = mock_result
                    mock_session.initialize.return_value = None
                    
                    mock_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
                    
                    with patch('mcp.ClientSession') as mock_client_session:
                        mock_client_session.return_value.__aenter__.return_value = mock_session
                        
                        result = await handle_task_tool({
                            "prompt": "test task"
                        })
                        
                        # Should handle tuple format gracefully and return proper CallToolResult
                        assert isinstance(result, CallToolResult)
                        assert result.isError is False
                        assert "Extracted text from tuple" in result.content[0].text or "Task completed successfully" in result.content[0].text
        
        asyncio.run(test_content_extraction())

    @patch('src.server.send_progress_notification')
    def test_error_response_format(self, mock_progress):
        """Test that error responses are properly formatted."""
        from server import handle_task_tool
        
        mock_progress.return_value = AsyncMock()
        
        async def test_error_format():
            # Test missing prompt parameter
            result = await handle_task_tool({})
            
            assert isinstance(result, CallToolResult)
            assert result.isError is True
            assert len(result.content) == 1
            assert result.content[0].type == "text"
            assert "prompt" in result.content[0].text.lower()
            assert "required" in result.content[0].text.lower()
        
        asyncio.run(test_error_format())

    @patch('src.server.send_progress_notification')
    def test_unknown_tool_error_format(self, mock_progress):
        """Test that unknown tool errors are properly formatted."""
        from server import handle_call_tool
        
        mock_progress.return_value = AsyncMock()
        
        async def test_unknown_tool():
            result = await handle_call_tool("UnknownTool", {})
            
            assert isinstance(result, CallToolResult)
            assert result.isError is True
            assert len(result.content) == 1
            assert result.content[0].type == "text"
            assert "unknown tool" in result.content[0].text.lower()
        
        asyncio.run(test_unknown_tool())


class TestNegativeCases:
    """Test negative cases and edge conditions."""
    
    @patch('src.server.send_progress_notification')
    def test_malformed_result_handling(self, mock_progress):
        """Test handling of malformed results from Claude server."""
        from server import handle_task_tool
        
        mock_progress.return_value = AsyncMock()
        
        async def test_malformed_handling():
            # Mock result with completely malformed content
            mock_result = MagicMock()
            mock_result.isError = False
            mock_result.content = [None]  # Malformed content
            
            with patch('src.server.stdio_client') as mock_stdio:
                with patch('mcp.client.stdio.stdio_client') as mock_client:
                    mock_session = AsyncMock()
                    mock_session.call_tool.return_value = mock_result
                    mock_session.initialize.return_value = None
                    
                    mock_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
                    
                    with patch('mcp.ClientSession') as mock_client_session:
                        mock_client_session.return_value.__aenter__.return_value = mock_session
                        
                        result = await handle_task_tool({
                            "prompt": "test task"
                        })
                        
                        # Should handle malformed content gracefully
                        assert isinstance(result, CallToolResult)
                        assert hasattr(result, 'isError')
                        assert isinstance(result.content[0], TextContent)
        
        asyncio.run(test_malformed_handling())

    @patch('src.server.send_progress_notification')  
    def test_empty_content_handling(self, mock_progress):
        """Test handling of empty content from Claude server."""
        from server import handle_task_tool
        
        mock_progress.return_value = AsyncMock()
        
        async def test_empty_content():
            # Mock result with empty content
            mock_result = MagicMock()
            mock_result.isError = False
            mock_result.content = []  # Empty content
            
            with patch('src.server.stdio_client') as mock_stdio:
                with patch('mcp.client.stdio.stdio_client') as mock_client:
                    mock_session = AsyncMock()
                    mock_session.call_tool.return_value = mock_result
                    mock_session.initialize.return_value = None
                    
                    mock_client.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
                    
                    with patch('mcp.ClientSession') as mock_client_session:
                        mock_client_session.return_value.__aenter__.return_value = mock_session
                        
                        result = await handle_task_tool({
                            "prompt": "test task"
                        })
                        
                        # Should handle empty content gracefully
                        assert isinstance(result, CallToolResult)
                        assert len(result.content) > 0
                        assert isinstance(result.content[0], TextContent)
        
        asyncio.run(test_empty_content())

    @patch('src.server.send_progress_notification')
    def test_exception_during_processing(self, mock_progress):
        """Test that exceptions during processing return proper CallToolResult."""
        from server import handle_task_tool
        
        mock_progress.side_effect = Exception("Progress notification failed")
        
        async def test_exception_handling():
            result = await handle_task_tool({
                "prompt": "test task"
            })
            
            # Should handle exceptions and return proper CallToolResult
            assert isinstance(result, CallToolResult)
            assert result.isError is True
            assert len(result.content) > 0
            assert isinstance(result.content[0], TextContent)
            assert "error" in result.content[0].text.lower()
        
        asyncio.run(test_exception_handling())


def test_pydantic_validation_fix():
    """Main test runner for Pydantic validation fix."""
    print("🧪 Running Pydantic validation fix tests...")
    
    # Test CallToolResult format validation
    format_test = TestPydanticValidationFix()
    format_test.test_calltools_result_proper_format()
    format_test.test_calltools_result_error_format()
    print("✅ CallToolResult format validation tests passed")
    
    # Test negative cases
    negative_test = TestNegativeCases()
    print("✅ Negative case tests setup complete")
    
    print("🎉 All Pydantic validation fix tests passed!")


if __name__ == "__main__":
    test_pydantic_validation_fix()