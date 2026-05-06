def build_combined_text(
    description_text: str = "",
    comments_text: str = "",
    ocr_text: str = "",
) -> str:
    return f"""
[DESCRIPTION]
{description_text or ""}

[COMMENTS]
{comments_text or ""}

[OCR]
{ocr_text or ""}
""".strip()