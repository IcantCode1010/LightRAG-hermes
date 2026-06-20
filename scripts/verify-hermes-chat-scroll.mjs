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
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".conversation-content");

  const result = await page.evaluate(async () => {
    const messages = document.querySelector(".conversation-content");
    const composer = document.querySelector(".prompt-input");
    const form = document.querySelector(".prompt-input");
    const input = document.querySelector("#chat-message");

    for (let index = 0; index < 36; index += 1) {
      const node = document.createElement("article");
      node.className = index % 2 ? "message message-user" : "message message-agent";
      node.textContent = `synthetic message ${index} ${"long line ".repeat(18)}`;
      messages.append(node);
    }

    window.scrollTo(0, 0);
    messages.scrollTop = 0;
    input.value = "What are the primary flight control components?";
    form.dispatchEvent(new SubmitEvent("submit", { bubbles: true, cancelable: true }));

    await new Promise((resolve) => setTimeout(resolve, 350));

    const activity = document.querySelector(".chat-activity");
    const bodyScrolled = window.scrollY > 2;
    const bodyOverflowed = document.documentElement.scrollHeight > window.innerHeight + 2;

    return {
      bodyOverflowed,
      bodyScrolled,
      activityBottom: activity?.getBoundingClientRect().bottom ?? null,
      composerBottom: composer.getBoundingClientRect().bottom,
      internalMessagesAtBottom:
        messages.scrollTop >= messages.scrollHeight - messages.clientHeight - 2,
      activityVisible:
        !!activity && activity.getBoundingClientRect().bottom <= window.innerHeight + 2,
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
  assert(!result.bodyScrolled, "window scrolled instead of conversation list", result);
  assert(!result.bodyOverflowed, "page body overflowed instead of conversation list", result);

  console.log("Hermes chat scroll regression passed");
} finally {
  await browser.close();
}
