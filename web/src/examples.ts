// Example questions, per domain (the "Example questions" switch shows
// those of the active filters). Each one checked against the real index:
// it reaches its domain and passes its gate (FASE_7.md 7a.8).
export const EXAMPLES: Record<string, string[]> = {
  vllm: ["How do I load a LoRA adapter at runtime in vLLM?"],
  xquad: ["Who led the Carolina Panthers in sacks in 2015?", "¿En qué año murió Nikola Tesla?"],
  cv: [
    "What did Chrystian build for De La Luna Luna Studio?",
    "¿Qué proyectos hizo en 42 Madrid?",
    "Which instrument does Chrystian play?",
  ],
  // The project talking about itself (Phase 7a).
  about: [
    "What is RAG against the Machine?",
    "How does the router choose a domain?",
    "¿Qué modelo de lenguaje usa el proyecto?",
    "¿Cómo se mide el recall?",
  ],
};
