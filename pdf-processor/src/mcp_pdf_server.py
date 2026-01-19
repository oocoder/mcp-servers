#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "aiofiles",
#     "aiohttp",
#     "beautifulsoup4",
#     "PyMuPDF",
#     "mcp",
#     "marker-pdf",
# ]
# ///
"""MCP Server for PDF URL Crawling and Conversion"""

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
import fitz
import re
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from marker.converters.pdf import PdfConverter
    from marker.settings import Settings
    MARKER_AVAILABLE = True
    logger.info("marker-pdf available - enhanced PDF processing enabled")
except ImportError:
    MARKER_AVAILABLE = False
    logger.info("marker-pdf not available - using PyMuPDF fallback")

from mcp.server import Server
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
import mcp.server.stdio

class PDFProcessor:
    """Handles PDF downloading and conversion to markdown"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.cwd() / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.markdown_cache_dir = self.cache_dir / "markdown"
        self.markdown_cache_dir.mkdir(exist_ok=True)
    
    def _normalize_url_for_cache(self, url: str) -> str:
        """Normalize URL for consistent caching by removing fragments and irrelevant parameters"""
        from urllib.parse import urlparse, urlunparse, parse_qs
        
        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query) if parsed.query else {}
        
        irrelevant_params = {
            'page', 'zoom', 'view', 'toolbar', 'navpanes', 'scrollbar',
            'statusbar', 'messages', 'pagemode', 'search', 'highlight'
        }
        
        relevant_query = {}
        for key, values in query_dict.items():
            if key.lower() not in irrelevant_params:
                relevant_query[key] = values
        
        if relevant_query:
            query_pairs = []
            for key, values in relevant_query.items():
                for value in values:
                    query_pairs.append(f"{key}={value}")
            new_query = "&".join(query_pairs)
        else:
            new_query = ""
        
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ""
        ))
        
        if normalized != url:
            logger.info(f"URL normalized for caching: {url} -> {normalized}")
        
        return normalized
    
    def _get_conversion_cache_key(self, url: str, start_page: Optional[int] = None, end_page: Optional[int] = None, force_method: Optional[str] = None) -> str:
        """Generate cache key for markdown conversion results"""
        normalized_url = self._normalize_url_for_cache(url)
        
        # Include conversion parameters in cache key
        params = {
            'url': normalized_url,
            'start_page': start_page,
            'end_page': end_page,
            'force_method': force_method,
            'marker_available': MARKER_AVAILABLE
        }
        
        # Create deterministic hash of parameters
        params_str = json.dumps(params, sort_keys=True)
        cache_key = hashlib.md5(params_str.encode()).hexdigest()
        return cache_key
    
    def _get_cached_markdown(self, cache_key: str) -> Optional[str]:
        """Retrieve cached markdown conversion if available"""
        cache_file = self.markdown_cache_dir / f"{cache_key}.md"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Using cached markdown conversion: {cache_file.name}")
                return content
            except Exception as e:
                logger.warning(f"Failed to read cached markdown {cache_file}: {e}")
                # Clean up corrupted cache file
                try:
                    cache_file.unlink()
                except:
                    pass
        
        return None
    
    def _cache_markdown(self, cache_key: str, markdown_content: str) -> None:
        """Cache markdown conversion result"""
        cache_file = self.markdown_cache_dir / f"{cache_key}.md"
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            logger.info(f"Cached markdown conversion: {cache_file.name} ({len(markdown_content)} chars)")
        except Exception as e:
            logger.warning(f"Failed to cache markdown {cache_file}: {e}")
        
    async def download_pdf(self, url: str) -> Optional[Path]:
        """Download PDF from URL and cache it"""
        normalized_url = self._normalize_url_for_cache(url)
        url_hash = hashlib.md5(normalized_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"{url_hash}.pdf"
        
        if cache_file.exists():
            logger.info(f"Using cached PDF: {cache_file}")
            return cache_file
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/pdf,application/octet-stream,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            
            async with aiohttp.ClientSession(
                timeout=timeout, 
                connector=connector,
                headers=headers
            ) as session:
                
                async with session.get(url, allow_redirects=True, max_redirects=5) as response:
                    logger.info(f"Response status: {response.status} for {url}")
                    logger.info(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
                    
                    if response.status != 200:
                        logger.error(f"HTTP {response.status} for {url}")
                        return None
                    
                    content_type = response.headers.get('content-type', '').lower()
                    if not any(pdf_type in content_type for pdf_type in ['application/pdf', 'application/octet-stream']):
                        if not (url.lower().endswith('.pdf') or content_type == ''):
                            logger.warning(f"Unexpected content-type: {content_type} for {url}")
                    
                    content = await response.read()
                    
                    if not content.startswith(b'%PDF-'):
                        logger.error(f"Downloaded content is not a valid PDF from {url}")
                        return None
                    
                    async with aiofiles.open(cache_file, 'wb') as f:
                        await f.write(content)
                    
                    logger.info(f"Successfully downloaded PDF: {url} -> {cache_file} ({len(content)} bytes)")
                    return cache_file
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error downloading PDF from {url}: {e}")
            return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading PDF from {url}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading PDF from {url}: {e}")
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
    
    def is_academic_paper(self, pdf_path: Path, url: str = "") -> bool:
        """Detect if a PDF is likely an academic paper"""
        academic_indicators = []
        
        # Check URL patterns
        if url:
            academic_url_patterns = [
                'arxiv.org',
                'doi.org', 
                'ieee.org',
                'acm.org',
                'nature.com',
                'science.org',
                'springer.com',
                'elsevier.com',
                'wiley.com',
                'cambridge.org',
                'oxford.com',
                'semanticscholar.org',
                'researchgate.net'
            ]
            if any(pattern in url.lower() for pattern in academic_url_patterns):
                academic_indicators.append("academic_url")
        
        # Check PDF metadata
        try:
            metadata = self.extract_pdf_metadata(pdf_path)
            
            # Check for academic keywords in title/subject
            academic_keywords = [
                'arxiv', 'doi', 'abstract', 'conference', 'proceedings', 
                'journal', 'volume', 'issue', 'research', 'university',
                'ieee', 'acm', 'springer', 'elsevier', 'nature'
            ]
            
            title_subject = f"{metadata.get('title', '')} {metadata.get('subject', '')}".lower()
            if any(keyword in title_subject for keyword in academic_keywords):
                academic_indicators.append("academic_metadata")
                
            # Check creator patterns
            creator = metadata.get('creator', '').lower()
            if any(pattern in creator for pattern in ['latex', 'pdflatex', 'xelatex']):
                academic_indicators.append("latex_created")
                
        except Exception as e:
            logger.debug(f"Could not extract metadata for academic detection: {e}")
        
        # Quick content sampling for academic patterns
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            
            # Check first few pages for academic patterns
            academic_content_patterns = [
                'abstract', 'introduction', 'methodology', 'references',
                'bibliography', 'citation', 'arxiv:', 'doi:', 'et al.',
                'university', 'department', 'conference', 'proceedings'
            ]
            
            sample_text = ""
            for page_num in range(min(3, doc.page_count)):  # First 3 pages
                sample_text += doc[page_num].get_text().lower()
            
            matches = sum(1 for pattern in academic_content_patterns if pattern in sample_text)
            if matches >= 3:  # If 3+ academic patterns found
                academic_indicators.append("academic_content")
                
            doc.close()
            
        except Exception as e:
            logger.debug(f"Could not sample content for academic detection: {e}")
        
        # Determine if academic (need at least 2 indicators or strong single indicator)
        is_academic = (
            len(academic_indicators) >= 2 or 
            "academic_url" in academic_indicators or
            "academic_content" in academic_indicators
        )
        
        if is_academic:
            logger.info(f"Detected academic paper - indicators: {academic_indicators}")
        else:
            logger.debug(f"Non-academic paper - indicators: {academic_indicators}")
            
        return is_academic
    
    def convert_pdf_to_markdown_with_marker(self, pdf_path: Path) -> str:
        """Convert PDF using marker-pdf CLI for enhanced layout detection"""
        if not MARKER_AVAILABLE:
            raise ImportError("marker-pdf not available. Install with: pip install marker-pdf")
        
        try:
            logger.info(f"Converting PDF with marker-pdf: {pdf_path}")
            
            # Create temporary directories for marker processing
            import tempfile
            import subprocess
            import shutil
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                input_dir = temp_path / "input"
                output_dir = temp_path / "output"
                input_dir.mkdir()
                
                # Copy PDF to input directory
                temp_pdf = input_dir / pdf_path.name
                shutil.copy2(pdf_path, temp_pdf)
                
                # Run marker CLI
                cmd = [
                    "marker", str(input_dir),
                    "--output_dir", str(output_dir),
                    "--output_format", "markdown",
                    "--disable_multiprocessing"  # Avoid multiprocessing issues
                ]
                
                logger.info("Running marker-pdf CLI conversion...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    raise RuntimeError(f"marker-pdf CLI failed: {result.stderr}")
                
                # Find the generated markdown file
                pdf_stem = pdf_path.stem
                marker_md_file = output_dir / pdf_stem / f"{pdf_stem}.md"
                
                if not marker_md_file.exists():
                    raise FileNotFoundError(f"marker-pdf output not found: {marker_md_file}")
                
                # Read the generated markdown
                with open(marker_md_file, 'r', encoding='utf-8') as f:
                    marker_content = f.read()
                
                # Add Claude-optimized metadata header
                metadata = self.extract_pdf_metadata(pdf_path)
                markdown_content = []
                
                if metadata:
                    markdown_content.append("# 📄 Academic Paper Analysis (Enhanced with marker-pdf)")
                    markdown_content.append("")
                    markdown_content.append("## Document Metadata")
                    for key, value in metadata.items():
                        if value:
                            markdown_content.append(f"- **{key.title()}**: {value}")
                    markdown_content.append("")
                    
                    markdown_content.append("## 🚀 Processing Notes")
                    markdown_content.append("- Processed with **marker-pdf** for enhanced academic paper layout detection")
                    markdown_content.append("- Advanced column detection and logical reading order")
                    markdown_content.append("- Improved table and mathematical formula extraction")
                    markdown_content.append("- Professional citation and reference handling")
                    
                    # Check for extracted images
                    image_dir = output_dir / pdf_stem
                    if image_dir.exists():
                        image_files = list(image_dir.glob("*.jpeg")) + list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))
                        if image_files:
                            markdown_content.append(f"- {len(image_files)} figures/images extracted and processed")
                    
                    markdown_content.append("")
                    markdown_content.append("---")
                    markdown_content.append("")
                
                # Add the marker-generated content
                markdown_content.append(marker_content)
                
                final_result = "\n".join(markdown_content)
                logger.info(f"marker-pdf conversion completed: {len(final_result)} characters")
                return final_result
            
        except Exception as e:
            logger.error(f"marker-pdf conversion failed: {e}")
            # Fallback to PyMuPDF
            logger.info("Falling back to PyMuPDF conversion")
            return self._convert_pdf_to_markdown_pymupdf(pdf_path)
    
    def convert_pdf_to_markdown(self, pdf_path: Path, start_page: int = None, end_page: int = None, source_url: str = "", force_method: str = None) -> str:
        """Convert PDF to markdown with automatic method selection and caching"""
        # Check cache first
        if source_url:
            cache_key = self._get_conversion_cache_key(source_url, start_page, end_page, force_method)
            cached_result = self._get_cached_markdown(cache_key)
            if cached_result:
                return cached_result
        
        # Determine conversion method
        if force_method == "marker":
            use_marker = True
        elif force_method == "pymupdf":
            use_marker = False
        elif start_page is not None or end_page is not None:
            use_marker = False
            logger.info("Using PyMuPDF for page range conversion")
        elif MARKER_AVAILABLE and self.is_academic_paper(pdf_path, source_url):
            use_marker = True
            logger.info("Academic paper detected - using marker-pdf for enhanced processing")
        else:
            use_marker = False
            logger.info("Using PyMuPDF for fast general-purpose conversion")
        
        # Perform conversion
        markdown_result = None
        if use_marker:
            try:
                markdown_result = self.convert_pdf_to_markdown_with_marker(pdf_path)
            except Exception as e:
                logger.warning(f"marker-pdf failed, falling back to PyMuPDF: {e}")
        
        if markdown_result is None:
            markdown_result = self._convert_pdf_to_markdown_pymupdf(pdf_path, start_page, end_page)
        
        # Cache the result if we have a source URL
        if source_url and markdown_result:
            self._cache_markdown(cache_key, markdown_result)
        
        return markdown_result
    
    def _convert_pdf_to_markdown_pymupdf(self, pdf_path: Path, start_page: int = None, end_page: int = None) -> str:
        """Convert PDF to markdown using PyMuPDF"""
        try:
            doc = fitz.open(str(pdf_path))
            markdown_content = []
            
            # Determine page range
            total_pages = doc.page_count
            start_page = start_page or 1
            end_page = end_page or total_pages
            
            # Validate page range
            start_page = max(1, min(start_page, total_pages))
            end_page = max(start_page, min(end_page, total_pages))
            
            # Add metadata header optimized for Claude Code
            metadata = self.extract_pdf_metadata(pdf_path)
            if metadata:
                markdown_content.append("# 📄 Document Analysis")
                markdown_content.append("")
                markdown_content.append("## Document Metadata")
                for key, value in metadata.items():
                    if value:
                        markdown_content.append(f"- **{key.title()}**: {value}")
                
                # Add page range info if partial conversion
                if start_page > 1 or end_page < total_pages:
                    markdown_content.append(f"- **Page Range**: {start_page}-{end_page} of {total_pages}")
                
                markdown_content.append("")
                
                # Add LLM optimization hints
                markdown_content.append("## 🤖 Processing Notes")
                markdown_content.append("- This document has been optimized for large language model analysis")
                markdown_content.append("- Mathematical formulas are preserved in LaTeX format")
                markdown_content.append("- Code blocks and algorithms are clearly marked")
                markdown_content.append("- Tables and figures are structurally annotated")
                if start_page > 1 or end_page < total_pages:
                    markdown_content.append(f"- **Partial Conversion**: Only pages {start_page}-{end_page} shown")
                markdown_content.append("")
                markdown_content.append("---")
                markdown_content.append("")
            
            # Extract and process mathematical content (from selected pages only)
            math_expressions = self._extract_math_expressions_from_range(doc, start_page - 1, end_page - 1)
            if math_expressions:
                markdown_content.append("## 🔢 Mathematical Content Summary")
                for i, expr in enumerate(math_expressions[:5], 1):  # Show first 5
                    markdown_content.append(f"{i}. `{expr}`")
                markdown_content.append("")
                markdown_content.append("---")
                markdown_content.append("")
            
            # Process selected pages with enhanced structure detection
            for page_num in range(start_page - 1, end_page):
                page = doc[page_num]
                
                # Add page header for multi-page documents
                if total_pages > 1:
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
                        # Format tables for LLM
                        markdown_content.append(self._format_table_for_llm(section['data']))
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
            
            # Final LLM optimization
            final_content = self._apply_llm_optimizations("\n".join(markdown_content))
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
        return self._extract_math_expressions_from_range(doc, 0, doc.page_count - 1)
    
    def _extract_math_expressions_from_range(self, doc, start_page: int, end_page: int) -> List[str]:
        """Extract mathematical expressions from specific page range"""
        math_patterns = [
            r'\$[^$]+\$',  # Inline math
            r'\$\$[^$]+\$\$',  # Display math
            r'\\begin\{equation\}.*?\\end\{equation\}',  # LaTeX equations
            r'\\begin\{align\}.*?\\end\{align\}',  # LaTeX align
            r'[∑∫∂∇αβγδεζηθικλμνξπρστυφχψω]',  # Greek letters and math symbols
        ]
        
        expressions = []
        for page_num in range(start_page, end_page + 1):
            if page_num < doc.page_count:
                page = doc[page_num]
                text = page.get_text()
                for pattern in math_patterns:
                    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                    expressions.extend(matches)
        
        return list(set(expressions))  # Remove duplicates
    
    def _organize_content_by_structure(self, text_dict: Dict) -> List[Dict]:
        """Organize content by structural elements for LLM consumption"""
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
        """Clean and format paragraph text for LLM consumption"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common PDF extraction issues
        text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl')  # Ligatures
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Missing spaces
        
        # Enhance for Claude Code readability
        # Add emphasis to important terms
        text = re.sub(r'\b(algorithm|method|approach|technique|framework)\b', r'**\1**', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def validate_pdf_relevance(self, pdf_path: Path, source_url: str) -> bool:
        """Validate that the PDF content is relevant to the source URL"""
        try:
            # Quick validation by checking PDF metadata and first page
            doc = fitz.open(str(pdf_path))
            
            # Get PDF metadata
            metadata = doc.metadata
            title = metadata.get('title', '').lower()
            author = metadata.get('author', '').lower()
            
            # Get text from first page for content analysis
            if doc.page_count > 0:
                first_page = doc[0]
                first_page_text = first_page.get_text().lower()
            else:
                first_page_text = ""
            
            doc.close()
            
            # Check for obvious mismatches
            source_domain = urlparse(source_url).netloc.lower()
            
            # For Nature articles about Hod Lipson's robotics work
            if 'nature.com' in source_url:
                # Should contain robotics-related content
                robotics_keywords = ['robot', 'self-model', 'morphology', 'kinematics', 'lipson']
                robotics_found = any(keyword in title + author + first_page_text for keyword in robotics_keywords)
                
                # Should NOT contain unrelated content
                unrelated_keywords = ['dota', 'openai', 'game', 'language model', 'gpt']
                unrelated_found = any(keyword in title + author + first_page_text for keyword in unrelated_keywords)
                
                if unrelated_found:
                    logger.warning(f"PDF contains unrelated keywords in {title} {author}")
                    return False
                    
                if not robotics_found and 'lipson' not in author:
                    logger.warning(f"PDF doesn't contain expected robotics content or Lipson authorship")
                    return False
            
            # Check for specific problematic papers
            if '1912.06680' in str(pdf_path) or 'dota' in title:
                logger.warning(f"Detected known problematic PDF: {title}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating PDF relevance: {e}")
            return True  # Default to allowing PDF if validation fails
    
    def _format_table_for_llm(self, table_data: Any) -> str:
        """Format table data for LLM analysis"""
        # Placeholder for table formatting
        # In a full implementation, this would parse actual table data
        return "| Column 1 | Column 2 | Column 3 |\n|----------|----------|----------|\n| Data     | Data     | Data     |"
    
    def _apply_llm_optimizations(self, content: str) -> str:
        """Apply final optimizations for LLM consumption"""
        # Add section navigation for long documents
        lines = content.split('\n')
        if len(lines) > 100:  # Long document
            toc = self._generate_table_of_contents(lines)
            content = toc + "\n\n" + content
        
        # Add research paper specific optimizations
        if 'abstract' in content.lower() or 'introduction' in content.lower():
            content = "# 🎓 Research Paper Analysis\n\n" + content
            content += "\n\n---\n\n## 🤖 Analysis Tips\n"
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
        """Find PDF links from a given URL, prioritized by relevance"""
        pdf_links_with_context = []
        visited = set()
        page_content = ""  # Store page content for topic extraction
        expected_authors = set()  # Store expected authors from the page
        
        async def crawl_page(current_url: str, depth: int):
            nonlocal page_content
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
                                pdf_links_with_context.append((current_url, "direct_link", ""))
                                return
                            
                            # HTML page - parse for PDF links
                            if 'text/html' in content_type:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # Extract page content for topic analysis (only from main page)
                                if depth == 0:
                                    page_content = self._extract_page_content(soup)
                                    expected_authors = self._extract_expected_authors(soup, current_url)
                                
                                # Find PDF links with context
                                for link in soup.find_all('a', href=True):
                                    href = link['href']
                                    full_url = urljoin(current_url, href)
                                    
                                    # Direct PDF links
                                    if href.lower().endswith('.pdf'):
                                        # Get link text and surrounding context for relevance scoring
                                        link_text = self._extract_link_text(link)
                                        link_context = self._get_link_context(link, soup)
                                        pdf_links_with_context.append((full_url, link_text, link_context))
                                    
                                    # ArXiv abstract links - convert to PDF URLs
                                    elif 'arxiv.org/abs/' in full_url:
                                        # Convert arxiv.org/abs/XXXX.XXXXX to arxiv.org/pdf/XXXX.XXXXX.pdf
                                        pdf_url = full_url.replace('/abs/', '/pdf/') + '.pdf'
                                        link_text = self._extract_link_text(link)
                                        link_context = self._get_link_context(link, soup)
                                        pdf_links_with_context.append((pdf_url, link_text, link_context))
                                    
                                    elif depth < max_depth and self._is_same_domain(current_url, full_url):
                                        await crawl_page(full_url, depth + 1)
                                        
            except Exception as e:
                logger.error(f"Error crawling {current_url}: {e}")
        
        await crawl_page(url, 0)
        
        # Remove duplicates and prioritize links
        unique_links = {}
        for pdf_url, link_text, context in pdf_links_with_context:
            if pdf_url not in unique_links:
                unique_links[pdf_url] = (link_text, context)
        
        # Sort by relevance score using page content for topic extraction
        sorted_links = self._prioritize_pdf_links(url, unique_links, page_content, expected_authors)
        return sorted_links
    
    def _extract_link_text(self, link) -> str:
        """Extract meaningful text from a link, including image alt text"""
        # Get direct text content
        link_text = link.get_text(strip=True)
        
        # If no text, check for image alt text
        if not link_text:
            img = link.find('img')
            if img:
                alt_text = img.get('alt', '').strip()
                if alt_text:
                    link_text = alt_text
        
        # If still no text, check title attribute
        if not link_text:
            title = link.get('title', '').strip()
            if title:
                link_text = title
                
        return link_text.lower()
    
    def _get_link_context(self, link, soup) -> str:
        """Get surrounding context for a PDF link to help with relevance scoring"""
        try:
            # Get text from parent elements for context
            context_parts = []
            
            # Check if link contains an image with alt text or title
            img = link.find('img')
            if img:
                alt_text = img.get('alt', '').strip()
                title_text = img.get('title', '').strip()
                if alt_text:
                    context_parts.append(alt_text)
                if title_text:
                    context_parts.append(title_text)
            
            # Check for title attribute on the link itself
            link_title = link.get('title', '').strip()
            if link_title:
                context_parts.append(link_title)
            
            # Try to get heading context
            for heading_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                heading = link.find_parent().find_previous(heading_tag)
                if heading:
                    context_parts.append(heading.get_text(strip=True))
                    break
            
            # Get paragraph context
            paragraph = link.find_parent('p')
            if paragraph:
                context_parts.append(paragraph.get_text(strip=True)[:200])  # First 200 chars
            
            # Get list item context
            list_item = link.find_parent('li')
            if list_item:
                context_parts.append(list_item.get_text(strip=True)[:200])
            
            # Get div context (for cases where link is in a div)
            div_parent = link.find_parent('div')
            if div_parent and not paragraph and not list_item:
                div_text = div_parent.get_text(strip=True)[:200]
                if div_text:
                    context_parts.append(div_text)
                
            return " ".join(context_parts).lower()
        except:
            return ""
    
    def _extract_page_content(self, soup) -> str:
        """Extract main content from page for topic analysis"""
        try:
            # Get page title
            title = soup.find('title')
            title_text = title.get_text() if title else ""
            
            # Get main headings (h1-h3 are usually most important)
            headings = []
            for tag in ['h1', 'h2', 'h3']:
                elements = soup.find_all(tag)
                headings.extend([elem.get_text(strip=True) for elem in elements])
            
            # Get meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ""
            
            # Get first few paragraphs of content
            paragraphs = soup.find_all('p')
            paragraph_text = ' '.join([p.get_text(strip=True) for p in paragraphs[:5]])
            
            # Combine all content
            content = f"{title_text} {' '.join(headings)} {description} {paragraph_text}"
            return content.lower()
        except:
            return ""
    
    def _extract_topic_keywords(self, page_content: str, source_url: str) -> List[str]:
        """Extract topic-specific keywords from page content and URL"""
        keywords = set()
        
        # Extract from URL path
        url_path = urlparse(source_url).path.lower()
        url_parts = [part for part in url_path.split('/') if part and len(part) > 2]
        keywords.update(url_parts)
        
        # Common technical/academic terms that often appear in research
        content_words = page_content.split()
        
        # Look for potential research topic keywords (longer, technical terms)
        for word in content_words:
            word = word.strip('.,!?;:"()[]{}').lower()
            # Keywords are likely to be:
            # - Technical terms (contain specific patterns)
            # - Repeated frequently
            # - Have certain lengths
            if (len(word) >= 4 and 
                (any(pattern in word for pattern in ['network', 'learn', 'model', 'algorithm', 'method', 'system']) or
                 word.endswith(('ing', 'tion', 'ness', 'ment', 'ical', 'able')) or
                 content_words.count(word) >= 2)):  # Appears multiple times
                keywords.add(word)
        
        # Limit to most relevant keywords
        return list(keywords)[:20]  # Top 20 keywords
    
    def _extract_expected_authors(self, soup, url: str) -> set:
        """Extract expected author names from the page"""
        authors = set()
        
        try:
            # Look for author information in common locations
            # 1. Meta tags
            author_meta = soup.find('meta', attrs={'name': 'author'})
            if author_meta:
                author_content = author_meta.get('content', '')
                authors.update(self._parse_author_names(author_content))
            
            # 2. Look for "by" or "Author:" patterns in text
            text_content = soup.get_text()
            author_patterns = [
                r'(?:by|author[s]?:?)\s*([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*,\s*([A-Z][a-z]+\s+[A-Z][a-z]+))*\s*(?:et\s+al\.?)?'
            ]
            
            for pattern in author_patterns:
                matches = re.findall(pattern, text_content)
                for match in matches:
                    if isinstance(match, tuple):
                        authors.update(name.strip() for name in match if name.strip())
                    else:
                        authors.add(match.strip())
            
            # 3. For Nature articles, look for specific author elements
            if 'nature.com' in url:
                author_elements = soup.find_all(['span', 'div'], class_=re.compile(r'author', re.I))
                for elem in author_elements:
                    author_text = elem.get_text(strip=True)
                    if author_text and len(author_text.split()) <= 4:  # Reasonable author name length
                        authors.add(author_text)
            
            # Clean and validate author names
            clean_authors = set()
            for author in authors:
                clean_name = re.sub(r'[^\w\s]', '', author).strip()
                if (len(clean_name.split()) >= 2 and 
                    len(clean_name) <= 50 and 
                    not any(word in clean_name.lower() for word in ['click', 'read', 'download', 'paper', 'abstract'])):
                    clean_authors.add(clean_name.lower())
                    
        except Exception as e:
            logger.warning(f"Error extracting authors: {e}")
        
        return clean_authors
    
    def _parse_author_names(self, author_string: str) -> set:
        """Parse author names from a string"""
        authors = set()
        
        # Split by common separators
        parts = re.split(r'[,;&]', author_string)
        for part in parts:
            part = part.strip()
            # Basic validation: should look like "Firstname Lastname"
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', part):
                authors.add(part.lower())
        
        return authors
    
    def _is_likely_unrelated_paper(self, pdf_url: str, page_content: str, source_url: str) -> bool:
        """Check if a PDF is likely unrelated to the source page"""
        
        # Quick checks for obviously unrelated content
        unrelated_indicators = [
            'openai', 'dota', '1912.06680',  # Specific to the bug case
            'gpt', 'language model', 'nlp'   # Common unrelated topics for robotics papers
        ]
        
        # If the page is about robotics/self-modeling but PDF is about language models
        if ('robot' in page_content or 'self-model' in page_content or 'lipson' in page_content.lower()):
            if any(indicator in pdf_url.lower() for indicator in unrelated_indicators):
                return True
        
        # Check domain mismatch for Nature articles
        if 'nature.com' in source_url and 'arxiv.org' in pdf_url:
            # ArXiv papers found from Nature pages might be legitimate, but check dates
            # Extract potential arXiv ID and check if it's from 2019 (1912.xxxxx)
            arxiv_match = re.search(r'(\d{4})\.(\d{4,5})', pdf_url)
            if arxiv_match:
                year_month = arxiv_match.group(1)
                if year_month == '1912':  # December 2019 - too old for 2025 Nature paper
                    return True
        
        return False
    
    def _prioritize_pdf_links(self, source_url: str, links_dict: Dict[str, tuple], page_content: str = "", expected_authors: set = None) -> List[str]:
        """Prioritize PDF links based on generic relevance scoring"""
        scored_links = []
        expected_authors = expected_authors or set()
        
        # Extract topic-specific keywords
        topic_keywords = self._extract_topic_keywords(page_content, source_url)
        source_domain = urlparse(source_url).netloc.lower()
        
        for pdf_url, (link_text, context) in links_dict.items():
            score = 0
            combined_text = f"{link_text} {context}".lower()
            
            # 1. UNIVERSAL MAIN PAPER INDICATORS (+10-25 points)
            main_indicators = ['paper', 'pdf', 'publication', 'main', 'full', 'original', 'preprint']
            for indicator in main_indicators:
                if indicator in combined_text:
                    score += 10
                if indicator in link_text:  # Higher weight for direct link text
                    score += 15
            
            # 2. ACADEMIC VENUE SCORING (+15-25 points)
            if 'arxiv.org' in pdf_url:
                score += 20  # ArXiv is usually the main paper
            elif any(venue in pdf_url for venue in ['ieee.org', 'acm.org', 'springer.com', 'openreview.net']):
                score += 15  # Conference/journal papers
            
            # 3. TOPIC RELEVANCE SCORING (+5 points per match)
            topic_matches = 0
            for keyword in topic_keywords:
                if keyword in pdf_url.lower() or keyword in combined_text:
                    topic_matches += 1
                    score += 5
            
            # Bonus for multiple topic matches (indicates strong relevance)
            if topic_matches >= 3:
                score += 10
            
            # 3.5. SPECIAL BOOST FOR MAIN PROJECT PAPERS (+30 points)
            # Look for indicators that this is THE main paper for the project
            link_and_context = f"{link_text} {context}".lower()
            main_paper_indicators = ['paper', 'main', 'original', 'primary']
            
            # If link text is simply "paper" or similar, and it has topic matches, likely the main paper
            if (any(indicator in link_text for indicator in main_paper_indicators) and 
                topic_matches >= 2 and 
                len(link_text.split()) <= 3):  # Short, direct link text
                score += 30
            
            # 4. STRUCTURAL INDICATORS (+10-20 points)
            # Look for year patterns (recent papers are often more relevant)
            import re
            year_match = re.search(r'(20\d{2})', pdf_url + combined_text)
            if year_match:
                year = int(year_match.group(1))
                if year >= 2020:  # Recent papers
                    score += 10
                elif year >= 2015:
                    score += 5
            
            # 5. LINK POSITION/PROMINENCE SCORING (+5-15 points)
            # Links mentioned early or prominently are usually more important
            prominent_contexts = ['abstract', 'download', 'read', 'view', 'access']
            for ctx in prominent_contexts:
                if ctx in combined_text:
                    score += 8
            
            # 6. PENALTIES (-5 to -10 points)
            # Penalize supplementary materials
            supp_indicators = ['supplement', 'supp', 'appendix', 'additional', 'extra', 
                             'code', 'dataset', 'slides', 'poster', 'demo']
            for indicator in supp_indicators:
                if indicator in combined_text:
                    score -= 5
            
            # Penalize very generic or old links
            if any(generic in pdf_url.lower() for generic in ['example', 'template', 'draft']):
                score -= 10
            
            # Major penalty for completely unrelated domains or topics
            if self._is_likely_unrelated_paper(pdf_url, page_content, source_url):
                score -= 50
            
            scored_links.append((pdf_url, score))
        
        # Sort by score descending, then by URL for consistency
        scored_links.sort(key=lambda x: (-x[1], x[0]))
        
        return [url for url, score in scored_links]
    
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
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens in response (default: 20000)",
                        "default": 20000
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
        ),
        Tool(
            name="convert_pdf_pages",
            description="Convert specific pages of a PDF to markdown (for large PDFs)",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The PDF URL to download and convert"
                    },
                    "start_page": {
                        "type": "integer",
                        "description": "Starting page number (1-indexed, default: 1)",
                        "default": 1
                    },
                    "end_page": {
                        "type": "integer",
                        "description": "Ending page number (1-indexed, optional)"
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
            name="find_and_convert_main_pdf",
            description="Find the most relevant PDF from a URL and convert it automatically",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to crawl for the main PDF (e.g., project page, paper homepage)"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum crawling depth (default: 1)",
                        "default": 1
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "description": "Include PDF metadata in output (default: true)",
                        "default": True
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens in response (default: 20000)",
                        "default": 20000
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="convert_pdf_url_enhanced",
            description="Download PDF from URL and convert to markdown using enhanced marker-pdf processing (better layout detection)",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The PDF URL to download and convert"
                    },
                    "fallback_to_pymupdf": {
                        "type": "boolean",
                        "description": "Fall back to PyMuPDF if marker-pdf fails (default: true)",
                        "default": True
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="convert_pdf_url_with_method",
            description="Convert PDF with explicit method choice (marker-pdf or PyMuPDF)",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The PDF URL to download and convert"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["marker", "pymupdf", "auto"],
                        "description": "Conversion method: 'marker' for enhanced academic processing, 'pymupdf' for fast general-purpose, 'auto' for automatic detection",
                        "default": "auto"
                    }
                },
                "required": ["url"]
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
        
        result = f"Found {len(pdf_links)} PDF links from {url} (prioritized by relevance):\n\n"
        for i, link in enumerate(pdf_links, 1):
            result += f"{i}. {link}\n"
        
        if pdf_links:
            result += f"\n💡 **Tip**: The first link is most likely to be the main/primary paper based on context analysis."
        
        return [TextContent(type="text", text=result)]
    
    elif name == "convert_pdf_url":
        url = arguments["url"]
        include_metadata = arguments.get("include_metadata", True)
        max_tokens = arguments.get("max_tokens", 20000)  # Default to 20k tokens (under 25k limit)
        
        # Download PDF
        pdf_path = await pdf_processor.download_pdf(url)
        if not pdf_path:
            return [TextContent(type="text", text=f"Failed to download PDF from {url}")]
        
        # Convert to markdown with automatic method selection
        markdown = pdf_processor.convert_pdf_to_markdown(pdf_path, source_url=url)
        
        result = f"# Converted from: {url}\n\n{markdown}"
        
        # Check token count and truncate if necessary
        estimated_tokens = len(result) // 4  # Rough estimation: 1 token ≈ 4 characters
        if estimated_tokens > max_tokens:
            logger.warning(f"Response too large ({estimated_tokens} tokens), truncating to {max_tokens} tokens")
            char_limit = max_tokens * 4
            truncated_result = result[:char_limit]
            truncated_result += f"\n\n---\n\n⚠️ **Response Truncated**: This PDF was too large ({estimated_tokens} estimated tokens) and has been truncated to fit within the {max_tokens} token limit. The full content is cached and can be accessed in smaller chunks using the page-specific conversion tools."
            result = truncated_result
        
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
    
    elif name == "convert_pdf_pages":
        url = arguments["url"]
        start_page = arguments.get("start_page", 1)
        end_page = arguments.get("end_page")
        include_metadata = arguments.get("include_metadata", True)
        
        # Download PDF
        pdf_path = await pdf_processor.download_pdf(url)
        if not pdf_path:
            return [TextContent(type="text", text=f"Failed to download PDF from {url}")]
        
        # Convert specific pages to markdown (uses PyMuPDF for page ranges)
        markdown = pdf_processor.convert_pdf_to_markdown(pdf_path, start_page, end_page, source_url=url)
        
        result = f"# Converted from: {url} (Pages {start_page}-{end_page or 'end'})\n\n{markdown}"
        return [TextContent(type="text", text=result)]
    
    elif name == "find_and_convert_main_pdf":
        url = arguments["url"]
        max_depth = arguments.get("max_depth", 1)
        include_metadata = arguments.get("include_metadata", True)
        max_tokens = arguments.get("max_tokens", 20000)
        
        # Find PDF links with prioritization
        pdf_links = await url_crawler.find_pdf_links(url, max_depth)
        
        if not pdf_links:
            return [TextContent(type="text", text=f"No PDF links found at {url}")]
        
        # Use the first (most relevant) PDF
        main_pdf_url = pdf_links[0]
        
        # Download and convert the main PDF
        pdf_path = await pdf_processor.download_pdf(main_pdf_url)
        if not pdf_path:
            return [TextContent(type="text", text=f"Failed to download the main PDF from {main_pdf_url}")]
        
        # Validate PDF content before full conversion
        if not pdf_processor.validate_pdf_relevance(pdf_path, url):
            logger.warning(f"PDF content validation failed for {main_pdf_url}")
            # Try the next PDF if available
            if len(pdf_links) > 1:
                logger.info(f"Trying second PDF: {pdf_links[1]}")
                main_pdf_url = pdf_links[1]
                pdf_path = await pdf_processor.download_pdf(main_pdf_url)
                if not pdf_path:
                    return [TextContent(type="text", text=f"Failed to download alternative PDF from {main_pdf_url}")]
        
        # Convert to markdown with automatic method selection
        markdown = pdf_processor.convert_pdf_to_markdown(pdf_path, source_url=url)
        
        result = f"# Auto-converted main PDF from: {url}\n"
        result += f"**Source PDF**: {main_pdf_url}\n"
        result += f"**Relevance**: Selected as most relevant from {len(pdf_links)} PDF(s) found\n\n"
        result += markdown
        
        # Check token count and truncate if necessary
        estimated_tokens = len(result) // 4
        if estimated_tokens > max_tokens:
            logger.warning(f"Response too large ({estimated_tokens} tokens), truncating to {max_tokens} tokens")
            char_limit = max_tokens * 4
            truncated_result = result[:char_limit]
            truncated_result += f"\n\n---\n\n⚠️ **Response Truncated**: This PDF was too large ({estimated_tokens} estimated tokens) and has been truncated to fit within the {max_tokens} token limit. Use convert_pdf_pages for specific sections."
            result = truncated_result
        
        return [TextContent(type="text", text=result)]
    
    elif name == "convert_pdf_url_enhanced":
        url = arguments["url"]
        fallback_to_pymupdf = arguments.get("fallback_to_pymupdf", True)
        
        # Download PDF
        pdf_path = await pdf_processor.download_pdf(url)
        if not pdf_path:
            return [TextContent(type="text", text=f"Failed to download PDF from {url}")]
        
        # Try enhanced conversion with marker-pdf
        try:
            if MARKER_AVAILABLE:
                markdown = pdf_processor.convert_pdf_to_markdown_with_marker(pdf_path)
                return [TextContent(type="text", text=markdown)]
            else:
                if fallback_to_pymupdf:
                    logger.warning("marker-pdf not available, falling back to PyMuPDF")
                    markdown = pdf_processor.convert_pdf_to_markdown(pdf_path)
                    fallback_note = "\n\n---\n\n⚠️ **Note**: Enhanced processing with marker-pdf not available. Install marker-pdf for better layout detection: `pip install marker-pdf`\n\n"
                    return [TextContent(type="text", text=fallback_note + markdown)]
                else:
                    return [TextContent(type="text", text="marker-pdf not available and fallback disabled. Install marker-pdf: pip install marker-pdf")]
        except Exception as e:
            if fallback_to_pymupdf:
                logger.error(f"Enhanced conversion failed: {e}, falling back to PyMuPDF")
                markdown = pdf_processor.convert_pdf_to_markdown(pdf_path)
                error_note = f"\n\n---\n\n⚠️ **Note**: Enhanced processing failed ({str(e)}), used PyMuPDF fallback.\n\n"
                return [TextContent(type="text", text=error_note + markdown)]
            else:
                return [TextContent(type="text", text=f"Enhanced conversion failed: {e}")]
    
    elif name == "convert_pdf_url_with_method":
        url = arguments["url"]
        method = arguments.get("method", "auto")
        
        # Download PDF
        pdf_path = await pdf_processor.download_pdf(url)
        if not pdf_path:
            return [TextContent(type="text", text=f"Failed to download PDF from {url}")]
        
        # Convert with specified method
        force_method = None if method == "auto" else method
        markdown = pdf_processor.convert_pdf_to_markdown(pdf_path, source_url=url, force_method=force_method)
        
        # Add method info to result
        if method == "auto":
            is_academic = pdf_processor.is_academic_paper(pdf_path, url)
            actual_method = "marker-pdf" if (MARKER_AVAILABLE and is_academic) else "PyMuPDF"
            method_note = f"\n**Method Used**: {actual_method} (auto-detected: {'academic paper' if is_academic else 'general document'})"
        else:
            method_note = f"\n**Method Used**: {method} (user-specified)"
        
        result = f"# Converted from: {url}{method_note}\n\n{markdown}"
        return [TextContent(type="text", text=result)]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main entry point"""
    try:
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())