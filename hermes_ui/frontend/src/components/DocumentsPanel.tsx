import { FormEvent, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, apiForm, responseText } from "@/lib/api";
import type { ChatMessage, DocumentProcessingRecord, DocumentProcessingStatus, DocumentRecord, Tone } from "@/types";

export function DocumentsPanel({
  addMessage,
  documents,
  processingStatus,
  refresh,
}: {
  addMessage: (role: ChatMessage["role"], text: string) => void;
  documents: DocumentRecord[];
  processingStatus: DocumentProcessingStatus | null;
  refresh: () => Promise<void>;
}) {
  const [documentKey, setDocumentKey] = useState("");
  const [versionLabel, setVersionLabel] = useState(`${datePart()}-001`);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [buildSnapshot, setBuildSnapshot] = useState(false);
  const [isPending, setIsPending] = useState(false);

  async function ingest(event: FormEvent) {
    event.preventDefault();
    setIsPending(true);
    try {
      const response = selectedFile
        ? await ingestSelectedFile(selectedFile, documentKey, versionLabel, buildSnapshot)
        : await api<unknown>("/api/ingest", {
            method: "POST",
            body: { document_key: documentKey, version_label: versionLabel, title, text },
          });
      addMessage("agent", responseText(response, "Ingest request completed."));
      setVersionLabel(nextPatchLabel(versionLabel));
      setSelectedFile(null);
      await refresh();
    } catch (error) {
      addMessage("system", error instanceof Error ? error.message : String(error));
    } finally {
      setIsPending(false);
    }
  }

  async function loadFile(file: File | null) {
    setSelectedFile(file);
    if (!file) {
      return;
    }
    if (!documentKey) {
      setDocumentKey(documentKeyFromFilename(file.name));
    }
    if (!title) {
      setTitle(titleFromFilename(file.name));
    }
    if (isTextLikeFile(file)) {
      setText(await file.text());
    } else {
      setText(`Attached file: ${file.name}`);
    }
    addMessage("system", `Selected ${file.name}. Review the fields, then ingest this version.`);
  }

  return (
    <section className="tool-view" id="documents-tab" role="tabpanel" aria-labelledby="documents-tab-button">
      <form className="tool-form" onSubmit={ingest}>
        <label className="file-loader">
          <span>
            <Upload size={16} />
            Choose file
          </span>
          <input
            accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.markdown,.csv,.json,.log,text/*,application/pdf"
            onChange={(event) => void loadFile(event.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <p className="note">
          Choose a document file or paste text below, then ingest it as a stored version.
          PDF and Office files are processed by LightRAG when the latest snapshot is built.
        </p>
        <label>
          <span>Document key</span>
          <Input required value={documentKey} onChange={(event) => setDocumentKey(event.target.value)} />
        </label>
        <label>
          <span>Version label</span>
          <Input
            pattern="^\d{4}-\d{2}-\d{2}-[A-Za-z0-9._-]+$"
            required
            title="Use YYYY-MM-DD-label, for example 2026-06-20-001"
            value={versionLabel}
            onChange={(event) => setVersionLabel(event.target.value)}
          />
        </label>
        <label>
          <span>Title</span>
          <Input required value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label>
          <span>Text</span>
          <Textarea value={text} onChange={(event) => setText(event.target.value)} rows={8} />
        </label>
        <label className="inline-option">
          <input
            checked={buildSnapshot}
            onChange={(event) => setBuildSnapshot(event.target.checked)}
            type="checkbox"
          />
          <span>Build searchable snapshot after upload</span>
        </label>
        <Button disabled={isPending} type="submit">Ingest version</Button>
      </form>

      <ProcessingStatusSection
        onUploadReplacement={(documentRecord) => {
          setDocumentKey(documentRecord.document_key || "");
          setTitle(titleFromFilename(documentRecord.document_key || "Document"));
          setVersionLabel(`${datePart()}-001`);
          addMessage("system", `Ready to upload a replacement version for ${documentRecord.document_key || "this document"}.`);
        }}
        processingStatus={processingStatus}
      />

      <section className="registry-section" aria-label="Document registry">
        <div className="section-heading">
          <h3>Document registry</h3>
          <span className="meta">{documents.length} {documents.length === 1 ? "document" : "documents"}</span>
        </div>
        <div className="registry" aria-live="polite">
          {documents.length === 0 ? (
            <div className="empty-state">No document versions are registered yet.</div>
          ) : (
            documents.map((documentRecord) => <DocumentRow documentRecord={documentRecord} key={documentRecord.document_key} />)
          )}
        </div>
      </section>
    </section>
  );
}

function ProcessingStatusSection({
  onUploadReplacement,
  processingStatus,
}: {
  onUploadReplacement: (documentRecord: DocumentProcessingRecord) => void;
  processingStatus: DocumentProcessingStatus | null;
}) {
  const summary = processingStatus?.summary || {};
  const processingDocuments = Array.isArray(processingStatus?.documents) ? processingStatus.documents : [];
  return (
    <section className="processing-section" aria-label="Document processing status">
      <div className="section-heading">
        <h3>Processing status</h3>
        <span className="meta">Latest versions only</span>
      </div>
      <div className="summary-grid" aria-label="Document processing summary">
        <StatusMetric label="Registered" value={summary.registered_document_count} />
        <StatusMetric label="Searchable" tone="ok" value={summary.searchable_latest_count} />
        <StatusMetric label="Failed" tone={summary.failed_latest_count ? "error" : undefined} value={summary.failed_latest_count} />
        <StatusMetric label="Needs snapshot" tone={summary.unsearchable_latest_count ? "warn" : undefined} value={summary.unsearchable_latest_count} />
      </div>
      <div className="registry processing-registry" aria-live="polite">
        {processingDocuments.length === 0 ? (
          <div className="empty-state">No processing status has been reported yet.</div>
        ) : (
          processingDocuments.map((documentRecord) => (
            <ProcessingRow
              documentRecord={documentRecord}
              key={documentRecord.document_key}
              onUploadReplacement={onUploadReplacement}
            />
          ))
        )}
      </div>
    </section>
  );
}

function StatusMetric({
  label,
  tone,
  value,
}: {
  label: string;
  tone?: Tone;
  value?: number;
}) {
  return (
    <div className="status-metric">
      <span className="status-metric-value">{value ?? 0}</span>
      <Badge tone={tone}>{label}</Badge>
    </div>
  );
}

function ProcessingRow({
  documentRecord,
  onUploadReplacement,
}: {
  documentRecord: DocumentProcessingRecord;
  onUploadReplacement: (documentRecord: DocumentProcessingRecord) => void;
}) {
  const latest = documentRecord.latest || {};
  const state = latest.state || "registered";
  const stateLabel = latest.searchable ? "searchable" : state;
  const tone = statusTone(stateLabel);
  return (
    <article className={`doc-row processing-row processing-row-${stateLabel}`}>
      <div className="doc-row-header">
        <div>
          <div className="doc-key">{documentRecord.document_key || "untitled"}</div>
          <p className="meta">{latest.source_name || "No source file recorded"}</p>
        </div>
        <Badge tone={tone}>{stateLabel}</Badge>
      </div>
      <div className="version-list">
        <Badge tone={latest.searchable ? "ok" : undefined}>latest {latest.version_label || "unknown"}</Badge>
        {typeof latest.chunks_count === "number" && <Badge>{latest.chunks_count} chunks</Badge>}
      </div>
      {stateLabel === "failed" && (
        <div className="processing-action">
          <p className="note">{latest.error || "LightRAG could not extract usable text from this latest version."}</p>
          <Button onClick={() => onUploadReplacement(documentRecord)} type="button" variant="secondary">
            Upload replacement version
          </Button>
        </div>
      )}
    </article>
  );
}

function DocumentRow({ documentRecord }: { documentRecord: DocumentRecord }) {
  return (
    <article className="doc-row">
      <div className="doc-row-header">
        <div className="doc-key">{documentRecord.document_key || "untitled"}</div>
        <Badge tone="ok">latest {documentRecord.latest_version_label || "unknown"}</Badge>
      </div>
      <div className="version-list">
        {(documentRecord.versions || []).map((version) => {
          const normalized = typeof version === "string" ? { label: version, searchable: version === documentRecord.latest_version_label } : version;
          return (
            <Badge key={normalized.label} tone={normalized.searchable ? "ok" : undefined}>
              {normalized.searchable ? `${normalized.label} latest/searchable` : `${normalized.label} archived/non-searchable`}
            </Badge>
          );
        })}
      </div>
    </article>
  );
}

function ingestSelectedFile(file: File, documentKey: string, versionLabel: string, buildSnapshot: boolean) {
  const formData = new FormData();
  formData.append("document_key", documentKey);
  formData.append("version_label", versionLabel);
  formData.append("build_snapshot", String(buildSnapshot));
  formData.append("file", file, file.name);
  return apiForm<unknown>("/api/ingest-file", formData);
}

function statusTone(state: string): Tone | undefined {
  if (state === "searchable") {
    return "ok";
  }
  if (state === "failed") {
    return "error";
  }
  if (state === "registered") {
    return "warn";
  }
  return undefined;
}

function datePart() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function nextPatchLabel(label: string) {
  const match = /^(\d{4}-\d{2}-\d{2})-(\d{3})$/.exec(label);
  return match ? `${match[1]}-${String(Number(match[2]) + 1).padStart(3, "0")}` : `${datePart()}-001`;
}

function documentKeyFromFilename(filename: string) {
  return filename.replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "document";
}

function titleFromFilename(filename: string) {
  return filename.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim() || "Document";
}

function isTextLikeFile(file: File) {
  const name = file.name.toLowerCase();
  return Boolean(file.type?.startsWith("text/")) || [".md", ".markdown", ".txt", ".csv", ".json", ".log"].some((ext) => name.endsWith(ext));
}
