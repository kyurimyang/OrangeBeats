# 유튜브 링크 받아서 전체 파이프라인 돌리는 API 주소 파일

from fastapi import APIRouter, Query

from app.services.pipeline_service import run_youtube_pipeline

router = APIRouter(prefix="/youtube", tags=["YouTube"])


@router.get("/analyze")
def analyze_youtube(
    url: str = Query(...),
    mode: str = Query("text"),
):
    return run_youtube_pipeline(url, mode)
