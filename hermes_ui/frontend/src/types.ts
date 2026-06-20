export type Tone = "ok" | "warn" | "error";

export type StatusResponse = {
  state?: string;
  mcp?: { status?: string };
  pipeline?: { busy?: boolean; docs?: number };
  hermes_configured?: boolean;
  hermes_error?: string;
};

export type DocumentVersion = {
  label?: string;
  searchable?: boolean;
};

export type DocumentRecord = {
  document_key?: string;
  latest_version_label?: string;
  versions?: Array<string | DocumentVersion>;
};

export type DocumentsResponse = {
  documents?: DocumentRecord[];
};

export type SnapshotStatusResponse = {
  state?: string;
  reason?: string;
  can_build?: boolean;
  archived_document_count?: number;
  target_document_count?: number;
  active_snapshot?: { snapshot_id?: string } | null;
};

export type SnapshotArchive = {
  name?: string;
  size_bytes?: number;
};

export type SnapshotArchivesResponse = {
  archives?: SnapshotArchive[];
};

export type ChatRole = "system" | "user" | "agent";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
};
