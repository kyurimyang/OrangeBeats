# 전체 흐름 연결
# 설명란 분석 실패 -> 댓글로 넘어가기
from app.services.text_analysis import analyze_comments, analyze_description
from app.clients.youtube_client import collect_text_sources

from app.ocr.ocr_pipeline import run_ocr_pipeline
from app.services.youtube_downloader import download_youtube_video


# 유튜브 텍스트 파이프라인 전체 실행
def run_youtube_text_pipeline(url: str) -> dict:
    source_data = collect_text_sources(url)

    description_text = source_data.get("description", "")
    comments = source_data.get("comments", [])

    description_result = analyze_description(description_text)
    if description_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "description",
            "success": True,
            "songs": description_result["songs"],
            "signals": description_result["signals"],
            "metrics": description_result["metrics"],
            "debug": {
                "description": description_result,
            },
        }

    comments_result = analyze_comments(comments)
    if comments_result["success"]:
        return {
            "input_url": source_data["input_url"],
            "video_id": source_data["video_id"],
            "youtube_title": source_data.get("youtube_title", ""),
            "selected_stage": "comments",
            "success": True,
            "songs": comments_result["songs"],
            "signals": comments_result["signals"],
            "metrics": comments_result["metrics"],
            "debug": {
                "description": description_result,
                "comments": comments_result,
            },
        }

    return {
        "input_url": source_data["input_url"],
        "video_id": source_data["video_id"],
        "youtube_title": source_data.get("youtube_title", ""),
        "selected_stage": "none",
        "success": False,
        "songs": [],
        "signals": {
            "description": description_result["signals"],
            "comments": comments_result["signals"],
        },
        "metrics": {
            "description": description_result["metrics"],
            "comments": comments_result["metrics"],
        },
        "debug": {
            "description": description_result,
            "comments": comments_result,
        },
    }


def is_text_result_good(youtube_result: dict) -> bool:
    """
    텍스트 기반 추출 결과가 충분히 좋은지 판단
    """
    songs = youtube_result.get("songs", []) or []

    if len(songs) < 5:
        return False

    valid_count = 0
    for song in songs:
        artist = (song.get("artist") or "").strip()
        title = (song.get("title") or "").strip()

        if artist and title:
            valid_count += 1

    return (valid_count / max(len(songs), 1)) >= 0.6


def merge_text_and_ocr_results(text_result: dict, ocr_result: dict) -> dict:
    """
    텍스트 추출 결과와 OCR 후보를 합친다.
    일단은 단순 병합 + 중복 제거 버전
    """
    text_songs = text_result.get("songs", []) or []
    ocr_candidates = ocr_result.get("song_candidates", []) or []

    merged = []
    seen = set()

    for song in text_songs:
        key = (
            (song.get("artist") or "").strip().lower(),
            (song.get("title") or "").strip().lower(),
        )
        if key not in seen:
            seen.add(key)
            merged.append({
                "artist": song.get("artist"),
                "title": song.get("title"),
                "source": song.get("source", "text"),
            })

    for song in ocr_candidates:
        key = (
            (song.get("artist") or "").strip().lower(),
            (song.get("title") or "").strip().lower(),
        )
        if key not in seen:
            seen.add(key)
            merged.append({
                "artist": song.get("artist"),
                "title": song.get("title"),
                "source": song.get("source", "ocr"),
            })

    merged_result = dict(text_result)
    merged_result["songs"] = merged
    merged_result["ocr_used"] = True
    merged_result["ocr_raw_count"] = ocr_result.get("raw_text_count", 0)
    merged_result["ocr_candidate_count"] = len(ocr_candidates)
    merged_result["ocr_result"] = ocr_result

    return merged_result


def run_youtube_pipeline(url: str, mode: str = "auto") -> dict:
    """
    mode:
    - auto
    - text_only
    - ocr_only
    """
    mode = (mode or "auto").strip().lower()

    # 1. 텍스트만 강제 실행
    if mode == "text_only":
        text_result = run_youtube_text_pipeline(url)
        text_result["mode"] = "text_only"
        text_result["ocr_used"] = False
        return text_result

    # 2. OCR만 강제 실행
    if mode == "ocr_only":
        video_path = download_youtube_video(url)
        ocr_result = run_ocr_pipeline(video_path=video_path)

        return {
            "input_url": url,
            "video_id": None,
            "youtube_title": "",
            "selected_stage": "ocr",
            "success": True if ocr_result.get("song_candidates") else False,
            "songs": [
                {
                    "artist": item.get("artist"),
                    "title": item.get("title"),
                    "source": "ocr",
                }
                for item in ocr_result.get("song_candidates", [])
            ],
            "signals": {},
            "metrics": {},
            "debug": {
                "ocr": ocr_result,
            },
            "mode": "ocr_only",
            "ocr_used": True,
            "video_path": video_path,
        }

    # 3. 기본 자동 모드
    text_result = run_youtube_text_pipeline(url)
    text_result["mode"] = "auto"
    text_result["ocr_used"] = False

    # 텍스트 결과가 충분하면 그대로 반환
    if text_result.get("success") and is_text_result_good(text_result):
        return text_result

    # 텍스트 결과가 부족하거나 실패했을 때만 OCR fallback
    video_path = download_youtube_video(url)
    ocr_result = run_ocr_pipeline(video_path=video_path)

    merged_result = merge_text_and_ocr_results(text_result, ocr_result)
    merged_result["video_path"] = video_path

    # OCR 후보라도 있으면 success 보정
    if merged_result.get("songs"):
        merged_result["success"] = True
        merged_result["selected_stage"] = "ocr_fallback"

    return merged_result