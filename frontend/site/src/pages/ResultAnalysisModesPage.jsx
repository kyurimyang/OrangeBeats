import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";
import UrlLoadingScreen from "../components/UrlLoadingScreen.jsx";

const REMATCH_MODE_KEY = "orangebeats.rematch.mode";
const SPA_ANALYZE_BUNDLE_KEY = "orangebeats.spaAnalyzeBundle";
const SPA_ANALYZE_APPLIED_V_KEY = "orangebeats.spaAnalyzeAppliedV";
const LAST_ANALYZED_KEYS = {
  youtubeUrl: "orangebeats.lastAnalyzed.youtubeUrl",
  titleMode: "orangebeats.lastAnalyzed.titleMode",
  playlistName: "orangebeats.lastAnalyzed.playlistName",
};

export default function ResultAnalysisModesPage() {
  const navigate = useNavigate();
  const [runningMode, setRunningMode] = useState(null);
  const [runError, setRunError] = useState("");

  useEffect(() => {
    const y = sessionStorage.getItem(LAST_ANALYZED_KEYS.youtubeUrl)?.trim();
    if (!y) {
      navigate("/create", { replace: true });
    }
  }, [navigate]);

  /* transform+vw 음수마진 대신 zoom 사용 — 탭 복귀 시 레이아웃 드리프트 방지용 리플로우 */
  useEffect(() => {
    const nudgeLayout = () => {
      window.dispatchEvent(new Event("resize"));
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        nudgeLayout();
      }
    };
    window.addEventListener("pageshow", nudgeLayout);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pageshow", nudgeLayout);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const runAnalysis = async (mode) => {
    if (runningMode) return;
    const youtubeUrl = sessionStorage.getItem(LAST_ANALYZED_KEYS.youtubeUrl)?.trim();
    if (!youtubeUrl) {
      navigate("/create", { replace: true });
      return;
    }
    const titleMode = sessionStorage.getItem(LAST_ANALYZED_KEYS.titleMode) || "youtube";
    const playlistName = sessionStorage.getItem(LAST_ANALYZED_KEYS.playlistName) || "";

    setRunningMode(mode);
    setRunError("");
    try {
      const response = await fetch("/playlist/analyze-youtube", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          youtube_url: youtubeUrl,
          mode,
          extraction_mode: mode,
          title_mode: titleMode,
          playlist_name: playlistName,
          skip_spotify_matching: false,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || "분석 요청에 실패했습니다.");
      }
      try {
        sessionStorage.removeItem(REMATCH_MODE_KEY);
        sessionStorage.removeItem(SPA_ANALYZE_APPLIED_V_KEY);
        sessionStorage.setItem(SPA_ANALYZE_BUNDLE_KEY, JSON.stringify({ v: Date.now(), data }));
      } catch {
        // ignore
      }
      navigate("/result");
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "분석 중 오류가 발생했습니다.");
    } finally {
      setRunningMode(null);
    }
  };

  const busy = Boolean(runningMode);

  if (runningMode) {
    return <UrlLoadingScreen />;
  }

  return (
    <div className="result-analysis-page" data-node-id="161:1457">
      <SiteHeader />
      <main className="result-analysis-page__main">
        <div className="result-analysis-page__scale-wrap">
          <header className="result-analysis-page__intro" data-node-id="161:1511">
            <p className="result-analysis-page__intro-line">두가지 방법이 있어요.</p>
            <p className="result-analysis-page__intro-line">
              영상에 따라 더 잘 맞는 분석 방법이 달라, 적합한 분석 방식을 선택해주세요.
            </p>
          </header>

          {runError ? (
            <p className="result-analysis-page__run-error" role="alert">
              {runError}
            </p>
          ) : null}

          <div className="result-analysis-page__cards">
          <section
            className="result-analysis-card"
            aria-labelledby="result-analysis-ocr-title"
            data-node-id="314:266"
          >
            <div className="result-analysis-card__title-pill" data-node-id="314:264">
              <h2 id="result-analysis-ocr-title" className="result-analysis-card__title-pill-text">
                OCR 이미지 분석
              </h2>
            </div>
            <p className="result-analysis-card__lead" data-node-id="164:1708">
              <span className="result-analysis-card__lead-line">
                <span className="result-analysis-card__lead-strong">영상 속 자막·타임스탬프·곡명</span>을
              </span>
              <span className="result-analysis-card__lead-line">읽어 노래를 찾습니다.</span>
            </p>
            <p className="result-analysis-card__desc" data-node-id="314:257">
              <span className="result-analysis-card__desc-line">화면에 곡 제목이나 아티스트 정보가 보이는</span>
              <span className="result-analysis-card__desc-line">믹스 영상 매칭에 유리합니다.</span>
            </p>
            <div className="result-analysis-card__listbox" data-node-id="314:265">
              <svg
                className="result-analysis-card__listbox-bg"
                xmlns="http://www.w3.org/2000/svg"
                width="303"
                height="129"
                viewBox="0 0 303 129"
                fill="none"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path
                  d="M0 20C0 8.95431 8.9543 0 20 0H283C294.046 0 303 8.95431 303 20V109C303 120.046 294.046 129 283 129H20C8.9543 129 0 120.046 0 109V20Z"
                  fill="#D9D9D9"
                  fillOpacity="0.05"
                />
              </svg>
              <ul className="result-analysis-card__list">
                <li>타임스탬프 포함 영상</li>
                <li>곡명 자막 표시 영상</li>
                <li>DJ Tracklist 영상</li>
              </ul>
            </div>
            <p className="result-analysis-card__note" data-node-id="314:256">
              화면 정보나 자막이 없는 영상에서는 정확도가 낮아질 수 있습니다.
            </p>
            <button
              type="button"
              className={`figma-piece figma-playlist-create ${
                runningMode === "ocr" ? "figma-playlist-create--pressed" : "figma-playlist-create--default"
              } result-analysis-card__run`}
              onClick={() => runAnalysis("ocr")}
              disabled={busy}
              aria-busy={runningMode === "ocr"}
              data-node-id="164:1711"
            >
              <span className="figma-piece__label figma-playlist-create__label">
                {runningMode === "ocr" ? "OCR 분석 중…" : "실행하기"}
              </span>
            </button>
          </section>

          <section
            className="result-analysis-card result-analysis-card--acr"
            aria-labelledby="result-analysis-acr-title"
            data-node-id="314:267"
          >
            <div className="result-analysis-card__title-pill" data-node-id="314:268">
              <h2 id="result-analysis-acr-title" className="result-analysis-card__title-pill-text">
                ACR 오디오 분석
              </h2>
            </div>
            <p className="result-analysis-card__lead" data-node-id="314:271">
              <span className="result-analysis-card__lead-line">
                <span className="result-analysis-card__lead-strong">영상의 오디오</span>를 직접 분석해
              </span>
              <span className="result-analysis-card__lead-line">노래를 찾습니다.</span>
            </p>
            <p className="result-analysis-card__desc" data-node-id="314:272">
              <span className="result-analysis-card__desc-line">화면에 곡 정보가 없거나,</span>
              <span className="result-analysis-card__desc-line">OCR 이미지 인식이 어려운 영상에 사용됩니다.</span>
            </p>
            <div className="result-analysis-card__listbox" data-node-id="314:273">
              <svg
                className="result-analysis-card__listbox-bg"
                xmlns="http://www.w3.org/2000/svg"
                width="303"
                height="129"
                viewBox="0 0 303 129"
                fill="none"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path
                  d="M0 20C0 8.95431 8.9543 0 20 0H283C294.046 0 303 8.95431 303 20V109C303 120.046 294.046 129 283 129H20C8.9543 129 0 120.046 0 109V20Z"
                  fill="#D9D9D9"
                  fillOpacity="0.05"
                />
              </svg>
              <ul className="result-analysis-card__list">
                <li>자막 없는 영상</li>
                <li>음악 중심 믹스</li>
                <li>감성 플레이리스트</li>
              </ul>
            </div>
            <p className="result-analysis-card__note" data-node-id="314:276">
              OCR 분석에 비해 시간이 다소 오래 걸릴 수 있습니다.
            </p>
            <button
              type="button"
              className={`figma-piece figma-playlist-create ${
                runningMode === "acr" ? "figma-playlist-create--pressed" : "figma-playlist-create--default"
              } result-analysis-card__run`}
              onClick={() => runAnalysis("acr")}
              disabled={busy}
              aria-busy={runningMode === "acr"}
            >
              <span className="figma-piece__label figma-playlist-create__label">
                {runningMode === "acr" ? "ACR 분석 중…" : "실행하기"}
              </span>
            </button>
          </section>
          </div>
        </div>
      </main>
    </div>
  );
}
