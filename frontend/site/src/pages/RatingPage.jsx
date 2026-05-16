import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";
import StarRating from "../components/StarRating.jsx";

const MAX_COMMENT = 500;

export default function RatingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const playlistUrl = String(location.state?.playlistUrl || "").trim();
  const playlistName = String(location.state?.playlistName || "").trim();

  const [score, setScore] = useState(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const textareaRef = useRef(null);

  const handleStarSelect = (nextScore) => {
    if (submitting || done) return;
    setScore(nextScore);
    setError("");
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  const submitRating = async () => {
    if (submitting || done || score === 0) return;
    setSubmitting(true);
    setError("");
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
      if (!response.ok) {
        throw new Error(data?.detail || "평점 저장에 실패했습니다.");
      }
      setDone(true);
      window.setTimeout(() => navigate("/", { replace: true }), 1400);
    } catch (e) {
      setError(e instanceof Error ? e.message : "평점 저장에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      submitRating();
    }
  };

  return (
    <div className="rating-page" data-node-id="245:396">
      <SiteHeader />
      <main className="rating-page__main">
        <div className="rating-page__copy">
          <p>서비스는 만족하셨나요?</p>
          <p>Orangebeats의 평점을 매겨주세요!</p>
        </div>

        <StarRating value={score} disabled={submitting || done} onSelect={handleStarSelect} />

        {score > 0 && !done && (
          <div className="rating-page__feedback">
            <label className="rating-page__feedback-label" htmlFor="rating-comment">
              한 줄 피드백 <span className="rating-page__feedback-optional">(선택)</span>
            </label>
            <textarea
              id="rating-comment"
              ref={textareaRef}
              className="rating-page__comment"
              placeholder="어떤 점이 좋거나 아쉬우셨나요?"
              maxLength={MAX_COMMENT}
              rows={3}
              disabled={submitting}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <span className="rating-page__char-count">
              {comment.length} / {MAX_COMMENT}
            </span>
            <button
              className="rating-page__submit"
              type="button"
              disabled={submitting}
              onClick={submitRating}
            >
              {submitting ? "저장 중…" : "제출하기"}
            </button>
          </div>
        )}

        {done ? <p className="rating-page__thanks">감사합니다!</p> : null}
        {error ? <p className="rating-page__error">{error}</p> : null}
      </main>
    </div>
  );
}
