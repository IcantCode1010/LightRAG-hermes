from pathlib import Path


SCRIPT = Path("scripts/verify-hermes-chat-scroll.mjs")


def test_chat_scroll_browser_regression_script_exercises_real_viewport() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "chromium.launch" in text
    assert "PLAYWRIGHT_NODE_MODULES" in text
    assert "PLAYWRIGHT_CHROMIUM_EXECUTABLE" in text
    assert 'playwrightRequire("playwright")' in text
    assert 'import { chromium } from "playwright"' not in text
    assert "npm install --no-save playwright" in text
    assert "HERMES_UI_URL" in text
    assert "page.setViewportSize" in text
    assert "synthetic message" in text
    assert "internalMessagesAtBottom" in text
    assert "activityVisible" in text
    assert "composerVisible" in text
    assert "Hermes chat scroll regression passed" in text
