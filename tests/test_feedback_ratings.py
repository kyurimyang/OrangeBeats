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
