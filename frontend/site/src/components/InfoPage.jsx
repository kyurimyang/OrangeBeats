import { Link } from "react-router-dom";
import SiteHeader from "../components/SiteHeader.jsx";

export default function InfoPage({ title, description, children }) {
  return (
    <div className="site-page">
      <SiteHeader />
      <main className="site-info">
        <p className="site-info__eyebrow">Orange Beats</p>
        <h1 className="site-info__title">{title}</h1>
        <p className="site-info__description">{description}</p>
        <div className="site-info__content">{children}</div>
        <Link className="site-info__back" to="/">
          홈으로 돌아가기
        </Link>
      </main>
    </div>
  );
}
