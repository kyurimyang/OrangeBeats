import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";
import trashDefaultUrl from "../assets/figma/trash-default.svg?url";
import trashHoverUrl from "../assets/figma/trash-hover.svg?url";
import trashPressedUrl from "../assets/figma/trash-pressed.svg?url";

const TRASH_ICON_URL = {
  default: trashDefaultUrl,
  hover: trashHoverUrl,
  pressed: trashPressedUrl,
};

function ResultTrashButton({ ariaLabel, onRemove }) {
  const [hovered, setHovered] = useState(false);
  const [pressed, setPressed] = useState(false);
  const phase = pressed ? "pressed" : hovered ? "hover" : "default";

  return (
    <button
      type="button"
      className={`figma-piece figma-trash figma-trash--${phase} result-track-item__remove`}
      onClick={onRemove}
      aria-label={ariaLabel}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        setHovered(false);
        setPressed(false);
      }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
    >
      <img className="figma-trash__icon" src={TRASH_ICON_URL[phase]} alt="" aria-hidden="true" />
    </button>
  );
}

const PREFILL_KEYS = {
  youtubeUrl: "orangebeats.prefill.youtubeUrl",
  titleMode: "orangebeats.prefill.titleMode",
  playlistName: "orangebeats.prefill.playlistName",
  autoAnalyze: "orangebeats.prefill.autoAnalyze",
  mode: "orangebeats.prefill.mode",
};

function normalizeTracks(data) {
  const rows = Array.isArray(data?.results) ? data.results : [];
  const songs = Array.isArray(data?.songs)
    ? data.songs
    : Array.isArray(data?.extracted_songs)
      ? data.extracted_songs
      : [];
  return rows.map((item, index) => {
    const spotifyTitle = String(
      item.spotify_title ?? item.spotifyTitle ?? "",
    ).trim();
    const spotifyArtist = String(
      item.spotify_artist ?? item.spotifyArtist ?? "",
    ).trim();
    const songRow = songs[index] || {};
    const corr = songRow.corrected_input && typeof songRow.corrected_input === "object" ? songRow.corrected_input : null;
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
    /** 위 줄 = 곡명(Spotify track name), 아래 줄 = 가수 — 스포티파이 앱과 동일 */
    const trackName = spotifyTitle || inputTitle || "제목 없음";
    const performerLine = spotifyArtist || inputArtist || "아티스트 미상";
    return {
      id: `${item.spotify_uri || item.spotify_track_id || "track"}-${index}`,
      title: trackName,
      artist: performerLine,
      cover: item.album_image || "",
      spotifyUri: item.spotify_uri || "",
    };
  });
}

export default function ResultListPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [playlistName, setPlaylistName] = useState("YouTube 변환 플레이리스트");
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [tracks, setTracks] = useState([]);

  useEffect(() => {
    const run = async () => {
      try {
        const youtubeUrl = sessionStorage.getItem(PREFILL_KEYS.youtubeUrl)?.trim() || "";
        const titleMode = sessionStorage.getItem(PREFILL_KEYS.titleMode) || "youtube";
        const savedPlaylistName = sessionStorage.getItem(PREFILL_KEYS.playlistName) || "";
        if (!youtubeUrl) {
          setError("YouTube URL 정보가 없어 다시 입력이 필요합니다.");
          setLoading(false);
          return;
        }

        const payload = {
          youtube_url: youtubeUrl,
          mode: "text",
          extraction_mode: "text",
          title_mode: titleMode,
          playlist_name: savedPlaylistName,
          skip_spotify_matching: false,
        };
        const response = await fetch("/playlist/analyze-youtube", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.detail || "분석 요청에 실패했습니다.");
        }

        const normalized = normalizeTracks(data);
        setTracks(normalized);
        setPlaylistName(data?.playlist_name || savedPlaylistName || "YouTube 변환 플레이리스트");
        setYoutubeTitle(data?.youtube_title || "");

        sessionStorage.removeItem(PREFILL_KEYS.youtubeUrl);
        sessionStorage.removeItem(PREFILL_KEYS.titleMode);
        sessionStorage.removeItem(PREFILL_KEYS.playlistName);
        sessionStorage.removeItem(PREFILL_KEYS.autoAnalyze);
        sessionStorage.removeItem(PREFILL_KEYS.mode);
      } catch (e) {
        setError(e instanceof Error ? e.message : "분석 중 오류가 발생했습니다.");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const selectedUris = useMemo(() => tracks.map((track) => track.spotifyUri).filter(Boolean), [tracks]);

  const handleCreatePlaylist = async () => {
    if (creating) return;
    if (!selectedUris.length) {
      setError("Spotify 후보가 없어 플레이리스트를 만들 수 없습니다.");
      return;
    }
    try {
      setCreating(true);
      setError("");
      const response = await fetch("/playlist/create-selected", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playlist_name: playlistName,
          description: `Created from YouTube: ${youtubeTitle || "playlist"}`,
          track_uris: selectedUris,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "플레이리스트 생성 실패");
      }
      if (data?.playlist_url) {
        window.open(data.playlist_url, "_blank", "noopener,noreferrer");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "플레이리스트 생성 실패");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="result-list-page result-list-page--loading" data-node-id="97:131">
        <header className="result-loading-header" data-node-id="351:567">
          <div className="result-loading-header__inner" data-node-id="351:568">
            <a className="result-loading-header__logo" href="/" aria-label="Orange Beats 홈" data-node-id="351:569">
              <img src="/assets/home/logo.png" alt="Orange Beats" />
            </a>
            <nav className="result-loading-header__nav" aria-label="주요 메뉴" data-node-id="351:570">
              <a href="/help">Help</a>
              <a href="/faq">FAQ</a>
              <a href="/contact">Contact us</a>
            </nav>
          </div>
        </header>
        <main className="result-loading-main">
          <p className="result-list-loading__title">
            <span>Youtube에서 음원 가져오는 중</span>
            <span className="result-list-loading__dots" aria-hidden="true"></span>
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="result-list-page" data-node-id="161:1349">
      <SiteHeader />
      <main className="result-list-page__main">
        <p className="result-list-page__heading">Youtube에서 음악을 가져왔어요.</p>
        <section className="result-list-panel">
          {tracks.map((track, index) => (
            <article key={track.id} className="result-track-item">
              <span className="result-track-item__index">{index + 1}</span>
              {track.cover ? (
                <img className="result-track-item__cover" src={track.cover} alt="" />
              ) : (
                <div className="result-track-item__cover result-track-item__cover--placeholder" />
              )}
              <div className="result-track-item__meta">
                <p className="result-track-item__title">{track.title}</p>
                <p className="result-track-item__artist">{track.artist}</p>
              </div>
              <ResultTrashButton
                ariaLabel={`${track.title} 삭제`}
                onRemove={() => setTracks((prev) => prev.filter((_, i) => i !== index))}
              />
            </article>
          ))}
        </section>

        <div className="result-list-page__actions">
          <button
            type="button"
            className={`figma-piece figma-playlist-create ${creating ? "figma-playlist-create--pressed" : "figma-playlist-create--default"}`}
            onClick={handleCreatePlaylist}
            disabled={creating}
          >
            <span className="figma-piece__label figma-playlist-create__label">이대로 Playlist 만들기</span>
          </button>
          <button
            type="button"
            className="figma-piece figma-rematch figma-rematch--pressed"
            onClick={() => navigate("/create")}
          >
            <span className="figma-piece__label figma-rematch__label">원하는 노래가 없어요</span>
          </button>
        </div>

        {error ? <p className="result-list-page__error">{error}</p> : null}
      </main>
    </div>
  );
}
