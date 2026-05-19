const $ = (id) => document.getElementById(id);

const backendBaseUrlInput = $("backendBaseUrl");
const youtubeUrlInput = $("youtubeUrl");
const playlistNameInput = $("playlistName");
const modeSelect = $("mode");
const titleModeSelect = $("titleMode");

const spotifyLoginBtn = $("spotifyLoginBtn");
const spotifyLogoutBtn = $("spotifyLogoutBtn");
const analyzeBtn = $("analyzeBtn");
const createPlaylistBtn = $("createPlaylistBtn");
const openSpotifyBtn = $("openSpotifyBtn");
const selectAllBtn = $("selectAllBtn");
const clearAllBtn = $("clearAllBtn");
const selectRecommendedBtn = $("selectRecommendedBtn");
const createSelectedInlineBtn = $("createSelectedInlineBtn");
const inlineOpenSpotifyBtn = $("inlineOpenSpotifyBtn");
const fallbackPanel = $("fallbackPanel");
const fallbackMessage = $("fallbackMessage");
const runOcrBtn = $("runOcrBtn");
const runAcrBtn = $("runAcrBtn");
const matchTextOnlyBtn = $("matchTextOnlyBtn");

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
let textAnalysisData = null;
let mergedSongSource = [];
let selectedQaId = null;
let loginStatusRequestInFlight = null;
let loginStatusLastFetchedAt = 0;
let isAnalyzing = false;
let isSpotifyLoggedIn = false;
const LOGIN_STATUS_MIN_INTERVAL_MS = 30000;

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
  return modeSelect.value || "auto";
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
  [spotifyLoginBtn, spotifyLogoutBtn, analyzeBtn, createPlaylistBtn, createSelectedInlineBtn, runOcrBtn, runAcrBtn, matchTextOnlyBtn].forEach((button) => {
    if (!button) return;
    button.disabled = disabled;
  });
}

function updateSpotifyLoginUi(loggedIn) {
  isSpotifyLoggedIn = Boolean(loggedIn);
  setText("loginSummaryText", isSpotifyLoggedIn ? "로그인 완료" : "미로그인", "확인 중");
  if (spotifyLoginBtn) {
    spotifyLoginBtn.textContent = isSpotifyLoggedIn ? "다른 계정으로 로그인" : "Spotify 로그인";
  }
  if (spotifyLogoutBtn) {
    spotifyLogoutBtn.hidden = !isSpotifyLoggedIn;
  }
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

function parseNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function ratioPercent(value) {
  return `${Math.round(parseNumber(value) * 1000) / 10}%`;
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
  return Boolean(item?.spotify_uri && item?.confidence_label !== "failed");
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
  setText("summarySuccess", data?.analysis_state || data?.success, "-");
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
  setText("currentModeText", getMode(), "auto");
}

function setFallbackPanelVisible(visible, message = "", showTextFallback = false) {
  if (!fallbackPanel) return;
  fallbackPanel.hidden = !visible;
  if (fallbackMessage) {
    fallbackMessage.textContent = message || "OCR 또는 ACR을 선택해 분석을 보강하거나, 현재 텍스트 결과로 진행해주세요.";
  }
  if (matchTextOnlyBtn) {
    matchTextOnlyBtn.hidden = !showTextFallback;
  }
}

function shouldOfferFallbackAfterMatching(data) {
  const textState = data?.text_analysis_state || data?.analysis_state;
  const failed = Number(data?.failed_count || 0);
  const review = Number(data?.needs_review_count || 0);
  const candidates = Number(data?.candidate_count || data?.spotify_candidate_count || 0);
  const extracted = Number(data?.extracted_count || safeArray(data?.songs).length || 0);
  return (
    textState === "partial_success" ||
    textState === "text_failed" ||
    failed > 0 ||
    review > 0 ||
    (extracted > 0 && candidates === 0)
  );
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
  const score = typeof item.score === "number" ? item.score : item.confidence;
  const searchTitle = item.search_title || item.match_debug?.search_title || item.confidence_detail?.query_used || item.input_title || "-";

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
          <strong>점수</strong>: ${escapeHtml(formatScore(score))} · ${escapeHtml(labelForConfidence(item.confidence_label))}<br />
          <strong>검색 기준</strong>: ${escapeHtml(searchTitle)}<br />
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
    songResultsList.textContent = lastResultData?.ocr_used
      ? "OCR에서 곡을 추출하지 못했습니다. 위의 OCR 분석 정보 패널에서 읽힌 텍스트를 확인해주세요."
      : "아직 표시할 후보가 없습니다.";
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

function renderTable(container, columns, rows, emptyText) {
  if (!container) return;
  const normalizedRows = safeArray(rows);
  if (!normalizedRows.length) {
    container.className = "table-wrap empty-state";
    container.textContent = emptyText;
    return;
  }
  container.className = "table-wrap";
  container.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${normalizedRows
          .map(
            (row) => `
              <tr>
                ${columns.map((column) => `<td>${escapeHtml(column.format ? column.format(row[column.key], row) : row[column.key] ?? "")}</td>`).join("")}
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}


function renderDebugCard(title, body) {
  return `
    <details class="debug-card" open>
      <summary>${escapeHtml(title)}</summary>
      <pre>${escapeHtml(body)}</pre>
    </details>
  `;
}


function renderOcrInfoBanner(data) {
  const banner = $("ocrInfoBanner");
  const content = $("ocrInfoContent");
  if (!banner || !content) return;

  if (!data?.ocr_used) {
    banner.hidden = true;
    return;
  }
  banner.hidden = false;

  const youtubeResult = data?.youtube_result || {};
  const visionDebug = youtubeResult?.debug?.vision || {};
  const visionText = visionDebug?.raw_text || data?.ocr_text || "";
  const selectedBlock = data?.selected_ocr_block || youtubeResult?.selected_ocr_block || visionDebug?.selected_ocr_block || {};
  const ocrBlocks = safeArray(data?.ocr_blocks).length ? safeArray(data?.ocr_blocks) : safeArray(youtubeResult?.ocr_blocks || visionDebug?.ocr_blocks);
  const warning = data?.warning || "";
  const extractedCount = data?.extracted_count ?? safeArray(data?.songs).length;

  const statsItems = [
    visionDebug.duration != null ? `영상 ${visionDebug.duration}초` : null,
    visionDebug.interval_sec != null ? `${visionDebug.interval_sec}초 간격` : null,
    visionDebug.actual_frame_count != null
      ? `${visionDebug.actual_frame_count}/${visionDebug.expected_frame_count ?? "?"}프레임`
      : null,
    visionDebug.raw_text_count != null ? `텍스트 블록 ${visionDebug.raw_text_count}개` : null,
    selectedBlock.score != null ? `선택 블록 점수 ${selectedBlock.score}` : null,
    ocrBlocks.length ? `후보 블록 ${ocrBlocks.length}개` : null,
  ].filter(Boolean);

  const statsHtml = statsItems.length
    ? `<p class="ocr-stats">${escapeHtml(statsItems.join(" · "))}</p>`
    : "";

  const warningHtml = warning
    ? `<p class="ocr-warning-inline">${escapeHtml(warning)}</p>`
    : "";

  let textHtml;
  if (!visionText) {
    textHtml = `<p class="ocr-no-text">화면에서 읽힌 텍스트가 없습니다. 영상 화면에 곡 목록이 텍스트로 표시되어야 OCR 분석이 가능합니다.</p>`;
  } else {
    const lines = visionText.split("\n").filter((l) => l.trim()).length;
    textHtml = `
      <details class="debug-card ocr-text-details">
        <summary>OCR로 읽은 화면 텍스트 (${visionText.length}자, ${lines}줄, 추출된 곡 ${extractedCount}개)</summary>
        <pre>${escapeHtml(visionText)}</pre>
      </details>`;
  }

  content.innerHTML = warningHtml + statsHtml + textHtml;
}

function renderDebug(data) {
  const debugSections = [];
  const youtubeResult = data?.youtube_result || {};
  const youtubeDebug = youtubeResult?.debug || {};
  const visionDebug = youtubeDebug?.vision || {};
  const visionText = visionDebug?.raw_text || data?.ocr_text || "";
  const selectedOcrBlock = data?.selected_ocr_block || youtubeResult?.selected_ocr_block || visionDebug?.selected_ocr_block || {};
  const ocrBlocks = safeArray(data?.ocr_blocks).length ? safeArray(data?.ocr_blocks) : safeArray(youtubeResult?.ocr_blocks || visionDebug?.ocr_blocks);
  const debugResults = safeArray(data?.results);
  const spotifyLogs = [];

  if (visionText) {
    debugSections.push(renderDebugCard("OCR vision_text", visionText));
  }

  if (Object.keys(selectedOcrBlock).length) {
    debugSections.push(renderDebugCard("Selected OCR block", JSON.stringify(selectedOcrBlock, null, 2)));
  }

  if (ocrBlocks.length) {
    debugSections.push(renderDebugCard("OCR blocks", JSON.stringify(ocrBlocks, null, 2)));
  }

  if (Object.keys(visionDebug).length) {
    debugSections.push(renderDebugCard("OCR / Vision debug", JSON.stringify(visionDebug, null, 2)));
  }

  if (Object.keys(youtubeResult).length) {
    debugSections.push(renderDebugCard("YouTube result", JSON.stringify(youtubeResult, null, 2)));
  }

  if (debugResults.length) {
    debugResults.forEach((item) => {
      const caseResults = safeArray(item?.match_debug?.case_results);
      spotifyLogs.push(
        `[spotify-match:filter] input='${item.input_artist || ""} - ${item.input_title || ""}' `
          + `single_artist_filter_applied=${Boolean(item?.single_artist_filter_applied)} `
          + `reason='${item?.single_artist_filter_reason || item?.match_debug?.single_artist_filter_reason || ""}' `
          + `artist_id='${item?.spotify_artist_id_filter || item?.match_debug?.spotify_artist_id_filter || ""}'`,
      );
      caseResults.forEach((caseResult) => {
        const logs = safeArray(caseResult?.candidate_logs);
        const queries = safeArray(caseResult?.queries);
        logs.forEach((line) => {
          spotifyLogs.push(
            `[spotify-match:candidates] input='${item.input_artist || ""} - ${item.input_title || ""}' `
              + `queries=${JSON.stringify(queries)} ${line}`,
          );
        });
      });
    });

    if (spotifyLogs.length) {
      debugSections.push(renderDebugCard("Spotify match logs", spotifyLogs.join("\n")));
    }

    debugSections.push(
      ...debugResults.map((item, index) =>
        renderDebugCard(
          `${index + 1}. ${item.input_artist || "Unknown"} - ${item.input_title || "제목 없음"}`,
          JSON.stringify(item, null, 2),
        ),
      ),
    );
  }

  if (!debugSections.length) {
    debugHighlights.className = "debug-highlight-list empty-state";
    debugHighlights.textContent = "아직 디버그 정보가 없습니다.";
    return;
  }

  debugHighlights.className = "debug-highlight-list";
  debugHighlights.innerHTML = debugSections.join("");
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
  console.log("[api] response received", { url: response.url, status: response.status, ok: response.ok });
  let data = null;
  try {
    data = await response.json();
    console.log("[api] response json parsed", { url: response.url, keys: Object.keys(data || {}) });
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

function _buildAnalyzeProgressMessages(mode) {
  if (mode === "auto" || mode === "text") {
    return [
      "설명란 분석 중",
      "댓글 분석 중",
      "곡 정보 정리 중",
    ];
  }
  if (mode === "spotify") {
    return [
      "Spotify 후보 검색 중",
      "신뢰도와 근거를 계산하는 중",
      "후보 목록 정리 중",
    ];
  }
  if (mode === "ocr") {
    return [
      "영상 프레임 추출 중",
      "화면 텍스트 OCR 분석 중",
      "후보 목록 정리 중",
    ];
  }
  if (mode === "acr") {
    return [
      "오디오 구간 추출 중",
      "ACR 인식 결과 정리 중",
      "후보 목록 정리 중",
    ];
  }
  return [
    "설명/댓글에서 곡 후보를 분석하는 중입니다.",
    "Spotify 후보를 검색하는 중입니다.",
    "신뢰도와 근거를 계산하는 중입니다.",
  ];
}

function startAnalyzeProgress(mode) {
  const messages = _buildAnalyzeProgressMessages(mode);
  if (!messages.length) return () => {};
  let index = 0;
  setStatus("loading", messages[index]);
  const timer = window.setInterval(() => {
    index = (index + 1) % messages.length;
    setStatus("loading", messages[index]);
  }, mode === "ocr" ? 3000 : 1400);
  return () => window.clearInterval(timer);
}

async function refreshLoginStatus() {
  if (isAnalyzing) return null;

  const now = Date.now();
  if (loginStatusRequestInFlight) return loginStatusRequestInFlight;
  if (now - loginStatusLastFetchedAt < LOGIN_STATUS_MIN_INTERVAL_MS) return null;

  loginStatusLastFetchedAt = now;
  loginStatusRequestInFlight = (async () => {
    try {
      const response = await fetch(buildApiUrl("/spotify/login-status"), { credentials: "include" });
      const data = await handleApiResponse(response);
      updateSpotifyLoginUi(data?.logged_in);
      return data;
    } catch (error) {
      setText("loginSummaryText", "확인 실패", "확인 중");
      return null;
    } finally {
      loginStatusRequestInFlight = null;
    }
  })();

  try {
    return await loginStatusRequestInFlight;
  } catch (_error) {
    return null;
  }
}

function normalizeCandidateResults(data) {
  const results = safeArray(data?.results).length
    ? safeArray(data?.results)
    : safeArray(data?.matched_tracks).concat(safeArray(data?.unmatched_tracks));
  if (results.length) {
    return results.map((item) => ({ ...item, selected: Boolean(item.selected && item.spotify_uri) }));
  }

  const songs = safeArray(data?.songs).length ? safeArray(data?.songs) : safeArray(data?.extracted_songs);
  return songs.map((song) => {
    const artist = (song?.artist || "").trim();
    const title = (song?.title || "").trim();
    return {
      input_artist: artist,
      input_title: title,
      matched: false,
      spotify_track_id: null,
      spotify_uri: null,
      spotify_title: null,
      spotify_artist: null,
      album_image: null,
      confidence: 0,
      score: 0,
      final_score: 0,
      status: "unmatched",
      confidence_label: "failed",
      reason: ["Spotify 후보가 없어 사용자 확인이 필요합니다."],
      reason_text: "Spotify 후보가 없어 사용자 확인이 필요합니다.",
      selected: false,
      match_status: "unmatched",
      top_candidates: [],
      source_only: true,
      raw: song?.raw || "",
    };
  });
}

function applyAnalysisData(data, actionLabel) {
  lastResultData = data;
  mergedSongSource = safeArray(data?.songs).length ? safeArray(data.songs) : safeArray(data?.extracted_songs);
  candidateResults = normalizeCandidateResults(data);
  renderJson(data);
  renderOcrInfoBanner(data);
  renderCandidates();
  renderDebug(data);
  updateSummary(data);
  updateRecentSummary(actionLabel, data);
}

async function matchCandidatesFromCurrentSongs(sourceMode = "text", { offerFallback = false } = {}) {
  const songs = safeArray(mergedSongSource).length
    ? mergedSongSource
    : safeArray(lastResultData?.songs).length
    ? safeArray(lastResultData.songs)
    : safeArray(lastResultData?.extracted_songs);
  if (!songs.length) {
    const ocrUsed = lastResultData?.ocr_used;
    const acrUsed = lastResultData?.acr_used;
    if (ocrUsed || acrUsed) {
      setStatus("warn", `${ocrUsed ? "OCR" : "ACR"} 분석 결과에서 곡을 찾지 못했습니다. Raw Debug 탭에서 세부 내용을 확인해주세요.`);
      setFallbackPanelVisible(false);
    } else {
      setStatus("warn", "Spotify 후보를 검색할 곡이 없습니다. OCR 또는 ACR을 먼저 선택해주세요.");
      setFallbackPanelVisible(true);
    }
    return null;
  }

  const stopProgress = startAnalyzeProgress("spotify");
  try {
    prepareRunUi("Spotify 후보 검색 중입니다.");
    const response = await fetch(buildApiUrl("/spotify/match-candidates"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        songs,
        mode: sourceMode,
        source_mode: sourceMode,
      }),
    });
    const matchData = await handleApiResponse(response);
    const combined = {
      ...(lastResultData || {}),
      ...matchData,
      songs,
      extracted_songs: songs,
      youtube_title: lastResultData?.youtube_title || matchData?.youtube_title || textAnalysisData?.youtube_title || "",
      youtube_url: lastResultData?.youtube_url || youtubeUrlInput.value.trim(),
      thumbnail_url: lastResultData?.thumbnail_url || textAnalysisData?.thumbnail_url || "",
      playlist_name: getPlaylistName() || lastResultData?.playlist_name || textAnalysisData?.playlist_name || "",
      text_analysis_state: lastResultData?.analysis_state || lastResultData?.text_analysis_state || "",
      text_analysis_reasons: lastResultData?.analysis_reasons || lastResultData?.text_analysis_reasons || [],
      analysis_state: matchData?.analysis_state || "candidates_ready",
      next_action: matchData?.next_action || "select_tracks",
      needs_fallback: false,
      spotify_matching_skipped: false,
      analysis_elapsed_ms: lastResultData?.analysis_elapsed_ms || 0,
      total_elapsed_ms: (lastResultData?.analysis_elapsed_ms || 0) + (matchData?.spotify_elapsed_ms || 0),
      timings: {
        ...(lastResultData?.timings || {}),
        ...(matchData?.timings || {}),
        total_elapsed_ms: (lastResultData?.analysis_elapsed_ms || 0) + (matchData?.spotify_elapsed_ms || 0),
      },
    };
    const hasCandidates = combined.candidate_count > 0;
    const poorResults = !hasCandidates || combined.failed_count > 0 || combined.needs_review_count > 0;
    combined.needs_fallback = offerFallback;
    combined.next_action = poorResults ? "choose_fallback" : "select_tracks";
    applyAnalysisData(combined, "Spotify 후보 검색");
    if (offerFallback) {
      const fallbackMsg = poorResults
        ? "Spotify 매칭 결과가 부족합니다. OCR 또는 ACR로 보강할 수 있습니다."
        : "필요하다면 OCR 또는 ACR로 추가 보강할 수 있습니다.";
      const statusMsg = poorResults
        ? "Spotify 후보를 찾았지만 결과가 부족합니다. OCR/ACR로 보강하거나 현재 후보에서 선택해주세요."
        : "Spotify 매칭 후보를 찾았습니다. 후보 선택 탭에서 확인하거나 OCR/ACR로 추가 보강할 수 있습니다.";
      setFallbackPanelVisible(true, fallbackMsg, false);
      setStatus(poorResults ? "warn" : "success", statusMsg);
      activateTab(hasCandidates ? "candidatesTab" : "runTab");
    } else {
      setFallbackPanelVisible(false);
      if (candidateResults.some(canSelectCandidate)) {
        setStatus("success", "Spotify 매칭 후보를 찾았습니다. 후보 선택 탭에서 확인해주세요.");
      } else {
        setStatus("warn", "선택 가능한 Spotify 후보가 없습니다. 결과 탭에서 확인해주세요.");
      }
      activateTab("candidatesTab");
    }
    return combined;
  } finally {
    stopProgress();
    setButtonsDisabled(false);
  }
}

function _fallbackEmptyReason(mode, data) {
  const reason = data?.failure_reason || "";
  const errMsg = data?.error || "";
  if (mode === "acr") {
    if (reason === "acr_credentials_missing" || errMsg.includes("자격증명")) {
      return "ACRCloud 자격증명이 설정되지 않았습니다. .env 파일에서 ACRCLOUD_HOST, ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET을 확인해주세요.";
    }
    if (errMsg) return `ACR 분석 실패: ${errMsg}`;
    return "ACR 인식 결과가 없습니다. 오디오 DB에 등록되지 않은 음원이거나, 짧은 구간·전환부에서는 인식하지 못할 수 있습니다.";
  }
  if (reason === "frame_selection_failed") return "영상 프레임 추출에 실패했습니다. ffmpeg 또는 yt-dlp가 설치되어 있는지 확인해주세요.";
  if (reason === "no_text_frame") return "화면에서 텍스트를 읽지 못했습니다. 화면에 곡 목록이 텍스트로 표시되어야 OCR 분석이 가능합니다.";
  if (reason === "low_quality_frame") return "화면 텍스트 품질이 낮아 곡을 추출하지 못했습니다.";
  if (reason === "ocr_noise_too_high") return "OCR 노이즈가 높아 곡을 추출하지 못했습니다.";
  if (errMsg) return `OCR 분석 실패: ${errMsg}`;
  return "OCR에서 곡을 찾지 못했습니다. 화면에 곡 목록이 없거나 OPENAI_API_KEY가 설정되지 않았을 수 있습니다.";
}

async function runFallbackAnalysis(mode, { direct = false } = {}) {
  const stopProgress = startAnalyzeProgress(mode);
  const timeoutMs = mode === "ocr" ? 1800000 : 600000;
  const abortController = new AbortController();
  const timeoutId = window.setTimeout(() => abortController.abort(), timeoutMs);
  const actionLabel = `${mode.toUpperCase()} 분석`;
  try {
    prepareRunUi(`${mode.toUpperCase()} 분석 중입니다.`);
    const response = await fetch(buildApiUrl("/youtube/analyze-fallback"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        youtube_url: youtubeUrlInput.value.trim(),
        mode,
        text_songs: [],
      }),
      signal: abortController.signal,
    });
    const data = await handleApiResponse(response);
    const priorTitle = lastResultData?.youtube_title || textAnalysisData?.youtube_title || "";
    const priorThumbnail = lastResultData?.thumbnail_url || textAnalysisData?.thumbnail_url || "";
    const priorPlaylistName = getPlaylistName() || lastResultData?.playlist_name || textAnalysisData?.playlist_name || "";
    applyAnalysisData({
      ...data,
      youtube_title: data?.youtube_title || priorTitle,
      thumbnail_url: data?.thumbnail_url || priorThumbnail,
      playlist_name: priorPlaylistName,
      title_mode: titleModeSelect.value,
    }, actionLabel);

    const extractedSongs = safeArray(data?.songs).length ? safeArray(data.songs) : safeArray(data?.extracted_songs);
    if (!extractedSongs.length) {
      const reason = _fallbackEmptyReason(mode, data);
      setStatus("warn", reason);
      renderErrorBox(`${actionLabel} 결과 없음\n${reason}`);
      setFallbackPanelVisible(true, `${mode.toUpperCase()} 분석에서 곡을 찾지 못했습니다. 다른 방법을 선택하거나 결과를 확인해주세요.`);
      return;
    }

    setFallbackPanelVisible(false);
    setStatus("success", `${mode.toUpperCase()} 분석을 완료했습니다. Spotify 후보 검색을 진행합니다.`);
    stopProgress();
    await matchCandidatesFromCurrentSongs(mode);
  } catch (error) {
    const message = error.name === "AbortError" ? `${mode.toUpperCase()} 분석 시간 초과` : error.message;
    setStatus("error", `${actionLabel} 실패: ${message}`);
    renderErrorBox(`${actionLabel} 실패\n${message}`);
  } finally {
    window.clearTimeout(timeoutId);
    stopProgress();
    setButtonsDisabled(false);
  }
}

function updateNoticeFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const loginStatus = params.get("spotify_login");
  const reason = params.get("reason");

  if (loginStatus === "success") {
    history.replaceState(null, "", window.location.pathname);
    loginStatusLastFetchedAt = 0;
    updateSpotifyLoginUi(true);
    noticeBoard.textContent = "Spotify 로그인이 완료되었습니다. 이제 YouTube URL을 분석해 후보를 확인할 수 있습니다.";
    setStatus("success", "Spotify 로그인 완료. YouTube URL을 분석해주세요.");
    return;
  }

  if (loginStatus === "failed") {
    history.replaceState(null, "", window.location.pathname);
    const message = `Spotify 로그인 실패: ${reason || "unknown"}`;
    noticeBoard.textContent = message;
    setStatus("error", message);
    renderErrorBox(message);
  }
}

async function clearSpotifyLoginState() {
  const response = await fetch(buildApiUrl("/spotify/logout"), {
    method: "POST",
    credentials: "include",
  });
  await handleApiResponse(response);
  loginStatusLastFetchedAt = 0;
  updateSpotifyLoginUi(false);
}

async function startSpotifyLogin({ replaceAccount = false } = {}) {
  try {
    setButtonsDisabled(true);
    setStatus("loading", replaceAccount ? "기존 Spotify 로그인 기록을 지우고 새 로그인 URL을 가져오는 중입니다." : "Spotify 로그인 URL을 가져오는 중입니다.");
    if (replaceAccount) {
      await clearSpotifyLoginState();
    }
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
}

spotifyLoginBtn.addEventListener("click", () => {
  startSpotifyLogin({ replaceAccount: isSpotifyLoggedIn });
});

spotifyLogoutBtn?.addEventListener("click", async () => {
  try {
    setButtonsDisabled(true);
    setStatus("loading", "Spotify 로그인 기록을 지우는 중입니다.");
    await clearSpotifyLoginState();
    noticeBoard.textContent = "Spotify 로그아웃이 완료되었습니다. 필요하면 다른 계정으로 다시 로그인할 수 있습니다.";
    setStatus("success", "Spotify 로그아웃 완료.");
  } catch (error) {
    setStatus("error", `Spotify 로그아웃 실패: ${error.message}`);
    renderErrorBox(`Spotify 로그아웃 실패\n${error.message}`);
  } finally {
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

  const mode = getMode(); // "auto" | "text" | "ocr" | "acr"

  // ocr/acr 단독 모드: text 분석 없이 바로 실행
  if (mode === "ocr" || mode === "acr") {
    isAnalyzing = true;
    try {
      await runFallbackAnalysis(mode, { direct: true });
    } finally {
      isAnalyzing = false;
    }
    return;
  }

  // auto / text 모드: text 분석 먼저 실행
  isAnalyzing = true;
  const stopAnalyzeProgress = startAnalyzeProgress(mode);
  const timeoutMs = 300000;
  const timeoutMessage = "Text 분석 시간 초과 (5분). 서버 응답이 없습니다.";
  const abortController = new AbortController();
  const timeoutId = window.setTimeout(() => abortController.abort(), timeoutMs);
  try {
    prepareRunUi("description/comments 기반 Text 분석 중입니다.");
    setFallbackPanelVisible(false);
    const response = await fetch(buildApiUrl("/youtube/analyze-text"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        youtube_url: youtubeUrl,
        title_mode: titleModeSelect.value,
        playlist_name: getPlaylistName(),
      }),
      signal: abortController.signal,
    });
    const data = await handleApiResponse(response);
    textAnalysisData = {
      ...data,
      playlist_name: data?.playlist_name || getPlaylistName(),
      title_mode: titleModeSelect.value,
    };
    applyAnalysisData(textAnalysisData, "Text 분석");

    if (data?.youtube_result?.is_ai_playlist) {
      const aiMsg = data?.message || "AI 생성 음악 플레이리스트입니다. Spotify에서 찾을 수 없습니다.";
      setStatus("warn", aiMsg);
      renderErrorBox(`AI 플레이리스트 감지\n${aiMsg}`);
    } else if (mode === "text") {
      // text 모드: analysis_state 무관하게 항상 Spotify 매칭 진행
      setStatus("success", "Text 분석 완료. Spotify 후보 검색을 진행합니다.");
      stopAnalyzeProgress();
      await matchCandidatesFromCurrentSongs("text");
    } else if (data?.analysis_state === "text_success" || data?.analysis_state === "partial_success") {
      // auto 모드: 곡이 있으면 Spotify 매칭 진행, 매칭 결과가 나쁘면 그때 fallback 제안
      const statusMsg = data?.analysis_state === "partial_success"
        ? "텍스트에서 일부 곡을 찾았습니다. Spotify 후보 검색을 진행합니다."
        : "텍스트 분석이 충분합니다. Spotify 후보 검색을 진행합니다.";
      setStatus("success", statusMsg);
      stopAnalyzeProgress();
      await matchCandidatesFromCurrentSongs("text", { offerFallback: true });
    } else {
      // auto 모드 + text_failed: 곡이 없으니 매칭 건너뛰고 fallback 선택
      const reasonText = safeArray(data?.analysis_reasons).length
        ? ` 사유: ${safeArray(data.analysis_reasons).join(", ")}`
        : "";
      setFallbackPanelVisible(
        true,
        `${data?.message || "Text 분석에서 곡을 찾지 못했습니다."}${reasonText}`,
        false,
      );
      setStatus("warn", "Text 분석에서 곡을 찾지 못했습니다. OCR 또는 ACR을 선택해주세요.");
      activateTab("runTab");
    }
  } catch (error) {
    const message = error.name === "AbortError" ? timeoutMessage : error.message;
    setStatus("error", `Text 분석 실패: ${message}`);
    renderErrorBox(`Text 분석 실패\n${message}`);
    try { renderJson({ error: message }); } catch (_) {}
    candidateResults = [];
    try { renderCandidates(); } catch (_) {}
    try { updateRecentSummary("분석 실패", {}); } catch (_) {}
    if (mode === "auto") {
      setFallbackPanelVisible(true, "Text 분석 요청에 실패했습니다. OCR 또는 ACR로 시도해주세요.", false);
      activateTab("runTab");
    }
  } finally {
    window.clearTimeout(timeoutId);
    stopAnalyzeProgress();
    setButtonsDisabled(false);
    isAnalyzing = false;
  }
});

async function createPlaylistFromSelected() {
  const selectedUris = candidateResults
    .filter((item) => item.selected && canSelectCandidate(item))
    .map((item) => item.spotify_uri);

  if (selectedUris.length === 0) {
    const message = "선택된 곡이 없습니다.";
    setStatus("error", message);
    renderErrorBox(message);
    activateTab("candidatesTab");
    return;
  }

  try {
    prepareRunUi("선택한 곡으로 Spotify 플레이리스트를 생성하는 중입니다.");
    const titleMode = titleModeSelect.value || "youtube";
    const youtubeTitle = lastResultData?.youtube_title || "";
    const customName = getPlaylistName() || lastResultData?.playlist_name || "";
    const derivedName = titleMode === "custom"
      ? (customName || youtubeTitle || "YouTube 변환 플레이리스트")
      : (youtubeTitle || customName || "YouTube 변환 플레이리스트");
    const payload = {
      playlist_name: derivedName,
      description: `Created from YouTube: ${youtubeTitle || youtubeUrlInput.value.trim()}`,
      track_uris: selectedUris,
      thumbnail_url: lastResultData?.thumbnail_url || "",
      youtube_url: lastResultData?.youtube_url || youtubeUrlInput.value.trim(),
      title_mode: titleMode,
    };
    const response = await fetch(buildApiUrl("/playlist/create"), {
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
runOcrBtn?.addEventListener("click", () => runFallbackAnalysis("ocr"));
runAcrBtn?.addEventListener("click", () => runFallbackAnalysis("acr"));
matchTextOnlyBtn?.addEventListener("click", () => matchCandidatesFromCurrentSongs("text"));

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
  textAnalysisData = null;
  mergedSongSource = [];
  candidateResults = [];
  setFallbackPanelVisible(false);
  renderOcrInfoBanner({});
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
