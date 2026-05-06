import pypdfium2 as pdfium
from PIL import Image

try:
    import fitz
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False


def get_pdf_info(pdf_bytes: bytes) -> dict:
    info = {
        "page_count": 0,
        "size_bytes": len(pdf_bytes),
        "size_mb": round(len(pdf_bytes) / (1024 * 1024), 2),
        "title_text": "",
        "error": None,
    }
    try:
        if _HAS_FITZ:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            info["page_count"] = doc.page_count
            if doc.page_count > 0:
                info["title_text"] = doc.load_page(0).get_text("text").strip()[:500]
            doc.close()
        else:
            pdf = pdfium.PdfDocument(pdf_bytes)
            info["page_count"] = len(pdf)
            pdf.close()
    except Exception as exc:
        info["error"] = str(exc)
    return info


def render_page_to_image(pdf_bytes: bytes, page_number: int, dpi: int = 150) -> Image.Image:
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        if page_number < 1 or page_number > len(pdf):
            raise ValueError(f"Page {page_number} out of range (PDF has {len(pdf)} pages)")
        bitmap = pdf[page_number - 1].render(scale=dpi / 72)
        return bitmap.to_pil()
    finally:
        pdf.close()


def merge_pdfs(files: list[dict]) -> dict:
    """Merge multiple PDF inputs into one virtual PDF.

    files: list of {'filename': str, 'bytes': bytes}, in the desired merge order.

    Returns a dict:
      - merged_bytes:   bytes of the combined PDF
      - page_map:       list of {'source_file': str, 'page_in_source': int}
                        one entry per page of the merged PDF, 0-indexed in list
                        (so combined page N corresponds to page_map[N - 1])
      - per_file_info:  list of {'filename', 'page_count', 'size_bytes', 'error'}
                        in upload order, including any that failed
      - total_pages:    int — pages in the merged PDF
      - errors:         list of human-readable error strings for files that
                        could not be opened/merged
    """
    if not _HAS_FITZ:
        raise RuntimeError("PyMuPDF (fitz) is required for merging. Install pymupdf.")

    master = fitz.open()
    page_map: list[dict] = []
    per_file_info: list[dict] = []
    errors: list[str] = []

    try:
        for entry in files:
            filename = entry.get("filename", "unknown.pdf")
            pdf_bytes = entry.get("bytes", b"")
            info = {
                "filename": filename,
                "size_bytes": len(pdf_bytes),
                "page_count": 0,
                "error": None,
            }
            try:
                src = fitz.open(stream=pdf_bytes, filetype="pdf")
                try:
                    n = src.page_count
                    info["page_count"] = n
                    for i in range(n):
                        page_map.append({
                            "source_file": filename,
                            "page_in_source": i + 1,
                        })
                    master.insert_pdf(src)
                finally:
                    src.close()
            except Exception as exc:
                info["error"] = str(exc)[:300]
                errors.append(f"Could not merge {filename}: {exc}")
            per_file_info.append(info)

        merged_bytes = bytes(master.tobytes()) if master.page_count > 0 else b""
    finally:
        master.close()

    return {
        "merged_bytes": merged_bytes,
        "page_map": page_map,
        "per_file_info": per_file_info,
        "total_pages": len(page_map),
        "errors": errors,
    }
