"""Multimodal file processing for PDFs, images, and text files."""
import asyncio
import logging
import hashlib
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import base64
import io

# PDF processing
try:
    import PyPDF2
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Image processing
try:
    from PIL import Image
    import pytesseract
    IMAGE_AVAILABLE = True
except ImportError:
    IMAGE_AVAILABLE = False

from .config import config

logger = logging.getLogger(__name__)

class FileProcessor:
    def __init__(self):
        self.processed_files = {}  # In-memory cache
        
    def _generate_file_id(self, filename: str, content: bytes) -> str:
        """Generate unique ID for file."""
        content_hash = hashlib.md5(content).hexdigest()
        return f"{filename}_{content_hash[:8]}"
    
    async def process_pdf(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Process PDF file and extract text content."""
        if not PDF_AVAILABLE:
            return {"error": "PDF processing not available", "content": ""}
        
        try:
            # Try pdfplumber first (better for tables/structure)
            pdf_file = io.BytesIO(file_content)
            text_content = ""
            pages = []
            
            with pdfplumber.open(pdf_file) as pdf:
                for i, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    pages.append({
                        "page": i,
                        "text": page_text.strip()
                    })
                    text_content += f"\\n--- Page {i} ---\\n{page_text}\\n"
            
            # Fallback to PyPDF2 if pdfplumber fails
            if not text_content.strip():
                pdf_file.seek(0)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                for i, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text() or ""
                    pages.append({
                        "page": i, 
                        "text": page_text.strip()
                    })
                    text_content += f"\\n--- Page {i} ---\\n{page_text}\\n"
            
            return {
                "type": "pdf",
                "filename": filename,
                "content": text_content.strip(),
                "pages": pages,
                "page_count": len(pages),
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"PDF processing error: {e}")
            return {
                "type": "pdf",
                "filename": filename,
                "content": "",
                "error": f"Could not process PDF: {str(e)}",
                "processed_at": datetime.utcnow().isoformat()
            }
    
    async def process_image(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Process image file and extract text/description."""
        if not IMAGE_AVAILABLE:
            return {"error": "Image processing not available", "content": ""}
        
        try:
            # Open image
            image = Image.open(io.BytesIO(file_content))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract text using OCR
            ocr_text = ""
            try:
                ocr_text = pytesseract.image_to_string(image).strip()
            except Exception as e:
                logger.warning(f"OCR failed: {e}")
            
            # Basic image info
            width, height = image.size
            format_info = image.format or "Unknown"
            
            # Create base64 for potential vision model use
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            return {
                "type": "image",
                "filename": filename,
                "content": ocr_text,
                "ocr_text": ocr_text,
                "width": width,
                "height": height,
                "format": format_info,
                "base64": img_base64,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return {
                "type": "image",
                "filename": filename,
                "content": "",
                "error": f"Could not process image: {str(e)}",
                "processed_at": datetime.utcnow().isoformat()
            }
    
    async def process_text_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Process text file."""
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            text_content = ""
            
            for encoding in encodings:
                try:
                    text_content = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not text_content:
                text_content = file_content.decode('utf-8', errors='ignore')
            
            return {
                "type": "text",
                "filename": filename,
                "content": text_content.strip(),
                "char_count": len(text_content),
                "line_count": len(text_content.splitlines()),
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Text file processing error: {e}")
            return {
                "type": "text",
                "filename": filename,
                "content": "",
                "error": f"Could not process text file: {str(e)}",
                "processed_at": datetime.utcnow().isoformat()
            }
    
    async def process_file(self, file_content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """Process any file based on type."""
        file_id = self._generate_file_id(filename, file_content)
        
        # Check cache first
        if file_id in self.processed_files:
            return self.processed_files[file_id]
        
        # Determine file type
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf') or 'pdf' in content_type:
            result = await self.process_pdf(file_content, filename)
        elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')) or 'image' in content_type:
            result = await self.process_image(file_content, filename)
        elif filename_lower.endswith(('.txt', '.md', '.csv', '.json', '.xml', '.log')) or 'text' in content_type:
            result = await self.process_text_file(file_content, filename)
        else:
            # Try as text first, then give up
            try:
                result = await self.process_text_file(file_content, filename)
            except:
                result = {
                    "type": "unknown",
                    "filename": filename,
                    "content": "",
                    "error": "Unsupported file type",
                    "processed_at": datetime.utcnow().isoformat()
                }
        
        # Add file ID and cache
        result["file_id"] = file_id
        self.processed_files[file_id] = result
        
        return result
    
    def get_file_context(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all processed files for context."""
        # In a real implementation, this would be user-specific
        return list(self.processed_files.values())
    
    def clear_files(self, user_id: str = None):
        """Clear processed files."""
        if user_id:
            # In real implementation, clear user-specific files
            pass
        else:
            self.processed_files.clear()

# Global instance
file_processor = FileProcessor()