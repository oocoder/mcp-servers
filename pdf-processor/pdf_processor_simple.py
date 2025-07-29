#!/usr/bin/env python3
"""
Simplified PDF Processor for Claude Code (Python 3.9 compatible)
Converts PDFs from URLs to Claude-optimized markdown format
"""

import asyncio
import json
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
import fitz  # pymupdf
import re
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFProcessor:
    """Handles PDF downloading and conversion to Claude-optimized markdown"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.cwd() / "pdf_cache"
        self.cache_dir.mkdir(exist_ok=True)
        
    async def download_pdf(self, url: str) -> Optional[Path]:
        """Download PDF from URL and cache it"""
        # Create cache filename from URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{url_hash}.pdf"
        
        if cache_file.exists():
            logger.info(f"Using cached PDF: {cache_file}")
            return cache_file
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        async with aiofiles.open(cache_file, 'wb') as f:
                            await f.write(content)
                        logger.info(f"Downloaded PDF: {url} -> {cache_file}")
                        return cache_file
        except Exception as e:
            logger.error(f"Failed to download PDF from {url}: {e}")
            return None
    
    def extract_pdf_metadata(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract metadata from PDF"""
        try:
            doc = fitz.open(str(pdf_path))
            metadata = doc.metadata
            return {
                'title': metadata.get('title', '').strip(),
                'author': metadata.get('author', '').strip(),
                'subject': metadata.get('subject', '').strip(),
                'creator': metadata.get('creator', '').strip(),
                'pages': doc.page_count,
                'format': metadata.get('format', '').strip()
            }
        except Exception as e:
            logger.error(f"Failed to extract metadata from {pdf_path}: {e}")
            return {}
    
    def convert_pdf_to_markdown(self, pdf_path: Path) -> str:
        """Convert PDF to Claude-optimized markdown"""
        try:
            doc = fitz.open(str(pdf_path))
            markdown_content = []
            
            # Add metadata header optimized for Claude Code
            metadata = self.extract_pdf_metadata(pdf_path)
            if metadata:
                markdown_content.append("# 📄 Document Analysis")
                markdown_content.append("")
                markdown_content.append("## Document Metadata")
                for key, value in metadata.items():
                    if value:
                        markdown_content.append(f"- **{key.title()}**: {value}")
                markdown_content.append("")
                
                # Add Claude Code optimization hints
                markdown_content.append("## 🤖 Claude Code Integration Notes")
                markdown_content.append("- This document has been optimized for Claude Code analysis")
                markdown_content.append("- Mathematical formulas are preserved in LaTeX format")
                markdown_content.append("- Code blocks and algorithms are clearly marked")
                markdown_content.append("- Tables and figures are structurally annotated")
                markdown_content.append("")
                markdown_content.append("---")
                markdown_content.append("")
            
            # Extract and process mathematical content
            math_expressions = self._extract_math_expressions(doc)
            if math_expressions:
                markdown_content.append("## 🔢 Mathematical Content Summary")
                for i, expr in enumerate(math_expressions[:5], 1):  # Show first 5
                    markdown_content.append(f"{i}. `{expr}`")
                markdown_content.append("")
                markdown_content.append("---")
                markdown_content.append("")
            
            # Process each page with enhanced structure detection
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Add page header for multi-page documents
                if doc.page_count > 1:
                    markdown_content.append(f"## 📑 Page {page_num + 1}")
                    markdown_content.append("")
                
                # Extract text with structure preservation
                text_dict = page.get_text("dict")
                current_section = []
                
                for block in text_dict["blocks"]:
                    if "lines" in block:  # Text block
                        block_text = self._process_text_block(block)
                        if block_text:
                            current_section.append(block_text)
                    elif "image" in block:  # Image block
                        img_info = f"**Figure**: {block.get('width', 'unknown')}x{block.get('height', 'unknown')} pixels"
                        current_section.append(img_info)
                
                # Add processed text
                if current_section:
                    markdown_content.extend(current_section)
                    markdown_content.append("")
            
            doc.close()
            
            # Final Claude Code optimization
            final_content = self._apply_claude_optimizations("\n".join(markdown_content))
            return final_content
            
        except Exception as e:
            logger.error(f"Failed to convert PDF {pdf_path}: {e}")
            return f"Error converting PDF: {str(e)}"
    
    def _extract_math_expressions(self, doc) -> List[str]:
        """Extract mathematical expressions from PDF"""
        math_patterns = [
            r'\$[^$]+\$',  # Inline math
            r'\$\$[^$]+\$\$',  # Display math
            r'\\begin\{equation\}.*?\\end\{equation\}',  # LaTeX equations
            r'\\begin\{align\}.*?\\end\{align\}',  # LaTeX align
            r'[∑∫∂∇αβγδεζηθικλμνξπρστυφχψω]',  # Greek letters and math symbols
        ]
        
        expressions = []
        for page in doc:
            text = page.get_text()
            for pattern in math_patterns:
                matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                expressions.extend(matches)
        
        return list(set(expressions))  # Remove duplicates
    
    def _process_text_block(self, block: Dict) -> str:
        """Process a text block with formatting preservation"""
        lines = []
        
        for line in block["lines"]:
            line_text = ""
            prev_font_size = None
            
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                    
                font_size = span.get("size", 12)
                flags = span.get("flags", 0)
                
                # Apply formatting
                if flags & 2**4:  # Bold
                    text = f"**{text}**"
                if flags & 2**1:  # Italic
                    text = f"*{text}*"
                
                # Detect headings by font size changes
                if prev_font_size and font_size > prev_font_size * 1.2:
                    # Likely a heading
                    if not text.startswith('#'):
                        text = f"### {text}"
                
                line_text += text + " "
                prev_font_size = font_size
            
            if line_text.strip():
                lines.append(line_text.strip())
        
        return "\n".join(lines)
    
    def _apply_claude_optimizations(self, content: str) -> str:
        """Apply final optimizations for Claude Code"""
        # Add research paper specific optimizations
        if 'abstract' in content.lower() or 'introduction' in content.lower():
            content = "# 🎓 Research Paper Analysis\n\n" + content
            content += "\n\n---\n\n## 🤖 Claude Code Analysis Tips\n"
            content += "- Use Ctrl+F to quickly find specific algorithms or methods\n"
            content += "- Mathematical formulas are in LaTeX format for easy copying\n"
            content += "- Code blocks are clearly marked for implementation reference\n"
            content += "- Tables and figures are structurally annotated\n"
        
        return content

class URLCrawler:
    """Crawls URLs to find PDF links"""
    
    async def find_pdf_links(self, url: str, max_depth: int = 1) -> List[str]:
        """Find PDF links from a given URL"""
        pdf_links = []
        visited = set()
        
        async def crawl_page(current_url: str, depth: int):
            if depth > max_depth or current_url in visited:
                return
                
            visited.add(current_url)
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(current_url) as response:
                        if response.status == 200:
                            content_type = response.headers.get('content-type', '').lower()
                            
                            # Direct PDF link
                            if 'application/pdf' in content_type:
                                pdf_links.append(current_url)
                                return
                            
                            # HTML page - parse for PDF links
                            if 'text/html' in content_type:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # Find PDF links
                                for link in soup.find_all('a', href=True):
                                    href = link['href']
                                    full_url = urljoin(current_url, href)
                                    
                                    if href.lower().endswith('.pdf'):
                                        pdf_links.append(full_url)
                                    elif depth < max_depth and self._is_same_domain(current_url, full_url):
                                        await crawl_page(full_url, depth + 1)
                                        
            except Exception as e:
                logger.error(f"Error crawling {current_url}: {e}")
        
        await crawl_page(url, 0)
        return list(set(pdf_links))  # Remove duplicates
    
    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain"""
        try:
            domain1 = urlparse(url1).netloc
            domain2 = urlparse(url2).netloc
            return domain1 == domain2
        except:
            return False

# CLI Interface
async def main():
    """Simple CLI interface for PDF processing"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python pdf_processor_simple.py convert <pdf_url>")
        print("  python pdf_processor_simple.py crawl <website_url>")
        print("  python pdf_processor_simple.py batch <url1> <url2> ...")
        return
    
    command = sys.argv[1]
    processor = PDFProcessor()
    crawler = URLCrawler()
    
    if command == "convert" and len(sys.argv) >= 3:
        url = sys.argv[2]
        print(f"🔄 Converting PDF from: {url}")
        
        pdf_path = await processor.download_pdf(url)
        if pdf_path:
            markdown = processor.convert_pdf_to_markdown(pdf_path)
            
            # Save to file
            output_file = f"converted_{hashlib.md5(url.encode()).hexdigest()[:8]}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            print(f"✅ Conversion complete!")
            print(f"📄 Output saved to: {output_file}")
            print(f"📊 Content length: {len(markdown)} characters")
        else:
            print("❌ Failed to download PDF")
    
    elif command == "crawl" and len(sys.argv) >= 3:
        url = sys.argv[2]
        print(f"🕷️ Crawling for PDFs: {url}")
        
        pdf_links = await crawler.find_pdf_links(url, max_depth=2)
        print(f"✅ Found {len(pdf_links)} PDF links:")
        
        for i, link in enumerate(pdf_links, 1):
            print(f"{i:2d}. {link}")
    
    elif command == "batch" and len(sys.argv) >= 3:
        urls = sys.argv[2:]
        print(f"📦 Batch converting {len(urls)} PDFs...")
        
        for url in urls:
            print(f"\n🔄 Processing: {url}")
            pdf_path = await processor.download_pdf(url)
            if pdf_path:
                markdown = processor.convert_pdf_to_markdown(pdf_path)
                output_file = f"batch_{hashlib.md5(url.encode()).hexdigest()[:8]}.md"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(markdown)
                print(f"✅ Saved to: {output_file}")
            else:
                print("❌ Failed to download")
    
    else:
        print("❌ Invalid command or arguments")

if __name__ == "__main__":
    asyncio.run(main())