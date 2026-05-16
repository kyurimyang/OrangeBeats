import { useEffect, useState } from "react";
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
          </>
        )}
      </main>
    </div>
  );
}
