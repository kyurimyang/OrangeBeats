const API_BASE = "http://127.0.0.1:8000";

const spotifyLoginBtn = document.getElementById("spotifyLoginBtn");
const clearBtn = document.getElementById("clearBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const createBtn = document.getElementById("createBtn");
const youtubeUrlInput = document.getElementById("youtubeUrl");
const playlistNameInput = document.getElementById("playlistName");
const resultBox = document.getElementById("resultBox");
const summaryBox = document.getElementById("summaryBox");
const songList = document.getElementById("songList");
const statusBadge = document.getElementById("statusBadge");
const titleModeInputs = document.querySelectorAll('input[name="titleMode"]');

function getTitleMode() {
  const checked = document.querySelector('input[name="titleMode"]:checked');
  return checked ? checked.value : "youtube";
}

function syncTitleInputState() {
  const titleMode = getTitleMode();
  playlistNameInput.disabled = titleMode !== "custom";
  if (titleMode !== "custom") {
    playlistNameInput.value = "";
  }
}

function setStatus(type, text) {
  statusBadge.className = "badge";
  if (type) {
    statusBadge.classList.add(type);
  }
  statusBadge.textContent = text;
}

function setResult(data) {
  if (typeof data === "string") {
    resultBox.textContent = data;
    return;
  }
  resultBox.textContent = JSON.stringify(data, null, 2);
}

function clearSongs() {
  songList.innerHTML = "";
}

function renderSongs(songs = []) {
  clearSongs();

  if (!Array.isArray(songs) || songs.length === 0) {
    return;
  }

  songs.forEach((song, index) => {
    const li = document.createElement("li");
    li.className = "song-item";

    const artist = (song.artist || "").trim() || "아티스트 없음";
    const title = (song.title || "").trim() || "제목 없음";

    li.innerHTML = `
      <div class="song-index">${index + 1}번 곡</div>
      <div class="song-title">${escapeHtml(title)}</div>
      <div class="song-artist">${escapeHtml(artist)}</div>
    `;

    songList.appendChild(li);
  });
}

function renderAnalyzeSummary(data) {
  if (!data || !data.success) {
    summaryBox.classList.remove("empty");
    summaryBox.innerHTML = "분석은 실행됐지만 표시할 수 있는 결과가 없습니다.";
    return;
  }

  const youtubeTitle = data.youtube_title || "제목 없음";
  const count = Array.isArray(data.songs) ? data.songs.length : 0;

  summaryBox.classList.remove("empty");
  summaryBox.innerHTML = `
    <strong>유튜브 제목:</strong> ${escapeHtml(youtubeTitle)}<br>
    <strong>추출 곡 수:</strong> ${count}곡
  `;
}

function renderCreateSummary(data) {
  if (!data || !data.success) {
    summaryBox.classList.remove("empty");
    summaryBox.innerHTML = "플레이리스트 생성은 실행됐지만 표시할 수 있는 결과가 없습니다.";
    return;
  }

  const youtubeTitle = data.youtube_title || "제목 없음";
  const playlistName = data.playlist_name || "제목 없음";
  const count = data.extracted_count ?? (Array.isArray(data.songs) ? data.songs.length : 0);

  summaryBox.classList.remove("empty");
  summaryBox.innerHTML = `
    <strong>유튜브 제목:</strong> ${escapeHtml(youtubeTitle)}<br>
    <strong>생성된 플레이리스트 제목:</strong> ${escapeHtml(playlistName)}<br>
    <strong>전달 곡 수:</strong> ${count}곡
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);

  let data;
  try {
    data = await response.json();
  } catch (error) {
    data = { detail: "JSON 응답 파싱 실패", raw_error: error.message };
  }

  if (!response.ok) {
    const errorMessage = data?.detail || `HTTP ${response.status} 오류`;
    const err = new Error(errorMessage);
    err.status = response.status;
    err.payload = data;
    throw err;
  }

  return data;
}

spotifyLoginBtn.addEventListener("click", async () => {
  try {
    setStatus("loading", "Spotify 로그인 URL 요청 중");
    setResult("Spotify 로그인 URL 요청 중...");

    const data = await fetchJson(`${API_BASE}/spotify/login`);
    setResult(data);
    setStatus("success", "Spotify 로그인 페이지로 이동");

    if (data.login_url) {
      window.location.href = data.login_url;
      return;
    }

    throw new Error("login_url을 받지 못했습니다.");
  } catch (error) {
    console.error(error);
    setStatus("error", "Spotify 로그인 실패");
    setResult({
      message: error.message,
      status: error.status,
      detail: error.payload || null,
    });
  }
});

analyzeBtn.addEventListener("click", async () => {
  const youtubeUrl = youtubeUrlInput.value.trim();

  if (!youtubeUrl) {
    setStatus("error", "URL 필요");
    setResult("유튜브 링크를 입력해줘.");
    return;
  }

  try {
    setStatus("loading", "유튜브 분석 중");
    setResult("유튜브 분석 요청 보내는 중...");

    const encodedUrl = encodeURIComponent(youtubeUrl);
    const data = await fetchJson(`${API_BASE}/youtube/analyze?url=${encodedUrl}`);

    renderAnalyzeSummary(data);
    renderSongs(data.songs || []);
    setResult(data);
    setStatus("success", "유튜브 분석 완료");
  } catch (error) {
    console.error(error);
    summaryBox.classList.remove("empty");
    summaryBox.textContent = "분석 실패";
    clearSongs();
    setStatus("error", `분석 실패 (${error.status || "ERR"})`);
    setResult({
      message: error.message,
      status: error.status,
      detail: error.payload || null,
    });
  }
});

createBtn.addEventListener("click", async () => {
  const youtubeUrl = youtubeUrlInput.value.trim();
  const titleMode = getTitleMode();
  const playlistName = playlistNameInput.value.trim();

  if (!youtubeUrl) {
    setStatus("error", "URL 필요");
    setResult("유튜브 링크를 입력해줘.");
    return;
  }

  const payload = {
    url: youtubeUrl,
    title_mode: titleMode,
    playlist_name: playlistName,
  };

  try {
    setStatus("loading", "플레이리스트 생성 중");
    setResult({ message: "플레이리스트 생성 요청 보내는 중...", payload });

    const data = await fetchJson(`${API_BASE}/playlist/from-youtube`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    renderCreateSummary(data);
    renderSongs(data.songs || []);
    setResult(data);
    setStatus("success", "플레이리스트 생성 완료");
  } catch (error) {
    console.error(error);
    summaryBox.classList.remove("empty");
    summaryBox.textContent = "플레이리스트 생성 실패";
    clearSongs();
    setStatus("error", `생성 실패 (${error.status || "ERR"})`);
    setResult({
      message: error.message,
      status: error.status,
      request_payload: payload,
      detail: error.payload || null,
      hint:
        error.status === 401
          ? "Spotify 로그인이 먼저 필요합니다. 로그인 후 이 화면으로 돌아와 다시 시도하세요."
          : error.status === 400
            ? "요청 body 값, 유튜브 분석 결과, 추출 곡 수를 다시 확인하세요."
            : null,
    });
  }
});

clearBtn.addEventListener("click", () => {
  youtubeUrlInput.value = "";
  playlistNameInput.value = "";
  document.querySelector('input[name="titleMode"][value="youtube"]').checked = true;
  syncTitleInputState();
  summaryBox.className = "summary empty";
  summaryBox.textContent = "아직 분석 결과가 없습니다.";
  clearSongs();
  setStatus("", "대기 중");
  setResult("아직 요청 안 함");
});

titleModeInputs.forEach((input) => {
  input.addEventListener("change", syncTitleInputState);
});

syncTitleInputState();
