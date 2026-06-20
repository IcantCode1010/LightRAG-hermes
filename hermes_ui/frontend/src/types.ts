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

export type DocumentProcessingVersion = {
  version_label?: string;
  source_name?: string;
  state?: "searchable" | "failed" | "archived" | "registered" | string;
  searchable?: boolean;
  chunks_count?: number | null;
  error?: string;
};

export type DocumentProcessingRecord = {
  document_key?: string;
  latest?: DocumentProcessingVersion;
  versions?: DocumentProcessingVersion[];
};

export type DocumentProcessingSummary = {
  registered_document_count?: number;
  registered_version_count?: number;
  searchable_latest_count?: number;
  failed_latest_count?: number;
  unsearchable_latest_count?: number;
};

export type DocumentProcessingStatus = {
  summary?: DocumentProcessingSummary;
  documents?: DocumentProcessingRecord[];
};

export type SnapshotStatusResponse = {
  state?: string;
  reason?: string;
  can_build?: boolean;
  current?: boolean;
  needs_rotation?: boolean;
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
