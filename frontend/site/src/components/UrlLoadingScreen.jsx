import SiteHeader from "./SiteHeader.jsx";

/** 텍스트 폭을 채울 때 막대 두께(4px)는 유지하고 개수·간격으로만 넓힘 */
const SOUNDBAR_BAR_COUNT = 42;

function soundbarAnimationDelays(count) {
  const center = (count - 1) / 2;
  return Array.from({ length: count }, (_, i) => {
    const phase = Math.abs(i - center) / center;
    return Number((phase * 0.36).toFixed(2));
  });
}

const SOUNDBAR_DELAYS = soundbarAnimationDelays(SOUNDBAR_BAR_COUNT);

/** Figma 002_URL_Loading (97:131) */
export default function UrlLoadingScreen({ nodeId = "97:131" }) {
  return (
    <div className="result-list-page result-list-page--loading url-loading-screen" data-node-id={nodeId}>
      <SiteHeader />
      <main className="result-loading-main" role="status" aria-live="polite" aria-busy="true">
        <div className="result-list-loading__stack">
          <div className="url-loading-soundbar" aria-hidden="true">
            {SOUNDBAR_DELAYS.map((delay, i) => (
              <span key={i} className="url-loading-soundbar__bar" style={{ animationDelay: `${delay}s` }} />
            ))}
          </div>
          <p className="result-list-loading__title">
            <span>Youtube에서 음원 가져오는 중</span>
            <span className="result-list-loading__dots" aria-hidden="true" />
          </p>
        </div>
      </main>
    </div>
  );
}
