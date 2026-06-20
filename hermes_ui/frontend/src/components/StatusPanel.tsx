import { Badge } from "@/components/ui/badge";
import type { StatusResponse, Tone } from "@/types";

export function StatusPanel({ status }: { status: StatusResponse | null }) {
  const pipeline = status?.pipeline || {};
  const configured = status?.hermes_configured !== false;
  const rows: Array<[string, string, Tone]> = status
    ? [
        ["MCP", status.mcp?.status || status.state || "unknown", status.state === "ok" ? "ok" : "warn"],
        ["Pipeline", pipeline.busy ? "Busy" : "Idle", pipeline.busy ? "warn" : "ok"],
        ["Indexed docs", String(pipeline.docs ?? 0), "ok"],
        ["Hermes", configured ? "Configured" : "Needs configuration", configured ? "ok" : "error"],
      ]
    : [
        ["MCP", "Loading", "warn"],
        ["Pipeline", "Loading", "warn"],
        ["Indexed docs", "Loading", "warn"],
      ];

  if (status?.hermes_error) {
    rows.push(["Configuration", status.hermes_error, "error"]);
  }

  return (
    <aside className="status-sidebar" aria-label="Service status">
      <header className="region-header">
        <p className="eyebrow">Hermes Local</p>
        <h2>Operations</h2>
      </header>
      <section className="status-stack" aria-live="polite">
        {rows.map(([label, value, tone]) => (
          <div className="status-item" key={label}>
            <div className="status-label">{label}</div>
            <Badge tone={tone}>{value}</Badge>
          </div>
        ))}
      </section>
    </aside>
  );
}
