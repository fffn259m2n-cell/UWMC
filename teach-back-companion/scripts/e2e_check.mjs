// End-to-end check: drives every screen in a real browser, fails on console/CSP errors,
// and runs axe-core accessibility checks (WCAG 2.x A/AA rules) on each view.
//
//   npm install playwright axe-core      (or use preinstalled copies)
//   teachback serve --port 8765 &
//   node scripts/e2e_check.mjs http://127.0.0.1:8765 [screenshot-dir] [path/to/axe.min.js]
import { createRequire } from "module";
import fs from "fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const base = process.argv[2] || "http://127.0.0.1:8765";
const shots = process.argv[3] || "";
const axePath = process.argv[4] || require.resolve("axe-core/axe.min.js");
const axeSource = fs.readFileSync(axePath, "utf8");
const problems = [];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
// 4xx responses are expected where the test checks that the server rejects bad input.
page.on("console", m => { if (m.type() === "error" && !/status of 4\d\d/.test(m.text())) problems.push(`console: ${m.text()}`); });
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));

async function audit(name) {
  // Runtime evaluation is not subject to the page CSP, so the app keeps its strict policy.
  await page.evaluate(axeSource);
  const r = await page.evaluate(async () => await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa", "best-practice"] }));
  for (const v of r.violations) problems.push(`axe[${name}] ${v.id} (${v.impact}): ${v.help} x${v.nodes.length}`);
  if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
async function shot(name) { if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true }); }
// Waits up to 8 s for the text (case-insensitive; CSS may upper-case labels).
const expectText = async (sel, text, label) => {
  try {
    await page.waitForFunction(([s, t]) => {
      const n = document.querySelector(s);
      return n && n.innerText.toLowerCase().includes(t.toLowerCase());
    }, [sel, text], { timeout: 8000 });
  } catch (_) { problems.push(`${label}: expected "${text}"`); }
};

await page.goto(base);
await page.waitForSelector(".patient-card");
await audit("01-landing");
await page.click("text=Alex Rivera (fictional)");
await page.waitForSelector("text=Atrial fibrillation (AFib)");
await audit("02-health");
await page.click("button[aria-pressed=false]:has-text('Simple')");
await expectText("main", "top parts of your heart", "reading level switch");

await page.click("#tabs button[data-view=medicines]");
await page.waitForSelector("text=Apixaban 5 mg tablet");
await audit("03-medicines");

await page.click("#tabs button[data-view=plan]");
await page.waitForSelector("h2:has-text('Warning signs')");
await page.locator("section:has-text('Bleeding precautions') button:has-text(\"I've read this\")").click();
await page.waitForSelector("section:has-text('Bleeding precautions') .pill.reviewed");
await audit("04-plan");

await page.click("#tabs button[data-view=check]");
await page.selectOption("#tb-item", "med-apixaban");
await page.fill("#tb-text", "I take it twice a day and I can stop when my heart feels normal again.");
await page.click("text=Check my explanation");
await page.waitForSelector("text=Points to check with your care team");
await expectText("main", "even when you feel well", "teach-back misconception");
await audit("05-teachback");

await page.click("#tabs button[data-view=ask]");
await page.fill("#ask-input", "What is apixaban for?");
await page.click("form button[type=submit]");
await page.waitForSelector(".msg.bot");
await expectText(".chat", "From your care plan", "chat grounding label");
await page.click("text=Say it more simply");
await page.waitForFunction(() => document.querySelectorAll(".msg.bot").length >= 2);
await expectText(".chat", "you may bleed or bruise more easily", "chat simpler level");
await page.fill("#ask-input", "I have chest pain right now");
await page.click("form button[type=submit]");
await page.waitForSelector(".msg.bot .emergency-box");
await expectText(".chat", "call 911 now", "chat emergency");
await page.fill("#ask-input", "Can I stop my metoprolol?");
await page.click("form button[type=submit]");
await page.waitForFunction(() => document.querySelectorAll(".msg.bot").length >= 3);
await expectText(".chat", "can't advise on starting, stopping", "chat medication-change refusal");
await audit("06-ask");

await page.click("#tabs button[data-view=reminders]");
await page.selectOption("#rem-item", "appt-cardiology");
const soon = new Date(Date.now() + 60 * 60 * 1000);
const local = new Date(soon.getTime() - soon.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
await page.fill("#rem-when", local);
await page.click("text=Add reminder");
await page.waitForSelector("table >> text=Cardiology follow-up visit");
await page.selectOption("#rem-item", "appt-cardiology");
await page.fill("#rem-when", "2099-01-01T09:00");
await page.click("text=Add reminder");
await page.waitForSelector("text=after the planned date");
await audit("07-reminders");

await page.click("#tabs button[data-view=staff]");
await page.selectOption("#ev-item", "med-apixaban");
await page.fill("#ev-text", "Apixaban is a blood thinner. Take one 5 mg pill once a day. You can stop it when you feel better.");
await page.click("main button.primary:has-text('Check')");
await page.waitForSelector("text=do not use: critical issues found");
await page.click("text=Run benchmark");
await page.waitForSelector("text=seeded errors detected");
await audit("08-staff");

await page.click("#help-open");
await page.waitForSelector("dialog[open]");
await expectText("dialog", "call 911 now", "help dialog");
await audit("09-help");
await page.keyboard.press("Escape");

await page.setViewportSize({ width: 390, height: 844 });
await page.click("#tabs button[data-view=medicines]");
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
if (overflow) problems.push("mobile: horizontal scroll at 390px");
await shot("10-mobile");

await browser.close();
if (problems.length) { console.log("PROBLEMS:\n" + problems.join("\n")); process.exit(1); }
console.log("E2E OK: all screens exercised, no console errors, no axe violations.");
