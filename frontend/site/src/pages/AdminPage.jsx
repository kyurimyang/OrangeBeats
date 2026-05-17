import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";

const SESSION_KEY = "ob_admin_key";

function StatCard({ label, value, sub }) {
  return (
    <div className="admin-stat-card">
      <span className="admin-stat-card__label">{label}</span>
      <span className="admin-stat-card__value">{value ?? "—"}</span>
      {sub ? <span className="admin-stat-card__sub">{sub}</span> : null}
    </div>
  );
}

function DistributionBar({ distribution, total }) {
  return (
    <div className="admin-dist">
      {[5, 4, 3, 2, 1].map((star) => {
        const count = distribution?.[String(star)] ?? 0;
        const pct = total > 0 ? Math.round((count / total) * 100) : 0;
        return (
          <div key={star} className="admin-dist__row">
            <span className="admin-dist__star">★{star}</span>
            <div className="admin-dist__bar-wrap">
              <div className="admin-dist__bar" style={{ width: `${pct}%` }} />
            </div>
            <span className="admin-dist__count">{count}건</span>
          </div>
        );
      })}
    </div>
  );
}

function RatingsTable({ ratings }) {
  if (!ratings?.length) {
    return <p className="admin-empty">아직 제출된 피드백이 없습니다.</p>;
  }
  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            <th>#</th>
            <th>점수</th>
            <th>플레이리스트</th>
            <th>코멘트</th>
            <th>날짜</th>
          </tr>
        </thead>
        <tbody>
          {ratings.map((r) => (
            <tr key={r.id}>
              <td className="admin-table__id">{r.id}</td>
              <td className="admin-table__score">
                {"★".repeat(r.score)}
                {"☆".repeat(5 - r.score)}
              </td>
              <td className="admin-table__name">
                {r.playlist_url ? (
                  <a href={r.playlist_url} target="_blank" rel="noopener noreferrer">
                    {r.playlist_name || r.playlist_url}
                  </a>
                ) : (
                  r.playlist_name || "—"
                )}
              </td>
              <td className="admin-table__comment">{r.comment || <span className="admin-table__no-comment">없음</span>}</td>
              <td className="admin-table__date">{r.created_at?.slice(0, 16).replace("T", " ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const SESSION_KEY_INNER = "ob_admin_key";

function QaItem({ post, onAnswered, onDeleted }) {
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  const isAnswered = post.status === "answered";
  const showForm = !isAnswered || editing;

  const handleDelete = useCallback(async () => {
    if (!window.confirm("이 문의를 삭제할까요?")) return;
    const adminKey = sessionStorage.getItem(SESSION_KEY_INNER) || "";
    setDeleting(true);
    try {
      const res = await fetch(`/qa/${post.id}?admin_key=${encodeURIComponent(adminKey)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || "삭제에 실패했습니다.");
      }
      onDeleted(post.id);
    } catch (e) {
      setError(e.message);
      setDeleting(false);
    }
  }, [post.id, onDeleted]);

  const handleSubmit = useCallback(async () => {
    const answer = draft.trim();
    if (!answer) return;
    const adminKey = sessionStorage.getItem(SESSION_KEY_INNER) || "";
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`/qa/${post.id}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer, admin_key: adminKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "답변 등록에 실패했습니다.");
      setDraft("");
      setEditing(false);
      onAnswered(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }, [draft, post.id, onAnswered]);

  return (
    <div className={`admin-qa-item${isAnswered ? " admin-qa-item--answered" : ""}`}>
      <div className="admin-qa-item__meta">
        <span className={`admin-qa-item__badge${isAnswered ? " admin-qa-item__badge--answered" : " admin-qa-item__badge--waiting"}`}>
          {isAnswered ? "답변 완료" : "답변 대기"}
        </span>
        <span className="admin-qa-item__id">#{post.id}</span>
        <span className="admin-qa-item__date">{post.created_at?.slice(0, 16).replace("T", " ")}</span>
        <button
          type="button"
          className="admin-qa-item__delete-btn"
          onClick={handleDelete}
          disabled={deleting}
        >
          {deleting ? "삭제 중…" : "삭제"}
        </button>
      </div>
      <p className="admin-qa-item__title">{post.title}</p>
      <p className="admin-qa-item__content">{post.content}</p>

      {isAnswered && !editing && (
        <div className="admin-qa-item__answer-box">
          <span className="admin-qa-item__answer-label">관리자 답변</span>
          <p className="admin-qa-item__answer-text">{post.answer}</p>
          <button
            type="button"
            className="admin-qa-item__edit-btn"
            onClick={() => { setEditing(true); setDraft(post.answer); }}
          >
            수정
          </button>
        </div>
      )}

      {showForm && (
        <div className="admin-qa-item__form">
          <textarea
            className="admin-qa-item__textarea"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="답변을 입력하세요…"
            rows={3}
            disabled={submitting}
          />
          {error && <p className="admin-qa-item__error">{error}</p>}
          <div className="admin-qa-item__actions">
            {editing && (
              <button type="button" className="admin-qa-item__cancel" onClick={() => setEditing(false)}>
                취소
              </button>
            )}
            <button
              type="button"
              className="admin-qa-item__submit"
              onClick={handleSubmit}
              disabled={submitting || !draft.trim()}
            >
              {submitting ? "등록 중…" : editing ? "수정 완료" : "답변 등록"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function QaSection() {
  const [posts, setPosts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");

  useEffect(() => {
    fetch("/qa")
      .then((res) => { if (!res.ok) throw new Error(); return res.json(); })
      .then(setPosts)
      .catch(() => setFetchError("문의 목록을 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const handleAnswered = useCallback((updatedPost) => {
    setPosts((prev) => prev.map((p) => (p.id === updatedPost.id ? updatedPost : p)));
  }, []);

  const handleDeleted = useCallback((deletedId) => {
    setPosts((prev) => prev.filter((p) => p.id !== deletedId));
  }, []);

  if (loading) return <p className="admin-empty">문의 불러오는 중…</p>;
  if (fetchError) return <p className="admin-error">{fetchError}</p>;
  if (!posts?.length) return <p className="admin-empty">접수된 문의가 없습니다.</p>;

  return (
    <div className="admin-qa-list">
      {posts.map((post) => (
        <QaItem key={post.id} post={post} onAnswered={handleAnswered} onDeleted={handleDeleted} />
      ))}
    </div>
  );
}

export default function AdminPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const key = sessionStorage.getItem(SESSION_KEY);
    if (!key) {
      navigate("/", { replace: true });
      return;
    }

    fetch(`/feedback/admin?key=${encodeURIComponent(key)}`, { credentials: "include" })
      .then(async (res) => {
        if (res.status === 401) throw new Error("인증 오류. 다시 로그인해주세요.");
        if (!res.ok) throw new Error("데이터를 불러오지 못했습니다.");
        return res.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleLogout = () => {
    sessionStorage.removeItem(SESSION_KEY);
    navigate("/", { replace: true });
  };

  const { stats, ratings } = data ?? {};

  return (
    <div className="admin-page">
      <SiteHeader />
      <main className="admin-main">
        <div className="admin-header">
          <h1 className="admin-header__title">
            <span className="admin-header__badge">ADMIN</span>
            피드백 대시보드
          </h1>
          <button className="admin-header__logout" type="button" onClick={handleLogout}>
            나가기
          </button>
        </div>

        {loading && <p className="admin-loading">불러오는 중…</p>}
        {error && <p className="admin-error">{error}</p>}

        {data && (
          <>
            <section className="admin-section">
              <h2 className="admin-section__title">통계</h2>
              <div className="admin-stats-grid">
                <StatCard label="총 제출 수" value={`${stats.count}건`} />
                <StatCard
                  label="평균 점수"
                  value={stats.average != null ? `${stats.average} ★` : null}
                />
                <StatCard
                  label="최근 7일 평균"
                  value={stats.recent_7day_average != null ? `${stats.recent_7day_average} ★` : null}
                />
                <StatCard
                  label="코멘트 비율"
                  value={`${Math.round(stats.comment_rate * 100)}%`}
                  sub={`${Math.round(stats.comment_rate * stats.count)}명 작성`}
                />
              </div>
            </section>

            <section className="admin-section">
              <h2 className="admin-section__title">점수 분포</h2>
              <DistributionBar distribution={stats.distribution} total={stats.count} />
            </section>

            <section className="admin-section">
              <h2 className="admin-section__title">평점 목록</h2>
              <RatingsTable ratings={ratings} />
            </section>

            <section className="admin-section">
              <h2 className="admin-section__title">문의 관리</h2>
              <QaSection />
            </section>
          </>
        )}
      </main>
    </div>
  );
}
