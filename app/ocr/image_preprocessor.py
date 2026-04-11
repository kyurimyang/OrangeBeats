import os
from pathlib import Path

import cv2


def preprocess_image(image_path: str, save_path: str) -> str:
    """
    OCR 인식률을 높이기 위한 기본 전처리:
    - grayscale
    - resize
    - threshold

    Args:
        image_path: 원본 이미지 경로
        save_path: 전처리 결과 저장 경로

    Returns:
        저장된 전처리 이미지 경로
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    Path(os.path.dirname(save_path)).mkdir(parents=True, exist_ok=True)

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"이미지를 읽을 수 없습니다: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    resized = cv2.resize(
        gray,
        None,
        fx=2.0,
        fy=2.0,
        interpolation=cv2.INTER_CUBIC,
    )

    _, thresh = cv2.threshold(resized, 150, 255, cv2.THRESH_BINARY)

    cv2.imwrite(save_path, thresh)
    return save_path