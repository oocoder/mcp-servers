#!/usr/bin/env python3
"""
Comprehensive tests for PDF processor caching functionality
"""

import pytest
import asyncio
import tempfile
import time
import json
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add src directory to path to import modules
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from mcp_pdf_server import PDFProcessor, MARKER_AVAILABLE


class TestPDFProcessorCaching:
    """Test caching functionality in PDF processor"""
    
    @pytest.fixture
    def temp_cache_processor(self):
        """Create a PDF processor with temporary cache directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            processor = PDFProcessor(cache_dir=cache_dir)
            yield processor
    
    def test_cache_directories_created(self, temp_cache_processor):
        """Test that cache directories are created correctly"""
        processor = temp_cache_processor
        
        assert processor.cache_dir.exists()
        assert processor.cache_dir.is_dir()
        assert processor.markdown_cache_dir.exists()
        assert processor.markdown_cache_dir.is_dir()
        assert processor.markdown_cache_dir.name == "markdown"
        assert processor.markdown_cache_dir.parent == processor.cache_dir
    
    def test_cache_key_generation(self, temp_cache_processor):
        """Test cache key generation for different parameters"""
        processor = temp_cache_processor
        
        url = "https://example.com/test.pdf"
        
        # Basic cache key
        key1 = processor._get_conversion_cache_key(url)
        assert isinstance(key1, str)
        assert len(key1) == 32  # MD5 hash length
        
        # Same parameters should generate same key
        key2 = processor._get_conversion_cache_key(url)
        assert key1 == key2
        
        # Different parameters should generate different keys
        key3 = processor._get_conversion_cache_key(url, start_page=1, end_page=5)
        assert key1 != key3
        
        key4 = processor._get_conversion_cache_key(url, force_method="pymupdf")
        assert key1 != key4
        assert key3 != key4
        
        # Different URLs should generate different keys
        key5 = processor._get_conversion_cache_key("https://other.com/test.pdf")
        assert key1 != key5
    
    def test_cache_key_deterministic(self, temp_cache_processor):
        """Test that cache keys are deterministic across runs"""
        processor = temp_cache_processor
        
        url = "https://example.com/test.pdf"
        params = {
            'start_page': 1,
            'end_page': 10,
            'force_method': 'marker'
        }
        
        # Generate key multiple times
        keys = [
            processor._get_conversion_cache_key(url, **params)
            for _ in range(5)
        ]
        
        # All keys should be identical
        assert all(key == keys[0] for key in keys)
    
    def test_cache_key_includes_marker_availability(self, temp_cache_processor):
        """Test that cache keys consider marker-pdf availability"""
        processor = temp_cache_processor
        url = "https://example.com/test.pdf"
        
        # Get key with current marker availability
        key1 = processor._get_conversion_cache_key(url)
        
        # Mock marker availability change and verify key changes
        with patch('mcp_pdf_server.MARKER_AVAILABLE', not MARKER_AVAILABLE):
            key2 = processor._get_conversion_cache_key(url)
            assert key1 != key2, "Cache key should change when marker availability changes"
    
    def test_markdown_cache_storage_and_retrieval(self, temp_cache_processor):
        """Test storing and retrieving markdown from cache"""
        processor = temp_cache_processor
        
        cache_key = "test_key_123"
        test_content = "# Test Markdown\n\nThis is test content with **bold** text."
        
        # Initially no cache
        cached = processor._get_cached_markdown(cache_key)
        assert cached is None
        
        # Store content
        processor._cache_markdown(cache_key, test_content)
        
        # Verify cache file was created
        cache_file = processor.markdown_cache_dir / f"{cache_key}.md"
        assert cache_file.exists()
        
        # Retrieve cached content
        cached = processor._get_cached_markdown(cache_key)
        assert cached == test_content
    
    def test_cache_file_corruption_handling(self, temp_cache_processor):
        """Test handling of corrupted cache files"""
        processor = temp_cache_processor
        
        cache_key = "corrupt_test"
        cache_file = processor.markdown_cache_dir / f"{cache_key}.md"
        
        # Create a corrupted cache file (binary data)
        cache_file.write_bytes(b'\x00\x01\x02\x03\xFF\xFE')
        
        # Should handle corruption gracefully
        cached = processor._get_cached_markdown(cache_key)
        assert cached is None
        
        # Corrupted file should be cleaned up
        assert not cache_file.exists()
    
    @patch('fitz.open')
    def test_conversion_with_caching(self, mock_fitz_open, temp_cache_processor):
        """Test that conversion uses and stores cache correctly"""
        processor = temp_cache_processor
        
        # Mock PDF file with proper structure
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.metadata = {'title': 'Test Paper', 'author': 'Test Author'}
        mock_page = MagicMock()
        
        # Mock get_text with different return values based on arguments
        def mock_get_text(format_type="text"):
            if format_type == "dict":
                return {
                    "blocks": [
                        {
                            "lines": [
                                {
                                    "spans": [
                                        {
                                            "text": "Test PDF content",
                                            "size": 12,
                                            "flags": 0
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            else:
                return "Test PDF content"
        
        mock_page.get_text.side_effect = mock_get_text
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__iter__.return_value = [mock_page]
        mock_fitz_open.return_value = mock_doc
        
        pdf_path = Path("/fake/path/test.pdf")
        source_url = "https://example.com/test.pdf"
        
        # First conversion - should not use cache
        result1 = processor.convert_pdf_to_markdown(
            pdf_path, 
            source_url=source_url, 
            force_method="pymupdf"
        )
        
        # Verify result is not empty
        assert len(result1) > 0
        assert "Test PDF content" in result1
        
        # Verify cache was created
        cache_key = processor._get_conversion_cache_key(source_url, force_method="pymupdf")
        cache_file = processor.markdown_cache_dir / f"{cache_key}.md"
        assert cache_file.exists()
        
        # Second conversion - should use cache
        result2 = processor.convert_pdf_to_markdown(
            pdf_path, 
            source_url=source_url, 
            force_method="pymupdf"
        )
        
        # Results should be identical
        assert result1 == result2
        
        # Fitz should only be called for first conversion (metadata + conversion)
        first_call_count = mock_fitz_open.call_count
        assert first_call_count >= 1
        
        # Reset call count to verify caching
        mock_fitz_open.reset_mock()
        
        # Third conversion - should use cache, no additional PDF operations
        result3 = processor.convert_pdf_to_markdown(
            pdf_path, 
            source_url=source_url, 
            force_method="pymupdf"
        )
        
        # Results should still be identical
        assert result1 == result3
        
        # No additional PDF operations should occur
        assert mock_fitz_open.call_count == 0
    
    def test_cache_miss_without_source_url(self, temp_cache_processor):
        """Test that caching is skipped when source_url is not provided"""
        processor = temp_cache_processor
        
        with patch.object(processor, '_get_cached_markdown') as mock_get_cache, \
             patch.object(processor, '_cache_markdown') as mock_set_cache, \
             patch.object(processor, '_convert_pdf_to_markdown_pymupdf') as mock_convert:
            
            mock_convert.return_value = "test result"
            
            # Call without source_url
            result = processor.convert_pdf_to_markdown(Path("/fake/path"))
            
            # Cache methods should not be called
            mock_get_cache.assert_not_called()
            mock_set_cache.assert_not_called()
            assert result == "test result"
    
    def test_different_methods_create_different_cache_entries(self, temp_cache_processor):
        """Test that different conversion methods create separate cache entries"""
        processor = temp_cache_processor
        
        url = "https://example.com/test.pdf"
        
        # Generate cache keys for different methods
        key_auto = processor._get_conversion_cache_key(url, force_method=None)
        key_pymupdf = processor._get_conversion_cache_key(url, force_method="pymupdf")
        key_marker = processor._get_conversion_cache_key(url, force_method="marker")
        
        # All keys should be different
        assert key_auto != key_pymupdf
        assert key_auto != key_marker
        assert key_pymupdf != key_marker
    
    def test_page_range_affects_cache_key(self, temp_cache_processor):
        """Test that page ranges create different cache entries"""
        processor = temp_cache_processor
        
        url = "https://example.com/test.pdf"
        
        key_all = processor._get_conversion_cache_key(url)
        key_pages_1_5 = processor._get_conversion_cache_key(url, start_page=1, end_page=5)
        key_pages_6_10 = processor._get_conversion_cache_key(url, start_page=6, end_page=10)
        key_pages_1_10 = processor._get_conversion_cache_key(url, start_page=1, end_page=10)
        
        # All should be different
        assert len({key_all, key_pages_1_5, key_pages_6_10, key_pages_1_10}) == 4


class TestCachingIntegration:
    """Integration tests for caching with real scenarios"""
    
    @pytest.fixture
    def integration_processor(self):
        """Create processor for integration testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir)
            processor = PDFProcessor(cache_dir=cache_dir)
            yield processor
    
    @patch('aiohttp.ClientSession.get')
    @pytest.mark.asyncio
    async def test_full_caching_workflow(self, mock_get, integration_processor):
        """Test complete workflow with PDF download and conversion caching"""
        processor = integration_processor
        
        # Mock PDF download
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        async def mock_read():
            return b'%PDF-1.4\nfake pdf content'
        mock_response.read = mock_read
        mock_get.return_value.__aenter__.return_value = mock_response
        
        # Mock PDF conversion
        with patch.object(processor, '_convert_pdf_to_markdown_pymupdf') as mock_convert:
            mock_convert.return_value = "Converted markdown content"
            
            url = "https://example.com/test.pdf"
            
            # First download and conversion
            start_time = time.time()
            pdf_path1 = await processor.download_pdf(url)
            result1 = processor.convert_pdf_to_markdown(pdf_path1, source_url=url, force_method="pymupdf")
            first_duration = time.time() - start_time
            
            # Second attempt - should use caches
            start_time = time.time()
            pdf_path2 = await processor.download_pdf(url)
            result2 = processor.convert_pdf_to_markdown(pdf_path2, source_url=url, force_method="pymupdf")
            second_duration = time.time() - start_time
            
            # Verify results
            assert result1 == result2 == "Converted markdown content"
            assert pdf_path1 == pdf_path2  # Same cached PDF file
            
            # Second run should be significantly faster
            assert second_duration < first_duration
            
            # Download should only happen once
            assert mock_get.call_count == 1
            
            # Conversion should only happen once
            assert mock_convert.call_count == 1
    
    def test_cache_persistence_across_instances(self, integration_processor):
        """Test that cache persists across different processor instances"""
        cache_dir = integration_processor.cache_dir
        
        # Store something in cache with first instance
        cache_key = "persistence_test"
        test_content = "Persistent cache content"
        integration_processor._cache_markdown(cache_key, test_content)
        
        # Create new processor instance with same cache directory
        new_processor = PDFProcessor(cache_dir=cache_dir)
        
        # Should be able to retrieve cached content
        cached_content = new_processor._get_cached_markdown(cache_key)
        assert cached_content == test_content
    
    def test_url_normalization_affects_caching(self, integration_processor):
        """Test that URL normalization works correctly for caching"""
        processor = integration_processor
        
        # URLs that should normalize to the same cache key
        url1 = "https://example.com/test.pdf"
        url2 = "https://example.com/test.pdf#page=1"
        url3 = "https://example.com/test.pdf?view=FitH"
        
        # Should generate same cache keys after normalization
        key1 = processor._get_conversion_cache_key(url1)
        key2 = processor._get_conversion_cache_key(url2)
        key3 = processor._get_conversion_cache_key(url3)
        
        assert key1 == key2 == key3


if __name__ == "__main__":
    # Run tests directly if called as script
    pytest.main([__file__, "-v"])