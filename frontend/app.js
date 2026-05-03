const $ = (id) => document.getElementById(id);

const backendBaseUrlInput = $("backendBaseUrl");
const youtubeUrlInput = $("youtubeUrl");
const playlistNameInput = $("playlistName");
const modeSelect = $("mode");
const titleModeSelect = $("titleMode");

const spotifyLoginBtn = $("spotifyLoginBtn");
const analyzeBtn = $("analyzeBtn");
const createPlaylistBtn = $("createPlaylistBtn");
const openSpotifyBtn = $("openSpotifyBtn");
const selectAllBtn = $("selectAllBtn");
const clearAllBtn = $("clearAllBtn");
const selectRecommendedBtn = $("selectRecommendedBtn");
const useArtistAliasesCheckbox = $("useArtistAliasesCheckbox");
const clearArtistAliasesBtn = $("clearArtistAliasesBtn");
const createSelectedInlineBtn = $("createSelectedInlineBtn");
const inlineOpenSpotifyBtn = $("inlineOpenSpotifyBtn");

const statusBox = $("statusBox");
const resultBox = $("resultBox");
const errorBox = $("errorBox");
const noticeBoard = $("noticeBoard");
const playlistLinkHint = $("playlistLinkHint");
const inlinePlaylistHint = $("inlinePlaylistHint");
const candidateSummary = $("candidateSummary");
const songResultsList = $("songResultsList");
const debugHighlights = $("debugHighlights");

const qaForm = $("qaForm");
const qaTitle = $("qaTitle");
const qaAuthor = $("qaAuthor");
const qaCategory = $("qaCategory");
const qaContent = $("qaContent");
const qaRefreshBtn = $("qaRefreshBtn");
const qaList = $("qaList");
const qaDetail = $("qaDetail");

const BACKEND_BASE_URL_STORAGE_KEY = "orangebeats.backendBaseUrl";

let lastResultData = null;
let candidateResults = [];
let selectedQaId = null;

function inferBackendBaseUrl() {
  const persisted = window.localStorage.getItem(BACKEND_BASE_URL_STORAGE_KEY)?.trim();
  if (persisted) return persisted.replace(/\/$/, "");

  const currentUrl = new URL(window.location.href);
  if (currentUrl.protocol.startsWith("http")) {
    return `${currentUrl.protocol}//${currentUrl.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

function initializeBackendBaseUrl() {
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

function buildApiUrl(path) {
  const baseUrl = getBackendBaseUrl();
  if (!baseUrl) throw new Error("Backend Base URL을 입력해주세요.");
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

function getMode() {
  return modeSelect.value || "text";
}

function getPlaylistName() {
  return playlistNameInput.value.trim();
}

function getFrontendRedirectUrl() {
  const currentUrl = new URL(window.location.href);
  currentUrl.searchParams.delete("spotify_login");
  currentUrl.searchParams.delete("reason");

  if (currentUrl.protocol !== "file:") return currentUrl.toString();

  const backendUrl = new URL(getBackendBaseUrl() || "http://127.0.0.1:8000");
  return `${backendUrl.protocol}//${backendUrl.hostname}:5500/frontend/index.html`;
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

function setText(idOrElement, value, fallback = "-") {
  const element = typeof idOrElement === "string" ? $(idOrElement) : idOrElement;
  if (!element) return;
  element.textContent = value === undefined || value === null || value === "" ? fallback : String(value);
}

function setStatus(type, message) {
  statusBox.className = `status-box ${type}`;
  statusBox.textContent = message;
}

function setButtonsDisabled(disabled) {
  [spotifyLoginBtn, analyzeBtn, createPlaylistBtn, createSelectedInlineBtn, clearArtistAliasesBtn].forEach((button) => {
    button.disabled = disabled;
  });
}

function renderJson(data) {
  resultBox.textContent = JSON.stringify(data || {}, null, 2);
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
    playlistLinkHint.textContent = "Spotify 플레이리스트 링크가 준비되었습니다.";
    inlineOpenSpotifyBtn.hidden = false;
    inlineOpenSpotifyBtn.href = url;
    inlineOpenSpotifyBtn.classList.remove("is-disabled");
    inlineOpenSpotifyBtn.setAttribute("aria-disabled", "false");
    inlinePlaylistHint.textContent = "생성이 끝났습니다. Spotify에서 바로 확인할 수 있어요.";
    return;
  }
  openSpotifyBtn.hidden = true;
  openSpotifyBtn.href = "#";
  openSpotifyBtn.classList.add("is-disabled");
  openSpotifyBtn.setAttribute("aria-disabled", "true");
  playlistLinkHint.textContent = "아직 생성된 플레이리스트 링크가 없습니다.";
  inlineOpenSpotifyBtn.hidden = true;
  inlineOpenSpotifyBtn.href = "#";
  inlineOpenSpotifyBtn.classList.add("is-disabled");
  inlineOpenSpotifyBtn.setAttribute("aria-disabled", "true");
  inlinePlaylistHint.textContent = "후보를 고른 뒤 이 화면에서 바로 생성할 수 있습니다.";
}

function formatScore(value) {
  return typeof value === "number" && !Number.isNaN(value) ? `${Math.round(value * 100)}%` : "-";
}

function formatDurationMs(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  if (value < 1000) return `${Math.max(0, Math.round(value))}ms`;
  const seconds = value / 1000;
  return seconds < 60 ? `${seconds.toFixed(seconds < 10 ? 1 : 0)}s` : `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function labelForConfidence(label) {
  return {
    high: "자동 선택 추천",
    mid: "확인 후 선택",
    low: "주의 필요",
    failed: "후보 없음",
  }[label] || label || "-";
}

function labelForEvidence(key) {
  return {
    artist_alias_match: "가수 별칭 일치",
    artist_romanization_match: "가수 로마자 표기 근거",
    title_direct_match: "제목 직접/부분 일치",
    token_overlap: "토큰 겹침",
  }[key] || key || "-";
}

function labelForDecision(value) {
  return {
    auto_select_recommended: "자동 선택 추천",
    confirm_before_select: "확인 후 선택",
    selectable: "추가 후보로 유지",
    warning: "주의 필요",
    rejected: "제외됨",
  }[value] || value || "-";
}

function yesNo(value) {
  return value ? "적용됨" : "없음";
}

function percent(value) {
  return typeof value === "number" && !Number.isNaN(value) ? `${Math.round(value * 1000) / 10}%` : "-";
}

function renderEvidenceList(items, emptyText) {
  const normalized = safeArray(items);
  if (!normalized.length) return `<li>${escapeHtml(emptyText)}</li>`;
  return normalized.map((item) => `<li>${escapeHtml(labelForEvidence(item))}</li>`).join("");
}

function renderConfidenceDetail(item) {
  const detail = item.confidence_detail;
  if (!detail) return "";
  const titleEvidence = detail.title_evidence || {};
  const artistEvidence = detail.artist_evidence || {};
  const queryEvidence = detail.query_evidence || {};
  const metadataEvidence = detail.metadata_evidence || {};
  const riskPenalty = detail.risk_penalty || {};

  return `
    <details class="confidence-details">
      <summary>근거 보기</summary>
      <div class="detail-grid">
        <section>
          <h4>판정</h4>
          <p>상태: ${escapeHtml(labelForConfidence(item.confidence_label))}</p>
          <p>패턴: ${escapeHtml(detail.pattern || detail.match_status || "-")}</p>
          <p>최종 판단: ${escapeHtml(labelForDecision(detail.decision || detail.candidate_decision))}</p>
          <p>점수 상한: ${escapeHtml(percent(detail.score_cap))}</p>
        </section>
        <section>
          <h4>점수</h4>
          <p>제목 근거: ${escapeHtml(titleEvidence.type || "-")} / ${escapeHtml(percent(titleEvidence.score))}</p>
          <p>가수 근거: ${escapeHtml(artistEvidence.type || "-")} / ${escapeHtml(percent(artistEvidence.score))}</p>
          <p>검색 근거: ${escapeHtml(queryEvidence.type || "none")} / ${escapeHtml(percent(queryEvidence.score))}</p>
          <p>메타데이터 근거: ${escapeHtml(percent(metadataEvidence.score))}</p>
          <p>위험 패널티: ${escapeHtml(percent(riskPenalty.score))}</p>
          <p>최종 confidence: ${escapeHtml(percent(detail.final_score ?? item.confidence))}</p>
        </section>
        <section>
          <h4>근거</h4>
          <p>제목: ${escapeHtml(titleEvidence.reason || "-")}</p>
          <p>가수: ${escapeHtml(artistEvidence.reason || "-")}</p>
          <p>검색: ${escapeHtml(queryEvidence.reason || "-")}</p>
          <p>앨범 이미지: ${metadataEvidence.album_image ? "있음" : "없음"}</p>
          <p>재생시간 근접: ${metadataEvidence.duration_close === null || metadataEvidence.duration_close === undefined ? "정보 없음" : escapeHtml(String(metadataEvidence.duration_close))}</p>
          <p>적용된 근거 목록</p>
          <ul>${renderEvidenceList(detail.matched_evidence, "적용된 근거 없음")}</ul>
          <p>부족한 근거</p>
          <ul>${renderEvidenceList(detail.missing_evidence, "부족한 근거 없음")}</ul>
        </section>
        <section>
          <h4>검색 정보</h4>
          <p>사용된 검색어: ${escapeHtml(detail.query_used || "-")}</p>
          <p>Spotify 검색 순위: ${detail.api_rank ? `${escapeHtml(detail.api_rank)}위` : "-"}</p>
          <p>검색 타입: ${escapeHtml(detail.query_type || "-")}</p>
          <p>검색 신뢰도: ${escapeHtml(detail.query_reliability || "-")}</p>
        </section>
        <section>
          <h4>차단/주의 사유</h4>
          <p>검색 순위 보너스: ${escapeHtml(yesNo(detail.rank_bonus_applied))}</p>
          <p>검색 신호: ${escapeHtml(yesNo(detail.search_engine_signal_applied))}</p>
          <p>검색 근거 적용: ${escapeHtml(yesNo(queryEvidence.applied))}</p>
          <p>표기 차이 감지: ${escapeHtml(yesNo(detail.notation_difference_detected))}</p>
          <p>표기 차이 사유: ${escapeHtml(detail.notation_difference_reason || "-")}</p>
          <p>차단 사유: ${escapeHtml(detail.blocked_reason || "-")}</p>
          <p>위험 사유: ${safeArray(riskPenalty.reasons).length ? escapeHtml(riskPenalty.reasons.join(", ")) : "-"}</p>
        </section>
      </div>
      <details class="raw-detail">
        <summary>raw detail 보기</summary>
        <pre>${escapeHtml(JSON.stringify(detail.raw_detail || detail, null, 2))}</pre>
      </details>
    </details>
  `;
}

function canSelectCandidate(item) {
  return Boolean(item?.matched && item?.spotify_uri);
}

function isRecommendedCandidate(item) {
  return canSelectCandidate(item) && ["high", "mid"].includes(item.confidence_label);
}

function selectedCount() {
  return candidateResults.filter((item) => item.selected && canSelectCandidate(item)).length;
}

function candidateCount() {
  return candidateResults.filter(canSelectCandidate).length;
}

function needsReviewCount() {
  return candidateResults.filter((item) => ["mid", "low"].includes(item.confidence_label)).length;
}

function failedCount() {
  return candidateResults.filter((item) => item.confidence_label === "failed" || !canSelectCandidate(item)).length;
}

function updateSummary(data = lastResultData || {}) {
  setText("summarySuccess", data?.success, "-");
  setText("summaryMessage", data?.message, "-");
  setText("summaryMode", data?.mode || getMode(), "-");
  setText("summaryYoutubeTitle", data?.youtube_title, "-");
  setText("summaryPlaylistName", data?.playlist_name || getPlaylistName(), "-");
  setText("infoStage", data?.selected_stage, "-");
  setText("infoOcrUsed", data?.ocr_used, "-");
  setText("infoAcrUsed", data?.acr_used, "-");
  setText("overviewExtractedCount", data?.extracted_count ?? candidateResults.length, "0");
  setText("overviewMatchedCount", data?.spotify_candidate_count ?? candidateCount(), "0");
  setText("overviewLowConfidenceCount", data?.needs_review_count ?? needsReviewCount(), "0");
  setText("overviewUnmatchedCount", data?.failed_count ?? failedCount(), "0");
  setText("overviewSelectedCount", selectedCount(), "0");
  setText("infoAnalysisElapsed", formatDurationMs(data?.analysis_elapsed_ms ?? data?.timings?.analysis_elapsed_ms), "-");
  setText("infoSpotifyElapsed", formatDurationMs(data?.spotify_elapsed_ms ?? data?.timings?.spotify_elapsed_ms), "-");
  setText("overviewTotalElapsed", formatDurationMs(data?.total_elapsed_ms ?? data?.timings?.total_elapsed_ms), "-");
}

function updateRecentSummary(actionLabel, data = lastResultData || {}) {
  setText("recentActionText", actionLabel, "대기 중");
  setText("recentYoutubeTitle", data?.youtube_title, "-");
  setText("recentStageText", data?.selected_stage, "-");
  setText("currentModeText", getMode(), "text");
}

function renderCandidateSummary() {
  candidateSummary.textContent = [
    `전체 추출곡 수: ${candidateResults.length}`,
    `Spotify 매칭 후보: ${candidateCount()}`,
    `확인 필요 후보: ${needsReviewCount()}`,
    `후보 없음: ${failedCount()}`,
    `현재 선택된 곡: ${selectedCount()}`,
  ].join(" · ");
  updateSummary();
}

function renderCandidateCard(item, index) {
  const selectable = canSelectCandidate(item);
  const checked = selectable && item.selected ? "checked" : "";
  const disabled = selectable ? "" : "disabled";
  const image = item.album_image
    ? `<img class="album-image" src="${escapeHtml(item.album_image)}" alt="앨범 이미지" />`
    : `<div class="album-image album-placeholder">no image</div>`;
  const cardClass = item.confidence_label === "failed" ? "failed-card" : item.confidence_label === "low" ? "low-card" : "matched-card";
  const spotifyLine = selectable
    ? `${escapeHtml(item.spotify_artist || "-")} - ${escapeHtml(item.spotify_title || "-")}`
    : "Spotify 후보 없음";

  return `
    <article class="song-card candidate-card ${cardClass}">
      <label class="candidate-check">
        <input type="checkbox" data-candidate-index="${index}" ${checked} ${disabled} />
        <span>${selectable ? "추가 후보 선택" : "선택 불가"}</span>
      </label>
      ${image}
      <div class="candidate-body">
        <div class="song-card-header">
          <span>${index + 1}. ${escapeHtml(item.input_artist || "Unknown")} - ${escapeHtml(item.input_title || "제목 없음")}</span>
          <span class="status-pill status-${escapeHtml(item.confidence_label)}">${escapeHtml(labelForConfidence(item.confidence_label))}</span>
        </div>
        <div class="song-card-meta">
          <strong>Spotify 검색 후보</strong>: ${spotifyLine}<br />
          <strong>confidence</strong>: ${escapeHtml(formatScore(item.confidence))}<br />
          <strong>reason</strong>: ${escapeHtml(item.reason || "-")}
        </div>
        ${renderConfidenceDetail(item)}
      </div>
    </article>
  `;
}

function renderCandidates() {
  if (!candidateResults.length) {
    songResultsList.className = "result-list empty-state";
    songResultsList.textContent = "아직 표시할 후보가 없습니다.";
    renderCandidateSummary();
    return;
  }

  songResultsList.className = "result-list";
  songResultsList.innerHTML = candidateResults.map(renderCandidateCard).join("");
  songResultsList.querySelectorAll("input[data-candidate-index]").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      const index = Number(checkbox.dataset.candidateIndex);
      if (candidateResults[index] && canSelectCandidate(candidateResults[index])) {
        candidateResults[index].selected = checkbox.checked;
      }
      renderCandidateSummary();
    });
  });
  renderCandidateSummary();
}

function renderDebug(data) {
  if (!data?.results?.length) {
    debugHighlights.className = "debug-highlight-list empty-state";
    debugHighlights.textContent = "아직 디버그 정보가 없습니다.";
    return;
  }
  debugHighlights.className = "debug-highlight-list";
  debugHighlights.innerHTML = data.results.map((item, index) => `
    <details class="debug-card">
      <summary>${index + 1}. ${escapeHtml(item.input_artist)} - ${escapeHtml(item.input_title)}</summary>
      <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
    </details>
  `).join("");
}

function activateTab(tabId) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tabTarget === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("is-active", panel.id === tabId);
  });
  if (tabId === "qaTab") loadQaPosts();
}

function initializeTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tabTarget));
  });
  modeSelect.addEventListener("change", () => {
    setText("currentModeText", getMode(), "text");
  });
}

async function handleApiResponse(response) {
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    throw new Error("JSON 응답 파싱에 실패했습니다.");
  }

  if (!response.ok) {
    const detail = data?.detail || data?.message || `HTTP ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function prepareRunUi(message) {
  setButtonsDisabled(true);
  setStatus("loading", message);
  renderErrorBox(null);
  setPlaylistLink(null);
}

async function refreshLoginStatus() {
  try {
    const response = await fetch(buildApiUrl("/spotify/login-status"), { credentials: "include" });
    const data = await handleApiResponse(response);
    setText("loginSummaryText", data?.logged_in ? "로그인 완료" : "미로그인", "확인 중");
  } catch (error) {
    setText("loginSummaryText", "확인 실패", "확인 중");
  }
}

function updateNoticeFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const loginStatus = params.get("spotify_login");
  const reason = params.get("reason");

  if (loginStatus === "success") {
    noticeBoard.textContent = "Spotify 로그인이 완료되었습니다. 이제 YouTube URL을 분석해 후보를 확인할 수 있습니다.";
    setStatus("success", "Spotify 로그인 완료. YouTube URL을 분석해주세요.");
    return;
  }

  if (loginStatus === "failed") {
    const message = `Spotify 로그인 실패: ${reason || "unknown"}`;
    noticeBoard.textContent = message;
    setStatus("error", message);
    renderErrorBox(message);
  }
}

spotifyLoginBtn.addEventListener("click", async () => {
  try {
    setButtonsDisabled(true);
    setStatus("loading", "Spotify 로그인 URL을 가져오는 중입니다.");
    const frontendRedirect = getFrontendRedirectUrl();
    const response = await fetch(
      buildApiUrl(`/spotify/login?frontend_origin=${encodeURIComponent(frontendRedirect)}`),
      { credentials: "include" }
    );
    const data = await handleApiResponse(response);
    const authUrl = data?.auth_url || data?.login_url;
    if (!authUrl) throw new Error("Spotify auth_url을 받지 못했습니다.");
    window.location.href = authUrl;
  } catch (error) {
    setStatus("error", `Spotify 로그인 준비 실패: ${error.message}`);
    renderErrorBox(`Spotify 로그인 준비 실패\n${error.message}`);
    setButtonsDisabled(false);
  }
});

analyzeBtn.addEventListener("click", async () => {
  const youtubeUrl = youtubeUrlInput.value.trim();
  if (!youtubeUrl) {
    setStatus("error", "YouTube URL을 먼저 입력해주세요.");
    renderErrorBox("YouTube URL이 비어 있습니다.");
    return;
  }

  try {
    prepareRunUi("YouTube 분석과 Spotify 후보 검색을 진행하는 중입니다.");
    const payload = {
      youtube_url: youtubeUrl,
      mode: getMode(),
      title_mode: titleModeSelect.value,
      playlist_name: getPlaylistName(),
      use_artist_aliases: Boolean(useArtistAliasesCheckbox.checked),
    };
    const response = await fetch(buildApiUrl("/playlist/analyze-youtube"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await handleApiResponse(response);
    lastResultData = data;
    candidateResults = safeArray(data.results).map((item) => ({ ...item, selected: Boolean(item.selected && item.spotify_uri) }));
    renderJson(data);
    renderCandidates();
    renderDebug(data);
    updateSummary(data);
    updateRecentSummary("후보 분석", data);
    setStatus("success", "Spotify 매칭 후보를 찾았습니다. 후보 선택 탭에서 확인해주세요.");
    activateTab("candidatesTab");
  } catch (error) {
    setStatus("error", `후보 분석 실패: ${error.message}`);
    renderErrorBox(`후보 분석 실패\n${error.message}`);
    renderJson({ error: error.message });
    candidateResults = [];
    renderCandidates();
    updateRecentSummary("분석 실패", {});
  } finally {
    setButtonsDisabled(false);
  }
});

async function createPlaylistFromSelected() {
  const selectedUris = candidateResults
    .filter((item) => item.selected && canSelectCandidate(item))
    .map((item) => item.spotify_uri);
  const selectedMatches = candidateResults
    .filter((item) => item.selected && canSelectCandidate(item))
    .map((item) => ({
      input_artist: item.input_artist,
      input_title: item.input_title,
      spotify_track_id: item.spotify_track_id,
      spotify_uri: item.spotify_uri,
      spotify_title: item.spotify_title,
      spotify_artist: item.spotify_artist,
      album_image: item.album_image,
    }));

  if (selectedUris.length === 0) {
    const message = "선택된 곡이 없습니다.";
    setStatus("error", message);
    renderErrorBox(message);
    activateTab("candidatesTab");
    return;
  }

  try {
    prepareRunUi("선택한 곡으로 Spotify 플레이리스트를 생성하는 중입니다.");
    const payload = {
      playlist_name: lastResultData?.playlist_name || getPlaylistName() || "YouTube 변환 플레이리스트",
      description: `Created from YouTube: ${lastResultData?.youtube_title || youtubeUrlInput.value.trim()}`,
      track_uris: selectedUris,
      selected_matches: selectedMatches,
      thumbnail_url: lastResultData?.thumbnail_url || "",
    };
    const response = await fetch(buildApiUrl("/playlist/create-selected"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await handleApiResponse(response);
    lastResultData = { ...(lastResultData || {}), create_result: data, message: "선택한 곡으로 플레이리스트를 생성했습니다." };
    renderJson(lastResultData);
    setPlaylistLink(data.playlist_url);
    updateSummary(lastResultData);
    updateRecentSummary("플레이리스트 생성", lastResultData);
    setStatus("success", `플레이리스트 생성 완료: ${data.added_count}곡 추가`);
    activateTab("candidatesTab");
  } catch (error) {
    setStatus("error", `플레이리스트 생성 실패: ${error.message}`);
    renderErrorBox(`플레이리스트 생성 실패\n${error.message}`);
  } finally {
    setButtonsDisabled(false);
  }
}

createPlaylistBtn.addEventListener("click", createPlaylistFromSelected);
createSelectedInlineBtn.addEventListener("click", createPlaylistFromSelected);

selectAllBtn.addEventListener("click", () => {
  candidateResults = candidateResults.map((item) => ({ ...item, selected: canSelectCandidate(item) }));
  renderCandidates();
});

clearAllBtn.addEventListener("click", () => {
  candidateResults = candidateResults.map((item) => ({ ...item, selected: false }));
  renderCandidates();
});

selectRecommendedBtn.addEventListener("click", () => {
  candidateResults = candidateResults.map((item) => ({ ...item, selected: isRecommendedCandidate(item) }));
  renderCandidates();
});

clearArtistAliasesBtn.addEventListener("click", async () => {
  const confirmed = window.confirm("저장된 artist alias 기록을 모두 삭제할까요?");
  if (!confirmed) return;

  try {
    setButtonsDisabled(true);
    resetErrorBox();
    const response = await fetch(buildApiUrl("/playlist/artist-aliases"), {
      method: "DELETE",
      credentials: "include",
    });
    const data = await handleApiResponse(response);
    setStatus("success", `artist alias 초기화 완료: ${data.deleted_count || 0}개 삭제`);
  } catch (error) {
    setStatus("error", `artist alias 초기화 실패: ${error.message}`);
    renderErrorBox(`artist alias 초기화 실패\n${error.message}`);
  } finally {
    setButtonsDisabled(false);
  }
});

async function loadQaPosts() {
  try {
    const response = await fetch(buildApiUrl("/qa"));
    const posts = await handleApiResponse(response);
    renderQaList(posts);
  } catch (error) {
    qaList.className = "qa-list empty-state";
    qaList.textContent = `QA 목록 조회 실패: ${error.message}`;
  }
}

function renderQaList(posts) {
  const items = safeArray(posts);
  if (!items.length) {
    qaList.className = "qa-list empty-state";
    qaList.textContent = "등록된 QA가 없습니다.";
    return;
  }
  qaList.className = "qa-list";
  qaList.innerHTML = items.map((post) => `
    <button class="qa-list-item" type="button" data-qa-id="${post.id}">
      <strong>${escapeHtml(post.title)}</strong>
      <span>${escapeHtml(post.category)} · ${escapeHtml(post.status)} · ${escapeHtml(post.created_at || "-")}</span>
    </button>
  `).join("");
  qaList.querySelectorAll("button[data-qa-id]").forEach((button) => {
    button.addEventListener("click", () => loadQaDetail(Number(button.dataset.qaId)));
  });
}

async function loadQaDetail(id) {
  try {
    selectedQaId = id;
    const response = await fetch(buildApiUrl(`/qa/${id}`));
    const post = await handleApiResponse(response);
    renderQaDetail(post);
  } catch (error) {
    qaDetail.className = "qa-detail empty-state";
    qaDetail.textContent = `QA 상세 조회 실패: ${error.message}`;
  }
}

function renderQaDetail(post) {
  qaDetail.className = "qa-detail";
  qaDetail.innerHTML = `
    <article class="qa-detail-card">
      <div class="song-card-header">
        <span>${escapeHtml(post.title)}</span>
        <span class="status-pill status-${escapeHtml(post.status)}">${escapeHtml(post.status)}</span>
      </div>
      <p class="qa-meta">${escapeHtml(post.author)} · ${escapeHtml(post.category)} · ${escapeHtml(post.created_at || "-")}</p>
      <p>${escapeHtml(post.content)}</p>
      <div class="qa-answer">
        <strong>답변</strong>
        <p>${post.answer ? escapeHtml(post.answer) : "아직 답변 대기 중입니다."}</p>
      </div>
      <details class="admin-answer-box">
        <summary>관리자 답변 작성</summary>
        <input id="adminKeyInput" type="password" placeholder="관리자 코드" />
        <textarea id="adminAnswerInput" rows="4" placeholder="답변 내용"></textarea>
        <button id="adminAnswerBtn" class="action-btn orange-btn" type="button">답변 저장</button>
      </details>
    </article>
  `;
  $("adminAnswerBtn").addEventListener("click", submitAdminAnswer);
}

async function submitAdminAnswer() {
  const adminKey = $("adminKeyInput").value.trim();
  const answer = $("adminAnswerInput").value.trim();
  if (!selectedQaId) return;

  try {
    const response = await fetch(buildApiUrl(`/qa/${selectedQaId}/answer`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ admin_key: adminKey, answer }),
    });
    const post = await handleApiResponse(response);
    renderQaDetail(post);
    loadQaPosts();
  } catch (error) {
    renderErrorBox(`관리자 답변 저장 실패\n${error.message}`);
  }
}

qaForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = {
      title: qaTitle.value.trim(),
      author: qaAuthor.value.trim(),
      category: qaCategory.value,
      content: qaContent.value.trim(),
    };
    const response = await fetch(buildApiUrl("/qa"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const post = await handleApiResponse(response);
    qaForm.reset();
    await loadQaPosts();
    renderQaDetail(post);
  } catch (error) {
    renderErrorBox(`QA 등록 실패\n${error.message}`);
  }
});

qaRefreshBtn.addEventListener("click", loadQaPosts);

function clearResponseState() {
  lastResultData = {};
  candidateResults = [];
  renderJson({ message: "아직 결과가 없습니다." });
  renderCandidates();
  renderDebug({});
  updateSummary({});
  setPlaylistLink(null);
  resetErrorBox();
}

initializeBackendBaseUrl();
initializeTabs();
clearResponseState();
updateNoticeFromQuery();
refreshLoginStatus();
