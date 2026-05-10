import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Dict

import requests

from app.config import ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET, ACRCLOUD_HOST


def acr_credentials_available() -> bool:
    return bool(ACRCLOUD_HOST and ACRCLOUD_ACCESS_KEY and ACRCLOUD_ACCESS_SECRET)


def recognize_acr_segment(segment_path: Path) -> Dict | None:
    if not acr_credentials_available():
        return None

    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))
    string_to_sign = "\n".join(
        [http_method, http_uri, ACRCLOUD_ACCESS_KEY, data_type, signature_version, timestamp]
    )
    signature = base64.b64encode(
        hmac.new(
            ACRCLOUD_ACCESS_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    data = {
        "access_key": ACRCLOUD_ACCESS_KEY,
        "sample_bytes": str(segment_path.stat().st_size),
        "timestamp": timestamp,
        "signature": signature,
        "data_type": data_type,
        "signature_version": signature_version,
    }

    try:
        with segment_path.open("rb") as sample_file:
            response = requests.post(
                f"https://{ACRCLOUD_HOST}{http_uri}",
                files={"sample": sample_file},
                data=data,
                timeout=15,
            )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print("[acr] request_failed =", str(exc))
        return None

    music_items = payload.get("metadata", {}).get("music", [])
    if not music_items:
        return None

    best = music_items[0]
    artists = best.get("artists") or []
    artist = ", ".join(item.get("name", "") for item in artists if item.get("name")).strip()
    title = str(best.get("title") or "").strip()
    score = int(best.get("score") or 0)

    if not title or score <= 60:
        return None

    spotify_meta = (best.get("external_metadata") or {}).get("spotify") or {}
    acr_spotify_track_id = (spotify_meta.get("track") or {}).get("id") or ""
    acr_spotify_artist_ids = [
        a.get("id", "") for a in (spotify_meta.get("artists") or []) if a.get("id")
    ]

    return {
        "artist": artist,
        "title": title,
        "score": score,
        "raw": json.dumps(best, ensure_ascii=False),
        "source": "acr",
        "acr_spotify_track_id": acr_spotify_track_id,
        "acr_spotify_artist_ids": acr_spotify_artist_ids,
    }
