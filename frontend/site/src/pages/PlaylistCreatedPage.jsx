import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";
import StarRating from "../components/StarRating.jsx";

const CREATED_PLAYLIST_KEY = "orangebeats.createdPlaylist";
const MAX_COMMENT = 500;

function readCreatedBundle(locationState) {
  const fromState = locationState?.createdPlaylist;
  if (fromState && typeof fromState === "object") return fromState;
  try {
    const raw = sessionStorage.getItem(CREATED_PLAYLIST_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export default function PlaylistCreatedPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [bundle] = useState(() => readCreatedBundle(location.state));

  const tracks = useMemo(
    () => (Array.isArray(bundle?.tracks) ? bundle.tracks : []),
    [bundle],
  );
  const playlistUrl = String(bundle?.playlistUrl || "").trim();
  const playlistName = String(bundle?.playlistName || "").trim();
  const thumbnailUrl = String(bundle?.thumbnailUrl || "").trim();
  const matchedCount = useMemo(
    () => tracks.filter((t) => t.spotifyUri).length,
    [tracks],
  );

  const [score, setScore] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [feedbackDone, setFeedbackDone] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");
  const textareaRef = useRef(null);

  useEffect(() => {
    if (!playlistUrl) navigate("/result", { replace: true });
  }, [playlistUrl, navigate]);

  const handleStarSelect = (nextScore) => {
    if (submitting || feedbackDone) return;
    setScore(nextScore);
    setFeedbackError("");
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  const submitRating = async () => {
    if (submitting || feedbackDone || score === 0) return;
    setSubmitting(true);
    setFeedbackError("");
    try {
      const response = await fetch("/feedback/ratings", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          score,
          playlist_url: playlistUrl,
          playlist_name: playlistName,
          comment: comment.trim(),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail || "평점 저장에 실패했습니다.");
      setFeedbackDone(true);
    } catch (e) {
      setFeedbackError(e instanceof Error ? e.message : "평점 저장에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!playlistUrl) return null;

  return (
    <div className="pcp">
      <SiteHeader />
      <main className="pcp-main">

        {/* 생성 완료 배지 */}
        <div className="pcp-badge">
          <span className="pcp-badge__check" aria-hidden="true">
            <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
              <polyline points="1,4 3.5,6.5 9,1" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          생성 완료
        </div>

        {/* 헤딩 */}
        <h1 className="pcp-heading">
          Playlist를<br />성공적으로 만들었어요!
        </h1>
        <p className="pcp-subheading">
          {tracks.length > 0
            ? `${tracks.length}곡 중 ${matchedCount}곡 모두 매칭됐어요. 지금 바로 스트리밍에서 열어보세요.`
            : "지금 바로 스트리밍에서 열어보세요."}
        </p>

        {/* 플레이리스트 카드 */}
        <div className="pcp-card">
          <div className="pcp-card__art">
            {thumbnailUrl && (
              <img
                className="pcp-card__art-thumbnail"
                src={thumbnailUrl}
                alt=""
                loading="lazy"
              />
            )}
          </div>
          <div className="pcp-card__info">
            <p className="pcp-card__meta-label">PLAYLIST · CREATED</p>
            <p className="pcp-card__title">{playlistName || "내 플레이리스트"}</p>
            <p className="pcp-card__meta">
              <span className="pcp-card__meta-dot" />
              orangebeats · {tracks.length}곡
            </p>
            <div className="pcp-card__actions">
              <a
                href={playlistUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="pcp-spotify-btn"
              >
                <svg className="pcp-spotify-btn__icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm5.52 17.315a.75.75 0 01-1.03.25c-2.822-1.725-6.376-2.115-10.562-1.158a.75.75 0 01-.335-1.462c4.578-1.046 8.503-.595 11.677 1.34a.75.75 0 01.25 1.03zm1.474-3.275a.937.937 0 01-1.288.309c-3.228-1.983-8.15-2.56-11.97-1.4a.937.937 0 01-.544-1.793c4.363-1.323 9.787-.683 13.492 1.596a.937.937 0 01.31 1.288zm.127-3.41c-3.873-2.3-10.26-2.511-13.953-1.39a1.125 1.125 0 01-.652-2.152c4.244-1.287 11.294-1.038 15.748 1.608a1.125 1.125 0 01-1.143 1.934z" />
                </svg>
                Spotify에서 바로 듣기
              </a>
            </div>
          </div>
        </div>

        {/* 하단 2열 레이아웃 */}
        <div className="pcp-bottom">

          {/* 트랙리스트 */}
          <div className="pcp-tracklist">
            <div className="pcp-tracklist__header">
              TRACKLIST · {tracks.length}
            </div>
            <div className="pcp-tracklist__body">
              {tracks.map((track, index) => (
                <div key={track.id || index} className="pcp-track">
                  <span className="pcp-track__num">{index + 1}</span>
                  {track.cover ? (
                    <img className="pcp-track__cover" src={track.cover} alt="" loading="lazy" />
                  ) : (
                    <div className="pcp-track__cover pcp-track__cover--placeholder" />
                  )}
                  <div className="pcp-track__meta">
                    <p className="pcp-track__title">{track.title}</p>
                    <p className="pcp-track__artist">{track.artist}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 사이드바 */}
          <div className="pcp-sidebar">

            {/* 피드백 카드 */}
            <div className="pcp-feedback">
              <p className="pcp-feedback__step-label">
                <span className="pcp-feedback__step-dot" aria-hidden="true" />
                LAST STEP
              </p>
              <p className="pcp-feedback__heading">
                orangebeats는<br />어땠나요?
              </p>
              <p className="pcp-feedback__desc">
                여러분의 평가가 서비스 개선과 품질 향상에 큰 도움이 돼요.
              </p>

              {!feedbackDone ? (
                <>
                  <StarRating value={score} disabled={submitting} onSelect={handleStarSelect} />
                  {score > 0 && (
                    <>
                      <textarea
                        ref={textareaRef}
                        className="pcp-feedback__textarea"
                        placeholder="추가로 남기고 싶은 의견이 있다면..."
                        maxLength={MAX_COMMENT}
                        rows={3}
                        disabled={submitting}
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submitRating();
                        }}
                      />
                      <button
                        className="pcp-feedback__submit"
                        type="button"
                        disabled={submitting || score === 0}
                        onClick={submitRating}
                      >
                        {submitting ? "저장 중…" : "평가 보내기"}
                      </button>
                    </>
                  )}
                  {feedbackError && <p className="pcp-feedback__error">{feedbackError}</p>}
                </>
              ) : (
                <p className="pcp-feedback__thanks">감사합니다!</p>
              )}
            </div>

            {/* 네비게이션 버튼 */}
            <button type="button" className="pcp-nav-btn" onClick={() => navigate("/create")}>
              <div>
                <p className="pcp-nav-btn__title">다른 영상 더 올리기</p>
                <p className="pcp-nav-btn__desc">새 내용으로 다시 시작</p>
              </div>
              <span className="pcp-nav-btn__arrow">→</span>
            </button>

            <button type="button" className="pcp-nav-btn" onClick={() => navigate("/")}>
              <div>
                <p className="pcp-nav-btn__title">홈으로 돌아가기</p>
                <p className="pcp-nav-btn__desc">추천 플레이리스트 보기</p>
              </div>
              <span className="pcp-nav-btn__arrow">→</span>
            </button>

          </div>
        </div>
      </main>
    </div>
  );
}
