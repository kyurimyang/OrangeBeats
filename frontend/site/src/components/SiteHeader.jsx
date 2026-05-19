import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  fetchSpotifyLoginStatus,
  fetchSpotifyLoginUrl,
  startSpotifyConnect,
} from "../utils/spotifyAuth.js";

const navItems = [
  { to: "/help", label: "Help", className: "figma-footer-link--help-default", activeClassName: "figma-footer-link--help-pressed" },
  { to: "/faq", label: "FAQ", className: "figma-footer-link--faq-default", activeClassName: "figma-footer-link--faq-pressed" },
  { to: "/contact", label: "Contact us", className: "figma-footer-link--contact-default", activeClassName: "figma-footer-link--contact-pressed" },
];

function SpotifyMarkIcon({ className = "" }) {
  return (
    <span className={`site-header__spotify-mark ${className}`.trim()} aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm5.52 17.315a.75.75 0 01-1.03.25c-2.822-1.725-6.376-2.115-10.562-1.158a.75.75 0 01-.335-1.462c4.578-1.046 8.503-.595 11.677 1.34a.75.75 0 01.25 1.03zm1.474-3.275a.937.937 0 01-1.288.309c-3.228-1.983-8.15-2.56-11.97-1.4a.937.937 0 01-.544-1.793c4.363-1.323 9.787-.683 13.492 1.596a.937.937 0 01.31 1.288zm.127-3.41c-3.873-2.3-10.26-2.511-13.953-1.39a1.125 1.125 0 01-.652-2.152c4.244-1.287 11.294-1.038 15.748 1.608a1.125 1.125 0 01-1.143 1.934z" />
      </svg>
    </span>
  );
}

export default function SiteHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const [loggedIn, setLoggedIn] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const menuWrapRef = useRef(null);

  const refreshStatus = useCallback(async () => {
    const data = await fetchSpotifyLoginStatus();
    setLoggedIn(Boolean(data?.logged_in));
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (e) => {
      if (menuWrapRef.current && !menuWrapRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  const redirectAfterOAuth = `${location.pathname}${location.search}` || "/";

  const handleConnect = async () => {
    if (busy || loggedIn === null) return;
    setBusy(true);
    try {
      await startSpotifyConnect();
    } catch (err) {
      console.error(err);
      window.alert("Spotify 로그인 연결에 실패했습니다. 잠시 후 다시 시도해주세요.");
      setBusy(false);
    }
  };

  const handleLogout = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch("/spotify/logout", { method: "POST", credentials: "include" });
      if (!res.ok) throw new Error("logout_failed");
      setLoggedIn(false);
      setMenuOpen(false);
      navigate("/", { replace: true });
    } catch (err) {
      console.error(err);
      window.alert("로그아웃에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };

  const handleLoginWithOtherAccount = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await fetch("/spotify/logout", { method: "POST", credentials: "include" });
      setMenuOpen(false);
      const loginUrl = await fetchSpotifyLoginUrl(redirectAfterOAuth);
      window.location.assign(loginUrl);
    } catch (err) {
      console.error(err);
      setBusy(false);
      window.alert("Spotify 로그인 이동에 실패했습니다.");
    }
  };

  return (
    <header className="site-header" data-node-id="483:315">
      <div className="site-header__inner">
        <div className="site-header__start" data-node-id="351:628">
          <NavLink className="site-header__logo" to="/" aria-label="Orange Beats 홈">
            <img src="/assets/home/logo.png" alt="Orange Beats" />
          </NavLink>

          {loggedIn ? (
                <div className="site-header__spotify" ref={menuWrapRef} data-node-id="486:382">
                  <button
                    type="button"
                    className="site-header__spotify-trigger"
                    aria-expanded={menuOpen}
                    aria-haspopup="menu"
                    aria-controls="site-header-spotify-menu"
                    id="site-header-spotify-trigger"
                    onClick={() => setMenuOpen((open) => !open)}
                  >
                    <span className="site-header__spotify-trigger-label">Spotify 연동중</span>
                    <span
                      className={`site-header__spotify-chevron${menuOpen ? " site-header__spotify-chevron--open" : ""}`}
                      aria-hidden
                    />
                  </button>
                  {menuOpen ? (
                    <div
                      className="site-header__spotify-menu"
                      id="site-header-spotify-menu"
                      role="menu"
                      aria-labelledby="site-header-spotify-trigger"
                    >
                      <button type="button" className="site-header__spotify-menu-item" role="menuitem" onClick={handleLogout} disabled={busy}>
                        logout
                      </button>
                      <div className="site-header__spotify-menu-rule" role="separator" />
                      <button
                        type="button"
                        className="site-header__spotify-menu-item"
                        role="menuitem"
                        onClick={handleLoginWithOtherAccount}
                        disabled={busy}
                      >
                        login with other account
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : (
                <button
                  type="button"
                  className="site-header__spotify-connect"
                  onClick={handleConnect}
                  disabled={busy || loggedIn === null}
                >
                  <SpotifyMarkIcon />
                  <span className="site-header__spotify-connect-label">
                    {busy ? "연결 중…" : "Spotify 연동"}
                  </span>
                </button>
              )}
        </div>

        <nav className="site-header__nav" aria-label="주요 메뉴" data-node-id="351:630">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `figma-piece figma-footer-link ${isActive ? item.activeClassName : item.className}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
