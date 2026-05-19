/** 002_URL — Playlist URL 입력 페이지 */
export const SPOTIFY_CONNECT_REDIRECT_PATH = "/create";

export async function fetchSpotifyLoginStatus() {
  try {
    const res = await fetch("/spotify/login-status", { method: "GET", credentials: "include" });
    if (!res.ok) return { logged_in: false };
    return res.json();
  } catch {
    return { logged_in: false };
  }
}

export async function fetchSpotifyLoginUrl(redirectPath = SPOTIFY_CONNECT_REDIRECT_PATH) {
  const frontendRedirect = `${window.location.origin}${redirectPath}`;
  const loginEndpoint = `/spotify/login?frontend_origin=${encodeURIComponent(frontendRedirect)}`;
  const res = await fetch(loginEndpoint, { method: "GET", credentials: "include" });
  if (!res.ok) throw new Error("spotify_login_request_failed");
  const data = await res.json();
  if (!data?.login_url) throw new Error("spotify_login_url_missing");
  return data.login_url;
}

/** 로그인됐으면 002_URL(/create), 아니면 Spotify OAuth */
export async function startSpotifyConnect(redirectPath = SPOTIFY_CONNECT_REDIRECT_PATH) {
  const status = await fetchSpotifyLoginStatus();
  if (status?.logged_in) {
    window.location.assign(`${window.location.origin}${redirectPath}`);
    return;
  }
  const loginUrl = await fetchSpotifyLoginUrl(redirectPath);
  window.location.assign(loginUrl);
}
