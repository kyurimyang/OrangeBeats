const backendBaseUrlInput = document.getElementById("backendBaseUrl");
const youtubeUrlInput = document.getElementById("youtubeUrl");
const modeSelect = document.getElementById("mode");
const titleModeSelect = document.getElementById("titleMode");
const playlistNameInput = document.getElementById("playlistName");

const spotifyLoginBtn = document.getElementById("spotifyLoginBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const createPlaylistBtn = document.getElementById("createPlaylistBtn");

const statusBox = document.getElementById("statusBox");
const resultBox = document.getElementById("resultBox");
const songsList = document.getElementById("songsList");

const summarySuccess = document.getElementById("summarySuccess");
const summaryStage = document.getElementById("summaryStage");
const summaryOcrUsed = document.getElementById("summaryOcrUsed");
const summarySongCount = document.getElementById("summarySongCount");

const guestbookLog = document.getElementById("guestbookLog");
const menuButtons = document.querySelectorAll(".menu-btn");

const thumbnailPreview = document.getElementById("thumbnailPreview");
const thumbnailImage = document.getElementById("thumbnailImage");
const thumbnailEmpty = document.getElementById("thumbnailEmpty");

function getBackendBaseUrl() {
  return backendBaseUrlInput.value.trim().replace(/\/$/, "");
}

function getYoutubeUrl() {
  return youtubeUrlInput.value.trim();
}

function getMode() {
  return modeSelect.value;
}

function getTitleMode() {
  return titleModeSelect.value;
}

function getPlaylistName() {
  return playlistNameInput.value.trim();
}

function setStatus(type, message) {
  statusBox.className = `status ${type}`;
  statusBox.textContent = message;
}

function setGuestbook(message) {
  if (!guestbookLog) return;

  guestbookLog.innerHTML = `
    <div class="guestbook-title">mini guestbook</div>
    <div class="guestbook-entry">${escapeHtml(message)}</div>
  `;
}

function renderJson(data) {
  resultBox.textContent = JSON.stringify(data, null, 2);
}

function renderSummary(data) {
  summarySuccess.textContent = String(data?.success ?? "-");
  summaryStage.textContent = data?.selected_stage ?? "-";
  summaryOcrUsed.textContent = String(data?.ocr_used ?? "-");
  summarySongCount.textContent = String((data?.songs || []).length ?? 0);
}

function renderSongs(songs) {
  if (!songs || songs.length === 0) {
    songsList.className = "songs-list empty";
    songsList.innerHTML = "아직 추출된 곡이 없어요 ...";
    return;
  }

  songsList.className = "songs-list";
  songsList.innerHTML = songs
    .map((song, index) => {
      const title = song.title || "(제목 없음)";
      const artist = song.artist || "(아티스트 없음)";
      const source = song.source || "-";

      return `
        <div class="song-item">
          <div class="song-title">${index + 1}. ${escapeHtml(title)}</div>
          <div class="song-meta">artist: ${escapeHtml(artist)}</div>
          <div class="song-meta">source: ${escapeHtml(source)}</div>
        </div>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function extractYoutubeVideoId(url) {
  try {
    const parsed = new URL(url);

    if (parsed.hostname.includes("youtu.be")) {
      return parsed.pathname.slice(1);
    }

    if (parsed.searchParams.get("v")) {
      return parsed.searchParams.get("v");
    }

    const paths = parsed.pathname.split("/");
    const embedIndex = paths.indexOf("embed");

    if (embedIndex !== -1 && paths[embedIndex + 1]) {
      return paths[embedIndex + 1];
    }

    return "";
  } catch {
    return "";
  }
}

function updateThumbnailPreview() {
  if (!thumbnailImage || !thumbnailEmpty) return;

  const youtubeUrl = getYoutubeUrl();
  const videoId = extractYoutubeVideoId(youtubeUrl);

  if (!videoId) {
    thumbnailImage.style.display = "none";
    thumbnailImage.src = "";
    thumbnailEmpty.style.display = "block";
    return;
  }

  thumbnailImage.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
  thumbnailImage.style.display = "block";
  thumbnailEmpty.style.display = "none";
}

async function handleApiResponse(response) {
  let data;

  try {
    data = await response.json();
  } catch (e) {
    throw new Error("JSON 응답 파싱 실패");
  }

  if (!response.ok) {
    const detail = data?.detail || data?.message || "요청 실패";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return data;
}

spotifyLoginBtn.addEventListener("click", async () => {
  try {
    setStatus("loading", "스포티파이 로그인 페이지 불러오는 중 ... ♫");
    setGuestbook("Spotify 로그인 페이지로 이동 준비 중이야 ♡");
    renderJson({ message: "Spotify 로그인 URL 요청 중..." });

    const baseUrl = getBackendBaseUrl();
    const response = await fetch(`${baseUrl}/spotify/login`);
    const data = await handleApiResponse(response);

    renderJson(data);

    const loginUrl = data?.login_url;
    if (!loginUrl) {
      throw new Error("login_url이 응답에 없습니다.");
    }

    setStatus("success", "Spotify 로그인 페이지로 이동할게 ♡");
    setGuestbook("로그인 링크 확인 완료! 이제 Spotify로 이동해 ♫");
    window.location.href = loginUrl;
  } catch (error) {
    setStatus("error", `로그인 요청 실패 ... ${error.message}`);
    setGuestbook(`로그인 실패 ㅠ ${error.message}`);
    renderJson({ error: error.message });
  }
});

analyzeBtn.addEventListener("click", async () => {
  const youtubeUrl = getYoutubeUrl();

  if (!youtubeUrl) {
    setStatus("error", "유튜브 링크를 먼저 넣어줘 ...");
    setGuestbook("먼저 유튜브 링크부터 넣어줘 ♡");
    return;
  }

  try {
    setStatus("loading", "플레이리스트 분석 중 ... 잠시만 기다려줘 ♫");
    setGuestbook("지금 열심히 곡 목록 분석 중이야 ... ♫");
    renderJson({ message: "분석 요청 중..." });
    renderSongs([]);
    renderSummary({});

    const baseUrl = getBackendBaseUrl();
    const query = new URLSearchParams({
      url: youtubeUrl,
      mode: getMode(),
    });

    const response = await fetch(`${baseUrl}/youtube/analyze?${query.toString()}`);
    const data = await handleApiResponse(response);

    renderJson(data);
    renderSummary(data);
    renderSongs(data?.songs || []);

    setStatus(
      "success",
      `분석 완료 ♡ stage=${data?.selected_stage ?? "-"} / ocr_used=${data?.ocr_used ?? false}`
    );
    setGuestbook(`분석 완료! ${(data?.songs || []).length}곡을 찾았어 ♡`);
  } catch (error) {
    setStatus("error", `분석 실패 ... ${error.message}`);
    setGuestbook(`분석 실패 ㅠ ${error.message}`);
    renderJson({ error: error.message });
    renderSummary({});
    renderSongs([]);
  }
});

createPlaylistBtn.addEventListener("click", async () => {
  const youtubeUrl = getYoutubeUrl();

  if (!youtubeUrl) {
    setStatus("error", "유튜브 링크를 먼저 넣어줘 ...");
    setGuestbook("유튜브 링크 없이 플레이리스트를 만들 수는 없어 ㅠ");
    return;
  }

  try {
    setStatus("loading", "스포티파이 플레이리스트 만드는 중 ... ♫");
    setGuestbook("Spotify 플레이리스트 생성 중이야 ... 조금만 기다려줘 ♡");
    renderJson({ message: "플레이리스트 생성 요청 중..." });

    const baseUrl = getBackendBaseUrl();
    const payload = {
      url: youtubeUrl,
      mode: getMode(),
      title_mode: getTitleMode(),
      playlist_name: getPlaylistName(),
    };

    const response = await fetch(`${baseUrl}/playlist/from-youtube`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await handleApiResponse(response);

    renderJson(data);

    const songs = data?.songs || data?.youtube_result?.songs || [];
    const summarySource = data?.youtube_result || data;

    renderSummary(summarySource);
    renderSongs(songs);

    setStatus(
      "success",
      `플레이리스트 생성 완료 ♡ name=${data?.playlist_name ?? "-"}`
    );
    setGuestbook(`플레이리스트 생성 완료! 이름은 ${data?.playlist_name ?? "unknown"} ♫`);
  } catch (error) {
    setStatus("error", `플레이리스트 생성 실패 ... ${error.message}`);
    setGuestbook(`플레이리스트 생성 실패 ㅠ ${error.message}`);
    renderJson({ error: error.message });
  }
});

menuButtons.forEach((button) => {
  button.addEventListener("click", () => {
    menuButtons.forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");

    const targetId = button.dataset.target;
    const target = document.getElementById(targetId);

    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

youtubeUrlInput.addEventListener("input", updateThumbnailPreview);

updateThumbnailPreview();