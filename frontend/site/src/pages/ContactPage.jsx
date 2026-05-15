import { useCallback, useState } from "react";
import SiteHeader from "../components/SiteHeader.jsx";

const INTRO_LEAD = "서비스 개선 제안, 오류 제보, 협업 문의를 남겨주세요.";

const INTRO_TIPS = [
  "긴급한 로그인·연동 문제는 Spotify 연동 상태를 내용에 함께 적어주세요.",
  "기능 제안은 사용하신 YouTube URL 예시를 함께 적어주시면 검토가 빠릅니다.",
];

const QA_AUTHOR_FALLBACK = "Contact us";

export default function ContactPage() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

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
            category: "question",
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
