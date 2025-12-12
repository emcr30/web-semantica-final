import os
import logging
from pdfminer.high_level import extract_text

# Reduce verbose pdfminer DEBUG logging (too noisy in server logs)
for logger_name in ('pdfminer', 'pdfminer.psparser', 'pdfminer.pdfinterp'):
    logging.getLogger(logger_name).setLevel(logging.WARNING)


def extract_text_from_pdf(path: str) -> str:
    """Extracts text from a PDF file using pdfminer.six.

    Suppresses low-level pdfminer DEBUG logs by configuring logger levels above.
    """
    # pdfminer will raise exceptions for malformed PDFs; caller should handle them
    return extract_text(path)
