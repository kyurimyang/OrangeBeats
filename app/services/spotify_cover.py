import requests


class SpotifyCoverUploadError(Exception):
    pass


def upload_playlist_cover_image(access_token: str, playlist_id: str, image_base64: str) -> None:
    print("### NEW spotify_cover.py loaded ###")

    if not access_token:
        raise SpotifyCoverUploadError("Spotify access token이 없습니다.")
    if not playlist_id:
        raise SpotifyCoverUploadError("playlist_id가 없습니다.")
    if not image_base64:
        raise SpotifyCoverUploadError("업로드할 이미지 데이터가 없습니다.")

    body = image_base64.encode("utf-8")

    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/images"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "image/jpeg",
        "Content-Length": str(len(body)),
    }

    session = requests.Session()
    response = session.put(
        url,
        headers=headers,
        data=body,
        timeout=30,
    )

    if response.status_code not in (200, 202):
        raise SpotifyCoverUploadError(
            f"Spotify 커버 업로드 실패: {response.status_code} / {response.text}"
        )