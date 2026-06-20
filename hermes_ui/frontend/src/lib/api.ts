export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch (error) {
    throw new Error(`Request failed for ${path}: ${error instanceof Error ? error.message : String(error)}`);
  }

  const text = await response.text();
  const payload = parseJson(text);
  if (!response.ok) {
    throw new Error(errorMessage(path, response.status, payload, text));
  }

  return (payload ?? {}) as T;
}

export async function apiForm<T>(path: string, formData: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { method: "POST", body: formData });
  } catch (error) {
    throw new Error(`Request failed for ${path}: ${error instanceof Error ? error.message : String(error)}`);
  }

  const text = await response.text();
  const payload = parseJson(text);
  if (!response.ok) {
    throw new Error(errorMessage(path, response.status, payload, text));
  }

  return (payload ?? {}) as T;
}

export function responseText(response: unknown, fallback: string): string {
  if (!response || typeof response !== "object") {
    return fallback;
  }
  const payload = response as Record<string, unknown>;
  return String(payload.text || payload.message || payload.detail || fallback);
}

function parseJson(text: string): unknown | null {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function errorMessage(path: string, status: number, payload: unknown, text: string): string {
  if (payload && typeof payload === "object") {
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === "string") {
      return `${path} failed (${status}): ${detail}`;
    }
    if (Array.isArray(detail)) {
      return `${path} failed (${status}): ${detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : "validation error"))
        .join("; ")}`;
    }
    const message = (payload as Record<string, unknown>).message;
    if (typeof message === "string") {
      return `${path} failed (${status}): ${message}`;
    }
  }
  return `${path} failed (${status}): ${text || "no response body"}`;
}
