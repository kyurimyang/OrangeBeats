from fastapi import APIRouter, Query

from app.services.pipeline_service import run_youtube_text_pipeline

router = APIRouter(prefix="/youtube", tags=["YouTube"])


@router.get("/analyze")
def analyze_youtube(url: str = Query(...)):
    return run_youtube_text_pipeline(url)