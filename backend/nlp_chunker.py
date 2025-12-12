def chunk_text(text, max_len=100000, overlap=2000):
    """
    Split `text` into chunks no longer than `max_len` characters.
    Each chunk (except the first) will include `overlap` characters
    from the previous chunk to avoid cutting entities in half.

    Yields (start_idx, chunk_text).
    """
    if not text:
        return

    text_len = len(text)
    if text_len <= max_len:
        yield 0, text
        return

    start = 0
    while start < text_len:
        end = start + max_len
        if end >= text_len:
            yield start, text[start:]
            break
        else:
            yield start, text[start:end]
            # move start forward but keep overlap
            start = end - overlap if (end - overlap) > start else end
