import { chromium } from "playwright";

const BASE = process.argv[2] || "http://127.0.0.1:4173";
const WIDTHS = [];
for (let w = 1400; w >= 360; w -= 20) WIDTHS.push(w);

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(`${BASE}/`, { waitUntil: "networkidle" });

  let prev = null;
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 900 });
    await page.waitForTimeout(100);
    const cur = await page.evaluate(() => {
      const copy = document.querySelector(".home-hero__copy");
      const cta = document.querySelector(".home-hero__cta");
      const logo = document.querySelector(".site-header__logo");
      const nav = document.querySelector(".site-header__nav");
      const cr = copy?.getBoundingClientRect();
      const ar = cta?.getBoundingClientRect();
      const lr = logo?.getBoundingClientRect();
      const nr = nav?.getBoundingClientRect();
      return {
        copyPos: copy ? getComputedStyle(copy).position : null,
        heroH: document.querySelector(".home-hero")?.getBoundingClientRect().height,
        ctaAboveCopy: cr && ar ? ar.top < cr.top : null,
        header2row: lr && nr ? nr.top > lr.top + 8 : null,
        logoW: lr ? Math.round(lr.width) : null,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    if (prev) {
      const ch = [];
      if (prev.copyPos !== cur.copyPos) ch.push(`copy ${prev.copyPos}→${cur.copyPos}`);
      if (prev.header2row !== cur.header2row) ch.push(`header2row ${prev.header2row}→${cur.header2row}`);
      if (prev.ctaAboveCopy !== cur.ctaAboveCopy) ch.push(`ctaAboveCopy ${prev.ctaAboveCopy}→${cur.ctaAboveCopy}`);
      if (prev.logoW && cur.logoW && Math.abs(prev.logoW - cur.logoW) > 30) ch.push(`logo ${prev.logoW}→${cur.logoW}`);
      if (prev.overflow <= 2 && cur.overflow > 2) ch.push(`overflow +${cur.overflow}`);
      if (ch.length) console.log(`${w}px: ${ch.join(", ")}`);
    }
    prev = cur;
  }
  await browser.close();
}

main();
