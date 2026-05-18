import json
from datetime import datetime, timedelta
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
MAX_COMMENT_LENGTH = 500


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

    comment = str(payload.get("comment") or "").strip()
    if len(comment) > MAX_COMMENT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"comment는 {MAX_COMMENT_LENGTH}자 이하여야 합니다.",
        )

    with RATINGS_LOCK:
        ratings = _read_ratings()
        next_id = max((int(item.get("id", 0)) for item in ratings), default=0) + 1
        now = _now_iso()
        entry = {
            "id": next_id,
            "score": score,
            "playlist_url": playlist_url,
            "playlist_name": playlist_name,
            "comment": comment,
            "created_at": now,
        }
        ratings.append(entry)
        _write_ratings(ratings)
        return entry


@router.get("/admin")
def admin_dashboard(key: str = ""):
    from app.config import ADMIN_KEY

    if not ADMIN_KEY or key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    with RATINGS_LOCK:
        ratings = _read_ratings()

    sorted_ratings = sorted(ratings, key=lambda r: r.get("created_at", ""), reverse=True)

    if not ratings:
        stats = {
            "count": 0,
            "average": None,
            "distribution": {str(s): 0 for s in range(1, 6)},
            "recent_7day_average": None,
            "comment_rate": 0.0,
        }
    else:
        scores = [int(r.get("score", 0)) for r in ratings]
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        recent_scores = [int(r["score"]) for r in ratings if r.get("created_at", "") >= cutoff]
        has_comment = sum(1 for r in ratings if str(r.get("comment") or "").strip())
        stats = {
            "count": len(ratings),
            "average": round(sum(scores) / len(scores), 2),
            "distribution": {str(s): scores.count(s) for s in range(1, 6)},
            "recent_7day_average": round(sum(recent_scores) / len(recent_scores), 2) if recent_scores else None,
            "comment_rate": round(has_comment / len(ratings), 4),
        }

    return {"stats": stats, "ratings": sorted_ratings}


@router.get("/stats")
def get_stats():
    """평점 통계: 전체 건수, 평균, 분포, 최근 7일 평균, 코멘트 보유 비율."""
    with RATINGS_LOCK:
        ratings = _read_ratings()

    if not ratings:
        return {
            "count": 0,
            "average": None,
            "distribution": {str(s): 0 for s in range(1, 6)},
            "recent_7day_average": None,
            "comment_rate": 0.0,
        }

    scores = [int(r.get("score", 0)) for r in ratings]
    distribution = {str(s): scores.count(s) for s in range(1, 6)}
    average = round(sum(scores) / len(scores), 2)

    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    recent_scores = [
        int(r["score"])
        for r in ratings
        if r.get("created_at", "") >= cutoff
    ]
    recent_avg = round(sum(recent_scores) / len(recent_scores), 2) if recent_scores else None

    has_comment = sum(1 for r in ratings if str(r.get("comment") or "").strip())
    comment_rate = round(has_comment / len(ratings), 4)

    return {
        "count": len(ratings),
        "average": average,
        "distribution": distribution,
        "recent_7day_average": recent_avg,
        "comment_rate": comment_rate,
    }
