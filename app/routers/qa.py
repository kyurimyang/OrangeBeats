import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from app.config import ADMIN_KEY

router = APIRouter(prefix="/qa", tags=["QA"])

QA_DATA_DIR = Path("data")
QA_POSTS_FILE = QA_DATA_DIR / "qa_posts.json"
QA_LOCK = Lock()
ALLOWED_CATEGORIES = {"bug", "matching", "question", "suggestion", "etc"}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _ensure_store() -> None:
    QA_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not QA_POSTS_FILE.exists():
        QA_POSTS_FILE.write_text("[]", encoding="utf-8")


def _read_posts() -> List[Dict]:
    _ensure_store()
    try:
        data = json.loads(QA_POSTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    return data if isinstance(data, list) else []


def _write_posts(posts: List[Dict]) -> None:
    _ensure_store()
    QA_POSTS_FILE.write_text(
        json.dumps(posts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _sorted_posts(posts: List[Dict]) -> List[Dict]:
    return sorted(posts, key=lambda item: item.get("created_at", ""), reverse=True)


@router.get("")
def list_qa_posts():
    with QA_LOCK:
        return _sorted_posts(_read_posts())


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

    with QA_LOCK:
        posts = _read_posts()
        next_id = max((int(post.get("id", 0)) for post in posts), default=0) + 1
        now = _now_iso()
        post = {
            "id": next_id,
            "title": title,
            "content": content,
            "author": author,
            "category": category,
            "status": "waiting",
            "answer": None,
            "created_at": now,
            "updated_at": now,
        }
        posts.append(post)
        _write_posts(posts)
        return post


@router.get("/{post_id}")
def get_qa_post(post_id: int):
    with QA_LOCK:
        post = next((item for item in _read_posts() if item.get("id") == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="QA 글을 찾을 수 없습니다.")
    return post


@router.delete("/{post_id}")
def delete_qa_post(post_id: int, admin_key: str = ""):
    if not ADMIN_KEY or admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="관리자 코드가 올바르지 않습니다.")
    with QA_LOCK:
        posts = _read_posts()
        new_posts = [p for p in posts if p.get("id") != post_id]
        if len(new_posts) == len(posts):
            raise HTTPException(status_code=404, detail="QA 글을 찾을 수 없습니다.")
        _write_posts(new_posts)
    return {"ok": True}


@router.post("/{post_id}/answer")
def answer_qa_post(post_id: int, payload: Dict):
    answer = (payload.get("answer") or "").strip()
    admin_key = (payload.get("admin_key") or "").strip()

    if not ADMIN_KEY or admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="관리자 코드가 올바르지 않습니다.")
    if not answer:
        raise HTTPException(status_code=400, detail="답변 내용을 입력해주세요.")

    with QA_LOCK:
        posts = _read_posts()
        for post in posts:
            if post.get("id") == post_id:
                post["answer"] = answer
                post["status"] = "answered"
                post["updated_at"] = _now_iso()
                _write_posts(posts)
                return post

    raise HTTPException(status_code=404, detail="QA 글을 찾을 수 없습니다.")
