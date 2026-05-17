import { useCallback, useEffect, useState } from "react";
import SiteHeader from "../components/SiteHeader.jsx";

const INTRO_LEAD = "서비스 개선 제안, 오류 제보, 협업 문의를 남겨주세요.";

const INTRO_TIPS = [
  "긴급한 로그인·연동 문제는 Spotify 연동 상태를 내용에 함께 적어주세요.",
  "기능 제안은 사용하신 YouTube URL 예시를 함께 적어주시면 검토가 빠릅니다.",
];

const QA_AUTHOR_FALLBACK = "Contact us";

const CATEGORY_LABELS = {
  question: "일반 문의",
  bug: "버그",
  matching: "매칭",
  suggestion: "기능 제안",
  etc: "기타",
};

const FORM_CATEGORIES = [
  { key: "question", label: "일반 문의" },
  { key: "bug", label: "버그" },
  { key: "matching", label: "매칭" },
  { key: "suggestion", label: "기능 제안" },
  { key: "etc", label: "기타" },
];

const CATEGORY_LIST = [
  { key: "all", label: "전체" },
  { key: "question", label: "일반 문의" },
  { key: "bug", label: "버그" },
  { key: "matching", label: "매칭" },
  { key: "suggestion", label: "기능 제안" },
];

const PAGE_SIZE = 5;

function QaBoard({ refreshTrigger }) {
  const [posts, setPosts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch("/qa")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setPosts(Array.isArray(data) ? data : []))
      .catch(() => setPosts([]))
      .finally(() => setLoading(false));
  }, [refreshTrigger]);

  useEffect(() => { setPage(1); }, [statusFilter, categoryFilter, search, sort]);

  if (loading) return <p className="contact-qa-board__empty">불러오는 중…</p>;
  if (!posts) return null;

  const totalCount = posts.length;
  const waitingCount = posts.filter((p) => p.status !== "answered").length;
  const answeredCount = posts.filter((p) => p.status === "answered").length;

  let filtered = posts;
  if (statusFilter === "waiting") filtered = filtered.filter((p) => p.status !== "answered");
  if (statusFilter === "answered") filtered = filtered.filter((p) => p.status === "answered");
  if (categoryFilter !== "all") filtered = filtered.filter((p) => p.category === categoryFilter);
  if (search.trim()) {
    const q = search.trim().toLowerCase();
    filtered = filtered.filter(
      (p) => p.title.toLowerCase().includes(q) || p.content.toLowerCase().includes(q),
    );
  }
  if (sort === "oldest") {
    filtered = [...filtered].sort((a, b) => a.created_at.localeCompare(b.created_at));
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const paged = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const STATUS_TABS = [
    { key: "all", label: "전체", count: totalCount },
    { key: "waiting", label: "답변 대기", count: waitingCount },
    { key: "answered", label: "답변 완료", count: answeredCount },
  ];

  return (
    <div className="contact-qa-board__inner">
      {/* Top bar: status tabs + search + sort */}
      <div className="contact-qa-board__topbar">
        <div className="contact-qa-board__tabs">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`contact-qa-board__tab${statusFilter === tab.key ? " contact-qa-board__tab--active" : ""}`}
              onClick={() => setStatusFilter(tab.key)}
            >
              {tab.label} <span className="contact-qa-board__tab-count">{tab.count}</span>
            </button>
          ))}
        </div>
        <div className="contact-qa-board__search-wrap">
          <svg className="contact-qa-board__search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.5" />
            <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            className="contact-qa-board__search"
            placeholder="제목·내용으로 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="contact-qa-board__sort-wrap">
          <select
            className="contact-qa-board__sort"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="newest">최신순</option>
            <option value="oldest">오래된순</option>
          </select>
        </div>
      </div>

      {/* Category chips */}
      <div className="contact-qa-board__cats">
        {CATEGORY_LIST.map((cat) => (
          <button
            key={cat.key}
            type="button"
            className={`contact-qa-board__cat${categoryFilter === cat.key ? " contact-qa-board__cat--active" : ""}`}
            onClick={() => setCategoryFilter(cat.key)}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Meta row: count + page */}
      <div className="contact-qa-board__meta-row">
        <span className="contact-qa-board__meta-count">{filtered.length}건의 문의</span>
        {totalPages > 1 && (
          <span className="contact-qa-board__meta-page">page {currentPage} / {totalPages}</span>
        )}
      </div>

      {/* Post list */}
      {paged.length === 0 ? (
        <p className="contact-qa-board__empty">해당하는 문의가 없습니다.</p>
      ) : (
        <ul className="contact-qa-board__list">
          {paged.map((post) => {
            const isExpanded = expandedId === post.id;
            const isAnswered = post.status === "answered";
            return (
              <li key={post.id} className={`contact-qa-board__item${isExpanded ? " contact-qa-board__item--open" : ""}`}>
                <button
                  type="button"
                  className="contact-qa-board__item-top"
                  onClick={() => setExpandedId(isExpanded ? null : post.id)}
                  aria-expanded={isExpanded}
                >
                  <span className="contact-qa-board__item-num">{String(post.id).padStart(2, "0")}</span>
                  <div className="contact-qa-board__item-badges">
                    <span className={`contact-qa-board__badge-status${isAnswered ? " contact-qa-board__badge-status--answered" : ""}`}>
                      <span className="contact-qa-board__badge-dot" />
                      {isAnswered ? "답변 완료" : "답변 대기"}
                    </span>
                    <span className="contact-qa-board__badge-cat">
                      {CATEGORY_LABELS[post.category] || post.category}
                    </span>
                  </div>
                  <span className={`contact-qa-board__expand-icon${isExpanded ? " contact-qa-board__expand-icon--open" : ""}`}>
                    ›
                  </span>
                </button>
                <p className="contact-qa-board__item-title">{post.title}</p>
                <div className="contact-qa-board__item-sub">
                  <span>익명</span>
                  <span className="contact-qa-board__dot">·</span>
                  <span>{post.created_at?.slice(0, 10)}</span>
                  {isAnswered && (
                    <>
                      <span className="contact-qa-board__dot">·</span>
                      <span className="contact-qa-board__reply-count">💬 답변 1</span>
                    </>
                  )}
                </div>
                <p className="contact-qa-board__item-preview">{post.content}</p>
                {isExpanded && isAnswered && (
                  <div className="contact-qa-board__answer">
                    <span className="contact-qa-board__answer-label">관리자 답변</span>
                    <p className="contact-qa-board__answer-text">{post.answer}</p>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="contact-qa-board__pagination">
          <button
            type="button"
            className="contact-qa-board__page-btn"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
          >
            ‹
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              type="button"
              className={`contact-qa-board__page-btn${p === currentPage ? " contact-qa-board__page-btn--active" : ""}`}
              onClick={() => setPage(p)}
            >
              {p}
            </button>
          ))}
          <button
            type="button"
            className="contact-qa-board__page-btn"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage >= totalPages}
          >
            ›
          </button>
        </div>
      )}

      {/* FAQ banner */}
      <div className="contact-qa-board__faq-banner">
        <div className="contact-qa-board__faq-icon">+</div>
        <div className="contact-qa-board__faq-body">
          <strong className="contact-qa-board__faq-title">자주 묻는 질문에서 먼저 확인해 보세요</strong>
          <span className="contact-qa-board__faq-sub">결제·매칭 관련 답변은 대부분 FAQ에서 빠르게 찾을 수 있어요.</span>
        </div>
        <a href="/help" className="contact-qa-board__faq-btn">FAQ 보러가기</a>
      </div>
    </div>
  );
}

export default function ContactPage() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("question");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [boardKey, setBoardKey] = useState(0);

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (submitting) return;

      const trimmedTitle = title.trim();
      const trimmedContent = content.trim();

      if (!trimmedTitle || !trimmedContent) {
        setError("제목과 내용을 모두 입력해주세요.");
        return;
      }

      setSubmitting(true);
      setError("");
      setSuccess(false);

      try {
        const response = await fetch("/qa", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: trimmedTitle,
            author: QA_AUTHOR_FALLBACK,
            category,
            content: trimmedContent,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = data?.detail;
          throw new Error(
            typeof detail === "string" ? detail : "문의 등록에 실패했습니다. 잠시 후 다시 시도해주세요.",
          );
        }

        setTitle("");
        setContent("");
        setSuccess(true);
        setBoardKey((k) => k + 1);
      } catch (e) {
        setError(e instanceof Error ? e.message : "문의 등록에 실패했습니다.");
      } finally {
        setSubmitting(false);
      }
    },
    [content, submitting, title],
  );

  return (
    <div className="contact-page" data-node-id="351:238" data-name="001_3_contactus">
      <SiteHeader />
      <main className="contact-page__main">
        <h1 className="contact-page__title" data-node-id="351:241">
          Contact us
        </h1>

        <div className="contact-page__intro">
          <p className="contact-page__lead">{INTRO_LEAD}</p>
          <ul className="contact-page__tips">
            {INTRO_TIPS.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </div>

        <section className="contact-page__section" aria-labelledby="contact-qa-heading">
          <h2 id="contact-qa-heading" className="contact-page__section-title">
            문의 남기기
          </h2>

          <form className="contact-page__form" onSubmit={handleSubmit} noValidate>
            <div className="contact-page__field">
              <label className="contact-page__label">문의 유형</label>
              <div className="contact-page__cat-chips">
                {FORM_CATEGORIES.map((cat) => (
                  <button
                    key={cat.key}
                    type="button"
                    className={`contact-page__cat-chip${category === cat.key ? " contact-page__cat-chip--active" : ""}`}
                    onClick={() => setCategory(cat.key)}
                    disabled={submitting}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="contact-page__field">
              <label className="contact-page__label" htmlFor="qa-title">
                제목
              </label>
              <input
                id="qa-title"
                className="contact-page__input"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="문의 제목을 입력해주세요"
                maxLength={200}
                disabled={submitting}
                autoComplete="off"
              />
            </div>

            <div className="contact-page__field">
              <label className="contact-page__label" htmlFor="qa-content">
                내용
              </label>
              <textarea
                id="qa-content"
                className="contact-page__textarea"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="문의 내용을 입력해주세요. 기능 제안 시 YouTube URL 예시를 함께 적어주세요."
                rows={6}
                disabled={submitting}
              />
            </div>

            {error ? (
              <p className="contact-page__message contact-page__message--error" role="alert">
                {error}
              </p>
            ) : null}
            {success ? (
              <p className="contact-page__message contact-page__message--success" role="status">
                문의가 등록되었습니다. 검토 후 답변드리겠습니다.
              </p>
            ) : null}

            <button type="submit" className="contact-page__submit" disabled={submitting}>
              {submitting ? "등록 중…" : "문의 등록"}
            </button>
          </form>
        </section>

        <section className="contact-qa-board" aria-label="Q&A 게시판">
          <QaBoard refreshTrigger={boardKey} />
        </section>

        <footer className="contact-page__footer">
          <p className="contact-page__footer-line">© 2026 ORANGEBEATS — orangecarml studio</p>
          <p className="contact-page__footer-line">
            instagram{" "}
            <span className="contact-page__footer-sep" aria-hidden="true">
              |
            </span>{" "}
            <a
              className="contact-page__footer-link"
              href="https://www.instagram.com/ajou_orangecrml"
              target="_blank"
              rel="noopener noreferrer"
            >
              @ajou_orangecrml
            </a>
          </p>
          <p className="contact-page__footer-line">
            Mail{" "}
            <span className="contact-page__footer-sep" aria-hidden="true">
              |
            </span>{" "}
            <a className="contact-page__footer-link" href="mailto:leesyeon0310@ajou.ac.kr">
              leesyeon0310@ajou.ac.kr
            </a>
          </p>
        </footer>
      </main>
    </div>
  );
}
