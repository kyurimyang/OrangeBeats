import { Link } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";

export default function NotFoundPage() {
  return (
    <div className="not-found-page">
      <SiteHeader />
      <main className="site-info not-found-page__main">
        <h1 className="site-info__title">페이지를 찾을 수 없어요</h1>
        <p className="site-info__description">
          주소가 바뀌었거나 잘못 입력되었을 수 있어요.
        </p>
        <nav className="not-found-page__actions" aria-label="안내 링크">
          <Link className="not-found-page__link" to="/">
            홈으로
          </Link>
          <Link className="not-found-page__link not-found-page__link--primary" to="/create">
            플레이리스트 만들기
          </Link>
        </nav>
      </main>
    </div>
  );
}
