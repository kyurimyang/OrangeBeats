import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";
import UrlLoadingScreen from "../components/UrlLoadingScreen.jsx";
import PlaylistCreateLoading, {
  usePlaylistCreateProgress,
} from "../components/PlaylistCreateLoading.jsx";
import { collectPlaylistTrackUris, normalizeTracks } from "../utils/resultTracks.js";
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
      <img
        className={`figma-trash__icon figma-trash__icon--${phase}`}
        src={TRASH_ICON_URL[phase]}
        alt=""
        aria-hidden="true"
      />
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

const LAST_ANALYZED_KEYS = {
  youtubeUrl: "orangebeats.lastAnalyzed.youtubeUrl",
  titleMode: "orangebeats.lastAnalyzed.titleMode",
  playlistName: "orangebeats.lastAnalyzed.playlistName",
};

const REMATCH_MODE_KEY = "orangebeats.rematch.mode";
const SPA_ANALYZE_BUNDLE_KEY = "orangebeats.spaAnalyzeBundle";
const SPA_ANALYZE_APPLIED_V_KEY = "orangebeats.spaAnalyzeAppliedV";
const CREATED_PLAYLIST_KEY = "orangebeats.createdPlaylist";

export default function ResultListPage() {
  const navigate = useNavigate();
  const location = useLocation();
  /** `navigate(..., { state })`로 분석 결과를 받은 뒤, replace로 state를 비울 때 한 번 POST를 건너뜀 */
  const skipFetchOnceRef = useRef(false);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [createTrackCount, setCreateTrackCount] = useState(0);
  const { percent, secondsLeft, finish } = usePlaylistCreateProgress(creating, createTrackCount);
  const [error, setError] = useState("");
  const [playlistName, setPlaylistName] = useState("YouTube 변환 플레이리스트");
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [tracks, setTracks] = useState([]);
  const analyzeDataRef = useRef(null);

  useEffect(() => {
    const run = async () => {
      try {
        setError("");

        const applyFromAnalyzeData = (data) => {
          analyzeDataRef.current = data;
          const normalized = normalizeTracks(data);
          setTracks(normalized);
          const savedPlaylistName =
            sessionStorage.getItem(PREFILL_KEYS.playlistName) ||
            sessionStorage.getItem(LAST_ANALYZED_KEYS.playlistName) ||
            "";
          const titleMode =
            sessionStorage.getItem(PREFILL_KEYS.titleMode) ||
            sessionStorage.getItem(LAST_ANALYZED_KEYS.titleMode) ||
            "youtube";
          setPlaylistName(data?.playlist_name || savedPlaylistName || "YouTube 변환 플레이리스트");
          setYoutubeTitle(data?.youtube_title || "");
          const youtubeUrl =
            sessionStorage.getItem(PREFILL_KEYS.youtubeUrl)?.trim() ||
            sessionStorage.getItem(LAST_ANALYZED_KEYS.youtubeUrl)?.trim() ||
            "";
          if (youtubeUrl) {
            sessionStorage.setItem(LAST_ANALYZED_KEYS.youtubeUrl, youtubeUrl);
            sessionStorage.setItem(LAST_ANALYZED_KEYS.titleMode, titleMode);
            sessionStorage.setItem(LAST_ANALYZED_KEYS.playlistName, savedPlaylistName);
          }
          try {
            sessionStorage.removeItem(REMATCH_MODE_KEY);
          } catch {
            // ignore
          }
          sessionStorage.removeItem(PREFILL_KEYS.youtubeUrl);
          sessionStorage.removeItem(PREFILL_KEYS.titleMode);
          sessionStorage.removeItem(PREFILL_KEYS.playlistName);
          sessionStorage.removeItem(PREFILL_KEYS.autoAnalyze);
          sessionStorage.removeItem(PREFILL_KEYS.mode);
        };

        const bundleRaw = sessionStorage.getItem(SPA_ANALYZE_BUNDLE_KEY);
        if (bundleRaw) {
          try {
            const bundle = JSON.parse(bundleRaw);
            const data = bundle?.data;
            const v = bundle?.v != null ? String(bundle.v) : "";
            if (data != null && typeof data === "object" && v) {
              const appliedV = sessionStorage.getItem(SPA_ANALYZE_APPLIED_V_KEY);
              if (appliedV === v) {
                applyFromAnalyzeData(data);
                sessionStorage.removeItem(SPA_ANALYZE_BUNDLE_KEY);
                sessionStorage.removeItem(SPA_ANALYZE_APPLIED_V_KEY);
                skipFetchOnceRef.current = true;
                navigate(location.pathname, { replace: true, state: {} });
                return;
              }
              applyFromAnalyzeData(data);
              sessionStorage.setItem(SPA_ANALYZE_APPLIED_V_KEY, v);
              skipFetchOnceRef.current = true;
              navigate(location.pathname, { replace: true, state: {} });
              return;
            }
          } catch {
            sessionStorage.removeItem(SPA_ANALYZE_BUNDLE_KEY);
            sessionStorage.removeItem(SPA_ANALYZE_APPLIED_V_KEY);
          }
        }

        const direct =
          location.state && typeof location.state === "object" ? location.state.analyzeResponse : undefined;
        if (direct != null && typeof direct === "object") {
          applyFromAnalyzeData(direct);
          skipFetchOnceRef.current = true;
          navigate(location.pathname, { replace: true, state: {} });
          return;
        }

        if (skipFetchOnceRef.current) {
          skipFetchOnceRef.current = false;
          return;
        }

        const rematchStored = sessionStorage.getItem(REMATCH_MODE_KEY);
        const rematchMode = rematchStored === "ocr" || rematchStored === "acr" ? rematchStored : null;

        const youtubeUrl =
          sessionStorage.getItem(PREFILL_KEYS.youtubeUrl)?.trim() ||
          sessionStorage.getItem(LAST_ANALYZED_KEYS.youtubeUrl)?.trim() ||
          "";
        const titleMode =
          sessionStorage.getItem(PREFILL_KEYS.titleMode) ||
          sessionStorage.getItem(LAST_ANALYZED_KEYS.titleMode) ||
          "youtube";
        const savedPlaylistName =
          sessionStorage.getItem(PREFILL_KEYS.playlistName) ||
          sessionStorage.getItem(LAST_ANALYZED_KEYS.playlistName) ||
          "";
        if (!youtubeUrl) {
          setError("YouTube URL 정보가 없어 다시 입력이 필요합니다.");
          setLoading(false);
          return;
        }

        const extractionMode = rematchMode || "text";

        const payload = {
          youtube_url: youtubeUrl,
          mode: extractionMode,
          extraction_mode: extractionMode,
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

        try {
          if (youtubeUrl) {
            sessionStorage.setItem(LAST_ANALYZED_KEYS.youtubeUrl, youtubeUrl);
            sessionStorage.setItem(LAST_ANALYZED_KEYS.titleMode, titleMode);
            sessionStorage.setItem(LAST_ANALYZED_KEYS.playlistName, savedPlaylistName);
          }
        } catch {
          // ignore
        }
        if (rematchMode) {
          try {
            sessionStorage.removeItem(REMATCH_MODE_KEY);
          } catch {
            // ignore
          }
        }

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
  }, [location.key, location.pathname, navigate]);

  const handleCreatePlaylist = async () => {
    if (creating) return;

    let urisToAdd = collectPlaylistTrackUris(tracks);
    if (!urisToAdd.length && analyzeDataRef.current) {
      urisToAdd = collectPlaylistTrackUris(normalizeTracks(analyzeDataRef.current));
    }

    if (!urisToAdd.length) {
      setError(
        "Spotify에 추가할 수 있는 곡이 없습니다. 매칭된 곡이 있는지 확인하거나, 다시 분석해 주세요.",
      );
      return;
    }
    try {
      setCreateTrackCount(urisToAdd.length);
      setCreating(true);
      setError("");
      const youtubeUrl =
        sessionStorage.getItem(LAST_ANALYZED_KEYS.youtubeUrl)?.trim() ||
        sessionStorage.getItem(PREFILL_KEYS.youtubeUrl)?.trim() ||
        String(analyzeDataRef.current?.youtube_url || "").trim();
      const response = await fetch("/playlist/create-selected", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playlist_name: playlistName,
          description: `Created from YouTube: ${youtubeTitle || "playlist"}`,
          track_uris: urisToAdd,
          youtube_url: youtubeUrl,
          youtube_title: youtubeTitle,
          thumbnail_url: String(analyzeDataRef.current?.thumbnail_url || "").trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "플레이리스트 생성 실패");
      }
      const playlistUrl = String(data?.playlist_url || "").trim();
      if (!playlistUrl) {
        throw new Error("Spotify 플레이리스트 URL을 받지 못했습니다.");
      }
      const createdPlaylist = {
        playlistUrl,
        playlistName: data?.playlist_name || playlistName,
        tracks,
      };
      try {
        sessionStorage.setItem(CREATED_PLAYLIST_KEY, JSON.stringify(createdPlaylist));
      } catch {
        // ignore
      }
      finish();
      await new Promise((resolve) => window.setTimeout(resolve, 480));
      navigate("/result/created", { state: { createdPlaylist } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "플레이리스트 생성 실패");
      setCreating(false);
    }
  };

  if (creating) {
    return (
      <div className="result-list-page result-list-page--creating" data-node-id="playlist-create-loading">
        <SiteHeader />
        <PlaylistCreateLoading
          percent={percent}
          secondsLeft={secondsLeft}
          playlistTitle={playlistName}
        />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="result-list-page result-list-page--loading" data-node-id="97:131">
        <SiteHeader />
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
            <article
              key={track.id}
              className={`result-track-item${track.confidenceLabel === "low" ? " result-track-item--low-confidence" : ""}`}
            >
              <span className="result-track-item__index">{index + 1}</span>
              {track.cover ? (
                <img
                  className="result-track-item__cover"
                  src={track.cover}
                  alt=""
                  loading="lazy"
                />
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
            onClick={() => navigate("/result/analysis")}
          >
            <span className="figma-piece__label figma-rematch__label">원하는 노래가 없어요</span>
          </button>
        </div>

        {error ? <p className="result-list-page__error">{error}</p> : null}
      </main>
    </div>
  );
}
