import json
import re
import threading
from pathlib import Path

_FILE = Path("data/confirmed_matches.json")
_lock = threading.Lock()


def _normalize_key(title: str, artist: str) -> str:
    def _clean(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^\w가-힣]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    return f"{_clean(title)}|||{_clean(artist)}"


def _load() -> dict:
    if not _FILE.exists():
        return {}
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_confirmed_matches(tracks: list[dict]) -> int:
    """사용자가 선택해 플레이리스트 생성까지 완료한 곡만 저장.

    tracks 항목: {input_title, input_artist, spotify_uri}
    반환값: 저장된 항목 수
    """
    saved = 0
    with _lock:
        data = _load()
        for item in tracks:
            title = str(item.get("input_title") or "").strip()
            artist = str(item.get("input_artist") or "").strip()
            uri = str(item.get("spotify_uri") or "").strip()
            if not uri or not title:
                continue
            key = _normalize_key(title, artist)
            existing = data.get(key, {})
            data[key] = {
                "input_title": title,
                "input_artist": artist,
                "spotify_uri": uri,
                "confirmed_count": existing.get("confirmed_count", 0) + 1,
            }
            saved += 1
        if saved:
            _FILE.parent.mkdir(parents=True, exist_ok=True)
            _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return saved


def lookup_confirmed_match(title: str, artist: str) -> str | None:
    """사용자 확정 매칭 URI 반환. 없으면 None."""
    with _lock:
        data = _load()
    key = _normalize_key(title, artist)
    entry = data.get(key)
    if entry and entry.get("spotify_uri"):
        return str(entry["spotify_uri"])
    return None
