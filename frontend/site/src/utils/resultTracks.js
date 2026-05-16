const SPOTIFY_TRACK_ID_RE = /^[0-9A-Za-z]{22}$/;

/** YouTube 텍스트 분석(설명·댓글 등) 결과일 때만 input from 줄 표시 */
export function isYoutubeTextExtraction(data) {
  if (!data || typeof data !== "object") return false;
  const mode = String(data.mode ?? data.extraction_mode ?? "text")
    .trim()
    .toLowerCase();
  if (mode === "ocr" || mode === "acr") return false;
  if (data.ocr_used === true || data.acr_used === true) return false;
  const stage = String(data.selected_stage ?? "")
    .trim()
    .toLowerCase();
  if (stage === "ocr" || stage === "acr") return false;
  return true;
}

/** YouTube에서 추출한 `from Title — Artist` (input이 있으면 항상 표시) */
export function buildInputFromParts(inputTitle, inputArtist) {
  const title = String(inputTitle || "").trim();
  const artist = String(inputArtist || "").trim();
  if (!title && !artist) return null;
  return { title, artist };
}

function pickDirectionalLeftRight(songRow) {
  const left = String(songRow?.left ?? "").trim();
  const right = String(songRow?.right ?? "").trim();
  if (!left && !right) return null;
  const dir = String(songRow?.global_direction ?? songRow?.line_direction ?? "").trim();
  if (dir === "artist_title") {
    return { title: right, artist: left };
  }
  return { title: left, artist: right };
}

/** YouTube 원문 표기 — 스왑·보정 전 텍스트 우선 */
export function pickYoutubeInputFields(item, songRow = {}) {
  const orig = songRow?.original_input;
  if (orig && typeof orig === "object") {
    const title = String(orig.title ?? "").trim();
    const artist = String(orig.artist ?? "").trim();
    if (title || artist) return { title, artist };
  }

  if (songRow?.swap_applied) {
    const directional = pickDirectionalLeftRight(songRow);
    if (directional && (directional.title || directional.artist)) {
      return directional;
    }
  }

  const itemTitle = String(item?.input_title ?? item?.inputTitle ?? "").trim();
  const itemArtist = String(item?.input_artist ?? item?.inputArtist ?? "").trim();
  if (itemTitle || itemArtist) {
    return { title: itemTitle, artist: itemArtist };
  }

  const directional = pickDirectionalLeftRight(songRow);
  if (directional && (directional.title || directional.artist)) {
    return directional;
  }

  const rowTitle = String(songRow?.title ?? "").trim();
  const rowArtist = String(songRow?.artist ?? "").trim();
  if (rowTitle || rowArtist) {
    return { title: rowTitle, artist: rowArtist };
  }

  const raw = String(songRow?.raw ?? "").trim();
  if (raw) {
    return { title: raw, artist: "" };
  }

  return { title: "", artist: "" };
}

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

const NON_SONG_RE = /^(intro|outro|skit|interlude)$/i;
const NON_SONG_CONTAINS_RE = /광고\s*제거|ad\s*remove[d]?|sponsor/i;

export function normalizeTracks(data, options = {}) {
  const showInputFrom = options.showInputFrom === true;
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
    const youtubeInput = pickYoutubeInputFields(item, songRow);
    const inputTitle = youtubeInput.title;
    const inputArtist = youtubeInput.artist;
    const trackName = spotifyTitle || inputTitle || "제목 없음";
    const performerLine = spotifyArtist || inputArtist || "아티스트 미상";
    const inputFrom = showInputFrom ? buildInputFromParts(inputTitle, inputArtist) : null;
    const confidenceLabel = String(item.confidence_label ?? item.confidenceLabel ?? "")
      .trim()
      .toLowerCase();
    const spotifyUri = pickSpotifyUriFromResultRow(item);
    return {
      id: `${spotifyUri || item.spotify_track_id || "track"}-${index}`,
      title: trackName,
      artist: performerLine,
      inputFrom,
      cover: pickCoverFromResultRow(item),
      spotifyUri,
      confidenceLabel,
      sourceRow: item,
    };
  }).filter((track) => {
    if (track.artist !== "아티스트 미상") return true;
    if (NON_SONG_RE.test(track.title)) return false;
    if (NON_SONG_CONTAINS_RE.test(track.title)) return false;
    return true;
  });
}

export function fillMissingArtists(tracks) {
  const UNKNOWN = "아티스트 미상";
  const knownArtists = tracks.map((t) => t.artist).filter((a) => a && a !== UNKNOWN);
  if (!knownArtists.length) return tracks;

  const freq = {};
  for (const a of knownArtists) freq[a] = (freq[a] || 0) + 1;
  const top = Object.entries(freq).sort((a, b) => b[1] - a[1])[0];
  if (top[1] / knownArtists.length < 0.5) return tracks;

  return tracks.map((t) => t.artist === UNKNOWN ? { ...t, artist: top[0] } : t);
}
