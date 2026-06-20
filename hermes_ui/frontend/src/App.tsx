import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HermesChat } from "@/components/HermesChat";
import { DocumentsPanel } from "@/components/DocumentsPanel";
import { SnapshotPanel } from "@/components/SnapshotPanel";
import { MaintenancePanel } from "@/components/MaintenancePanel";
import { StatusPanel } from "@/components/StatusPanel";
import { api } from "@/lib/api";
import type {
  ChatMessage,
  DocumentRecord,
  DocumentsResponse,
  SnapshotArchive,
  SnapshotArchivesResponse,
  SnapshotStatusResponse,
  StatusResponse,
} from "@/types";

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: crypto.randomUUID(), role: "system", text: "Ready. Status and document registry are loading." },
  ]);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [snapshot, setSnapshot] = useState<SnapshotStatusResponse | null>(null);
  const [archives, setArchives] = useState<SnapshotArchive[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"documents" | "snapshot" | "maintenance">("documents");

  const addMessage = useCallback((role: ChatMessage["role"], text: string) => {
    setMessages((current) => [...current, { id: crypto.randomUUID(), role, text }]);
  }, []);

  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [statusPayload, documentPayload, snapshotPayload, archivePayload] = await Promise.all([
        api<StatusResponse>("/api/status"),
        api<DocumentsResponse>("/api/documents"),
        api<SnapshotStatusResponse>("/api/snapshots/status"),
        api<SnapshotArchivesResponse>("/api/maintenance/snapshot-archives"),
      ]);
      setStatus(statusPayload);
      setDocuments(Array.isArray(documentPayload.documents) ? documentPayload.documents : []);
      setSnapshot(snapshotPayload);
      setArchives(Array.isArray(archivePayload.archives) ? archivePayload.archives : []);
    } catch (error) {
      addMessage("system", error instanceof Error ? error.message : String(error));
    } finally {
      setIsRefreshing(false);
    }
  }, [addMessage]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const statusSummary = useMemo(() => {
    const configured = status?.hermes_configured !== false;
    return configured ? "Configured" : "Needs configuration";
  }, [status]);

  return (
    <main className="app-shell">
      <StatusPanel status={status} />

      <section className="chat-panel" aria-label="Hermes chat">
        <header className="panel-header">
          <div>
            <p className="eyebrow">Hermes Chat</p>
            <h1>Latest document answers</h1>
          </div>
          <div className="header-actions">
            <Badge tone={status?.hermes_configured === false ? "error" : "ok"}>{statusSummary}</Badge>
            <Button disabled={isRefreshing} onClick={refresh} type="button" variant="secondary">
              <RefreshCw size={16} />
              Refresh
            </Button>
          </div>
        </header>
        <HermesChat addMessage={addMessage} messages={messages} />
      </section>

      <aside className="tools-panel" aria-label="Tools">
        <nav className="tabs" role="tablist" aria-label="Tool views">
          {(["documents", "snapshot", "maintenance"] as const).map((tab) => (
            <button
              aria-controls={`${tab}-tab`}
              aria-selected={activeTab === tab}
              className={`tab ${activeTab === tab ? "is-active" : ""}`}
              id={`${tab}-tab-button`}
              key={tab}
              onClick={() => setActiveTab(tab)}
              role="tab"
              type="button"
            >
              {tab[0].toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>

        {activeTab === "documents" && (
          <DocumentsPanel addMessage={addMessage} documents={documents} refresh={refresh} />
        )}
        {activeTab === "snapshot" && (
          <SnapshotPanel addMessage={addMessage} refresh={refresh} snapshot={snapshot} />
        )}
        {activeTab === "maintenance" && (
          <MaintenancePanel addMessage={addMessage} archives={archives} refresh={refresh} />
        )}
      </aside>
    </main>
  );
}
