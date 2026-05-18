import { Fragment, useCallback, useId, useState } from "react";
import SiteHeader from "../components/SiteHeader.jsx";

const FAQ_ITEMS = [
  {
    id: "free-spotify",
    number: "01",
    question: "스포티파이 무료 버전을 이용중인데 사용 가능한가요?",
    lines: [
      {
        type: "line",
        text: "ㄴ 가능합니다! Spotify 앱의 유료 유저가 아니어도, Orangebeats의 서비스를 이용하실 수 있습니다.",
      },
    ],
  },
  {
    id: "auto-playlist",
    number: "02",
    question: "플레이리스트는 자동으로 생성되나요?",
    lines: [
      {
        type: "line",
        text: "ㄴ 곡 후보를 먼저 보여드린 뒤, 사용자가 선택·확정한 곡만 Spotify 플레이리스트에 담습니다.",
      },
    ],
  },
  {
    id: "unmatched",
    number: "03",
    question: "매칭이 안되는 곡이 있으면 어떻게 하나요?",
    lines: [
      {
        type: "line",
        text: "ㄴ 후보 화면에서 다른 검색 결과를 선택하거나, 해당 곡을 제외한 뒤 다시 생성할 수 있습니다.",
      },
    ],
  },
  {
    id: "opacity",
    number: "04",
    question: "생성된 곡 리스트에서 투명도 차이는 무엇인가요?",
    lines: [
      {
        type: "hang",
        rows: [
          "매칭 신뢰도가 낮은 곡은 행 전체가 더 투명하게 표시됩니다.",
          "선명하게 보이는 곡은 신뢰도가 높은 매칭 결과입니다.",
        ],
      },
    ],
  },
];

function FaqAnswerHang({ rows }) {
  return (
    <div className="faq-page__answer-hang">
      {rows.map((text, rowIndex) => (
        <Fragment key={text}>
          <span className="faq-page__answer-marker" aria-hidden={rowIndex > 0}>
            {rowIndex === 0 ? (
              "ㄴ"
            ) : (
              <span className="faq-page__answer-marker-spacer" aria-hidden="true">
                ㄴ
              </span>
            )}
          </span>
          <p className="faq-page__answer-line">{text}</p>
        </Fragment>
      ))}
    </div>
  );
}

function FaqAnswerContent({ lines }) {
  return (
    <>
      {lines.map((line, index) => {
        if (line.type === "hang") {
          return <FaqAnswerHang key={`hang-${index}`} rows={line.rows} />;
        }
        return (
          <p key={`line-${index}`} className="faq-page__answer-line">
            {line.text}
          </p>
        );
      })}
    </>
  );
}

function FaqToggleIcon({ className }) {
  return <span className={className} aria-hidden="true" />;
}

function FaqItem({ item, isOpen, onToggle }) {
  const panelId = useId();
  const questionId = useId();

  return (
    <li className="faq-page__item">
      <div
        className={`faq-page__question${isOpen ? " faq-page__question--open" : ""}`}
        data-node-id={item.number === "01" ? "245:250" : undefined}
      >
        <span className="faq-page__number">{item.number}</span>
        <p className="faq-page__question-text" id={questionId}>
          {item.question}
        </p>
        {!isOpen ? (
          <button
            type="button"
            className="faq-page__toggle faq-page__toggle--expand"
            aria-expanded={false}
            aria-controls={panelId}
            aria-labelledby={questionId}
            onClick={onToggle}
          >
            <FaqToggleIcon className="faq-page__toggle-icon" />
            <span className="visually-hidden">답변 보기</span>
          </button>
        ) : null}
      </div>

      {isOpen ? (
        <div
          id={panelId}
          className="faq-page__answer"
          role="region"
          aria-labelledby={questionId}
          data-node-id="245:328"
        >
          <div
            className={`faq-page__answer-body${
              item.lines.length === 1 && item.lines[0].type === "line"
                ? " faq-page__answer-body--single"
                : ""
            }`}
          >
            <FaqAnswerContent lines={item.lines} />
          </div>
          <button
            type="button"
            className="faq-page__toggle faq-page__toggle--collapse"
            aria-expanded
            aria-controls={panelId}
            onClick={onToggle}
          >
            <FaqToggleIcon className="faq-page__toggle-icon faq-page__toggle-icon--close" />
            <span className="visually-hidden">답변 닫기</span>
          </button>
        </div>
      ) : null}
    </li>
  );
}

export default function FaqPage() {
  const [openId, setOpenId] = useState(null);

  const handleToggle = useCallback((id) => {
    setOpenId((current) => (current === id ? null : id));
  }, []);

  return (
    <div className="faq-page" data-node-id="241:199" data-name="001_1_FAQ">
      <SiteHeader />
      <main className="faq-page__main">
        <h1 className="faq-page__title" data-node-id="244:636">
          FAQ
        </h1>

        <ul className="faq-page__list">
          {FAQ_ITEMS.map((item) => (
            <FaqItem
              key={item.id}
              item={item}
              isOpen={openId === item.id}
              onToggle={() => handleToggle(item.id)}
            />
          ))}
        </ul>
      </main>
    </div>
  );
}
