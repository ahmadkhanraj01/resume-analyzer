#!/usr/bin/env node
/**
 * Exports every page of docs/architecture.drawio to a PNG in docs/.
 *
 * Usage (needs Node 20+, a Chrome or Chromium, and network access to
 * embed.diagrams.net):
 *
 *   cd docs
 *   npm install          # once; installs Playwright into docs/node_modules only
 *   npm run export
 *
 * docs/package.json is separate from the app on purpose: Playwright is a
 * documentation tool here, not a project dependency, and nothing under
 * docs/ ships. Browser, in order of preference: the one at DRAWIO_CHROME if
 * set, then Playwright's own Chromium (install once with
 * `npx playwright install chromium`), then the system Chrome. The system
 * Chrome timed out on the embed page's init on one Linux machine, which is
 * why it is the last resort rather than the default.
 *
 * Why this route: draw.io has no headless CLI without the desktop app, its
 * export service refuses anonymous calls, and the viewer does not render in
 * a headless browser. Embed mode does, and it speaks a small postMessage
 * protocol made for exactly this: load XML, ask for PNG, receive a data URL.
 * Two quirks handled below: the export call's page selector is ignored, so
 * each page is loaded on its own; and the background option is ignored, so
 * the PNG is flattened onto white in a canvas before saving.
 */

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const SOURCE = path.join(__dirname, "architecture.drawio");
// Output file per page, in the order the pages appear in the file.
const NAMES = ["architecture", "request-flows"];

const HOST_PAGE = `<!doctype html><html><body style="margin:0">
<iframe id="f" style="width:1400px;height:900px;border:0"
  src="https://embed.diagrams.net/?embed=1&proto=json&spin=1&ui=min"></iframe>
<script>
  window.state = "boot"; window.result = null;
  const f = document.getElementById("f");
  window.addEventListener("message", (e) => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    if (m.event === "init") window.state = "init";
    if (m.event === "load") window.state = "loaded";
    if (m.event === "export") { window.result = m.data; window.state = "exported"; }
  });
  window.send = (o) => f.contentWindow.postMessage(JSON.stringify(o), "*");
  window.flatten = (dataUrl) => new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = img.width; c.height = img.height;
      const ctx = c.getContext("2d");
      ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(img, 0, 0);
      resolve(c.toDataURL("image/png"));
    };
    img.src = dataUrl;
  });
</script></body></html>`;

async function launch() {
  if (process.env.DRAWIO_CHROME) {
    return chromium.launch({ executablePath: process.env.DRAWIO_CHROME, headless: true });
  }
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ channel: "chrome", headless: true });
  }
}

async function exportPage(browser, diagramXml, outFile) {
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  try {
    await page.setContent(HOST_PAGE);
    await page.waitForFunction(() => window.state === "init", null, { timeout: 60_000 });
    await page.evaluate((xml) => window.send({ action: "load", xml, autosave: 0 }), diagramXml);
    await page.waitForFunction(() => window.state === "loaded", null, { timeout: 60_000 });
    await page.evaluate(() => window.send({ action: "export", format: "png", scale: 2, border: 20 }));
    await page.waitForFunction(() => window.state === "exported", null, { timeout: 120_000 });
    const flat = await page.evaluate(() => window.flatten(window.result));
    fs.writeFileSync(outFile, Buffer.from(flat.replace(/^data:image\/png;base64,/, ""), "base64"));
  } finally {
    await page.close();
  }
}

(async () => {
  const xml = fs.readFileSync(SOURCE, "utf8");
  const diagrams = [...xml.matchAll(/<diagram [^>]*>[\s\S]*?<\/diagram>/g)].map((m) => m[0]);
  if (diagrams.length !== NAMES.length) {
    throw new Error(`found ${diagrams.length} pages but NAMES lists ${NAMES.length}; update NAMES`);
  }
  const browser = await launch();
  try {
    for (let i = 0; i < diagrams.length; i++) {
      const out = path.join(__dirname, `${NAMES[i]}.png`);
      await exportPage(browser, `<mxfile>${diagrams[i]}</mxfile>`, out);
      console.log(`wrote ${path.relative(process.cwd(), out)}`);
    }
  } finally {
    await browser.close();
  }
})().catch((err) => {
  console.error("export failed:", err.message);
  process.exit(1);
});
