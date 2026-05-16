import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import feedback as feedback_router

client = TestClient(app)


@pytest.fixture
def ratings_file(tmp_path, monkeypatch):
    path = tmp_path / "ratings.json"
    monkeypatch.setattr(feedback_router, "RATINGS_FILE", path)
    monkeypatch.setattr(feedback_router, "RATINGS_DATA_DIR", tmp_path)
    return path


def test_create_rating_persists_to_json(ratings_file):
    response = client.post(
        "/feedback/ratings",
        json={
            "score": 5,
            "playlist_url": "https://open.spotify.com/playlist/example",
            "playlist_name": "테스트 플레이리스트",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 5
    assert body["playlist_name"] == "테스트 플레이리스트"
    assert body["id"] == 1

    stored = json.loads(ratings_file.read_text(encoding="utf-8"))
    assert len(stored) == 1
    assert stored[0]["score"] == 5


def test_create_rating_rejects_invalid_score(ratings_file):
    response = client.post("/feedback/ratings", json={"score": 0})
    assert response.status_code == 400


def test_create_rating_with_comment(ratings_file):
    response = client.post(
        "/feedback/ratings",
        json={
            "score": 4,
            "playlist_url": "https://open.spotify.com/playlist/example",
            "playlist_name": "테스트",
            "comment": "노래 추천이 마음에 들었어요!",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["comment"] == "노래 추천이 마음에 들었어요!"

    stored = json.loads(ratings_file.read_text(encoding="utf-8"))
    assert stored[0]["comment"] == "노래 추천이 마음에 들었어요!"


def test_create_rating_comment_too_long(ratings_file):
    response = client.post(
        "/feedback/ratings",
        json={"score": 3, "comment": "가" * 501},
    )
    assert response.status_code == 400


def test_create_rating_empty_comment_stored(ratings_file):
    response = client.post("/feedback/ratings", json={"score": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["comment"] == ""


def test_stats_empty(ratings_file):
    response = client.get("/feedback/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["average"] is None
    assert body["recent_7day_average"] is None
    assert body["comment_rate"] == 0.0
    assert set(body["distribution"].keys()) == {"1", "2", "3", "4", "5"}


def test_stats_aggregation(ratings_file):
    scores = [5, 5, 4, 3, 2]
    for s in scores:
        client.post("/feedback/ratings", json={"score": s, "comment": "좋아요" if s >= 4 else ""})

    response = client.get("/feedback/stats")
    assert response.status_code == 200
    body = response.json()

    assert body["count"] == 5
    assert body["average"] == round(sum(scores) / len(scores), 2)
    assert body["distribution"]["5"] == 2
    assert body["distribution"]["4"] == 1
    assert body["distribution"]["3"] == 1
    assert body["distribution"]["2"] == 1
    assert body["distribution"]["1"] == 0
    assert body["comment_rate"] == 0.6
