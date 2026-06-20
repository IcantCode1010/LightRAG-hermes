from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[2] / "hermes_ui" / "static"
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "hermes_ui" / "frontend"
FRONTEND_SRC = FRONTEND_DIR / "src"
DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile.hermes-ui"


def test_documents_panel_exposes_file_loader_for_ingest_form() -> None:
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    documents_panel = (FRONTEND_SRC / "components" / "DocumentsPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "/api/documents/status" in app
    assert "processingStatus" in app
    assert ".pdf" in documents_panel
    assert ".docx" in documents_panel
    assert "Choose file" in documents_panel
    assert "loadFile" in documents_panel
    assert "/api/ingest-file" in documents_panel
    assert "FormData" in documents_panel
    assert "file.text()" in documents_panel
    assert "build_snapshot" in documents_panel
    assert "Build searchable snapshot after upload" in documents_panel
    assert "Processing status" in documents_panel
    assert "Latest versions only" in documents_panel
    assert "Registered" in documents_panel
    assert "Searchable" in documents_panel
    assert "Failed" in documents_panel
    assert "Needs snapshot" in documents_panel
    assert "Upload replacement version" in documents_panel
    assert "chunks" in documents_panel


def test_snapshot_panel_exposes_readiness_status() -> None:
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    snapshot_panel = (FRONTEND_SRC / "components" / "SnapshotPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "/api/snapshots/status" in app
    assert "Snapshot target" in snapshot_panel
    assert "Target indexed docs" in snapshot_panel
    assert "Active snapshot" in snapshot_panel


def test_maintenance_panel_exposes_snapshot_archive_cleanup() -> None:
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    maintenance_panel = (FRONTEND_SRC / "components" / "MaintenancePanel.tsx").read_text(
        encoding="utf-8"
    )

    assert "maintenance" in app
    assert 'id="maintenance-tab"' in maintenance_panel
    assert "/api/maintenance/snapshot-archives" in app
    assert "/api/maintenance/snapshot-archives" in maintenance_panel
    assert "deleteArchive" in maintenance_panel
    assert "confirmation" in maintenance_panel


def test_chat_flow_exposes_activity_indicator_and_scheduled_scroll() -> None:
    chat_surface = (FRONTEND_SRC / "components" / "HermesChat.tsx").read_text(
        encoding="utf-8"
    )
    css = (FRONTEND_SRC / "index.css").read_text(encoding="utf-8")

    assert 'className="chat-activity"' in chat_surface
    assert 'aria-live="polite"' in chat_surface
    assert "setIsThinking" in chat_surface
    assert "scrollHeight" in chat_surface
    assert "scrollTo" in chat_surface
    assert ".chat-activity" in css
    assert "typing-dots" in chat_surface
    assert "typing-dot" in chat_surface
    assert "@keyframes typingPulse" in css
    assert "Hermes is still working" in chat_surface
    assert "ConversationScrollButton" in chat_surface


def test_chat_layout_constrains_outer_scroll_to_conversation() -> None:
    css = (FRONTEND_SRC / "index.css").read_text(encoding="utf-8")

    assert "height: 100%;" in css
    assert "height: 100dvh;" in css
    assert "overflow: hidden;" in css
    assert "overscroll-behavior: contain;" in css
    assert ".conversation-content" in css
    assert "overflow-y: auto;" in css


def test_hermes_frontend_declares_shadcn_chat_components() -> None:
    package_json = (FRONTEND_DIR / "package.json").read_text(encoding="utf-8")
    components_json = (FRONTEND_DIR / "components.json").read_text(encoding="utf-8")
    chat_surface = (FRONTEND_DIR / "src" / "components" / "HermesChat.tsx").read_text(
        encoding="utf-8"
    )
    conversation = (
        FRONTEND_DIR / "src" / "components" / "ai-elements" / "conversation.tsx"
    ).read_text(encoding="utf-8")
    message = (
        FRONTEND_DIR / "src" / "components" / "ai-elements" / "message.tsx"
    ).read_text(encoding="utf-8")
    prompt_input = (
        FRONTEND_DIR / "src" / "components" / "ai-elements" / "prompt-input.tsx"
    ).read_text(encoding="utf-8")

    assert '"build": "vite build --outDir ../static --emptyOutDir"' in package_json
    assert '"@vitejs/plugin-react"' in package_json
    assert '"lucide-react"' in package_json
    assert '"react-markdown"' in package_json
    assert '"style": "new-york"' in components_json
    assert "ConversationScrollButton" in conversation
    assert "MessageAvatar" in message
    assert "PromptInputTextarea" in prompt_input
    assert "Hermes is thinking" in chat_surface
    assert "SendHorizonal" in chat_surface


def test_hermes_ui_dockerfile_builds_react_frontend_assets() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS frontend-builder" in dockerfile
    assert "COPY hermes_ui/frontend/package*.json ./hermes_ui/frontend/" in dockerfile
    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "COPY --from=frontend-builder /app/hermes_ui/static ./hermes_ui/static" in dockerfile
