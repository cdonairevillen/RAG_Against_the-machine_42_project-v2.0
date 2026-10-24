// Example questions, per domain. Out of the page for now: where to show
// them is still to be decided.
export const EXAMPLES: Record<string, string[]> = {
  vllm: ["How do I load a LoRA adapter at runtime in vLLM?"],
  xquad: ["Who led the Carolina Panthers in sacks in 2015?", "¿En qué año murió Nikola Tesla?"],
  cv: [
    "What did Chrystian build for De La Luna Luna Studio?",
    "¿Qué proyectos hizo en 42 Madrid?",
    "Which instrument does he play?",
  ],
  // The project talking about itself (Phase 7a).
  about: [
    "What is RAG against the Machine?",
    "How does the router choose a domain?",
    "¿Qué modelos usa el proyecto?",
    "¿Cómo se mide el recall?",
  ],
};
