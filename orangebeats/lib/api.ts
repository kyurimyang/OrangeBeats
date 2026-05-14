// Empty string = same-origin (served from FastAPI). Set NEXT_PUBLIC_API_URL
// to an explicit URL only when running Next.js dev server separately.
const API = process.env.NEXT_PUBLIC_API_URL ?? '';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    const e = new Error((err.detail as string) ?? r.statusText) as Error & { status: number };
    e.status = r.status;
    throw e;
  }
  return r.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface LoginStatus { logged_in: boolean; reason?: string }

export function checkLoginStatus() {
  return apiFetch<LoginStatus>('/spotify/login-status');
}

export function getSpotifyLoginUrl(frontendOrigin: string) {
  return apiFetch<{ login_url: string; state: string }>(
    `/spotify/login?frontend_origin=${encodeURIComponent(frontendOrigin)}`
  );
}

export function logout() {
  return apiFetch<{ success: boolean; logged_in: boolean }>('/spotify/logout', { method: 'POST' });
}

// ── Analysis ─────────────────────────────────────────────────────────────────

export interface SpotifyCandidate {
  spotify_track_id: string;
  spotify_uri: string;
  spotify_title: string;
  spotify_artist: string;
  album_image: string | null;
  confidence: number;
}

export interface MatchResult {
  input_artist: string;
  input_title: string;
  matched: boolean;
  spotify_track_id: string | null;
  spotify_uri: string | null;
  spotify_title: string | null;
  spotify_artist: string | null;
  album_image: string | null;
  confidence: number;
  confidence_label: 'high' | 'mid' | 'low' | 'failed';
  top_candidates: SpotifyCandidate[];
}

export interface AnalyzeResponse {
  success: boolean;
  analysis_state: string;
  needs_fallback: boolean;
  next_action: string;
  message: string;
  playlist_name: string;
  youtube_url: string;
  youtube_title: string;
  thumbnail_url?: string;
  title_mode?: string;
  mode: string;
  extracted_count: number;
  spotify_candidate_count: number;
  results?: MatchResult[];
  songs: Array<{ artist: string; title: string; source: string }>;
  timings: Record<string, number>;
}

export function analyzeYoutube(data: {
  youtube_url: string;
  title_mode: string;
  playlist_name?: string;
  mode?: string;
}) {
  return apiFetch<AnalyzeResponse>('/playlist/analyze-youtube', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// fallback (OCR/ACR) — routes through /playlist/analyze-youtube so Spotify
// matching is included and the response shape is identical to analyzeYoutube.
export function fallbackAnalysis(data: {
  youtube_url: string;
  mode: 'ocr' | 'acr';
}) {
  return apiFetch<AnalyzeResponse>('/playlist/analyze-youtube', {
    method: 'POST',
    body: JSON.stringify({ youtube_url: data.youtube_url, mode: data.mode }),
  });
}

// ── Playlist creation ────────────────────────────────────────────────────────

// Matches the actual backend response from /playlist/create-selected
export interface CreatePlaylistResponse {
  success: boolean;
  playlist_id?: string;
  playlist_url?: string;
  added_count?: number;
  deduped_count?: number;
  cover_upload_status?: string;
  cover_upload_error?: string | null;
  detail?: string;
}

export function createPlaylist(data: {
  youtube_url: string;
  youtube_title: string;
  title_mode: string;
  playlist_name: string;
  track_uris: string[];
  thumbnail_url?: string;
}) {
  return apiFetch<CreatePlaylistResponse>('/playlist/create-selected', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
