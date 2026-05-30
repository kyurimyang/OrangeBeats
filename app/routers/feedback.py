from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, HTTPException

from app.clients.supabase_client import get_supabase

router = APIRouter(prefix="/feedback", tags=["Feedback"])

MIN_SCORE = 1
MAX_SCORE = 5
MAX_COMMENT_LENGTH = 500


@router.get("/ratings")
def list_ratings():
    result = get_supabase().table("ratings").select("*").order("created_at", desc=True).execute()
    return result.data


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

    entry = {
        "score": score,
        "playlist_url": playlist_url,
        "playlist_name": playlist_name,
        "comment": comment,
    }
    result = get_supabase().table("ratings").insert(entry).execute()
    return result.data[0]


@router.get("/admin")
def admin_dashboard(key: str = ""):
    from app.config import ADMIN_KEY

    if not ADMIN_KEY or key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    result = get_supabase().table("ratings").select("*").order("created_at", desc=True).execute()
    ratings = result.data

    sorted_ratings = ratings

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
    result = get_supabase().table("ratings").select("*").execute()
    ratings = result.data

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
    recent_scores = [int(r["score"]) for r in ratings if r.get("created_at", "") >= cutoff]
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
