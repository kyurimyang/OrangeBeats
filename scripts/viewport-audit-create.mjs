/**
 * /create 페이지 상세 뷰포트 스캔
 */
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://127.0.0.1:4173";
const WIDTHS = [];
for (let w = 1400; w >= 360; w -= 20) WIDTHS.push(w);

async function snapshot(page, width) {
  await page.setViewportSize({ width, height: 900 });
  await page.waitForTimeout(120);
  return page.evaluate((w) => {
    const logo = document.querySelector(".site-header__logo");
    const nav = document.querySelector(".site-header__nav");
    const field = document.querySelector(".figma-url-input__field");
    const btn = document.querySelector(".figma-url-input__action");
    const doc = document.documentElement;

    const lr = logo?.getBoundingClientRect();
    const nr = nav?.getBoundingClientRect();
    const fr = field?.getBoundingClientRect();
    const br = btn?.getBoundingClientRect();

    return {
      w,
      overflow: doc.scrollWidth - doc.clientWidth,
      header2row: logo && nav ? nr.top > lr.top + 8 : null,
      logoW: lr ? Math.round(lr.width) : null,
      navY: nr ? Math.round(nr.top) : null,
      logoY: lr ? Math.round(lr.top) : null,
      btnPosition: btn ? getComputedStyle(btn).position : null,
      fieldFlexWrap: field ? getComputedStyle(field).flexWrap : null,
      fieldH: fr ? Math.round(fr.height) : null,
      btnInsideField:
        fr && br ? br.left >= fr.left - 2 && br.right <= fr.right + 2 : null,
      btnTop: br ? Math.round(br.top) : null,
      fieldTop: fr ? Math.round(fr.top) : null,
    };
  }, width);
}

function findTransitions(rows) {
  const transitions = [];
  for (let i = 1; i < rows.length; i++) {
    const a = rows[i - 1];
    const b = rows[i];
    const changes = [];
    if (a.header2row !== b.header2row) changes.push(`header2row ${a.header2row}→${b.header2row}`);
    if (a.btnPosition !== b.btnPosition) changes.push(`btn ${a.btnPosition}→${b.btnPosition}`);
    if (a.fieldFlexWrap !== b.fieldFlexWrap) changes.push(`flexWrap ${a.fieldFlexWrap}→${b.fieldFlexWrap}`);
    if (a.logoW && b.logoW && Math.abs(a.logoW - b.logoW) > 30) changes.push(`logoW ${a.logoW}→${b.logoW}`);
    if (a.overflow <= 2 && b.overflow > 2) changes.push(`overflow +${b.overflow}px`);
    if (a.btnInsideField && !b.btnInsideField) changes.push("btn outside field");
    if (Math.abs((a.fieldH || 0) - (b.fieldH || 0)) > 25) changes.push(`fieldH ${a.fieldH}→${b.fieldH}`);
    if (changes.length) transitions.push({ at: b.w, from: a.w, changes });
  }
  return transitions;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(`${BASE}/create`, { waitUntil: "networkidle", timeout: 20000 });

  const rows = [];
  for (const w of WIDTHS) rows.push(await snapshot(page, w));

  await browser.close();

  const transitions = findTransitions(rows);
  console.log("=== /create layout transitions (width decreases) ===");
  for (const t of transitions) {
    console.log(`${t.at}px (from ${t.from}px): ${t.changes.join(", ")}`);
  }
  console.log("\n=== Sample widths ===");
  for (const w of [1440, 1100, 960, 900, 768, 720, 641, 640, 480]) {
    const r = rows.find((x) => x.w === w);
    if (r) console.log(JSON.stringify(r));
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
