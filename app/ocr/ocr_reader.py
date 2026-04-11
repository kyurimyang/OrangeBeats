from typing import List
import logging

import easyocr

logging.getLogger("easyocr").setLevel(logging.ERROR)

_reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)


def read_text(image_path: str) -> List[str]:
    results = _reader.readtext(image_path, detail=0)

    cleaned = []
    for text in results:
        text = str(text).strip()
        if text:
            cleaned.append(text)

    return cleaned