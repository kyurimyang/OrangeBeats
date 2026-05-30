import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import HomeHeroSpotify from "../components/HomeHeroSpotify.jsx";
import SiteHeader from "../components/SiteHeader.jsx";

const SESSION_KEY = "ob_admin_key";
/** How to use PNG 캐시 무효화 — 이미지 교체 시 값만 올리면 됨 */
const HOWTO_IMG_V = "20260211figma333244";
const howtoImg = (filename) => `/assets/home/${filename}?v=${HOWTO_IMG_V}`;
const howtoImgSrcSet = (filename, filename2x) =>
  `${howtoImg(filename)} 1x, ${howtoImg(filename2x)} 2x`;

export default function HomePage() {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [adminKey, setAdminKey] = useState("");
  const [keyError, setKeyError] = useState("");
  const [checking, setChecking] = useState(false);
  const inputRef = useRef(null);

  const openModal = () => {
    setAdminKey("");
    setKeyError("");
    setModalOpen(true);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const closeModal = () => {
    setModalOpen(false);
    setAdminKey("");
    setKeyError("");
  };

  const submitKey = async () => {
    if (checking || !adminKey.trim()) return;
    setChecking(true);
    setKeyError("");
    try {
      const res = await fetch(`/feedback/admin`, {
        credentials: "include",
        headers: { "X-Admin-Key": adminKey.trim() },
      });
      if (res.status === 401) {
        setKeyError("잘못된 키입니다.");
        return;
      }
      if (!res.ok) throw new Error();
      sessionStorage.setItem(SESSION_KEY, adminKey.trim());
      navigate("/admin");
    } catch {
      setKeyError("오류가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setChecking(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") submitKey();
    if (e.key === "Escape") closeModal();
  };

  return (
    <div className="home-page" data-node-id="37:222">
      <SiteHeader />

      <main className="home-shell">
        <section className="home-hero" data-node-id="99:284">
          <HomeHeroSpotify />
          <div className="home-hero__copy" data-node-id="37:9544">
            <div className="home-hero__title-wrap" data-node-id="67:2">
              <h1 className="home-hero__title" data-node-id="67:3">
                <span>Youtube Playlist를 ㅡ </span>
                <span>링크 한번에 내 Spotify로.</span>
              </h1>
            </div>
            <div className="home-hero__subtitle-wrap" data-node-id="37:9547">
              <p className="home-hero__subtitle" data-node-id="37:9548">
                <span>Youtube Playlist를 이용하면서 힘들었던적은 없었나요?</span>
                <span>orangebeats로 내가 주로 이용하는 Spotify에 Playlist를 불러와 마음껏 Playlist를 수정하고, 재생하고, 즐기세요.</span>
              </p>
            </div>
            <div className="home-hero__spacer" aria-hidden="true" data-node-id="37:9549" />
          </div>
        </section>

        <div className="home-scroll-indicator" data-node-id="309:257">
          <img src="/assets/home/scroll-indicator.svg" alt="" aria-hidden="true" />
        </div>

        <div className="home-placeholder" aria-hidden="true" data-node-id="311:272" />

        <h2 className="home-section-title" data-node-id="311:270">How to use</h2>

        <figure className="home-howto-shot home-howto-shot--step1" data-node-id="309:259">
          <img src={howtoImg("step-1-bundle.png")} alt="브라우저에서 YouTube URL 복사" />
        </figure>

        <ol className="home-copy home-copy--step-1" start={1} data-node-id="281:196">
          <li>플레이리스트를 생성할 Youtube URL을 복사하고, URL을 붙여넣어주세요.</li>
        </ol>

        <figure className="home-howto-shot home-howto-shot--title" data-node-id="301:369">
          <img src={howtoImg("step-2-title.png")} alt="직접 제목 입력 및 Playlist 제목 입력" />
        </figure>

        <div className="home-copy home-copy--step-2" data-node-id="311:268">
          <ol className="home-copy__list" start={2}>
            <li>기존 유튜브 영상 제목 외에 원하는 제목이 있다면 “직접 제목 입력”을 선택하고, 제목을 입력해주세요.</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>“유튜브 제목 그대로 사용”을 선택한다면, Youtube영상 제목이 Playlist의 제목이 됩니다.</p>
        </div>

        <figure className="home-howto-shot home-howto-shot--tracklist" data-node-id="311:262">
          <img src={howtoImg("step-3-tracklist.png")} alt="추출된 곡 목록" />
        </figure>

        <div className="home-copy home-copy--wide" data-node-id="301:348">
          <ol className="home-copy__list" start={3}>
            <li>text 기반으로 추출된 tracklist가 마음에 든다면 “이대로 Playlist 만들기”를,</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>원하는 노래가 없다면 “원하는 노래가 없어요”를 선택해주세요.</p>
        </div>

        <figure className="home-howto-shot home-howto-shot--ocr-acr" data-node-id="331:240">
          <img src={howtoImg("step-4-ocr-acr.png")} alt="OCR/ACR 분석 화면" />
        </figure>

        <div className="home-copy home-copy--wide home-copy--tall" data-node-id="328:247">
          <ol className="home-copy__list" start={4}>
            <li>OCR, ACR 두가지 방법이 있어요.</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>설명을 읽고 둘 중 영상에 더 잘 맞는 분석 방법을 골라 “실행하기”를 눌러주세요.</p>
        </div>

        <figure className="home-howto-shot home-howto-shot--candidates" data-node-id="341:243">
          <img src={howtoImg("step-5-candidates.png")} alt="생성된 플레이리스트 후보" />
        </figure>

        <div className="home-copy home-copy--wide" data-node-id="336:240">
          <ol className="home-copy__list" start={5}>
            <li>생성된 플레이리스트 후보를 볼 수 있어요.</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>“Spotify 바로가기”를 통해서  Spotify로 바로 연동 가능해요.</p>
        </div>

        <figure className="home-howto-shot home-howto-shot--ratings" data-node-id="333:244">
          <img
            src={howtoImg("step-6-ratings.png")}
            srcSet={howtoImgSrcSet("step-6-ratings.png", "step-6-ratings@2x.png")}
            sizes="(max-width: 480px) 100vw, 324px"
            alt="서비스 평점 남기기"
          />
        </figure>

        <div className="home-copy home-copy--wide" data-node-id="341:240">
          <ol className="home-copy__list" start={6}>
            <li>마지막으로, oragebeats의 서비스 평점을 매겨주세요!</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>서비스 개선과 품질 향상에 큰 도움이 되어요.</p>
        </div>

        <div className="home-placeholder home-placeholder--bottom" aria-hidden="true" data-node-id="357:284" />

        <button
          className="admin-hidden-tab"
          type="button"
          onClick={openModal}
          aria-label="관리자"
          tabIndex={-1}
        >
          ···
        </button>
      </main>

      {modalOpen && (
        <div className="admin-key-overlay" onClick={(e) => e.target === e.currentTarget && closeModal()}>
          <div className="admin-key-modal" role="dialog" aria-modal="true" aria-label="관리자 인증">
            <p className="admin-key-modal__title">관리자 키를 입력하세요</p>
            <input
              ref={inputRef}
              className="admin-key-modal__input"
              type="password"
              placeholder="admin key"
              value={adminKey}
              onChange={(e) => setAdminKey(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={checking}
              autoComplete="off"
            />
            {keyError && <p className="admin-key-modal__error">{keyError}</p>}
            <div className="admin-key-modal__actions">
              <button className="admin-key-modal__cancel" type="button" onClick={closeModal}>취소</button>
              <button className="admin-key-modal__submit" type="button" onClick={submitKey} disabled={checking || !adminKey.trim()}>
                {checking ? "확인 중…" : "확인"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
