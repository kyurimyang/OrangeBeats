import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/help", label: "Help", className: "figma-footer-link--help-default", activeClassName: "figma-footer-link--help-pressed" },
  { to: "/faq", label: "FAQ", className: "figma-footer-link--faq-default", activeClassName: "figma-footer-link--faq-pressed" },
  { to: "/contact", label: "Contact us", className: "figma-footer-link--contact-default", activeClassName: "figma-footer-link--contact-pressed" },
];

export default function SiteHeader() {
  return (
    <header className="site-header" data-node-id="351:627">
      <div className="site-header__inner">
        <div className="site-header__cluster" data-node-id="351:628">
          <NavLink className="site-header__logo" to="/" aria-label="Orange Beats 홈">
            <img src="/assets/home/logo.png" alt="Orange Beats" />
          </NavLink>
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
      </div>
    </header>
  );
}
