# CHANGELOG — Fase 7: Opcionales y mejoras

Fase abierta el 2026-10-24, tras el commit `3378494` (Fase 6). El plan está en `ROADMAP.md` (Fase 7). Aquí se irá apuntando qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`.

## Estado

| Bloque | Estado |
|---|---|
| 7a — Dominio "about" (README, `docs/`, código) | Planificado; empieza por el README |
| 7b — Calidad de las respuestas (Markdown, plan B del agente, formato, juez del CV) | Planificado; el juez depende de P11 |
| 7c — Visual (tarjetas que giran, scroll) | Planificado |
| 7d — Opcionales (Gulliver, MLQA, `repetition_penalty`) | Aparcados |

## 7a.1 — README reescrito (borrador para tu revisión)

`README.md` estaba como en la entrega a 42: solo vLLM, BM25, el reranker MiniLM y las cifras de la v1 (que además tenían la etiqueta de los datasets privados, aunque eran de los públicos). Se reescribe en inglés:
- **Qué es:** tres dominios con su tamaño, Qwen3-0.6B como base y los perfiles opcionales.
- **Resultados:**
  - Recall oficial de 42, de la v1 a la v2.0 (docs R@5 +0.07, code R@5 +0.17).
  - XQuAD y CV (recall y generación).
  - Router.
  - Agente frente a directo.
- **Cómo funciona:** ingesta, recuperación (con el detalle de que el reranker solo actúa siempre en la rama de code), generación, agente y MCP.
- **El resto:** la web y su API, cómo ejecutarlo y medirlo, el despliegue (con las latencias simuladas), la estructura de carpetas, los enlaces a `docs/`, los créditos (vLLM Apache-2.0, XQuAD CC-BY-SA 4.0, modelos y herramientas) y el uso de IA.

Todas las cifras salen de `BENCHMARK_REPORT.md`, `CHECKPOINT_42.md` y los changelogs; ninguna es nueva. Sin datos personales, salvo tu nombre y el correo público.

**Tras tu revisión:**
- **Primera línea:** *"Started as part of the 42 curriculum by cdonaire…"*, aprobada.
- **Uso de IA:** *"updated together with Claude (Anthropic), and reviewed and designed by hand by Chrystian"*.
- **Licencia MIT** (`LICENSE`, DEC-14 resuelto), con una sección en el README que deja fuera lo de terceros (XQuAD CC-BY-SA, datasets de 42, `llm_sdk`). También en la ficha del Space y en `make space-stage`.
- **Demo:** *"Live demo: coming soon"*, al principio y en *Deployment*, con un `TODO` para el enlace del Space.
- **Índice de secciones** al principio.

## Decisiones (tuyas, 2026-10-24)

- **README en inglés.**
- **P11, juez del CV: Groq**, hasta agotar los tokens gratuitos. Es una excepción expresa a la regla de la Fase 4b ("el juez externo no se usa con datos personales salvo que lo decidas"): las fuentes y respuestas del CV se mandan a Groq, con los datos de contacto privados enmascarados. Si hace falta, se repite con Qwen3-4B como juez local.
