#!/usr/bin/env python3
"""
Test script for MCP PDF Server
"""

import asyncio
import json
from pathlib import Path
from mcp_pdf_server import PDFProcessor, URLCrawler

async def test_pdf_processor():
    """Test PDF processing functionality"""
    processor = PDFProcessor()
    
    # Test with existing PDF
    pdf_path = Path("data/MPC-Based_Walking.pdf")
    if pdf_path.exists():
        print("Testing PDF conversion...")
        markdown = processor.convert_pdf_to_markdown(pdf_path)
        
        # Save result for inspection
        output_path = Path("test_output.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        print(f"✅ PDF converted successfully!")
        print(f"📄 Output saved to: {output_path}")
        print(f"📊 Content length: {len(markdown)} characters")
        
        # Show first few lines
        lines = markdown.split('\n')
        print("\n📖 First 10 lines of output:")
        for i, line in enumerate(lines[:10], 1):
            print(f"{i:2d}: {line}")
        
        return True
    else:
        print(f"❌ Test PDF not found: {pdf_path}")
        return False

async def test_url_crawler():
    """Test URL crawling functionality"""
    crawler = URLCrawler()
    
    # Test with a known academic site (adjust URL as needed)
    test_url = "https://arxiv.org"  # Example - may not have PDFs on main page
    
    print(f"Testing URL crawler with: {test_url}")
    try:
        pdf_links = await crawler.find_pdf_links(test_url, max_depth=1)
        print(f"✅ Found {len(pdf_links)} PDF links")
        
        for i, link in enumerate(pdf_links[:5], 1):  # Show first 5
            print(f"{i}. {link}")
        
        return len(pdf_links) > 0
    except Exception as e:
        print(f"❌ URL crawling failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Testing MCP PDF Server Components\n")
    
    # Test PDF processing
    pdf_test = await test_pdf_processor()
    print()
    
    # Test URL crawling
    url_test = await test_url_crawler()
    print()
    
    # Summary
    print("📋 Test Summary:")
    print(f"  PDF Processing: {'✅ PASS' if pdf_test else '❌ FAIL'}")
    print(f"  URL Crawling:   {'✅ PASS' if url_test else '❌ FAIL'}")
    
    if pdf_test or url_test:
        print("\n🎉 MCP PDF Server is ready for use!")
        print("📚 See README_MCP.md for usage instructions")
    else:
        print("\n⚠️ Some tests failed. Check dependencies and test data.")

if __name__ == "__main__":
    asyncio.run(main())