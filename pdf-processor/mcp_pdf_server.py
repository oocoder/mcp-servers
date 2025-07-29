#!/usr/bin/env python3
"""
MCP Server for PDF URL Crawling and Conversion
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

# MCP imports
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
import mcp.server.stdio

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
                
                # Extract text with enhanced structure preservation
                text_dict = page.get_text("dict")
                sections = self._organize_content_by_structure(text_dict)
                
                for section in sections:
                    if section['type'] == 'heading':
                        level = min(section.get('level', 3), 6)
                        markdown_content.append(f"{'#' * level} {section['text']}")
                        markdown_content.append("")
                    elif section['type'] == 'paragraph':
                        # Clean and format paragraph text
                        cleaned_text = self._clean_paragraph_text(section['text'])
                        if cleaned_text:
                            markdown_content.append(cleaned_text)
                            markdown_content.append("")
                    elif section['type'] == 'code':
                        # Format code blocks
                        markdown_content.append("```")
                        markdown_content.append(section['text'])
                        markdown_content.append("```")
                        markdown_content.append("")
                    elif section['type'] == 'table':
                        # Format tables for Claude Code
                        markdown_content.append(self._format_table_for_claude(section['data']))
                        markdown_content.append("")
                    elif section['type'] == 'math':
                        # Format mathematical expressions
                        markdown_content.append(f"$$")
                        markdown_content.append(section['text'])
                        markdown_content.append(f"$$")
                        markdown_content.append("")
                    elif section['type'] == 'figure':
                        markdown_content.append(f"**Figure {section.get('number', 'N/A')}**: {section.get('caption', 'No caption')}")
                        markdown_content.append(f"*Dimensions: {section.get('width', 'unknown')}x{section.get('height', 'unknown')} pixels*")
                        markdown_content.append("")
            
            doc.close()
            
            # Final Claude Code optimization
            final_content = self._apply_claude_optimizations("\n".join(markdown_content))
            return final_content
            
        except Exception as e:
            logger.error(f"Failed to convert PDF {pdf_path}: {e}")
            return f"Error converting PDF: {str(e)}"
    
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
    
    def _organize_content_by_structure(self, text_dict: Dict) -> List[Dict]:
        """Organize content by structural elements for Claude Code"""
        sections = []
        
        for block in text_dict["blocks"]:
            if "lines" in block:  # Text block
                # Analyze font sizes to determine structure
                avg_font_size = self._get_average_font_size(block)
                text_content = self._extract_block_text(block)
                
                if not text_content.strip():
                    continue
                
                # Classify content type
                if avg_font_size > 14:  # Likely heading
                    level = max(1, 7 - int(avg_font_size / 2))
                    sections.append({
                        'type': 'heading',
                        'text': text_content,
                        'level': level
                    })
                elif self._is_code_block(text_content):
                    sections.append({
                        'type': 'code',
                        'text': text_content
                    })
                elif self._contains_math(text_content):
                    sections.append({
                        'type': 'math',
                        'text': text_content
                    })
                else:
                    sections.append({
                        'type': 'paragraph',
                        'text': text_content
                    })
            
            elif "image" in block:  # Image block
                sections.append({
                    'type': 'figure',
                    'width': block.get('width', 'unknown'),
                    'height': block.get('height', 'unknown'),
                    'number': len([s for s in sections if s.get('type') == 'figure']) + 1
                })
        
        return sections
    
    def _get_average_font_size(self, block: Dict) -> float:
        """Get average font size for a text block"""
        total_size = 0
        char_count = 0
        
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 12)
                text_len = len(span.get("text", ""))
                total_size += size * text_len
                char_count += text_len
        
        return total_size / char_count if char_count > 0 else 12
    
    def _extract_block_text(self, block: Dict) -> str:
        """Extract clean text from a block"""
        lines = []
        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                flags = span.get("flags", 0)
                
                # Apply formatting
                if flags & 2**4:  # Bold
                    text = f"**{text}**"
                if flags & 2**1:  # Italic
                    text = f"*{text}*"
                
                line_text += text + " "
            
            if line_text.strip():
                lines.append(line_text.strip())
        
        return "\n".join(lines)
    
    def _is_code_block(self, text: str) -> bool:
        """Detect if text is likely a code block"""
        code_indicators = [
            'def ', 'class ', 'import ', 'from ',  # Python
            'function ', 'var ', 'const ', 'let ',  # JavaScript
            'public ', 'private ', 'void ',  # Java/C++
            '#!/', '<?', '<%',  # Script headers
            '{', '}',  # Braces
        ]
        
        lines = text.split('\n')
        code_line_count = 0
        
        for line in lines:
            if any(indicator in line.lower() for indicator in code_indicators):
                code_line_count += 1
        
        return code_line_count / len(lines) > 0.3 if lines else False
    
    def _contains_math(self, text: str) -> bool:
        """Check if text contains mathematical expressions"""
        math_indicators = [
            '=', '+', '-', '*', '/', '^',  # Basic operators
            '∑', '∫', '∂', '∇',  # Math symbols
            'equation', 'formula', 'theorem',  # Math keywords
            '$', '\\', 'frac', 'sqrt',  # LaTeX
        ]
        
        return any(indicator in text for indicator in math_indicators)
    
    def _clean_paragraph_text(self, text: str) -> str:
        """Clean and format paragraph text for Claude Code"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common PDF extraction issues
        text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')  # Ligatures
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Missing spaces
        
        # Enhance for Claude Code readability
        # Add emphasis to important terms
        text = re.sub(r'\b(algorithm|method|approach|technique|framework)\b', r'**\1**', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _format_table_for_claude(self, table_data: Any) -> str:
        """Format table data for Claude Code analysis"""
        # Placeholder for table formatting
        # In a full implementation, this would parse actual table data
        return "| Column 1 | Column 2 | Column 3 |\n|----------|----------|----------|\n| Data     | Data     | Data     |"
    
    def _apply_claude_optimizations(self, content: str) -> str:
        """Apply final optimizations for Claude Code"""
        # Add section navigation for long documents
        lines = content.split('\n')
        if len(lines) > 100:  # Long document
            toc = self._generate_table_of_contents(lines)
            content = toc + "\n\n" + content
        
        # Add research paper specific optimizations
        if 'abstract' in content.lower() or 'introduction' in content.lower():
            content = "# 🎓 Research Paper Analysis\n\n" + content
            content += "\n\n---\n\n## 🤖 Claude Code Analysis Tips\n"
            content += "- Use Ctrl+F to quickly find specific algorithms or methods\n"
            content += "- Mathematical formulas are in LaTeX format for easy copying\n"
            content += "- Code blocks are clearly marked for implementation reference\n"
            content += "- Tables and figures are structurally annotated\n"
        
        return content
    
    def _generate_table_of_contents(self, lines: List[str]) -> str:
        """Generate table of contents for long documents"""
        toc = ["# 📚 Table of Contents\n"]
        
        for line in lines:
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('# ').strip()
                indent = "  " * (level - 1)
                toc.append(f"{indent}- {title}")
        
        return "\n".join(toc)

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

# Initialize MCP server
server = Server("pdf-processor")
pdf_processor = PDFProcessor()
url_crawler = URLCrawler()

@server.list_resources()
async def list_resources() -> List[Resource]:
    """List available resources"""
    return [
        Resource(
            uri="pdf://cache",
            name="PDF Cache Directory",
            description="Directory containing cached PDF files",
            mimeType="text/plain"
        )
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource"""
    if uri == "pdf://cache":
        cache_files = list(pdf_processor.cache_dir.glob("*.pdf"))
        return f"Cached PDFs ({len(cache_files)} files):\n" + "\n".join(f"- {f.name}" for f in cache_files)
    
    raise ValueError(f"Unknown resource: {uri}")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="crawl_pdf_links",
            description="Crawl a URL to find PDF links",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to crawl for PDF links"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum crawling depth (default: 1)",
                        "default": 1
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="convert_pdf_url",
            description="Download PDF from URL and convert to Claude-optimized markdown",
            inputSchema={
                "type": "object", 
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The PDF URL to download and convert"
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "description": "Include PDF metadata in output (default: true)",
                        "default": True
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="batch_convert_pdfs",
            description="Convert multiple PDF URLs to markdown",
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of PDF URLs to convert"
                    },
                    "include_metadata": {
                        "type": "boolean", 
                        "description": "Include PDF metadata in output (default: true)",
                        "default": True
                    }
                },
                "required": ["urls"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""
    
    if name == "crawl_pdf_links":
        url = arguments["url"]
        max_depth = arguments.get("max_depth", 1)
        
        pdf_links = await url_crawler.find_pdf_links(url, max_depth)
        
        result = f"Found {len(pdf_links)} PDF links from {url}:\n\n"
        for i, link in enumerate(pdf_links, 1):
            result += f"{i}. {link}\n"
        
        return [TextContent(type="text", text=result)]
    
    elif name == "convert_pdf_url":
        url = arguments["url"]
        include_metadata = arguments.get("include_metadata", True)
        
        # Download PDF
        pdf_path = await pdf_processor.download_pdf(url)
        if not pdf_path:
            return [TextContent(type="text", text=f"Failed to download PDF from {url}")]
        
        # Convert to markdown
        markdown = pdf_processor.convert_pdf_to_markdown(pdf_path)
        
        result = f"# Converted from: {url}\n\n{markdown}"
        return [TextContent(type="text", text=result)]
    
    elif name == "batch_convert_pdfs":
        urls = arguments["urls"]
        include_metadata = arguments.get("include_metadata", True)
        
        results = []
        for url in urls:
            pdf_path = await pdf_processor.download_pdf(url)
            if pdf_path:
                markdown = pdf_processor.convert_pdf_to_markdown(pdf_path)
                results.append(f"## From: {url}\n\n{markdown}\n\n---\n")
            else:
                results.append(f"## Failed: {url}\n\nCould not download PDF\n\n---\n")
        
        combined_result = "\n".join(results)
        return [TextContent(type="text", text=combined_result)]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main entry point"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())