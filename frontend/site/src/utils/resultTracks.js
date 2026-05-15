const SPOTIFY_TRACK_ID_RE = /^[0-9A-Za-z]{22}$/;

function firstHttpImageUrl(value) {
  if (typeof value !== "string") return "";
  const u = value.trim();
  return u.startsWith("http://") || u.startsWith("https://") ? u : "";
}

/** API 행 → Spotify `spotify:track:` URI (id·웹 URL·후보도 포함) */
export function pickSpotifyUriFromResultRow(item) {
  if (!item || typeof item !== "object") return "";

  const direct = String(item.spotify_uri ?? item.spotifyUri ?? item.uri ?? "").trim();
  if (direct.startsWith("spotify:track:")) return direct;
  if (direct.includes("open.spotify.com") && direct.includes("/track/")) {
    const m = direct.match(/\/(?:intl-[a-z]{2}\/)?track\/([0-9A-Za-z]{22})/);
    if (m) return `spotify:track:${m[1]}`;
  }

  const tid = String(item.spotify_track_id ?? item.spotifyTrackId ?? item.id ?? "").trim();
  if (SPOTIFY_TRACK_ID_RE.test(tid)) return `spotify:track:${tid}`;

  const cands = item.top_candidates;
  if (Array.isArray(cands)) {
    for (const c of cands) {
      const u = pickSpotifyUriFromResultRow(c);
      if (u) return u;
    }
  }

  return direct.startsWith("spotify:") ? direct : "";
}

/** 플레이리스트 생성용 URI 목록 (중복 제거) */
export function collectPlaylistTrackUris(tracks) {
  const seen = new Set();
  const uris = [];
  for (const track of tracks || []) {
    const row = track?.sourceRow && typeof track.sourceRow === "object" ? track.sourceRow : track;
    const uri = pickSpotifyUriFromResultRow(row) || String(track?.spotifyUri || "").trim();
    if (!uri || seen.has(uri)) continue;
    seen.add(uri);
    uris.push(uri);
  }
  return uris;
}

/** API 행에서 앨범 커버 URL — 필드명 변형·top_candidates 보조 */
export function pickCoverFromResultRow(item) {
  if (!item || typeof item !== "object") return "";
  const direct =
    firstHttpImageUrl(item.album_image) ||
    firstHttpImageUrl(item.albumImage) ||
    firstHttpImageUrl(item.cover_url) ||
    firstHttpImageUrl(item.coverUrl);
  if (direct) return direct;
  if (Array.isArray(item.images)) {
    for (const im of item.images) {
      const u = firstHttpImageUrl(typeof im === "string" ? im : im?.url);
      if (u) return u;
    }
  }
  const cands = item.top_candidates;
  if (!Array.isArray(cands)) return "";
  for (const c of cands) {
    if (!c || typeof c !== "object") continue;
    const u =
      firstHttpImageUrl(c.album_image) ||
      firstHttpImageUrl(c.albumImage) ||
      firstHttpImageUrl(c.cover_url) ||
      firstHttpImageUrl(c.coverUrl);
    if (u) return u;
  }
  return "";
}

export function normalizeTracks(data) {
  const rows = Array.isArray(data?.results) ? data.results : [];
  const songs = Array.isArray(data?.songs)
    ? data.songs
    : Array.isArray(data?.extracted_songs)
      ? data.extracted_songs
      : [];
  return rows.map((item, index) => {
    const uiTrack = String(item.ui_track_line ?? item.uiTrackLine ?? "").trim();
    const uiArtist = String(item.ui_artist_line ?? item.uiArtistLine ?? "").trim();
    const spotifyTitle =
      uiTrack || String(item.spotify_title ?? item.spotifyTitle ?? "").trim();
    const spotifyArtist =
      uiArtist || String(item.spotify_artist ?? item.spotifyArtist ?? "").trim();
    const songRow = songs[index] || {};
    const corr =
      songRow.corrected_input && typeof songRow.corrected_input === "object"
        ? songRow.corrected_input
        : null;
    const inputTitle = String(
      (corr?.title != null && String(corr.title).trim() !== "" ? corr.title : null) ??
        songRow.title ??
        item.input_title ??
        "",
    ).trim();
    const inputArtist = String(
      (corr?.artist != null && String(corr.artist).trim() !== "" ? corr.artist : null) ??
        songRow.artist ??
        item.input_artist ??
        "",
    ).trim();
    const trackName = spotifyTitle || inputTitle || "제목 없음";
    const performerLine = spotifyArtist || inputArtist || "아티스트 미상";
    const confidenceLabel = String(item.confidence_label ?? item.confidenceLabel ?? "")
      .trim()
      .toLowerCase();
    const spotifyUri = pickSpotifyUriFromResultRow(item);
    return {
      id: `${spotifyUri || item.spotify_track_id || "track"}-${index}`,
      title: trackName,
      artist: performerLine,
      cover: pickCoverFromResultRow(item),
      spotifyUri,
      confidenceLabel,
      sourceRow: item,
    };
  });
}
