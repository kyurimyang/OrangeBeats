/**
 * 페이지별 뷰포트 레이아웃 감사 (Playwright)
 * 사용: node scripts/viewport-audit.mjs [baseUrl]
 */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://127.0.0.1:8000";
const WIDTHS = [1440, 1280, 1100, 960, 900, 840, 768, 720, 641, 640, 480, 390];

const PAGES = [
  { path: "/", name: "home" },
  { path: "/create", name: "create" },
  { path: "/help", name: "help" },
  { path: "/faq", name: "faq" },
  { path: "/contact", name: "contact" },
  { path: "/result/analysis", name: "result-analysis" },
  { path: "/result", name: "result-list" },
  { path: "/result/created", name: "result-created" },
  { path: "/result/rating", name: "rating" },
];

async function auditPage(page, width) {
  await page.setViewportSize({ width, height: 900 });
  await page.waitForTimeout(150);

  return page.evaluate((w) => {
    const issues = [];
    const doc = document.documentElement;
    const overflowX = doc.scrollWidth - doc.clientWidth;

    if (overflowX > 2) {
      issues.push({ type: "horizontal-overflow", detail: `+${overflowX}px` });
    }

    const header = document.querySelector(".site-header__inner");
    const logo = document.querySelector(".site-header__logo");
    const nav = document.querySelector(".site-header__nav");
    const start = document.querySelector(".site-header__start");

    if (header && logo && nav) {
      const lr = logo.getBoundingClientRect();
      const nr = nav.getBoundingClientRect();
      const sr = start?.getBoundingClientRect();

      if (nr.top > lr.top + 8) {
        issues.push({
          type: "header-2row",
          detail: `nav Y=${Math.round(nr.top)} logo Y=${Math.round(lr.top)}`,
        });
      }

      if (lr.width < 180 && w >= 641) {
        issues.push({
          type: "logo-small",
          detail: `logo width=${Math.round(lr.width)}px`,
        });
      }

      if (sr && nr.left < sr.right - 4 && nr.top <= lr.top + 8 && w >= 641) {
        issues.push({
          type: "header-overlap",
          detail: `nav overlaps start (nav.left=${Math.round(nr.left)} start.right=${Math.round(sr.right)})`,
        });
      }
    }

    const urlField = document.querySelector(".figma-url-input__field");
    const urlBtn = document.querySelector(".figma-url-input__action");
    if (urlField && urlBtn) {
      const btnStyle = getComputedStyle(urlBtn);
      if (btnStyle.position === "static" && w > 768) {
        issues.push({ type: "url-btn-static", detail: "button not absolute (>768 expected)" });
      }
      if (btnStyle.position === "absolute" && w <= 768) {
        issues.push({ type: "url-btn-absolute", detail: "button still absolute (<=768 mobile layout)" });
      }

      const br = urlBtn.getBoundingClientRect();
      const fr = urlField.getBoundingClientRect();
      if (br.right > fr.right + 2 || br.left < fr.left - 2) {
        issues.push({
          type: "url-btn-outside-field",
          detail: `btn [${Math.round(br.left)},${Math.round(br.right)}] field [${Math.round(fr.left)},${Math.round(fr.right)}]`,
        });
      }

      const glow = urlBtn;
      const before = getComputedStyle(glow, "::before");
      if (before.content && before.content !== "none" && before.display !== "none") {
        /* pseudo — approximate: button should contain glow */
      }
    }

    const hero = document.querySelector(".home-hero");
    const heroCopy = document.querySelector(".home-hero__copy");
    const heroCta = document.querySelector(".home-hero__cta");
    if (hero && heroCopy && heroCta) {
      const cr = heroCopy.getBoundingClientRect();
      const ar = heroCta.getBoundingClientRect();
      if (ar.top < cr.bottom - 20 && getComputedStyle(heroCopy).position === "relative") {
        /* CTA above copy when flex — check order */
        if (ar.top < cr.top) {
          issues.push({ type: "hero-cta-above-copy", detail: "CTA visually above title block" });
        }
      }
      const copyPos = getComputedStyle(heroCopy).position;
      if (copyPos === "absolute" && w <= 1280) {
        issues.push({ type: "hero-copy-absolute", detail: "copy still absolute at <=1280" });
      }
    }

    const scaleWrap = document.querySelector(".result-analysis-page__scale-wrap");
    if (scaleWrap) {
      const zoom = getComputedStyle(scaleWrap).zoom;
      if (zoom && parseFloat(zoom) < 1 && w <= 1280 && w > 840) {
        issues.push({ type: "analysis-zoom", detail: `zoom=${zoom}` });
      }
    }

    return issues;
  }, width);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  /** @type {Record<string, Record<number, object[]>>} */
  const report = {};

  for (const { path, name } of PAGES) {
    const url = `${BASE}${path}`;
    try {
      const res = await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
      if (!res || res.status() >= 400) {
        report[name] = { error: `HTTP ${res?.status() ?? "fail"}` };
        continue;
      }
    } catch (e) {
      report[name] = { error: String(e.message || e) };
      continue;
    }

    report[name] = {};
    let prevCount = 0;

    for (const w of WIDTHS) {
      const issues = await auditPage(page, w);
      report[name][w] = issues;
      const count = issues.length;
      if (count > 0 && prevCount === 0) {
        report[name]._firstBreak = report[name]._firstBreak || {};
        for (const iss of issues) {
          report[name]._firstBreak[iss.type] = report[name]._firstBreak[iss.type] ?? w;
        }
      }
      prevCount = count;
    }
  }

  await browser.close();

  console.log(JSON.stringify(report, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
