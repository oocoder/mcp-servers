#!/usr/bin/env python3
"""
Test PDF processing with local file
"""

from pathlib import Path
from pdf_processor_simple import PDFProcessor

def test_local_pdf():
    """Test with local PDF file"""
    processor = PDFProcessor()
    
    # Test with existing PDF
    pdf_path = Path("data/MPC-Based_Walking.pdf")
    if pdf_path.exists():
        print(f"🔄 Converting local PDF: {pdf_path}")
        markdown = processor.convert_pdf_to_markdown(pdf_path)
        
        # Save result
        output_path = Path("MPC_Walking_converted.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        print(f"✅ Conversion complete!")
        print(f"📄 Output saved to: {output_path}")
        print(f"📊 Content length: {len(markdown)} characters")
        
        # Show first few lines
        lines = markdown.split('\n')
        print(f"\n📖 First 15 lines:")
        for i, line in enumerate(lines[:15], 1):
            print(f"{i:2d}: {line}")
        
        return True
    else:
        print(f"❌ PDF not found: {pdf_path}")
        return False

if __name__ == "__main__":
    test_local_pdf()