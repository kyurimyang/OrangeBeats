import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/feedback", tags=["Feedback"])

RATINGS_DATA_DIR = Path("data")
RATINGS_FILE = RATINGS_DATA_DIR / "ratings.json"
RATINGS_LOCK = Lock()
MIN_SCORE = 1
MAX_SCORE = 5


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _ensure_store() -> None:
    RATINGS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not RATINGS_FILE.exists():
        RATINGS_FILE.write_text("[]", encoding="utf-8")


def _read_ratings() -> List[Dict]:
    _ensure_store()
    try:
        data = json.loads(RATINGS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    return data if isinstance(data, list) else []


def _write_ratings(ratings: List[Dict]) -> None:
    _ensure_store()
    RATINGS_FILE.write_text(
        json.dumps(ratings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/ratings")
def list_ratings():
    with RATINGS_LOCK:
        return sorted(_read_ratings(), key=lambda item: item.get("created_at", ""), reverse=True)


@router.post("/ratings")
def create_rating(payload: Dict):
    try:
        score = int(payload.get("score"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="score는 1~5 정수여야 합니다.") from None

    if score < MIN_SCORE or score > MAX_SCORE:
        raise HTTPException(status_code=400, detail="score는 1~5 사이여야 합니다.")

    playlist_url = str(payload.get("playlist_url") or "").strip()
    playlist_name = str(payload.get("playlist_name") or "").strip()

    with RATINGS_LOCK:
        ratings = _read_ratings()
        next_id = max((int(item.get("id", 0)) for item in ratings), default=0) + 1
        now = _now_iso()
        entry = {
            "id": next_id,
            "score": score,
            "playlist_url": playlist_url,
            "playlist_name": playlist_name,
            "created_at": now,
        }
        ratings.append(entry)
        _write_ratings(ratings)
        return entry
