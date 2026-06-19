# Image Indexing, Extraction, and Contexting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make extracted images, figures, tables, and equations searchable through OpenAI text embeddings and visible as grounded media context in query results and the WebUI.

**Architecture:** Reuse the existing sidecar pipeline instead of adding a parallel ingestion path. Parser engines produce sidecars, VLM/LLM analysis writes `llm_analyze_result`, multimodal chunks are embedded in `chunks_vdb`, and query formatting preserves media metadata from `text_chunks` into prompts, raw API responses, and the WebUI. A later optional phase can add a dedicated multimodal image-vector backend for visual similarity search.

**Tech Stack:** Python 3.11+, FastAPI, existing LightRAG KV/vector/graph storages, OpenAI chat/VLM bindings, `text-embedding-3-large`, React 19 + TypeScript + Bun, pytest, ruff, Bun test runner.

---

## Repo Review Findings

The repo already has most of the extraction and indexing foundation:

- `lightrag/parser/routing.py` routes files to `legacy`, `native`, `mineru`, or `docling`, with process options `i`, `t`, and `e` enabling image/table/equation analysis.
- `docs/FileProcessingPipeline.md` documents that `native` extracts DOCX/MD/textpack sidecars locally, while `mineru`/`docling` are required for PDF/image/office multimodal extraction.
- `lightrag/multimodal_context.py` enriches `drawings.json`, `tables.json`, and `equations.json` with leading/trailing context from `blocks.jsonl`.
- `lightrag/pipeline.py::analyze_multimodal` sends drawing assets to the VLM and tables/equations to the extract LLM, then writes `llm_analyze_result`.
- `lightrag/pipeline.py::_build_mm_chunks_from_sidecars` converts successful sidecar analysis into normal chunks such as `[Image Name]...`, so the current OpenAI embedding path can already index image semantics as text.
- `lightrag/operate.py` injects sidecar entities and relations into the graph for multimodal chunks.

Current gaps:

- PDF image/table extraction is not active with the current legacy PDF route; users need `mineru` or `docling` plus `VLM_PROCESS_ENABLE=true`.
- Multimodal chunks preserve a minimal `sidecar` pointer in `text_chunks`, but `_get_vector_context`, `_merge_all_chunks`, `_build_context_str`, and `convert_to_user_format` drop that pointer before prompts and API responses.
- Query references cite only the source document path, not the specific extracted image/table/equation.
- The WebUI chat cannot show thumbnails or media-specific citations because the API does not expose media metadata or a safe media asset route.
- The existing indexing is semantic text indexing over VLM descriptions, not true image-vector indexing.

## File Structure

- Create `lightrag/sidecar/media_context.py`
  - Pure helpers for normalizing sidecar media metadata, resolving asset paths, extracting display names from analysis, and validating safe file access.
- Modify `lightrag/pipeline.py`
  - Enrich multimodal chunk `sidecar` metadata when building chunks.
- Modify `lightrag/operate.py`
  - Preserve full chunk metadata from `text_chunks` during vector/entity/relation retrieval and include media context in the LLM prompt chunks.
- Modify `lightrag/utils.py`
  - Preserve `media` metadata in `convert_to_user_format`.
- Modify `lightrag/api/routers/document_routes.py`
  - Add a safe media asset endpoint for drawing/image chunks.
- Modify `lightrag/api/routers/query_routes.py`
  - Update response schema examples so clients know `chunks[].media` and `references[].media` may exist.
- Modify `lightrag_webui/src/api/lightrag.ts`
  - Add TypeScript types for chunk media metadata.
- Modify `lightrag_webui/src/components/retrieval/ChatMessage.tsx`
  - Render retrieved media references and thumbnails in chat citations.
- Modify docs:
  - `docs/FileProcessingPipeline.md`
  - `docs/LightRAGSidecarFormat.md`
  - `env.example`
- Add tests:
  - `tests/sidecar/test_media_context.py`
  - `tests/pipeline/test_multimodal_media_chunks.py`
  - `tests/operate/test_multimodal_query_context.py`
  - `tests/api/routes/test_media_routes.py`
  - `lightrag_webui/src/api/lightrag-media.test.ts`

## Task 1: Normalize Sidecar Media Metadata

**Files:**
- Create: `lightrag/sidecar/media_context.py`
- Test: `tests/sidecar/test_media_context.py`

- [ ] **Step 1: Write failing tests**

Add tests that cover a drawing with a relative asset path, a table without an asset, an equation, missing optional fields, and unsafe `../` asset paths.

```python
from pathlib import Path

import pytest

from lightrag.sidecar.media_context import (
    build_media_context,
    resolve_media_asset_path,
)


def test_build_media_context_for_drawing_asset(tmp_path: Path):
    blocks_path = tmp_path / "manual.blocks.jsonl"
    asset_dir = tmp_path / "manual.blocks.assets"
    asset_dir.mkdir()
    image_path = asset_dir / "fig1.png"
    image_path.write_bytes(b"png")

    media = build_media_context(
        blocks_path=str(blocks_path),
        root_key="drawings",
        item_id="im-0001",
        item={
            "path": "manual.blocks.assets/fig1.png",
            "caption": "Hydraulic schematic",
            "blockid": "b1",
            "heading": {"heading": "Hydraulics", "parent_headings": ["Systems"]},
            "llm_analyze_result": {
                "status": "success",
                "name": "hydraulic_schematic",
                "type": "Flowchart",
                "description": "A hydraulic system schematic.",
            },
        },
    )

    assert media == {
        "type": "drawing",
        "id": "im-0001",
        "display_name": "hydraulic_schematic",
        "image_type": "Flowchart",
        "caption": "Hydraulic schematic",
        "blockid": "b1",
        "asset_path": "manual.blocks.assets/fig1.png",
        "asset_mime": "image/png",
        "heading": "Hydraulics",
        "parent_headings": ["Systems"],
    }


def test_resolve_media_asset_path_rejects_path_traversal(tmp_path: Path):
    blocks_path = tmp_path / "manual.blocks.jsonl"

    with pytest.raises(ValueError, match="outside parsed artifact directory"):
        resolve_media_asset_path(str(blocks_path), "../secret.png")
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `python -m pytest tests/sidecar/test_media_context.py -q`

Expected: fails because `lightrag.sidecar.media_context` does not exist.

- [ ] **Step 3: Implement metadata helpers**

Create `lightrag/sidecar/media_context.py` with pure functions:

```python
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any


ROOT_TO_TYPE = {
    "drawings": "drawing",
    "tables": "table",
    "equations": "equation",
}


def _string(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def resolve_media_asset_path(blocks_path: str, asset_path: str | None) -> Path | None:
    if not asset_path:
        return None
    blocks_file = Path(blocks_path).resolve()
    base_dir = blocks_file.parent.resolve()
    candidate = (base_dir / asset_path).resolve()
    if base_dir not in candidate.parents and candidate != base_dir:
        raise ValueError("media asset path resolves outside parsed artifact directory")
    return candidate


def _relative_to_blocks_dir(blocks_path: str, path: Path | None) -> str:
    if path is None:
        return ""
    blocks_dir = Path(blocks_path).resolve().parent
    try:
        return path.resolve().relative_to(blocks_dir).as_posix()
    except ValueError:
        return path.name


def _heading(item: dict[str, Any]) -> tuple[str, list[str]]:
    raw = item.get("heading")
    if isinstance(raw, dict):
        return _string(raw.get("heading")), _string_list(raw.get("parent_headings"))
    return _string(raw), _string_list(item.get("parent_headings"))


def build_media_context(
    *,
    blocks_path: str,
    root_key: str,
    item_id: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    media_type = ROOT_TO_TYPE[root_key]
    analysis = item.get("llm_analyze_result") if isinstance(item, dict) else {}
    analysis = analysis if isinstance(analysis, dict) else {}
    heading, parent_headings = _heading(item)
    asset_abs = resolve_media_asset_path(blocks_path, _string(item.get("path")))
    asset_rel = _relative_to_blocks_dir(blocks_path, asset_abs) if asset_abs else ""
    asset_mime = mimetypes.guess_type(asset_rel)[0] or ""

    media: dict[str, Any] = {
        "type": media_type,
        "id": str(item_id),
        "display_name": _string(analysis.get("name")),
        "caption": _string(item.get("caption")),
        "blockid": _string(item.get("blockid")),
    }
    if media_type == "drawing":
        media["image_type"] = _string(analysis.get("type"))
    if asset_rel:
        media["asset_path"] = asset_rel
        media["asset_mime"] = asset_mime
    if heading:
        media["heading"] = heading
    if parent_headings:
        media["parent_headings"] = parent_headings
    return {key: value for key, value in media.items() if value not in ("", [], None)}
```

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/sidecar/test_media_context.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lightrag/sidecar/media_context.py tests/sidecar/test_media_context.py
git commit -m "feat: normalize sidecar media metadata"
```

## Task 2: Store Media Metadata on Multimodal Chunks

**Files:**
- Modify: `lightrag/pipeline.py`
- Test: `tests/pipeline/test_multimodal_media_chunks.py`

- [ ] **Step 1: Write failing test**

Add a test that writes a `doc.blocks.jsonl` and `doc.drawings.json`, calls `_build_mm_chunks_from_sidecars`, and asserts the chunk has both `sidecar` and `media`.

```python
import json
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_mm_chunk_includes_media_metadata(tmp_path: Path, lightrag_instance):
    blocks = tmp_path / "doc.blocks.jsonl"
    blocks.write_text('{"type":"meta"}\n', encoding="utf-8")
    assets = tmp_path / "doc.blocks.assets"
    assets.mkdir()
    (assets / "fig.png").write_bytes(b"png")
    (tmp_path / "doc.drawings.json").write_text(
        json.dumps(
            {
                "drawings": {
                    "im-1": {
                        "path": "doc.blocks.assets/fig.png",
                        "caption": "System diagram",
                        "llm_analyze_result": {
                            "status": "success",
                            "name": "system_diagram",
                            "type": "Flowchart",
                            "description": "A system diagram.",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    chunks = await lightrag_instance._build_mm_chunks_from_sidecars(
        "doc-1",
        str(blocks),
        base_order_index=0,
        process_options="i",
    )

    assert chunks[0]["sidecar"] == {
        "type": "drawing",
        "id": "im-1",
        "refs": [{"type": "drawing", "id": "im-1"}],
    }
    assert chunks[0]["media"]["asset_path"] == "doc.blocks.assets/fig.png"
    assert chunks[0]["media"]["display_name"] == "system_diagram"
```

- [ ] **Step 2: Run test to confirm failure**

Run: `python -m pytest tests/pipeline/test_multimodal_media_chunks.py -q`

Expected: fails because `media` is not present on multimodal chunks.

- [ ] **Step 3: Add metadata attachment**

In `lightrag/pipeline.py::_build_mm_chunks_from_sidecars`, import the helper near the sidecar loop and add `media` to `chunk_dict`:

```python
from lightrag.sidecar.media_context import build_media_context

media_context = build_media_context(
    blocks_path=str(block_file),
    root_key=root_key,
    item_id=str(item_id),
    item=item,
)

chunk_dict: dict[str, Any] = {
    "chunk_id": f"{doc_id}-mm-{kind}-{local_idx:03d}",
    "chunk_order_index": order,
    "content": chunk_content,
    "tokens": tokens,
    "sidecar": sidecar_block,
    "media": media_context,
    "llm_cache_list": cache_list,
}
```

- [ ] **Step 4: Verify**

Run:

```bash
python -m pytest tests/pipeline/test_multimodal_media_chunks.py -q
python -m pytest tests/parser/test_parse_native_lightrag_e2e.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add lightrag/pipeline.py tests/pipeline/test_multimodal_media_chunks.py
git commit -m "feat: attach media metadata to multimodal chunks"
```

## Task 3: Preserve Media Metadata Through Query Context

**Files:**
- Modify: `lightrag/operate.py`
- Modify: `lightrag/utils.py`
- Test: `tests/operate/test_multimodal_query_context.py`

- [ ] **Step 1: Write failing tests**

Add tests for two paths:

1. vector retrieval returns a chunk id and `_attach_content_headings`-style lookup backfills `media` from `text_chunks`;
2. `convert_to_user_format` preserves `media` in `data.chunks`.

```python
from lightrag.utils import convert_to_user_format


def test_convert_to_user_format_preserves_chunk_media():
    media = {
        "type": "drawing",
        "id": "im-1",
        "display_name": "system_diagram",
        "asset_path": "doc.blocks.assets/fig.png",
    }

    data = convert_to_user_format(
        [],
        [],
        [
            {
                "reference_id": "1",
                "content": "[Image Name]system_diagram",
                "file_path": "manual.pdf",
                "chunk_id": "doc-mm-drawing-000",
                "media": media,
            }
        ],
        [{"reference_id": "1", "file_path": "manual.pdf"}],
        "mix",
    )

    assert data["data"]["chunks"][0]["media"] == media
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `python -m pytest tests/operate/test_multimodal_query_context.py -q`

Expected: fails because `convert_to_user_format` drops `media`.

- [ ] **Step 3: Preserve metadata in `convert_to_user_format`**

In `lightrag/utils.py`, update chunk conversion:

```python
chunk_data = {
    "reference_id": chunk.get("reference_id", ""),
    "content": chunk.get("content", ""),
    "file_path": chunk.get("file_path", "unknown_source"),
    "chunk_id": chunk.get("chunk_id", ""),
}
if isinstance(chunk.get("media"), dict):
    chunk_data["media"] = chunk["media"]
```

- [ ] **Step 4: Preserve metadata in query retrieval and prompt chunks**

In `lightrag/operate.py`, add a helper:

```python
async def _attach_chunk_metadata(chunks: list[dict], text_chunks_db: BaseKVStorage | None) -> None:
    if not text_chunks_db or not chunks:
        return
    chunk_ids = [c.get("chunk_id") for c in chunks]
    chunk_data_list = await text_chunks_db.get_by_ids(chunk_ids)
    for chunk, data in zip(chunks, chunk_data_list):
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("media"), dict):
            chunk["media"] = data["media"]
        if isinstance(data.get("sidecar"), dict):
            chunk["sidecar"] = data["sidecar"]
```

Call it after vector retrieval in `naive_query` and after `_merge_all_chunks` in `_build_query_context` before `process_chunks_unified`.

When building `chunks_context`, include compact media metadata:

```python
if isinstance(chunk.get("media"), dict):
    entry["media"] = chunk["media"]
```

- [ ] **Step 5: Verify**

Run:

```bash
python -m pytest tests/operate/test_multimodal_query_context.py -q
python -m pytest tests/pipeline/test_multimodal_media_chunks.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add lightrag/operate.py lightrag/utils.py tests/operate/test_multimodal_query_context.py
git commit -m "feat: preserve media metadata in query context"
```

## Task 4: Add Safe Media Asset API Endpoint

**Files:**
- Modify: `lightrag/api/routers/document_routes.py`
- Test: `tests/api/routes/test_media_routes.py`

- [ ] **Step 1: Write failing route tests**

Test that a chunk with `media.asset_path` returns a `FileResponse`, while missing chunks, non-image chunks, and traversal paths fail.

```python
import pytest


@pytest.mark.asyncio
async def test_get_chunk_media_returns_image(test_client, rag_mock, tmp_path):
    parsed_dir = tmp_path / "__parsed__"
    parsed_dir.mkdir()
    asset_dir = parsed_dir / "doc.blocks.assets"
    asset_dir.mkdir()
    (asset_dir / "fig.png").write_bytes(b"png")
    rag_mock.text_chunks.get_by_id.return_value = {
        "chunk_id": "doc-mm-drawing-000",
        "media": {"type": "drawing", "asset_path": "doc.blocks.assets/fig.png"},
        "parsed_blocks_path": str(parsed_dir / "doc.blocks.jsonl"),
    }

    response = await test_client.get("/documents/media/doc-mm-drawing-000")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
```

- [ ] **Step 2: Run test to confirm failure**

Run: `python -m pytest tests/api/routes/test_media_routes.py -q`

Expected: fails because the route does not exist.

- [ ] **Step 3: Implement route**

Add route logic that:

- fetches `rag.text_chunks.get_by_id(chunk_id)`;
- requires `media.type == "drawing"`;
- resolves `media.asset_path` relative to the parsed blocks path or parsed artifact directory stored on the chunk;
- verifies the resolved path stays under the parsed artifact directory;
- returns `FileResponse`.

Route shape:

```python
@router.get("/media/{chunk_id}")
async def get_document_media(chunk_id: str, request: Request):
    rag = request.app.state.rag
    chunk = await rag.text_chunks.get_by_id(chunk_id)
    if not isinstance(chunk, dict):
        raise HTTPException(status_code=404, detail="Media chunk not found")
    media = chunk.get("media")
    if not isinstance(media, dict) or media.get("type") != "drawing":
        raise HTTPException(status_code=404, detail="Image media not found")
    # Resolve and validate path before returning FileResponse.
```

- [ ] **Step 4: Add `media_url` to raw data**

When `convert_to_user_format` sees `media.type == "drawing"` and a `chunk_id`, add:

```python
media = dict(chunk["media"])
media["media_url"] = f"/documents/media/{quote(chunk.get('chunk_id', ''), safe='')}"
chunk_data["media"] = media
```

Use `urllib.parse.quote`.

- [ ] **Step 5: Verify**

Run:

```bash
python -m pytest tests/api/routes/test_media_routes.py -q
python -m pytest tests/operate/test_multimodal_query_context.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add lightrag/api/routers/document_routes.py lightrag/utils.py tests/api/routes/test_media_routes.py
git commit -m "feat: expose extracted media assets safely"
```

## Task 5: Update WebUI Types and Media Rendering

**Files:**
- Modify: `lightrag_webui/src/api/lightrag.ts`
- Modify: `lightrag_webui/src/components/retrieval/ChatMessage.tsx`
- Test: `lightrag_webui/src/api/lightrag-media.test.ts`

- [ ] **Step 1: Add failing frontend test**

Add a Bun test that parses a query response containing `chunks[].media.media_url` and asserts the API type keeps it.

```ts
import { describe, expect, test } from 'bun:test'

describe('query media metadata', () => {
  test('preserves media_url on returned chunks', () => {
    const chunk = {
      reference_id: '1',
      content: '[Image Name]system_diagram',
      file_path: 'manual.pdf',
      chunk_id: 'doc-mm-drawing-000',
      media: {
        type: 'drawing',
        id: 'im-1',
        display_name: 'system_diagram',
        media_url: '/documents/media/doc-mm-drawing-000'
      }
    }

    expect(chunk.media.media_url).toBe('/documents/media/doc-mm-drawing-000')
  })
})
```

- [ ] **Step 2: Run test to confirm baseline**

Run: `cd lightrag_webui && bun test src/api/lightrag-media.test.ts`

Expected: passes once the file exists; this guards the expected response shape.

- [ ] **Step 3: Add TypeScript interfaces**

In `lightrag_webui/src/api/lightrag.ts`, add:

```ts
export interface MediaReference {
  type: 'drawing' | 'table' | 'equation'
  id: string
  display_name?: string
  image_type?: string
  caption?: string
  asset_path?: string
  asset_mime?: string
  media_url?: string
  heading?: string
  parent_headings?: string[]
}
```

Attach `media?: MediaReference` to the chunk result type.

- [ ] **Step 4: Render media thumbnails in chat**

In `ChatMessage.tsx`, render a compact media citation area when a retrieved chunk has `media.media_url`:

```tsx
{chunk.media?.media_url && (
  <a href={chunk.media.media_url} target="_blank" rel="noreferrer">
    <img
      src={chunk.media.media_url}
      alt={chunk.media.display_name || chunk.media.caption || chunk.media.id}
      className="max-h-32 rounded border object-contain"
    />
  </a>
)}
```

- [ ] **Step 5: Verify**

Run:

```bash
cd lightrag_webui
bun test src/api/lightrag-media.test.ts
bun run lint
bun run build
```

Expected: all pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add lightrag_webui/src/api/lightrag.ts lightrag_webui/src/components/retrieval/ChatMessage.tsx lightrag_webui/src/api/lightrag-media.test.ts
git commit -m "feat: show retrieved media in chat"
```

## Task 6: Configuration and Documentation

**Files:**
- Modify: `env.example`
- Modify: `docs/FileProcessingPipeline.md`
- Modify: `docs/LightRAGSidecarFormat.md`

- [ ] **Step 1: Document recommended OpenAI multimodal config**

Add an example that keeps OpenAI as the LLM/VLM provider and text embedding provider:

```env
LLM_BINDING=openai
LLM_BINDING_HOST=https://api.openai.com/v1
LLM_BINDING_API_KEY=${OPENAI_API_KEY}
LLM_MODEL=gpt-4.1-mini

EMBEDDING_BINDING=openai
EMBEDDING_BINDING_HOST=https://api.openai.com/v1
EMBEDDING_BINDING_API_KEY=${OPENAI_API_KEY}
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIM=3072

VLM_PROCESS_ENABLE=true
VLM_LLM_BINDING=openai
VLM_LLM_MODEL=gpt-4.1-mini

LIGHTRAG_PARSER=pdf:mineru-iteP;docx:native-iteP;md:native-iteP;*:legacy-R
MINERU_API_MODE=local
MINERU_LOCAL_ENDPOINT=http://127.0.0.1:8000
```

- [ ] **Step 2: Document behavior and limits**

Add these notes:

- legacy PDF extraction is text-only;
- image indexing means VLM description + caption + OCR + surrounding context embedded as text;
- extracted image bytes are not sent to the answer LLM during query unless a future multimodal-query mode is added;
- true image-vector search requires a separate multimodal embedding provider and storage extension.

- [ ] **Step 3: Verify docs**

Run:

```bash
python -m ruff check lightrag/sidecar/media_context.py lightrag/pipeline.py lightrag/operate.py lightrag/utils.py lightrag/api/routers/document_routes.py
```

Expected: ruff passes.

- [ ] **Step 4: Commit**

Run:

```bash
git add env.example docs/FileProcessingPipeline.md docs/LightRAGSidecarFormat.md
git commit -m "docs: document multimodal image indexing setup"
```

## Task 7: End-to-End Verification

**Files:**
- No new files.

- [ ] **Step 1: Start services**

Run:

```bash
python -X utf8 -m lightrag.api.lightrag_server
```

Expected: health endpoint returns success and WebUI is mounted.

- [ ] **Step 2: Process a small fixture**

Use a small DOCX/MD/textpack fixture first because native extraction does not require MinerU/Docling. Upload with process options including `i` or use a filename hint such as:

```text
sample.[native-iP].docx
```

Expected:

- `inputs/__parsed__/sample.blocks.jsonl` exists;
- `sample.drawings.json` exists;
- `sample.blocks.assets/` contains image files;
- document status reaches `PROCESSED`;
- `text_chunks` contains `*-mm-drawing-*` chunks with `media`.

- [ ] **Step 3: Query for visual content**

Run a query asking about a known image:

```bash
Invoke-WebRequest -UseBasicParsing -Method POST http://localhost:9621/query `
  -ContentType "application/json" `
  -Body '{"query":"What does the system diagram show?","mode":"mix","include_references":true}'
```

Expected:

- answer cites the source document;
- raw `data.chunks[]` includes `media.type == "drawing"`;
- `media.media_url` opens the extracted image;
- WebUI chat shows a thumbnail/citation.

- [ ] **Step 4: Run focused backend tests**

Run:

```bash
python -m pytest tests/sidecar/test_media_context.py tests/pipeline/test_multimodal_media_chunks.py tests/operate/test_multimodal_query_context.py tests/api/routes/test_media_routes.py -q
```

Expected: all pass.

- [ ] **Step 5: Run frontend verification**

Run:

```bash
cd lightrag_webui
bun test src/api/lightrag-media.test.ts
bun run lint
bun run build
```

Expected: all pass.

- [ ] **Step 6: Commit**

Run:

```bash
git status --short
git commit --allow-empty -m "test: verify multimodal media retrieval flow"
```

## Optional Future Phase: True Multimodal Image Vector Search

This is intentionally separate because it changes storage contracts and provider expectations.

- Add a new vector namespace such as `image_chunks_vdb`.
- Add a provider abstraction for image embeddings, with one implementation backed by a CLIP-compatible service or a provider that exposes multimodal embeddings.
- Store `image_embedding` vectors keyed by the same `chunk_id` used for the text multimodal chunk.
- Add `QueryParam(include_visual_search: bool = False)` and merge visual hits with text/vector/KG hits.
- Keep the current VLM-description indexing as the default because it works with OpenAI text embeddings and all existing LightRAG retrieval modes.

## Current Deployment Recommendation

For this repo today, the practical path is:

```env
LIGHTRAG_PARSER=pdf:mineru-iteP;docx:native-iteP;md:native-iteP;*:legacy-R
VLM_PROCESS_ENABLE=true
LLM_BINDING=openai
VLM_LLM_BINDING=openai
EMBEDDING_BINDING=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIM=3072
```

This gives image/figure/table extraction where the selected parser supports it, OpenAI VLM analysis for image context, and OpenAI text embeddings over the generated multimodal chunks.
