import { Link } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";

export default function HomePage() {
  return (
    <div className="home-page" data-node-id="37:222">
      <SiteHeader />

      <main className="home-shell">
        <section className="home-hero" data-node-id="99:284">
          <Link className="figma-piece figma-spotify-connect figma-spotify-connect--default home-hero__cta" to="/lab" data-node-id="99:281">
            <span className="figma-piece__label figma-spotify-connect__label">Spotify 연동하기</span>
          </Link>
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

        <figure className="home-step-1-bundle" data-node-id="309:259">
          <div className="home-step-1-bundle__layer" data-node-id="309:258">
            <div className="home-crop home-crop--step1-browser" data-node-id="278:184">
              <img src="/assets/home/step-1-browser.png" alt="브라우저에서 YouTube URL 복사" />
            </div>
            <img className="home-step-1-bundle__arrow-border" src="/assets/home/arrow-border.svg" alt="" aria-hidden="true" data-node-id="301:372" />
            <img className="home-step-1-bundle__arrow" src="/assets/home/arrow.svg" alt="" aria-hidden="true" data-node-id="301:373" />
          </div>
          <div className="home-crop home-crop--step1-url-bar" data-node-id="281:194">
            <img src="/assets/home/step-1-url-bar.png" alt="URL 입력 바" />
          </div>
        </figure>

        <ol className="home-copy home-copy--step-1" start={1} data-node-id="281:196">
          <li>플레이리스트를 생성할 Youtube URL을 복사하고, URL을 붙여넣어주세요.</li>
        </ol>

        <figure className="home-shot home-shot--url-input" data-node-id="301:369">
          <img src="/assets/home/step-1-url-input.png" alt="제목 입력 옵션" />
        </figure>

        <div className="home-copy home-copy--step-2" data-node-id="311:268">
          <ol className="home-copy__list" start={2}>
            <li>기존 유튜브 영상 제목 외에 원하는 제목이 있다면 “직접 제목 입력”을 선택하고, 제목을 입력해주세요.</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>“유튜브 제목 그대로 사용”을 선택한다면, Youtube영상 제목이 Playlist의 제목이 됩니다.</p>
        </div>

        <figure className="home-crop home-crop--title" data-node-id="311:262">
          <img src="/assets/home/step-2-title.png" alt="제목 입력 옵션" />
        </figure>

        <div className="home-copy home-copy--wide" data-node-id="301:348">
          <ol className="home-copy__list" start={3}>
            <li>text 기반으로 추출된 tracklist가 마음에 든다면 “이대로 Playlist 만들기”를,</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>원하는 노래가 없다면 “원하는 노래가 없어요”를 선택해주세요.</p>
        </div>

        <figure className="home-crop home-crop--tracklist" data-node-id="331:240">
          <img src="/assets/home/step-3-tracklist.png" alt="OCR/ACR 선택" />
        </figure>

        <div className="home-copy home-copy--wide home-copy--tall" data-node-id="328:247">
          <ol className="home-copy__list" start={4}>
            <li>OCR, ACR 두가지 방법이 있어요.</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>설명을 읽고 둘 중 영상에 더 잘 맞는 분석 방법을 골라 “실행하기”를 눌러주세요.</p>
        </div>

        <figure className="home-step-4-bundle" data-node-id="341:246">
          <figure className="home-shot home-shot--ocr-acr" data-node-id="341:243">
            <img src="/assets/home/step-4-ocr-acr.png" alt="OCR/ACR 분석 화면" />
          </figure>
          <div className="home-step-4-bundle__arrow" data-node-id="281:183">
            <img src="/assets/home/step-4-arrow.svg" alt="" aria-hidden="true" />
          </div>
        </figure>

        <div className="home-copy home-copy--wide" data-node-id="336:240">
          <ol className="home-copy__list" start={5}>
            <li>생성된 플레이리스트 후보를 볼 수 있어요.</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>“Spotify 바로가기”를 통해서  Spotify로 바로 연동 가능해요.</p>
        </div>

        <figure className="home-shot home-shot--candidates" data-node-id="333:244">
          <img src="/assets/home/step-5-candidates.png" alt="플레이리스트 후보" />
        </figure>

        <div className="home-copy home-copy--wide" data-node-id="341:240">
          <ol className="home-copy__list" start={6}>
            <li>마지막으로, oragebeats의 서비스 평점을 매겨주세요!</li>
          </ol>
          <p className="home-copy__gap" aria-hidden="true">{"\u200b"}</p>
          <p>서비스 개선과 품질 향상에 큰 도움이 되어요.</p>
        </div>

        <div className="home-placeholder home-placeholder--bottom" aria-hidden="true" data-node-id="357:284" />
      </main>
    </div>
  );
}
