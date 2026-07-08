// Capture real UI screenshots for the report using the bundled Puppeteer.
// Runs a real GLM negotiation with the mediator and saves conversation + result.
const puppeteer = require("puppeteer");

const URL = process.env.UI_URL || "http://127.0.0.1:8023";
const MODEL = process.env.UI_MODEL || "z-ai/glm-5.2";

(async () => {
  const browser = await puppeteer.launch({
    args: ["--no-sandbox"],
    defaultViewport: { width: 960, height: 1500, deviceScaleFactor: 2 },
  });
  try {
    const page = await browser.newPage();
    await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForFunction(
      () => {
        const el = document.getElementById("buyer-provider");
        return el && el.options.length > 0;
      },
      { timeout: 60000 }
    );
    await page.select("#buyer-provider", "openrouter");
    await page.select("#seller-provider", "openrouter");
    await page.$eval("#buyer-model", (el, v) => (el.value = v), MODEL);
    await page.$eval("#seller-model", (el, v) => (el.value = v), MODEL);
    await page.$eval("#mediator-enabled", (el) => {
      if (!el.checked) el.click();
    });
    await page.$eval("#mediator-start", (el) => (el.value = "2"));

    // Capture the configuration panel before launching (clean form).
    const config = await page.$(".config");
    await config.screenshot({ path: "docs/diagrams/09_interfaz_config.png" });

    await page.click("#run-btn");
    console.log("negotiating...");
    await page.waitForSelector(".verdict", { timeout: 240000 });
    await page.$eval("#conversation", (el) => (el.style.maxHeight = "none"));
    await new Promise((r) => setTimeout(r, 500));

    const stream = await page.$(".stream");
    await stream.screenshot({ path: "docs/diagrams/06_interfaz_conversacion.png" });
    const results = await page.$(".results");
    await results.screenshot({ path: "docs/diagrams/07_interfaz_resultado.png" });
    console.log("saved screenshots");
  } finally {
    await browser.close();
  }
})();
