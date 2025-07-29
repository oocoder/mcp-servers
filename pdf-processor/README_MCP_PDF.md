# 🤖 MCP PDF Server for Claude Code

A powerful Model Context Protocol (MCP) server that crawls URLs for PDFs and converts them to Claude Code-optimized markdown format.

## ✨ Features

- **🕷️ URL Crawling**: Automatically finds PDF links from web pages
- **📄 PDF Processing**: Converts PDFs to structured markdown with LaTeX math
- **🎯 Claude Code Optimization**: Output specifically formatted for Claude Code analysis
- **⚡ Caching**: Smart caching system to avoid re-downloading PDFs
- **🔍 Content Analysis**: Extracts metadata, math expressions, code blocks, and figures
- **📚 Structure Detection**: Automatically identifies headings, paragraphs, tables, and equations

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r mcp_requirements.txt
```

### 2. Configure Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "pdf-processor": {
      "command": "python",
      "args": ["/path/to/your/project/mcp_pdf_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/your/project"
      }
    }
  }
}
```

### 3. Test the Server

```bash
python test_mcp_pdf.py
```

## 🛠️ Available Tools

### `crawl_pdf_links`
Crawl a URL to find PDF links.

**Parameters:**
- `url` (string): The URL to crawl for PDF links
- `max_depth` (integer, optional): Maximum crawling depth (default: 1)

**Example:**
```
crawl_pdf_links url=https://arxiv.org/list/cs.AI/recent max_depth=2
```

### `convert_pdf_url`
Download and convert a PDF from URL to Claude-optimized markdown.

**Parameters:**
- `url` (string): The PDF URL to download and convert
- `include_metadata` (boolean, optional): Include PDF metadata (default: true)

**Example:**
```
convert_pdf_url url=https://arxiv.org/pdf/2301.00000.pdf
```

### `batch_convert_pdfs`
Convert multiple PDF URLs to markdown in one operation.

**Parameters:**
- `urls` (array): List of PDF URLs to convert
- `include_metadata` (boolean, optional): Include PDF metadata (default: true)

**Example:**
```
batch_convert_pdfs urls=["https://arxiv.org/pdf/2301.00000.pdf", "https://arxiv.org/pdf/2301.00001.pdf"]
```

## 📋 Output Features

### Claude Code Optimizations

The server generates markdown specifically optimized for Claude Code:

- **📄 Document Analysis Header**: Metadata and integration notes
- **🔢 Mathematical Content Summary**: List of key mathematical expressions
- **🎓 Research Paper Detection**: Special formatting for academic papers
- **📚 Table of Contents**: Auto-generated for long documents
- **🤖 Analysis Tips**: Built-in guidance for effective Claude Code usage

### Example Output Structure

```markdown
# 📄 Document Analysis

## Document Metadata
- **Title**: MPC-Based Walking Control
- **Author**: Research Team
- **Pages**: 12

## 🤖 Claude Code Integration Notes
- This document has been optimized for Claude Code analysis
- Mathematical formulas are preserved in LaTeX format
- Code blocks and algorithms are clearly marked
- Tables and figures are structurally annotated

## 🔢 Mathematical Content Summary
1. `x_{k+1} = Ax_k + Bu_k`
2. `J = \sum_{i=0}^{N} ||x_i - x_{ref}||^2`

---

## 📑 Page 1

### Introduction

This paper presents a **method** for MPC-based walking control...

$$
x_{k+1} = Ax_k + Bu_k
$$

```python
def mpc_controller(state, reference):
    return optimal_control
```

**Figure 1**: Control architecture diagram
*Dimensions: 800x600 pixels*
```

## 🔧 Advanced Configuration

### Custom Cache Directory

```python
processor = PDFProcessor(cache_dir=Path("/custom/cache/path"))
```

### Enhanced Math Detection

The server automatically detects and formats:
- LaTeX equations (`$$...$$`)
- Inline math (`$...$`)
- Greek letters and symbols (α, β, ∑, ∫)
- Mathematical operators and expressions

### Code Block Recognition

Automatically identifies code in multiple languages:
- Python (`def`, `class`, `import`)
- JavaScript (`function`, `var`, `const`)
- Java/C++ (`public`, `private`, `void`)
- Shell scripts (`#!/`)

## 🧪 Testing Your Setup

Run the test script to verify everything works:

```bash
python test_mcp_pdf.py
```

Expected output:
```
🧪 Testing MCP PDF Server Components

Testing PDF conversion...
✅ PDF converted successfully!
📄 Output saved to: test_output.md
📊 Content length: 15420 characters

📋 Test Summary:
  PDF Processing: ✅ PASS
  URL Crawling:   ✅ PASS

🎉 MCP PDF Server is ready for use!
```

## 📝 Usage Examples

### Research Paper Analysis

```
# In Claude Code, use the MCP tool:
convert_pdf_url url=https://arxiv.org/pdf/2301.00000.pdf

# Result: Optimized markdown with:
# - Structured sections
# - LaTeX math formulas  
# - Code blocks highlighted
# - Figure annotations
# - Research paper formatting
```

### Batch Processing Academic Papers

```
batch_convert_pdfs urls=[
  "https://arxiv.org/pdf/2301.00000.pdf",
  "https://arxiv.org/pdf/2301.00001.pdf",
  "https://proceedings.mlr.press/v139/paper.pdf"
]
```

### Finding PDFs from Conference Sites

```
crawl_pdf_links url=https://neurips.cc/Conferences/2023 max_depth=2
# Returns list of all PDF links found
```

## 🚨 Troubleshooting

### Common Issues

1. **Missing Dependencies**
   ```bash
   pip install pymupdf aiohttp beautifulsoup4 mcp
   ```

2. **Permission Errors**
   - Ensure Python script is executable
   - Check file paths in configuration

3. **Network Issues**
   - Verify URL accessibility
   - Check firewall settings for web requests

4. **PDF Processing Errors**
   - Some PDFs may be password-protected
   - Corrupted PDFs will return error messages

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Integration with Your Workflow

This MCP server is designed to seamlessly integrate with Claude Code for:

- **📚 Research Analysis**: Convert academic papers for deep analysis
- **📖 Documentation Processing**: Extract information from technical PDFs  
- **🔍 Literature Review**: Batch process multiple papers
- **💡 Code Implementation**: Extract algorithms and methods from papers

## 🎯 Next Steps

1. **Install and test** the MCP server
2. **Configure** Claude Code with the server
3. **Try converting** a research paper relevant to your project
4. **Explore** the optimized markdown output
5. **Integrate** into your research workflow

The server is specifically optimized for your FFKSM robotics research, making academic paper analysis much more efficient with Claude Code!