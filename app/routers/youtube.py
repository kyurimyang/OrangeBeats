# 유튜브 링크 받아서 전체 파이프라인 돌리는 API 주소 파일

import time

from fastapi import APIRouter, Query

from app.services.pipeline_service import run_youtube_pipeline

router = APIRouter(prefix="/youtube", tags=["YouTube"])


@router.get("/analyze")
def analyze_youtube(
    url: str = Query(...),
    mode: str = Query("text"),
):
    started_at = time.perf_counter()
    result = run_youtube_pipeline(url, mode)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    result["timings"] = {
        **result.get("timings", {}),
        "analysis_elapsed_ms": elapsed_ms,
        "total_elapsed_ms": elapsed_ms,
    }
    return result
