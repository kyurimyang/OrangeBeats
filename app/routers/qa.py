from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Header, HTTPException

from app.clients.supabase_client import get_supabase
from app.config import ADMIN_KEY

router = APIRouter(prefix="/qa", tags=["QA"])

ALLOWED_CATEGORIES = {"bug", "matching", "question", "suggestion", "etc"}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@router.get("")
def list_qa_posts():
    result = get_supabase().table("qa_posts").select("*").order("created_at", desc=True).execute()
    return result.data


@router.post("")
def create_qa_post(payload: Dict):
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    author = (payload.get("author") or "").strip()
    category = (payload.get("category") or "question").strip().lower()

    if not title or not content or not author:
        raise HTTPException(status_code=400, detail="title, content, author는 필수입니다.")
    if category not in ALLOWED_CATEGORIES:
        category = "question"

    now = _now_iso()
    data = {
        "title": title,
        "content": content,
        "author": author,
        "category": category,
        "status": "waiting",
        "answer": None,
        "created_at": now,
        "updated_at": now,
    }
    result = get_supabase().table("qa_posts").insert(data).execute()
    return result.data[0]


@router.get("/{post_id}")
def get_qa_post(post_id: int):
    result = (
        get_supabase()
        .table("qa_posts")
        .select("*")
        .eq("id", post_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="QA 글을 찾을 수 없습니다.")
    return result.data


@router.delete("/{post_id}")
def delete_qa_post(post_id: int, x_admin_key: str = Header(default="")):
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="관리자 코드가 올바르지 않습니다.")
    result = (
        get_supabase()
        .table("qa_posts")
        .delete()
        .eq("id", post_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="QA 글을 찾을 수 없습니다.")
    return {"ok": True}


@router.post("/{post_id}/answer")
def answer_qa_post(post_id: int, payload: Dict, x_admin_key: str = Header(default="")):
    answer = (payload.get("answer") or "").strip()

    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="관리자 코드가 올바르지 않습니다.")
    if not answer:
        raise HTTPException(status_code=400, detail="답변 내용을 입력해주세요.")

    now = _now_iso()
    result = (
        get_supabase()
        .table("qa_posts")
        .update({"answer": answer, "status": "answered", "updated_at": now})
        .eq("id", post_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="QA 글을 찾을 수 없습니다.")
    return result.data[0]
