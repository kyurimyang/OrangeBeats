import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from app.services import spotify_common

DATA_DIR = Path("data")
ALIASES_FILE = DATA_DIR / "artist_aliases.json"
LOCK = Lock()
DYNAMIC_ALIAS_PAIRS: set[tuple[str, str]] = set()


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _artist_key(value: str) -> str:
    return spotify_common._normalize_artist_key(value or "")


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ALIASES_FILE.exists():
        ALIASES_FILE.write_text("[]", encoding="utf-8")


def _read_aliases() -> List[Dict[str, Any]]:
    _ensure_store()
    try:
        data = json.loads(ALIASES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    return data if isinstance(data, list) else []


def _write_aliases(items: List[Dict[str, Any]]) -> None:
    _ensure_store()
    ALIASES_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _merge_runtime_alias(input_artist: str, spotify_artist: str) -> None:
    input_artist = (input_artist or "").strip()
    spotify_artist = (spotify_artist or "").strip()
    if not input_artist or not spotify_artist:
        return

    existing = spotify_common.ARTIST_ALIAS_MAP.get(input_artist)
    if existing is None:
        spotify_common.ARTIST_ALIAS_MAP[input_artist] = [spotify_artist]
        DYNAMIC_ALIAS_PAIRS.add((input_artist, spotify_artist))
        return

    values = existing if isinstance(existing, list) else [existing]
    if spotify_artist not in values:
        values.append(spotify_artist)
        DYNAMIC_ALIAS_PAIRS.add((input_artist, spotify_artist))
    spotify_common.ARTIST_ALIAS_MAP[input_artist] = values


def _remove_runtime_alias(input_artist: str, spotify_artist: str) -> None:
    input_artist = (input_artist or "").strip()
    spotify_artist = (spotify_artist or "").strip()
    if (input_artist, spotify_artist) not in DYNAMIC_ALIAS_PAIRS:
        return
    existing = spotify_common.ARTIST_ALIAS_MAP.get(input_artist)
    if existing is None:
        return

    values = existing if isinstance(existing, list) else [existing]
    remaining = [value for value in values if value != spotify_artist]
    if remaining:
        spotify_common.ARTIST_ALIAS_MAP[input_artist] = remaining
    else:
        spotify_common.ARTIST_ALIAS_MAP.pop(input_artist, None)
    DYNAMIC_ALIAS_PAIRS.discard((input_artist, spotify_artist))


def apply_saved_artist_aliases() -> int:
    with LOCK:
        aliases = _read_aliases()
        for item in aliases:
            _merge_runtime_alias(item.get("input_artist", ""), item.get("spotify_artist", ""))
    return len(aliases)


def save_artist_aliases(matches: List[Dict[str, Any]]) -> int:
    if not matches:
        return 0

    saved_count = 0
    with LOCK:
        items = _read_aliases()
        by_key = {item.get("key"): item for item in items if item.get("key")}

        for match in matches:
            input_artist = (match.get("input_artist") or "").strip()
            spotify_artist = (match.get("spotify_artist") or "").strip()
            if not input_artist or not spotify_artist:
                continue

            key = f"{_artist_key(input_artist)}::{_artist_key(spotify_artist)}"
            if key == "::":
                continue

            now = _now_iso()
            existing = by_key.get(key, {})
            by_key[key] = {
                **existing,
                "key": key,
                "input_artist": input_artist,
                "spotify_artist": spotify_artist,
                "source": "user_confirmed",
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
            }
            _merge_runtime_alias(input_artist, spotify_artist)
            saved_count += 1

        _write_aliases(list(by_key.values()))

    return saved_count


def clear_artist_aliases() -> int:
    with LOCK:
        items = _read_aliases()
        for item in items:
            _remove_runtime_alias(item.get("input_artist", ""), item.get("spotify_artist", ""))
        _write_aliases([])
    return len(items)
