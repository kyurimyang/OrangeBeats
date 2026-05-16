import SiteHeader from "./SiteHeader.jsx";

/** Figma 002_URL_Loading (97:131) */
export default function UrlLoadingScreen({ nodeId = "97:131" }) {
  return (
    <div className="result-list-page result-list-page--loading url-loading-screen" data-node-id={nodeId}>
      <SiteHeader />
      <main className="result-loading-main" role="status" aria-live="polite" aria-busy="true">
        <div className="result-list-loading__stack">
          <p className="result-list-loading__title">
            <span>Youtube에서 음원 가져오는 중</span>
            <span className="result-list-loading__dots" aria-hidden="true" />
          </p>
          <p className="result-list-loading__hint">( 페이지 이탈 시 분석이 중단됩니다..)</p>
        </div>
      </main>
    </div>
  );
}
