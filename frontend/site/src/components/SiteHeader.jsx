import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

const navItems = [
  { to: "/help", label: "Help", className: "figma-footer-link--help-default", activeClassName: "figma-footer-link--help-pressed" },
  { to: "/faq", label: "FAQ", className: "figma-footer-link--faq-default", activeClassName: "figma-footer-link--faq-pressed" },
  { to: "/contact", label: "Contact us", className: "figma-footer-link--contact-default", activeClassName: "figma-footer-link--contact-pressed" },
];

async function fetchLoginStatus() {
  try {
    const res = await fetch("/spotify/login-status", { method: "GET", credentials: "include" });
    if (!res.ok) return { logged_in: false };
    return res.json();
  } catch {
    return { logged_in: false };
  }
}

async function fetchLoginUrl(frontendPath) {
  const frontendRedirect = `${window.location.origin}${frontendPath}`;
  const loginEndpoint = `/spotify/login?frontend_origin=${encodeURIComponent(frontendRedirect)}`;
  const res = await fetch(loginEndpoint, { method: "GET", credentials: "include" });
  if (!res.ok) throw new Error("spotify_login_request_failed");
  const data = await res.json();
  if (!data?.login_url) throw new Error("spotify_login_url_missing");
  return data.login_url;
}

export default function SiteHeader() {
  const location = useLocation();
  const navigate = useNavigate();
  const [loggedIn, setLoggedIn] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const menuWrapRef = useRef(null);

  const refreshStatus = useCallback(async () => {
    const data = await fetchLoginStatus();
    setLoggedIn(Boolean(data?.logged_in));
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const hideSpotifyInBanner = location.pathname === "/";

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
      const status = await fetchLoginStatus();
      if (status?.logged_in) {
        window.location.assign(`${window.location.origin}/create`);
        return;
      }
      const loginUrl = await fetchLoginUrl("/create");
      window.location.assign(loginUrl);
    } catch (err) {
      console.error(err);
      window.alert("Spotify 로그인 연결에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
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
      const loginUrl = await fetchLoginUrl(redirectAfterOAuth);
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

          {hideSpotifyInBanner
            ? null
            : loggedIn ? (
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
                  Spotify 연동하기
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
