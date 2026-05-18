import { useState } from "react";
import SiteHeader from "../components/SiteHeader.jsx";

const PREFILL_KEYS = {
  youtubeUrl: "orangebeats.prefill.youtubeUrl",
  titleMode: "orangebeats.prefill.titleMode",
  playlistName: "orangebeats.prefill.playlistName",
  autoAnalyze: "orangebeats.prefill.autoAnalyze",
  mode: "orangebeats.prefill.mode",
};

function isLikelyYoutubeUrl(value) {
  const trimmed = value.trim();
  if (!trimmed) return false;
  try {
    const withProto = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    const u = new URL(withProto);
    return /(^|\.)youtube\.com$/i.test(u.hostname) || /^youtu\.be$/i.test(u.hostname);
  } catch {
    return false;
  }
}

function RadioYoutubeIcon({ pressed }) {
  if (pressed) {
    return (
      <svg className="figma-radio__dot" viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="9" cy="9" r="8.5" fill="#ffffff" stroke="#fd6d11" />
        <circle cx="9" cy="9" r="6" fill="#fd6d11" />
      </svg>
    );
  }
  return (
    <svg className="figma-radio__dot" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="9" cy="9" r="8.5" fill="#ffffff" stroke="#6b6b6b" />
      <circle cx="9" cy="9" r="6" fill="#afafaf" />
    </svg>
  );
}

function RadioSelfIcon({ pressed }) {
  if (pressed) {
    return (
      <svg className="figma-radio__dot" viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="9" cy="9" r="8.5" fill="#ffffff" stroke="#fd6d11" />
        <circle cx="9" cy="9" r="6" fill="#fd6d11" />
      </svg>
    );
  }
  return (
    <svg className="figma-radio__dot" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="9" cy="9" r="8.5" fill="#ffffff" stroke="#6b6b6b" />
      <circle cx="9" cy="9" r="6" fill="#afafaf" />
    </svg>
  );
}

export default function PlaylistUrlPage() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [titleMode, setTitleMode] = useState("youtube");
  const [playlistTitle, setPlaylistTitle] = useState("");
  const [urlError, setUrlError] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    const url = youtubeUrl.trim();
    if (!isLikelyYoutubeUrl(url)) {
      setUrlError(true);
      return;
    }
    setUrlError(false);
    try {
      sessionStorage.setItem(PREFILL_KEYS.youtubeUrl, url);
      sessionStorage.setItem(PREFILL_KEYS.titleMode, titleMode);
      sessionStorage.setItem(PREFILL_KEYS.playlistName, titleMode === "custom" ? playlistTitle.trim() : "");
      sessionStorage.setItem(PREFILL_KEYS.mode, "text");
      sessionStorage.setItem(PREFILL_KEYS.autoAnalyze, "1");
    } catch {
      // sessionStorage unavailable — still navigate; user can paste in Lab
    }
    window.location.assign(`${window.location.origin}/result`);
  };

  return (
    <div className="playlist-url-page" data-node-id="99:304">
      <SiteHeader />

      <main className="playlist-url-page__main">
        <h1 className="playlist-url-page__heading" data-node-id="99:301">
          Playlist를 생성할 Youtube URL을 입력해주세요.
        </h1>

        <form className="playlist-url-page__form" onSubmit={handleSubmit} data-node-id="301:278" noValidate>
          <div
            className={`figma-piece figma-url-input ${urlError ? "figma-url-input--error" : "figma-url-input--default"}`}
            data-node-id="241:183"
          >
            <div className="figma-url-input__shell">
              <div className="figma-url-input__field">
                <input
                  id="playlist-youtube-url"
                  name="youtubeUrl"
                  className="figma-url-input__native"
                  type="url"
                  inputMode="url"
                  autoComplete="off"
                  placeholder="Youtube URL 입력"
                  value={youtubeUrl}
                  onChange={(ev) => {
                    setYoutubeUrl(ev.target.value);
                    if (urlError) setUrlError(false);
                  }}
                  aria-invalid={urlError}
                  aria-describedby={urlError ? "playlist-url-error" : undefined}
                />
                <span className="figma-url-input__glow" aria-hidden="true" />
                <button
                  className="figma-piece figma-playlist-create figma-playlist-create--default figma-url-input__action"
                  type="submit"
                  data-node-id="101:322"
                >
                  <span className="figma-piece__label figma-playlist-create__label">Playlist 생성</span>
                </button>
              </div>
            </div>
            {urlError ? (
              <p id="playlist-url-error" className="figma-url-input__error">
                유효하지 않은 URL 입니다!
              </p>
            ) : null}
          </div>

          <div className="playlist-url-page__radios" role="radiogroup" aria-label="플레이리스트 제목 방식">
            <button
              type="button"
              role="radio"
              aria-checked={titleMode === "youtube"}
              className={`figma-piece figma-radio ${titleMode === "youtube" ? "figma-radio--youtube-pressed" : "figma-radio--youtube-default"}`}
              data-node-id="157:110"
              onClick={() => setTitleMode("youtube")}
            >
              <RadioYoutubeIcon pressed={titleMode === "youtube"} />
              <span className="figma-piece__label figma-radio__label">유튜브 제목 그대로 사용</span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={titleMode === "custom"}
              className={`figma-piece figma-radio ${titleMode === "custom" ? "figma-radio--self-pressed" : "figma-radio--self-default"}`}
              data-node-id="157:116"
              onClick={() => setTitleMode("custom")}
            >
              <RadioSelfIcon pressed={titleMode === "custom"} />
              <span className="figma-piece__label figma-radio__label">직접 제목 입력</span>
            </button>
          </div>

          {titleMode === "custom" ? (
            <div className="playlist-url-page__title-field" data-node-id="159:156">
              <label className="playlist-url-page__title-label" htmlFor="playlist-custom-title">
                <span className="visually-hidden">Playlist 제목</span>
                <div className="playlist-url-page__title-input-wrap">
                  <input
                    id="playlist-custom-title"
                    className="playlist-url-page__title-input"
                    type="text"
                    placeholder="Playlist 제목 입력"
                    value={playlistTitle}
                    onChange={(e) => setPlaylistTitle(e.target.value)}
                    autoComplete="off"
                  />
                </div>
              </label>
            </div>
          ) : null}
        </form>
      </main>
    </div>
  );
}
