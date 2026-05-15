import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";
import StarRating from "../components/StarRating.jsx";

export default function RatingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const playlistUrl = String(location.state?.playlistUrl || "").trim();
  const playlistName = String(location.state?.playlistName || "").trim();

  const [score, setScore] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const submitRating = async (nextScore) => {
    if (submitting || done) return;
    setScore(nextScore);
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch("/feedback/ratings", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          score: nextScore,
          playlist_url: playlistUrl,
          playlist_name: playlistName,
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
      setScore(0);
    } finally {
      setSubmitting(false);
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
        <StarRating value={score} disabled={submitting || done} onSelect={submitRating} />
        {done ? <p className="rating-page__thanks">감사합니다!</p> : null}
        {error ? <p className="rating-page__error">{error}</p> : null}
      </main>
    </div>
  );
}
