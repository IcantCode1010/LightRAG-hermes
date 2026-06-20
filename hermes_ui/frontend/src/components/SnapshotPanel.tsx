import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, responseText } from "@/lib/api";
import type { ChatMessage, SnapshotStatusResponse, Tone } from "@/types";

export function SnapshotPanel({
  addMessage,
  refresh,
  snapshot,
}: {
  addMessage: (role: ChatMessage["role"], text: string) => void;
  refresh: () => Promise<void>;
  snapshot: SnapshotStatusResponse | null;
}) {
  const [snapshotId, setSnapshotId] = useState(`snapshot-${datePart()}.001`);
  const [isPending, setIsPending] = useState(false);
  const canBuild = Boolean(snapshot?.can_build);
  const isCurrent = Boolean(snapshot?.current);
  const targetTone: Tone = canBuild || isCurrent ? "ok" : "warn";
  const activeLatestCount = Object.keys(snapshot?.active_snapshot?.latest_versions || {}).length;
  const isDegraded = snapshot?.state === "degraded";

  async function buildSnapshot(event: FormEvent) {
    event.preventDefault();
    setIsPending(true);
    try {
      const response = await api<unknown>("/api/snapshots/build", {
        method: "POST",
        body: { snapshot_id: snapshotId },
      });
      addMessage("agent", responseText(response, "Snapshot build request completed."));
      await refresh();
    } catch (error) {
      addMessage("system", error instanceof Error ? error.message : String(error));
    } finally {
      setIsPending(false);
    }
  }

  return (
    <section className="tool-view" id="snapshot-tab" role="tabpanel" aria-labelledby="snapshot-tab-button">
      <section className="snapshot-readiness" aria-live="polite">
        {isDegraded && (
          <div className="status-item snapshot-degraded">
            <div className="status-label">Snapshot coverage</div>
            <Badge tone="warn">Some latest documents are searchable. Failed documents need a replacement version.</Badge>
          </div>
        )}
        <StatusBadge label="Snapshot target" value={snapshot?.reason || snapshot?.state || "Loading"} tone={targetTone} />
        <StatusBadge label="Archived latest docs" value={String(snapshot?.archived_document_count ?? 0)} tone="ok" />
        <StatusBadge label="Target indexed docs" value={String(snapshot?.target_document_count ?? 0)} tone={targetTone} />
        <StatusBadge label="Active snapshot" value={snapshot?.active_snapshot?.snapshot_id || "None"} tone={snapshot?.active_snapshot ? "ok" : "warn"} />
        <StatusBadge label="Active latest versions" value={String(activeLatestCount)} tone={activeLatestCount ? "ok" : "warn"} />
      </section>
      <form className="tool-form" onSubmit={buildSnapshot}>
        <label>
          <span>Snapshot ID</span>
          <Input required value={snapshotId} onChange={(event) => setSnapshotId(event.target.value)} />
        </label>
        <p className="note">Snapshot builds may use embedding/model API credits.</p>
        <Button disabled={!canBuild || isPending} type="submit">Build latest snapshot</Button>
      </form>
    </section>
  );
}

function StatusBadge({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <div className="status-item">
      <div className="status-label">{label}</div>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}

function datePart() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
