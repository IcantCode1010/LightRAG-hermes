import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, responseText } from "@/lib/api";
import type { ChatMessage, SnapshotArchive } from "@/types";

export function MaintenancePanel({
  addMessage,
  archives,
  refresh,
}: {
  addMessage: (role: ChatMessage["role"], text: string) => void;
  archives: SnapshotArchive[];
  refresh: () => Promise<void>;
}) {
  return (
    <section className="tool-view" id="maintenance-tab" role="tabpanel" aria-labelledby="maintenance-tab-button">
      <section className="registry-section" aria-label="Snapshot archive maintenance">
        <div className="section-heading">
          <h3>Archived snapshots</h3>
          <span className="meta">{archives.length} {archives.length === 1 ? "archive" : "archives"}</span>
        </div>
        <p className="note">
          Deletes archived snapshot folders only. Active snapshots and source document versions are not available here.
        </p>
        <div className="registry archive-registry" aria-live="polite">
          {archives.length === 0 ? (
            <div className="empty-state">No archived snapshots are available for cleanup.</div>
          ) : (
            archives.map((archive) => (
              <ArchiveRow addMessage={addMessage} archive={archive} key={archive.name} refresh={refresh} />
            ))
          )}
        </div>
      </section>
    </section>
  );
}

function ArchiveRow({
  addMessage,
  archive,
  refresh,
}: {
  addMessage: (role: ChatMessage["role"], text: string) => void;
  archive: SnapshotArchive;
  refresh: () => Promise<void>;
}) {
  const [confirmation, setConfirmation] = useState("");
  const [isPending, setIsPending] = useState(false);
  const archiveName = archive.name || "unknown";

  async function deleteArchive() {
    setIsPending(true);
    try {
      const response = await api<unknown>(`/api/maintenance/snapshot-archives/${encodeURIComponent(archiveName)}`, {
        method: "DELETE",
        body: { confirmation },
      });
      addMessage("system", responseText(response, "Snapshot archive deleted."));
      await refresh();
    } catch (error) {
      addMessage("system", error instanceof Error ? error.message : String(error));
    } finally {
      setIsPending(false);
    }
  }

  return (
    <article className="doc-row archive-row">
      <div className="doc-row-header">
        <div className="doc-key">{archiveName}</div>
        <Badge>{formatBytes(Number(archive.size_bytes || 0))}</Badge>
      </div>
      <div className="archive-delete">
        <label>
          <span>Type archive name to delete</span>
          <Input placeholder={archiveName} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
        </label>
        <Button
          disabled={confirmation.trim() !== archiveName || isPending}
          onClick={deleteArchive}
          type="button"
          variant="destructive"
        >
          <Trash2 size={16} />
          Delete archive
        </Button>
      </div>
    </article>
  );
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}
