import pdfplumber


class ResumeParseError(Exception):
    pass


def extract_resume(file_stream):
    """Returns (text, layout_flags) from an uploaded PDF file stream."""
    try:
        with pdfplumber.open(file_stream) as pdf:
            pages_text = []
            multi_column_pages = 0
            table_pages = 0

            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text)

                if page.find_tables():
                    table_pages += 1

                words = page.extract_words()
                if _looks_multi_column(words, page.width):
                    multi_column_pages += 1

            full_text = "\n".join(pages_text).strip()

            if not full_text:
                raise ResumeParseError(
                    "No selectable text found. The PDF may be a scanned image."
                )

            layout_flags = {
                "page_count": len(pdf.pages),
                "has_tables": table_pages > 0,
                "multi_column": multi_column_pages > 0,
            }
            return full_text, layout_flags

    except ResumeParseError:
        raise
    except Exception as exc:
        raise ResumeParseError(f"Could not read PDF: {exc}") from exc


def _looks_multi_column(words, page_width):
    if not words:
        return False
    midpoint = page_width / 2
    left = sum(1 for w in words if w["x1"] < midpoint - 20)
    right = sum(1 for w in words if w["x0"] > midpoint + 20)
    total = len(words)
    if total == 0:
        return False
    return left / total > 0.25 and right / total > 0.25
