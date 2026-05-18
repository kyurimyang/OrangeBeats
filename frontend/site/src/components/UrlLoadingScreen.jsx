import SiteHeader from "./SiteHeader.jsx";

/** Figma 002_URL_Loading (97:131) */
export default function UrlLoadingScreen({ nodeId = "97:131" }) {
  return (
    <div className="result-list-page result-list-page--loading url-loading-screen" data-node-id={nodeId}>
      <SiteHeader />
      <main className="result-loading-main" role="status" aria-live="polite" aria-busy="true">
        <div className="result-list-loading__stack">
          <div className="url-loading-soundbar" aria-hidden="true">
            {[0, 0.12, 0.24, 0.36, 0.24, 0.12, 0].map((delay, i) => (
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
