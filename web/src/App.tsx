import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  chat, getConfig, getHealth, getMetrics, getSource, resetChat,
  type Config, type Metrics, type RecallSet, type Retrieval, type Source,
} from "./api";
import { EXAMPLES } from "./examples";

const GITHUB = "https://github.com/cdonairevillen/RAG_Against_the-machine_42_project-v2.0";

const BLURB =
  "A multi-domain RAG over the vLLM docs and code, general knowledge from Wikipedia (English and Spanish) and the author's profile, and the project explaining itself (\"about\", always on). The filters choose where it searches.";

// Short notes for the model menu (docs/BENCHMARK_REPORT.md §5 and §8).
const MODEL_NOTES: Record<string, string> = {
  default: "Base model · fastest",
  "llm-qwen3-1.7b": "Better answers · a bit slower",
  "llm-qwen3-4b": "Best agent · slowest",
};

function depthLabel(depth: number): string {
  return `${depth} sources`;
}

function depthNote(depth: number): string {
  if (depth <= 3) return "Shorter context · faster";
  if (depth >= 10) return "More context · slower";
  return "Standard · the k that 42 evaluates";
}

interface Turn {
  question: string;
  answer: string;
  retrievals: Retrieval[];
  trace: string;
  pending: boolean;
  error?: string;
}

function traceLine(trace: Record<string, unknown>): string {
  const line = traceBody(trace);
  if (trace.cut) return `${line} · cut at the length limit`;
  return line;
}

function traceBody(trace: Record<string, unknown>): string {
  if (trace.mode === "no-filter") return "";
  const model = trace.model ? `${trace.model} · ` : "";
  if (trace.mode === "agent") {
    const queries = (trace.queries as string[]) ?? [];
    const extra = [
      trace.fallback ? "fallback" : "",
      ...(((trace.retries as string[]) ?? []).map((r) => `retry: ${r}`)),
    ].filter(Boolean);
    return `${model}agent · searched: ${queries.map((q) => `“${q}”`).join(", ")}${extra.length ? ` · ${extra.join(", ")}` : ""}`;
  }
  const route = (trace.route as [string, number | null][]) ?? [];
  return `${model}direct · route: ${route.map(([d, s]) => (s === null ? d : `${d} (${s.toFixed(2)})`)).join(", ")}`;
}

function SourceCard({ source, cited }: { source: Source; cited: boolean }) {
  const [full, setFull] = useState<string | null>(null);
  return (
    <div className="source-card">
      <div className="source-path">
        {cited ? `[${source.index}] ` : ""}
        {source.title}
      </div>
      <div className="source-meta">
        chars {source.first_character_index}–{source.last_character_index}
        {source.credit ? ` · ${source.credit}` : ""}
      </div>
      <div className="source-text">{full ?? `${source.preview}…`}</div>
      {source.id && full === null && (
        <button
          type="button"
          className="link-button"
          onClick={() => getSource(source.id!).then((s) => setFull(s.text)).catch(() => setFull(source.preview))}
        >
          show full source
        </button>
      )}
    </div>
  );
}

// Corner accents for a card: a 3x3 grid of dots per corner, fading
// towards the inside. Drawn for the top-left corner and rotated 90° for
// each of the others. The parent needs `position: relative`.
const DOT_OPACITY = [1, 1, 1, 1, 0.6, 0.3, 1, 0.3, 0];

function CornerDots() {
  return (
    <span className="corner-dots" aria-hidden>
      {[0, 90, 180, 270].map((angle) => (
        <span key={angle} className={`corner corner-${angle}`}>
          {DOT_OPACITY.map((opacity, i) => (
            <span key={i} className="corner-dot" style={{ opacity }} />
          ))}
        </span>
      ))}
    </span>
  );
}

// One domain's results, one source at a time with arrows.
function RetrievalPanel({ retrieval }: { retrieval: Retrieval }) {
  const [at, setAt] = useState(0);
  const count = retrieval.sources.length;
  const source = retrieval.sources[at];
  return (
    <div className={`retrieval ${retrieval.used ? "used" : ""}`}>
      <CornerDots />
      <div className="retrieval-head">
        <span className="retrieval-domain">{retrieval.domain}</span>
        {retrieval.score !== null && <span className="retrieval-score">score {retrieval.score.toFixed(2)}</span>}
        <span className="retrieval-badge">{retrieval.used ? "used in the answer" : "not used"}</span>
        {count > 1 && (
          <span className="carousel">
            <button type="button" aria-label="Previous source" onClick={() => setAt((at - 1 + count) % count)}>‹</button>
            <span>{at + 1}/{count}</span>
            <button type="button" aria-label="Next source" onClick={() => setAt((at + 1) % count)}>›</button>
          </span>
        )}
      </div>
      {source ? (
        <SourceCard key={`${source.file_path}:${source.first_character_index}`} source={source} cited={retrieval.used} />
      ) : (
        <div className="source-empty">No relevant results in this domain.</div>
      )}
    </div>
  );
}

// The domain the answer came from; the other searched domains stay
// folded in one line (they show how the router chose).
function Retrievals({ retrievals }: { retrievals: Retrieval[] }) {
  const [showOthers, setShowOthers] = useState(false);
  const used = retrievals.filter((r) => r.used);
  const others = retrievals.filter((r) => !r.used);
  const summary = others.map((r) => (r.score === null ? r.domain : `${r.domain} (${r.score.toFixed(2)})`)).join(", ");
  return (
    <div className="retrievals">
      <div className="section-label">Retrieval</div>
      {used.map((r) => <RetrievalPanel key={r.domain} retrieval={r} />)}
      {others.length > 0 && (
        <button type="button" className="link-button others-toggle" onClick={() => setShowOthers(!showOthers)}>
          {showOthers ? "▾" : "▸"} also searched: {summary}
        </button>
      )}
      {showOthers && others.map((r) => <RetrievalPanel key={r.domain} retrieval={r} />)}
    </div>
  );
}

// A dropdown that opens upwards from the composer, like the model
// pickers of AI chat apps.
function Picker<T>({ value, options, render, note, onChange, title }: {
  value: T;
  options: T[];
  render: (option: T) => ReactNode;
  note: (option: T) => string;
  onChange: (option: T) => void;
  title: string;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);
  return (
    <div className="picker" ref={box}>
      <button type="button" className="picker-button" title={title} aria-expanded={open} onClick={() => setOpen(!open)}>
        {render(value)} <span className="picker-caret">▾</span>
      </button>
      {open && (
        <div className="picker-menu" role="listbox">
          <div className="picker-title">{title}</div>
          {options.map((option, i) => (
            <button
              type="button"
              role="option"
              aria-selected={option === value}
              key={i}
              className={`picker-option ${option === value ? "selected" : ""}`}
              onClick={() => {
                onChange(option);
                setOpen(false);
              }}
            >
              <span className="picker-option-label">{render(option)}</span>
              <span className="picker-option-note">{note(option)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// One card per domain ("vLLM docs" + "vLLM code" -> vLLM), with arrows
// to move between its sets, like the retrievals of an answer.
function RecallCard({ name, sets }: { name: string; sets: RecallSet[] }) {
  const [at, setAt] = useState(0);
  const set = sets[at];
  const part = set.label.slice(name.length).trim();
  return (
    <div className="metric-card">
      <div className="metric-head">
        <span className="metric-label">
          {name}
          {part && <span className="metric-part"> · {part}</span>}
        </span>
        {sets.length > 1 && (
          <span className="carousel">
            <button type="button" aria-label="Previous set" onClick={() => setAt((at - 1 + sets.length) % sets.length)}>‹</button>
            <span>{at + 1}/{sets.length}</span>
            <button type="button" aria-label="Next set" onClick={() => setAt((at + 1) % sets.length)}>›</button>
          </span>
        )}
      </div>
      {Object.entries(set.recall_at_k).map(([k, score]) => (
        <div className="recall-row" key={k}>
          <span className="recall-label">Recall@{k}</span>
          <div className="recall-bar-bg">
            <div className="recall-bar-fill" style={{ width: `${score * 100}%` }} />
          </div>
          <span className="recall-value">{Math.round(score * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

function RecallCards({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) return <div className="status-line">Loading metrics…</div>;
  const groups = new Map<string, RecallSet[]>();
  for (const set of metrics.recall) {
    const name = set.label.split(" ")[0];
    groups.set(name, [...(groups.get(name) ?? []), set]);
  }
  return (
    <>
      {[...groups].map(([name, sets]) => (
        <RecallCard key={name} name={name} sets={sets} />
      ))}
    </>
  );
}

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [useAgent, setUseAgent] = useState(false);
  const [domains, setDomains] = useState<string[]>([]);
  const [model, setModel] = useState("default");
  const [depth, setDepth] = useState(5);
  const [showExamples, setShowExamples] = useState(false);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const sessionId = useRef<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    getMetrics().then(setMetrics).catch(() => setMetrics({ recall: [], agent: null }));
    const poll = () =>
      getHealth()
        .then((h) => {
          setLoaded(h.loaded);
          if (h.loaded) {
            getConfig().then((c) => {
              setConfig(c);
              setUseAgent(c.agent_default);
              setDepth(c.depth_default ?? 5);
              setDomains(c.domains.map((d) => d.name));
            });
          } else setTimeout(poll, 3000);
        })
        .catch(() => {
          setApiError("The API is not reachable (it may be starting up).");
          setTimeout(poll, 5000);
        });
    poll();
  }, []);

  // Braces matter: an effect may only return a cleanup function, and
  // recent browsers make scrollIntoView return a Promise (React then
  // crashed and unmounted the page).
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  // The input grows with its text, up to a limit (then it scrolls).
  useEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [question]);

  const newConversation = () => {
    if (sessionId.current) resetChat(sessionId.current).catch(() => undefined);
    sessionId.current = null;
    setTurns([]);
  };

  const ask = async (text: string) => {
    const message = text.trim();
    if (!message || busy || !loaded) return;
    setQuestion("");
    setBusy(true);
    setTurns((t) => [...t, { question: message, answer: "", retrievals: [], trace: "", pending: true }]);
    const update = (patch: Partial<Turn>) =>
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, ...patch } : turn)));
    let streamed = "";
    controller.current = new AbortController();
    try {
      const result = await chat(
        { message, session_id: sessionId.current, agent: useAgent, domains, model, depth },
        (piece) => {
          streamed += piece;
          update({ answer: streamed });
        },
        controller.current.signal,
        (id) => {
          sessionId.current = id;
        },
      );
      sessionId.current = result.session_id;
      update({
        answer: result.answer,
        // An older API has no retrievals: show none instead of failing.
        retrievals: (result.retrievals ?? []).filter((r) => r.sources.length > 0 || r.used),
        trace: traceLine(result.trace),
        pending: false,
      });
      // The first answer with a model loads it: refresh "loaded".
      getConfig().then(setConfig).catch(() => undefined);
    } catch (error) {
      if (controller.current?.signal.aborted) {
        update({ pending: false, answer: streamed ? `${streamed} …` : "", trace: "stopped" });
      } else {
        update({ pending: false, error: String(error) });
      }
    } finally {
      controller.current = null;
      setBusy(false);
    }
  };

  const stop = () => controller.current?.abort();

  const pinned = (name: string) => config?.domains.some((d) => d.name === name && d.pinned) ?? false;
  const toggleDomain = (name: string) => {
    if (pinned(name)) return;
    setDomains((d) => (d.includes(name) ? d.filter((x) => x !== name) : [...d, name]));
  };

  const models = config?.models ?? [{ id: "default", label: config?.model ?? "Qwen3-0.6B", model: "", loaded: true }];
  const modelInfo = (id: string) => models.find((m) => m.id === id);

  return (
    <div className="page">
      <header>
        <div className="rag-title">⚡ RAG against the Machine</div>
        <div className="rag-subtitle">Multi-domain RAG · {modelInfo(model)?.label ?? "Qwen3-0.6B"} · {useAgent ? "agent" : "direct"}</div>
      </header>

      <div className="columns">
        <main className="col-main">
          <div className="controls">
            <div className="chips">
              {config?.domains.map((d) => (
                <button
                  key={d.name}
                  className={`chip ${domains.includes(d.name) ? "on" : ""} ${d.pinned ? "pinned" : ""}`}
                  title={d.pinned ? `${d.description} (always on)` : d.description}
                  aria-pressed={domains.includes(d.name)}
                  aria-disabled={d.pinned}
                  onClick={() => toggleDomain(d.name)}
                >
                  {d.name}
                </button>
              ))}
            </div>
            <div className="agent-toggle">
              <label className="switch" title="The agent remembers the conversation and rewrites follow-up questions">
                <span className="switch-label">{useAgent ? "With agent (memory)" : "Direct RAG"}</span>
                <input type="checkbox" checked={useAgent} onChange={(e) => setUseAgent(e.target.checked)} />
                <span className="switch-track"><span className="switch-thumb" /></span>
              </label>
              {/* Floats under the switch, so turning it on moves nothing. */}
              {useAgent && (
                <div className="wip-note">
                  Work in progress: the agent's conversation memory is still being improved, and it may mix in earlier
                  topics.
                </div>
              )}
            </div>
          </div>

          {apiError && !loaded && <div className="notice">{apiError}</div>}
          {!apiError && !loaded && <div className="notice">Loading the models… the first start takes a minute.</div>}

          <div className="conversation">
            {turns.length === 0 && <div className="empty-state">{BLURB}</div>}
            {turns.map((turn, i) => (
              <div className="turn" key={i}>
                <div className="question">› {turn.question}</div>
                <div className="answer-box">
                  {turn.error ? `Error: ${turn.error}` : turn.answer || (turn.pending ? "Searching…" : "")}
                </div>
                {turn.trace && <div className="trace">{turn.trace}</div>}
                {turn.retrievals.length > 0 && <Retrievals retrievals={turn.retrievals} />}
              </div>
            ))}
            <div ref={bottom} />
          </div>

          <div className="examples-bar">
            {/* Floats above the switch: opening it moves nothing. */}
            {showExamples && (
              <div className="examples">
                {domains.flatMap((d) => EXAMPLES[d] ?? []).map((example) => (
                  <button key={example} type="button" className="example" disabled={!loaded || busy} onClick={() => ask(example)}>
                    {example}
                  </button>
                ))}
                {domains.length === 0 && <span className="examples-empty">Turn on a filter to see its examples.</span>}
              </div>
            )}
            <label className="switch small" title="Show example questions for the active filters">
              <span className="switch-label">Example questions</span>
              <input type="checkbox" checked={showExamples} onChange={(e) => setShowExamples(e.target.checked)} />
              <span className="switch-track"><span className="switch-thumb" /></span>
            </label>
          </div>

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              ask(question);
            }}
          >
            <textarea
              ref={input}
              rows={1}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                // Enter sends, Shift+Enter adds a line.
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask(question);
                }
              }}
              placeholder="Ask anything about vLLM, Wikipedia, the author or this project…"
              maxLength={1000}
              disabled={!loaded}
            />
            <div className="composer-bar">
              <Picker
                title="Model"
                value={model}
                options={models.map((m) => m.id)}
                render={(id) => modelInfo(id)?.label ?? id}
                note={(id) => `${MODEL_NOTES[id] ?? ""}${modelInfo(id)?.loaded ? "" : " · loads on first use"}`}
                onChange={setModel}
              />
              <Picker
                title="Depth"
                value={depth}
                options={config?.depths ?? [3, 5, 10]}
                render={depthLabel}
                note={depthNote}
                onChange={setDepth}
              />
              <span className="composer-spacer" />
              <button type="button" className="composer-new" onClick={newConversation} disabled={busy || !turns.length}>
                New chat
              </button>
              {busy ? (
                <button type="button" className="composer-send stop" aria-label="Stop" title="Stop generating" onClick={stop}>
                  ■
                </button>
              ) : (
                <button type="submit" className="composer-send" aria-label="Send" disabled={!loaded || !question.trim()}>
                  ↑
                </button>
              )}
            </div>
          </form>
        </main>

        <aside className="col-right">
          <div className="section-label">System</div>
          <div className="metric-card">
            <div className="status-line">
              <span className="status-dot" style={{ background: loaded ? "#2ecc71" : "#333" }} />
              {loaded ? "Models loaded" : "Loading…"}
            </div>
            {config?.domains.map((d) => (
              <div className="status-line" key={d.name}>
                <span className="status-dot" />
                {d.name}: {d.chunks.toLocaleString()} chunks
              </div>
            ))}
          </div>
          <div className="section-label">Retrieval metrics</div>
          <RecallCards metrics={metrics} />
          <footer>
            <a href={GITHUB}>Source code</a> · Built by Chrystian Donaire Villén ·{" "}
            <a href="mailto:cdonairevillen@gmail.com">cdonairevillen@gmail.com</a> · General knowledge from XQuAD
            (Google), CC-BY-SA 4.0, based on Wikipedia
          </footer>
        </aside>
      </div>
    </div>
  );
}
