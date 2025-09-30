#!/usr/bin/env python3
"""
Comprehensive tests for the PDF processor functionality
"""

import asyncio
import pytest
from pathlib import Path
import tempfile
import sys
import os
from typing import List, Dict, Any

# Add src directory to path to import modules
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from mcp_pdf_server import PDFProcessor, URLCrawler, server, call_tool


class TestPDFProcessor:
    """Test PDF processing functionality"""
    
    @pytest.fixture
    def processor(self):
        """Create a PDF processor instance for testing"""
        return PDFProcessor()
    
    def test_pdf_processor_initialization(self, processor: PDFProcessor) -> None:
        """Test that PDF processor initializes correctly with proper cache setup."""
        assert processor is not None
        assert processor.cache_dir.exists()
        assert processor.cache_dir.is_dir()
        # Test new markdown cache directory
        assert processor.markdown_cache_dir.exists()
        assert processor.markdown_cache_dir.is_dir()
        assert processor.markdown_cache_dir.name == "markdown"
    
    def test_markdown_conversion_basic(self, processor: PDFProcessor) -> None:
        """Test basic markdown conversion functionality exists."""
        # Verify essential methods exist
        assert hasattr(processor, 'convert_pdf_to_markdown')
        assert hasattr(processor, '_convert_pdf_to_markdown_pymupdf')
        assert hasattr(processor, 'extract_pdf_metadata')
        assert callable(processor.convert_pdf_to_markdown)
        
        # Verify new caching methods exist
        assert hasattr(processor, '_get_conversion_cache_key')
        assert hasattr(processor, '_get_cached_markdown')
        assert hasattr(processor, '_cache_markdown')
        assert callable(processor._get_conversion_cache_key)
        assert callable(processor._get_cached_markdown)
        assert callable(processor._cache_markdown)


class TestURLCrawler:
    """Test URL crawling functionality"""
    
    @pytest.fixture
    def crawler(self):
        """Create a URL crawler instance for testing"""
        return URLCrawler()
    
    def test_crawler_initialization(self, crawler: URLCrawler) -> None:
        """Test that URL crawler initializes correctly."""
        assert crawler is not None
        # Verify essential methods exist
        assert hasattr(crawler, 'find_pdf_links')
        assert hasattr(crawler, '_extract_topic_keywords')
        assert hasattr(crawler, '_prioritize_pdf_links')
    
    def test_keyword_extraction(self, crawler: URLCrawler) -> None:
        """Test keyword extraction from content."""
        test_content = "NeRF Neural Radiance Fields for View Synthesis using deep learning"
        test_url = "https://example.com/nerf"
        
        keywords = crawler._extract_topic_keywords(test_content.lower(), test_url)
        
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        # Should extract relevant keywords
        expected_keywords = ['nerf', 'neural', 'radiance', 'fields']
        found_keywords = [kw for kw in expected_keywords if kw in keywords]
        assert len(found_keywords) > 0, f"Expected keywords {expected_keywords} not found in {keywords}"
    
    def test_link_prioritization(self, crawler: URLCrawler) -> None:
        """Test PDF link prioritization logic."""
        source_url = "https://example.com/research"
        page_content = "neural networks deep learning research"
        
        # Mock PDF links with different characteristics
        pdf_links: Dict[str, tuple[str, str]] = {
            "https://arxiv.org/pdf/2020.12345.pdf": ("paper", "main research paper on neural networks"),
            "https://example.com/slides.pdf": ("slides", "presentation slides"),
            "https://ieee.org/paper.pdf": ("publication", "ieee conference paper"),
            "https://github.com/repo/doc.pdf": ("documentation", "code documentation")
        }
        
        prioritized = crawler._prioritize_pdf_links(source_url, pdf_links, page_content)
        
        assert isinstance(prioritized, list)
        assert len(prioritized) == len(pdf_links)
        
        # ArXiv papers should generally be prioritized highly
        top_link = prioritized[0]
        assert "arxiv.org" in top_link or "ieee.org" in top_link, f"Top link should be academic: {top_link}"
    
    def test_unrelated_paper_detection(self, crawler: URLCrawler) -> None:
        """Test detection of unrelated papers (regression test for bug fix)."""
        # This tests the bug fix for returning wrong papers
        robotics_content = "robot self-modeling lipson manipulation"
        nature_url = "https://www.nature.com/articles/s42256-025-01006-w"
        
        # Wrong paper (OpenAI Dota from 2019)
        wrong_pdf = "https://arxiv.org/pdf/1912.06680.pdf"
        
        # Should detect this as unrelated
        is_unrelated = crawler._is_likely_unrelated_paper(wrong_pdf, robotics_content, nature_url)
        assert is_unrelated is True, "Should detect 2019 Dota paper as unrelated to robotics"
        
        # Correct paper should not be flagged
        correct_pdf = "https://arxiv.org/pdf/2311.12151.pdf"
        is_unrelated = crawler._is_likely_unrelated_paper(correct_pdf, robotics_content, nature_url)
        assert is_unrelated is False, "Should not flag robotics-related paper as unrelated"


@pytest.mark.asyncio
async def test_integration() -> None:
    """Integration test for the full pipeline."""
    processor = PDFProcessor()
    crawler = URLCrawler()
    
    # Test that components work together
    assert processor is not None
    assert crawler is not None
    
    # Test keyword extraction with real content
    content = "machine learning artificial intelligence deep neural networks"
    url = "https://example.com/ai"
    keywords = crawler._extract_topic_keywords(content, url)
    
    assert len(keywords) > 0
    expected_keywords = {'machine', 'learning', 'neural', 'intelligence', 'artificial'}
    found_keywords = set(keywords) & expected_keywords
    assert len(found_keywords) > 0, f"Expected at least one keyword from {expected_keywords} in {keywords}"


class TestVariableScopingFix:
    """Test the variable scoping fix for MCP tool functions"""
    
    @pytest.mark.asyncio
    async def test_convert_pdf_url_enhanced_no_scoping_error(self) -> None:
        """Test that convert_pdf_url_enhanced doesn't have variable scoping issues (regression test)."""
        # Mock arguments that would trigger the scoping bug
        mock_arguments: Dict[str, Any] = {
            "url": "https://arxiv.org/pdf/invalid.pdf",  # Invalid URL to fail quickly
            "fallback_to_pymupdf": True
        }
        
        # This should not raise "local variable 'pdf_processor' referenced before assignment"
        try:
            result = await call_tool("convert_pdf_url_enhanced", mock_arguments)
            # We expect this to fail due to invalid URL, but NOT due to variable scoping
            result_text = result[0].text if result else ""
            assert "Failed to download PDF" in result_text or "marker-pdf" in result_text
        except NameError as e:
            if "pdf_processor" in str(e):
                pytest.fail(f"Variable scoping bug still exists in convert_pdf_url_enhanced: {e}")
            else:
                # Other NameErrors are acceptable (e.g., missing dependencies)
                pass
        except Exception as e:
            # Other exceptions are acceptable as long as they're not scoping issues
            assert "pdf_processor" not in str(e), f"Unexpected scoping error: {e}"
    
    @pytest.mark.asyncio 
    async def test_convert_pdf_url_with_method_no_scoping_error(self) -> None:
        """Test that convert_pdf_url_with_method doesn't have variable scoping issues (regression test)."""
        # Mock arguments that would trigger the scoping bug
        mock_arguments: Dict[str, Any] = {
            "url": "https://arxiv.org/pdf/invalid.pdf",  # Invalid URL to fail quickly
            "method": "auto"
        }
        
        # This should not raise "local variable 'pdf_processor' referenced before assignment"
        try:
            result = await call_tool("convert_pdf_url_with_method", mock_arguments)
            # We expect this to fail due to invalid URL, but NOT due to variable scoping
            result_text = result[0].text if result else ""
            expected_phrases = ["Failed to download PDF", "Method Used", "Converted from"]
            assert any(phrase in result_text for phrase in expected_phrases)
        except NameError as e:
            if "pdf_processor" in str(e):
                pytest.fail(f"Variable scoping bug still exists in convert_pdf_url_with_method: {e}")
            else:
                # Other NameErrors are acceptable (e.g., missing dependencies)
                pass
        except Exception as e:
            # Other exceptions are acceptable as long as they're not scoping issues
            assert "pdf_processor" not in str(e), f"Unexpected scoping error: {e}"


if __name__ == "__main__":
    # Run tests directly if called as script
    pytest.main([__file__, "-v"])