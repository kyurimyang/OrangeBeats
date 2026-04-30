const backendBaseUrlInput = document.getElementById("backendBaseUrl");
const youtubeUrlInput = document.getElementById("youtubeUrl");
const playlistNameInput = document.getElementById("playlistName");
const modeSelect = document.getElementById("mode");
const titleModeSelect = document.getElementById("titleMode");

const spotifyLoginBtn = document.getElementById("spotifyLoginBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const createPlaylistBtn = document.getElementById("createPlaylistBtn");
const openSpotifyBtn = document.getElementById("openSpotifyBtn");

const statusBox = document.getElementById("statusBox");
const resultBox = document.getElementById("resultBox");
const errorBox = document.getElementById("errorBox");
const noticeBoard = document.getElementById("noticeBoard");
const playlistLinkHint = document.getElementById("playlistLinkHint");

const songsList = document.getElementById("songsList");
const matchedSongsList = document.getElementById("matchedSongsList");
const lowConfidenceSongsList = document.getElementById("lowConfidenceSongsList");
const failedSongsList = document.getElementById("failedSongsList");

const summarySuccess = document.getElementById("summarySuccess");
const summaryMessage = document.getElementById("summaryMessage");
const summaryYoutubeTitle = document.getElementById("summaryYoutubeTitle");
const summaryPlaylistName = document.getElementById("summaryPlaylistName");

const overviewExtractedCount = document.getElementById("overviewExtractedCount");
const overviewMatchedCount = document.getElementById("overviewMatchedCount");
const overviewUnmatchedCount = document.getElementById("overviewUnmatchedCount");
const overviewLowConfidenceCount = document.getElementById("overviewLowConfidenceCount");
const overviewMatchingRate = document.getElementById("overviewMatchingRate");
const overviewTotalElapsed = document.getElementById("overviewTotalElapsed");

const infoStage = document.getElementById("infoStage");
const infoOcrUsed = document.getElementById("infoOcrUsed");
const infoExtractedCount = document.getElementById("infoExtractedCount");
const infoMatchedCount = document.getElementById("infoMatchedCount");
const infoUnmatchedCount = document.getElementById("infoUnmatchedCount");
const infoLowConfidenceCount = document.getElementById("infoLowConfidenceCount");
const infoMatchingRate = document.getElementById("infoMatchingRate");
const infoAnalysisElapsed = document.getElementById("infoAnalysisElapsed");
const infoSpotifyElapsed = document.getElementById("infoSpotifyElapsed");
const infoTotalElapsed = document.getElementById("infoTotalElapsed");
const infoCoverStatus = document.getElementById("infoCoverStatus");

const loginSummaryText = document.getElementById("loginSummaryText");
const recentActionText = document.getElementById("recentActionText");
const recentYoutubeTitle = document.getElementById("recentYoutubeTitle");
const recentStageText = document.getElementById("recentStageText");
const BACKEND_BASE_URL_STORAGE_KEY = "orangebeats.backendBaseUrl";

function inferBackendBaseUrl() {
  const persisted = window.localStorage.getItem(BACKEND_BASE_URL_STORAGE_KEY)?.trim();
  if (persisted) {
    return persisted.replace(/\/$/, "");
  }

  const currentUrl = new URL(window.location.href);
  if (currentUrl.protocol.startsWith("http")) {
    return `${currentUrl.protocol}//${currentUrl.hostname}:8000`;
  }

  return "http://127.0.0.1:8000";
}

function initializeBackendBaseUrl() {
  if (!backendBaseUrlInput) {
    return;
  }

  backendBaseUrlInput.value = inferBackendBaseUrl();
  backendBaseUrlInput.addEventListener("change", () => {
    const normalized = backendBaseUrlInput.value.trim().replace(/\/$/, "");
    backendBaseUrlInput.value = normalized;
    window.localStorage.setItem(BACKEND_BASE_URL_STORAGE_KEY, normalized);
  });
}

function getBackendBaseUrl() {
  return backendBaseUrlInput.value.trim().replace(/\/$/, "");
}

function getYoutubeUrl() {
  return youtubeUrlInput.value.trim();
}

function getMode() {
  const modeMap = {
    auto: "text",
    text_only: "text",
    ocr_only: "ocr",
  };
  return modeMap[modeSelect.value] || modeSelect.value || "text";
}

function getTitleMode() {
  return titleModeSelect.value;
}

function getPlaylistName() {
  return playlistNameInput.value.trim();
}

function buildApiUrl(path) {
  const baseUrl = getBackendBaseUrl();
  if (!baseUrl) {
    throw new Error("Backend Base URL을 입력해 주세요.");
  }
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setText(element, value, fallback = "-") {
  if (!element) {
    return;
  }
  const normalized = value === undefined || value === null || value === "" ? fallback : String(value);
  element.textContent = normalized;
}

function setStatus(type, message) {
  statusBox.className = `status-box ${type}`;
  statusBox.textContent = message;
}

function setButtonsDisabled(disabled) {
  spotifyLoginBtn.disabled = disabled;
  analyzeBtn.disabled = disabled;
  createPlaylistBtn.disabled = disabled;
}

function renderJson(data) {
  resultBox.textContent = JSON.stringify(data, null, 2);
}

function resetErrorBox() {
  errorBox.className = "error-box is-empty";
  errorBox.textContent = "현재 에러가 없습니다.";
}

function renderErrorBox(message) {
  if (!message) {
    resetErrorBox();
    return;
  }
  errorBox.className = "error-box";
  errorBox.textContent = message;
}

function setPlaylistLink(url) {
  if (url) {
    openSpotifyBtn.hidden = false;
    openSpotifyBtn.href = url;
    openSpotifyBtn.classList.remove("is-disabled");
    openSpotifyBtn.setAttribute("aria-disabled", "false");
    playlistLinkHint.textContent = "Spotify 링크가 준비되었습니다.";
    return;
  }

  openSpotifyBtn.hidden = true;
  openSpotifyBtn.href = "#";
  openSpotifyBtn.classList.add("is-disabled");
  openSpotifyBtn.setAttribute("aria-disabled", "true");
  playlistLinkHint.textContent = "아직 생성된 플레이리스트 링크가 없습니다.";
}

function formatScore(value) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}

function formatPercent(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

function formatDurationMs(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  if (value < 1000) {
    return `${Math.max(0, Math.round(value))}ms`;
  }
  const seconds = value / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return `${minutes}m ${remainder}s`;
}

function formatMatchStatus(value) {
  const statusMap = {
    matched: "자동 매칭됨",
    probable_match: "표기 차이 가능성",
    review_needed: "확인 필요",
    unmatched: "매칭 실패",
  };
  return statusMap[value] || value || "-";
}

function formatScoreDetail(detail) {
  if (!detail || typeof detail !== "object") {
    return "";
  }
  const parts = [
    ["title", detail.title_score],
    ["artist", detail.artist_score],
    ["token", detail.token_score],
    ["version_penalty", detail.version_penalty],
  ]
    .filter(([, value]) => typeof value === "number")
    .map(([label, value]) => `${label}: ${Math.round(value * 100)}%`);
  return parts.length ? parts.join(" / ") : "";
}

function getSongTitle(item) {
  return item?.title || item?.input?.title || item?.song?.title || "(제목 없음)";
}

function getSongArtist(item) {
  return item?.artist || item?.input?.artist || item?.song?.artist || "(아티스트 없음)";
}

function renderSongCollection({ container, items, emptyMessage, cardClass, renderMeta }) {
  const normalizedItems = safeArray(items);
  if (!container) {
    return;
  }

  if (normalizedItems.length === 0) {
    container.className = "result-list empty-state";
    container.textContent = emptyMessage;
    return;
  }

  container.className = "result-list";
  container.innerHTML = normalizedItems
    .map((item, index) => {
      const title = getSongTitle(item);
      const artist = getSongArtist(item);
      return `
        <article class="song-card ${cardClass}">
          <div class="song-card-header">${index + 1}. ${escapeHtml(title)} - ${escapeHtml(artist)}</div>
          <div class="song-card-meta">${renderMeta(item)}</div>
        </article>
      `;
    })
    .join("");
}

function renderExtractedSongs(items) {
  renderSongCollection({
    container: songsList,
    items,
    emptyMessage: "아직 추출된 곡이 없습니다.",
    cardClass: "",
    renderMeta: (item) => {
      const source = item?.source || "unknown";
      return `source: ${escapeHtml(source)}`;
    },
  });
}

function renderMatchedSongs(items) {
  renderSongCollection({
    container: matchedSongsList,
    items,
    emptyMessage: "매칭 성공 곡이 여기에 표시됩니다.",
    cardClass: "matched-card",
    renderMeta: (item) => {
      const matchedTitle = item?.matched_title || "-";
      const matchedArtists = safeArray(item?.matched_artists).join(", ") || "-";
      const userMessage = item?.user_message || "자동 매칭되었습니다.";
      const status = formatMatchStatus(item?.match_status);
      const scoreDetail = formatScoreDetail(item?.score_detail);
      return `Spotify: ${escapeHtml(matchedTitle)} / ${escapeHtml(matchedArtists)}<br />status: ${escapeHtml(status)}<br />score: ${escapeHtml(formatScore(item?.score))}<br />message: ${escapeHtml(userMessage)}${scoreDetail ? `<br />detail: ${escapeHtml(scoreDetail)}` : ""}`;
    },
  });
}

function renderLowConfidenceSongs(items) {
  renderSongCollection({
    container: lowConfidenceSongsList,
    items,
    emptyMessage: "저신뢰 곡이 여기에 표시됩니다.",
    cardClass: "low-card",
    renderMeta: (item) => {
      const matchedTitle = item?.matched_title || "-";
      const matchedArtists = safeArray(item?.matched_artists).join(", ") || "-";
      const reason = item?.low_confidence_reason || item?.reason || item?.llm_reason || "review_needed";
      const userMessage = item?.user_message || reason;
      const status = formatMatchStatus(item?.match_status);
      const scoreDetail = formatScoreDetail(item?.score_detail);
      return `Spotify: ${escapeHtml(matchedTitle)} / ${escapeHtml(matchedArtists)}<br />status: ${escapeHtml(status)}<br />score: ${escapeHtml(formatScore(item?.score))}<br />reason: ${escapeHtml(reason)}<br />message: ${escapeHtml(userMessage)}${scoreDetail ? `<br />detail: ${escapeHtml(scoreDetail)}` : ""}`;
    },
  });
}

function renderFailedSongs(items) {
  renderSongCollection({
    container: failedSongsList,
    items,
    emptyMessage: "매칭 실패 곡이 여기에 표시됩니다.",
    cardClass: "failed-card",
    renderMeta: (item) => {
      const reason = item?.unmatched_reason || item?.reason || "unknown";
      const userMessage = item?.user_message || reason;
      const status = formatMatchStatus(item?.match_status || "unmatched");
      const topCandidate = safeArray(item?.top_candidates)[0];
      const topCandidateText = topCandidate
        ? `<br />top candidate: ${escapeHtml(topCandidate.name || "-")} / ${escapeHtml(safeArray(topCandidate.artists).join(", ") || "-")} (${escapeHtml(formatScore(topCandidate.score))})`
        : "";
      return `status: ${escapeHtml(status)}<br />reason: ${escapeHtml(reason)}<br />message: ${escapeHtml(userMessage)}${topCandidateText}`;
    },
  });
}

function resetResultLists() {
  renderExtractedSongs([]);
  renderMatchedSongs([]);
  renderLowConfidenceSongs([]);
  renderFailedSongs([]);
}

function extractList(data, flatKey) {
  return safeArray(data?.[flatKey] ?? data?.spotify_result?.[flatKey]);
}

function extractNumber(data, key, fallback = 0) {
  const value = data?.[key] ?? data?.spotify_result?.[key];
  return typeof value === "number" ? value : fallback;
}

function extractTiming(data, key) {
  const value = data?.timings?.[key] ?? data?.[key] ?? data?.youtube_result?.timings?.[key];
  return typeof value === "number" ? value : null;
}

function extractMatchingRate(data) {
  const explicit = data?.matching_rate ?? data?.spotify_result?.matching_rate;
  if (typeof explicit === "number") {
    return explicit;
  }

  const matched = extractNumber(data, "matched_count");
  const lowConfidence = extractNumber(data, "low_confidence_count");
  const unmatched = extractNumber(data, "unmatched_count");
  const total = matched + lowConfidence + unmatched;
  if (total <= 0) {
    return null;
  }
  return Math.round(((matched + lowConfidence) / total) * 1000) / 10;
}

function getYoutubeTitle(data) {
  return data?.youtube_title ?? data?.youtube_result?.youtube_title;
}

function getExtractedSongs(data) {
  return safeArray(data?.songs ?? data?.youtube_result?.songs);
}

function renderSummary(data) {
  setText(summarySuccess, data?.success, "-");
  setText(summaryMessage, data?.message, "-");
  setText(summaryYoutubeTitle, getYoutubeTitle(data), "-");
  setText(summaryPlaylistName, data?.playlist_name, "-");
}

function renderOverview(data) {
  setText(overviewExtractedCount, data?.extracted_count ?? getExtractedSongs(data).length, "0");
  setText(overviewMatchedCount, extractNumber(data, "matched_count"), "0");
  setText(overviewUnmatchedCount, extractNumber(data, "unmatched_count"), "0");
  setText(overviewLowConfidenceCount, extractNumber(data, "low_confidence_count"), "0");
  setText(overviewMatchingRate, formatPercent(extractMatchingRate(data)), "-");
  setText(overviewTotalElapsed, formatDurationMs(extractTiming(data, "total_elapsed_ms")), "-");
}

function renderQuickInfo(data) {
  setText(infoStage, data?.selected_stage ?? data?.youtube_result?.selected_stage, "-");
  setText(infoOcrUsed, data?.ocr_used ?? data?.youtube_result?.ocr_used, "-");
  setText(infoExtractedCount, data?.extracted_count ?? getExtractedSongs(data).length, "0");
  setText(infoMatchedCount, extractNumber(data, "matched_count"), "0");
  setText(infoUnmatchedCount, extractNumber(data, "unmatched_count"), "0");
  setText(infoLowConfidenceCount, extractNumber(data, "low_confidence_count"), "0");

  setText(infoMatchingRate, formatPercent(extractMatchingRate(data)), "-");
  setText(infoAnalysisElapsed, formatDurationMs(extractTiming(data, "analysis_elapsed_ms")), "-");
  setText(infoSpotifyElapsed, formatDurationMs(extractTiming(data, "spotify_elapsed_ms")), "-");
  setText(infoTotalElapsed, formatDurationMs(extractTiming(data, "total_elapsed_ms")), "-");
  setText(infoCoverStatus, data?.cover_upload_status, "-");
}

function renderRecentSummary(data, actionLabel) {
  setText(recentActionText, actionLabel, "대기 중");
  setText(recentYoutubeTitle, getYoutubeTitle(data), "-");
  setText(recentStageText, data?.selected_stage ?? data?.youtube_result?.selected_stage, "-");
}

function clearResponseState() {
  renderSummary({});
  renderOverview({});
  renderQuickInfo({});
  resetResultLists();
  setPlaylistLink(null);
  renderJson({ message: "아직 결과가 없습니다." });
  resetErrorBox();
}

async function handleApiResponse(response) {
  let data = null;

  try {
    data = await response.json();
  } catch (error) {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    throw new Error("JSON 응답 파싱에 실패했습니다.");
  }

  if (!response.ok) {
    const detail = data?.detail || data?.message || `HTTP ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return data;
}

async function refreshLoginStatus() {
  try {
    const response = await fetch(buildApiUrl("/spotify/login-status"), {
      credentials: "include",
    });
    const data = await handleApiResponse(response);
    setText(loginSummaryText, data?.logged_in ? "로그인 완료" : "미로그인", "확인 전");
  } catch (error) {
    setText(loginSummaryText, "확인 실패", "확인 전");
  }
}

function updateNoticeFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const loginStatus = params.get("spotify_login");
  const reason = params.get("reason");

  if (loginStatus === "success") {
    noticeBoard.textContent = "Spotify 로그인이 완료되었습니다. 이제 분석 또는 플레이리스트 생성을 테스트할 수 있습니다.";
    setStatus("success", "Spotify 로그인 완료. 원하는 작업을 실행해 주세요.");
    return;
  }

  if (loginStatus === "failed") {
    noticeBoard.textContent = `Spotify 로그인 콜백이 실패했습니다. reason=${reason || "unknown"}`;
    setStatus("error", `Spotify 로그인 실패: ${reason || "unknown"}`);
    renderErrorBox(`Spotify 로그인 실패\nreason=${reason || "unknown"}`);
  }
}

function prepareRunUi(loadingMessage) {
  setButtonsDisabled(true);
  setStatus("loading", loadingMessage);
  renderErrorBox(null);
  renderMatchedSongs([]);
  renderLowConfidenceSongs([]);
  renderFailedSongs([]);
  setPlaylistLink(null);
}

spotifyLoginBtn.addEventListener("click", async () => {
  try {
    setButtonsDisabled(true);
    setStatus("loading", "Spotify 로그인 URL을 가져오는 중입니다.");

    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("spotify_login");
    currentUrl.searchParams.delete("reason");
    const frontendRedirect = currentUrl.toString();
    const response = await fetch(
      buildApiUrl(`/spotify/login?frontend_origin=${encodeURIComponent(frontendRedirect)}`),
      {
        credentials: "include",
      }
    );
    const data = await handleApiResponse(response);

    const authUrl = data?.auth_url || data?.login_url;

    if (!authUrl) {
      throw new Error("Spotify auth_url을 받지 못했습니다.");
    }

    window.location.href = authUrl;
  } catch (error) {
    setStatus("error", `Spotify 로그인 준비 실패: ${error.message}`);
    renderErrorBox(`Spotify 로그인 준비 실패\n${error.message}`);
    setButtonsDisabled(false);
  }
});

analyzeBtn.addEventListener("click", async () => {
  const youtubeUrl = getYoutubeUrl();
  if (!youtubeUrl) {
    setStatus("error", "YouTube URL을 먼저 입력해 주세요.");
    renderErrorBox("YouTube URL이 비어 있습니다.");
    return;
  }

  try {
    prepareRunUi("YouTube 분석을 진행하는 중입니다.");

    const query = new URLSearchParams({
      url: youtubeUrl,
      mode: getMode(),
    });

    const response = await fetch(buildApiUrl(`/youtube/analyze?${query.toString()}`));
    const data = await handleApiResponse(response);

    renderJson(data);
    renderSummary({
      success: data?.success,
      message: "YouTube 분석 결과입니다.",
      youtube_title: data?.youtube_title,
      playlist_name: getPlaylistName() || "-",
    });
    renderOverview({
      extracted_count: getExtractedSongs(data).length,
      matched_count: 0,
      unmatched_count: 0,
      low_confidence_count: 0,
      timings: data?.timings,
    });
    renderQuickInfo({
      selected_stage: data?.selected_stage,
      ocr_used: data?.ocr_used,
      extracted_count: getExtractedSongs(data).length,
      matched_count: 0,
      unmatched_count: 0,
      low_confidence_count: 0,
      timings: data?.timings,
      cover_upload_status: "-",
    });
    renderExtractedSongs(getExtractedSongs(data));
    renderRecentSummary(data, "YouTube 분석");
    setStatus("success", `분석 완료: selected_stage=${data?.selected_stage ?? "-"}`);
  } catch (error) {
    setStatus("error", `분석 실패: ${error.message}`);
    renderErrorBox(`분석 실패\n${error.message}`);
    renderJson({ error: error.message });
    resetResultLists();
    renderRecentSummary({}, "분석 실패");
  } finally {
    setButtonsDisabled(false);
  }
});

createPlaylistBtn.addEventListener("click", async () => {
  const youtubeUrl = getYoutubeUrl();
  if (!youtubeUrl) {
    setStatus("error", "YouTube URL을 먼저 입력해 주세요.");
    renderErrorBox("YouTube URL이 비어 있습니다.");
    return;
  }

  try {
    prepareRunUi("Spotify 플레이리스트를 생성하는 중입니다.");

    const payload = {
      url: youtubeUrl,
      mode: getMode(),
      title_mode: getTitleMode(),
      playlist_name: getPlaylistName(),
    };

    const response = await fetch(buildApiUrl("/playlist/from-youtube"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await handleApiResponse(response);

    renderJson(data);
    renderSummary(data);
    renderOverview(data);
    renderQuickInfo(data);
    renderExtractedSongs(getExtractedSongs(data));
    renderMatchedSongs(extractList(data, "matched"));
    renderLowConfidenceSongs(extractList(data, "low_confidence"));
    renderFailedSongs(extractList(data, "unmatched"));
    setPlaylistLink(data?.playlist_url || data?.spotify_result?.playlist_url || null);
    renderRecentSummary(data, "플레이리스트 생성");

    const errorMessages = [
      data?.add_tracks_error,
      data?.cover_upload_error,
      data?.message && data?.success === false ? data.message : null,
    ].filter(Boolean);
    renderErrorBox(errorMessages.join("\n\n"));

    if (data?.success) {
      setStatus("success", data?.message || "플레이리스트 생성이 완료되었습니다.");
    } else {
      setStatus("error", data?.message || "플레이리스트 생성 결과를 확인해 주세요.");
    }
  } catch (error) {
    setStatus("error", `플레이리스트 생성 실패: ${error.message}`);
    renderErrorBox(`플레이리스트 생성 실패\n${error.message}`);
    renderJson({ error: error.message });
    renderMatchedSongs([]);
    renderLowConfidenceSongs([]);
    renderFailedSongs([]);
    setPlaylistLink(null);
    renderRecentSummary({}, "생성 실패");
  } finally {
    setButtonsDisabled(false);
  }
});

initializeBackendBaseUrl();
clearResponseState();
updateNoticeFromQuery();
refreshLoginStatus();
