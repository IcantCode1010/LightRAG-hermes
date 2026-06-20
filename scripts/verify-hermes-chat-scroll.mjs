#!/usr/bin/env node

import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const playwrightRequire = process.env.PLAYWRIGHT_NODE_MODULES
  ? createRequire(pathToFileURL(path.join(process.env.PLAYWRIGHT_NODE_MODULES, "package.json")))
  : createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = playwrightRequire("playwright"));
} catch (error) {
  console.error("Playwright is required to run this optional browser regression.");
  console.error("Install it temporarily with: npm install --no-save playwright");
  console.error(`Original error: ${error.message}`);
  process.exit(1);
}

const baseUrl = process.env.HERMES_UI_URL || "http://127.0.0.1:8787";

function assert(condition, message, details = {}) {
  if (condition) {
    return;
  }

  console.error(`Hermes chat scroll regression failed: ${message}`);
  console.error(JSON.stringify(details, null, 2));
  process.exit(1);
}

const launchOptions = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
  ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
  : {};
const browser = await chromium.launch(launchOptions);
const page = await browser.newPage();

try {
  await page.setViewportSize({ width: 390, height: 720 });
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#chat-form");

  const result = await page.evaluate(async () => {
    const messages = document.querySelector("#messages");
    const activity = document.querySelector("#chat-activity");
    const composer = document.querySelector("#chat-form");
    const form = document.querySelector("#chat-form");
    const input = document.querySelector("#chat-message");

    for (let index = 0; index < 36; index += 1) {
      const node = document.createElement("div");
      node.className = index % 2 ? "message user" : "message agent";
      node.textContent = `synthetic message ${index} ${"long line ".repeat(18)}`;
      messages.append(node);
    }

    window.scrollTo(0, 0);
    messages.scrollTop = 0;
    input.value = "What are the primary flight control components?";
    form.dispatchEvent(new SubmitEvent("submit", { bubbles: true, cancelable: true }));

    await new Promise((resolve) => setTimeout(resolve, 350));

    return {
      activityHidden: activity.hidden,
      activityBottom: activity.getBoundingClientRect().bottom,
      composerBottom: composer.getBoundingClientRect().bottom,
      internalMessagesAtBottom:
        messages.scrollTop >= messages.scrollHeight - messages.clientHeight - 2,
      activityVisible:
        !activity.hidden && activity.getBoundingClientRect().bottom <= window.innerHeight + 2,
      composerVisible: composer.getBoundingClientRect().bottom <= window.innerHeight + 2,
      messagesClientHeight: messages.clientHeight,
      messagesScrollHeight: messages.scrollHeight,
      messagesScrollTop: messages.scrollTop,
      viewportHeight: window.innerHeight,
    };
  });

  assert(result.internalMessagesAtBottom, "message list did not scroll to bottom", result);
  assert(result.activityVisible, "typing activity row was not visible", result);
  assert(result.composerVisible, "composer was not visible", result);

  console.log("Hermes chat scroll regression passed");
} finally {
  await browser.close();
}
