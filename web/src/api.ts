// Client of the RAG API (src/api/app.py).

// VITE_API_URL: where the API lives when the web is hosted elsewhere
// (GitHub Pages -> the Hugging Face Space). Unset: the local API in
// development, and the same origin in a build served by the API itself.
export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export interface Domain {
  name: string;
  description: string;
  chunks: number;
  // Always searched: its chip cannot be turned off.
  pinned?: boolean;
}

export interface ModelOption {
  id: string;
  label: string;
  model: string;
  loaded: boolean;
  // False: offered only without the agent (Qwen3-4B: GPU memory).
  agent?: boolean;
}

export interface Config {
  model: string;
  profile: string;
  domains: Domain[];
  // LLMs to choose from (rag.toml profiles) and depth options (sources
  // given to the LLM; null = each domain's default).
  models: ModelOption[];
  // The model the web starts with (the base stays Qwen3-0.6B).
  model_default?: string;
  depths: number[];
  depth_default: number;
  agent_default: boolean;
  k: number;
}

export interface Source {
  index: number;
  id: string | null;
  domain: string;
  file_path: string;
  title: string;
  first_character_index: number;
  last_character_index: number;
  preview: string;
  credit: string | null;
}

// What one domain found for the question. The answered domain carries
// the sources the answer used (their [n] citations); the others, their
// own results.
export interface Retrieval {
  domain: string;
  score: number | null;
  used: boolean;
  sources: Source[];
}

export interface ChatResult {
  session_id: string;
  answer: string;
  not_found: boolean;
  domain: string | null;
  sources: Source[];
  retrievals: Retrieval[];
  trace: Record<string, unknown>;
}

export interface RecallSet {
  label: string;
  run: string;
  recall_at_k: Record<string, number>;
}

export interface Metrics {
  recall: RecallSet[];
  agent: {
    run: string;
    model: string;
    results: Record<string, Record<string, { contains_answer: number; seconds_per_answer: number }>>;
  } | null;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return (await response.json()) as T;
}

export const getConfig = () => getJson<Config>("/config");
export const getMetrics = () => getJson<Metrics>("/metrics");
export const getHealth = () => getJson<{ status: string; loaded: boolean }>("/health");
export const getSource = (id: string) =>
  getJson<Source & { text: string }>(`/sources/${encodeURIComponent(id)}`);

export async function resetChat(sessionId: string): Promise<void> {
  await fetch(`${API_URL}/chat/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export interface ChatRequest {
  message: string;
  session_id: string | null;
  agent: boolean;
  // The active filters ([] = all off: the API asks to turn one on).
  domains: string[];
  model: string;
  depth: number | null;
}

// POST /chat answers as Server-Sent Events: "start" with the session id,
// "token" pieces while the answer is generated, then "done" with the
// final answer and sources (or "error"). EventSource only does GET, so
// the stream is read here. Aborting `signal` (the Stop button) closes the
// connection, and the API stops generating.
export async function chat(
  request: ChatRequest,
  onToken: (piece: string) => void,
  signal?: AbortSignal,
  onStart?: (sessionId: string) => void,
): Promise<ChatResult> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`The API answered ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const message = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = /^event: (.*)$/m.exec(message)?.[1];
      const data = /^data: (.*)$/m.exec(message)?.[1];
      if (!event || data === undefined) continue;
      const payload = JSON.parse(data);
      if (event === "start") onStart?.(payload.session_id as string);
      else if (event === "token") onToken(payload as string);
      else if (event === "done") return payload as ChatResult;
      else if (event === "error") throw new Error(payload.detail);
    }
  }
  throw new Error("The answer stream ended unexpectedly");
}
