# CHANGELOG — Fase 7: Opcionales y mejoras

Fase abierta el 2026-10-24, tras el commit `3378494` (Fase 6). El plan está en `ROADMAP.md` (Fase 7). Aquí se irá apuntando qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`.

## Estado

| Bloque | Estado |
|---|---|
| 7a — Dominio "about" (README, `docs/`, código) | En curso: README, fuente y benchmark hechos; faltan las fuentes múltiples, el umbral, el router y la web |
| 7b — Calidad de las respuestas (Markdown, plan B del agente, formato, juez del CV) | Agente desactivado por defecto en la web; el resto, planificado (P11 resuelto: Groq) |
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

## 7a.2 — Fuente "about" indexada y primer benchmark

**Selección de ficheros sin copias:** la fuente lee el repo en vivo (`root = "."`). Tras editar los documentos hay que volver a lanzar `make index SOURCE=about`.
- **`exclude_paths`, campo nuevo de `SourceConfig`:** rutas relativas que se saltan enteras. Hacía falta porque `exclude_dirs` compara nombres, y excluir `deploy` quitaba también `src/deploy/`. Es aditivo: las demás fuentes se indexan igual. Test `test_exclude_paths_skips_one_folder_not_its_namesakes`.
- **Entran 53 ficheros:** el README, `deploy/README.md`, la ficha del Space, 12 documentos de `docs/` y 38 de código.
- **Fuera:** `data/`, `bench/`, `web/`, `tests/`, `llm_sdk/`, `deploy/stage`, `deploy/bundle`, `PLANING.md`, `RESPUESTA.md`, `Elements_frontend.md` y `CLAUDE.md`.
- **Indexado** (`make index SOURCE=about`): 537 padres y 1.369 hijos (635 de documentación y 734 de código), en 14 s. Los demás dominios no se tocan.

**Benchmark** (`bench/datasets/about/questions.json`, borrador para tu revisión): 18 preguntas en EN y ES con su evidencia exacta: 15 en el README, 1 en el ROADMAP y 2 en el código. Se construye con `python -m src build_about_bench` (mismo método que el CV) y se mide con `make bench SUITE=about`.

| Ejecución | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 |
|---|---|---|
| `70-about-base` | 0.50 / 0.50 / 0.78 / 0.78 | 0.11 / 0.22 / 0.22 / 0.33 |

**Por qué el español sale tan bajo:** las preguntas en español recuperan los documentos en español (changelogs, `decisions.md`, `ROADMAP.md`), que dicen lo mismo que el README. Como cada pregunta solo admite una fuente, se cuentan como fallos respuestas válidas (licencia → DEC-14; despliegue → la Fase 6 del ROADMAP; botón Stop → `FASE_6.md` §6g). Las preguntas en inglés recuperan el README.

## 7b.0 — Agente desactivado por defecto en la web (decisión tuya, 2026-10-24)

**Motivo:** con los modelos pequeños, la memoria del agente mezcla temas anteriores o da respuestas demasiado básicas (medido en `FASE_6.md`: el 0.6B no reescribe los seguimientos y el plan B responde a dos preguntas juntas).
- **API:** `agent` vale `False` por defecto en `/chat` y `/config` devuelve `agent_default: false` (`AGENT_DEFAULT` en `src/api/app.py`).
- **Web:** el interruptor arranca en "Direct RAG". Al encenderlo aparece, flotando bajo el interruptor (sin mover la página), un aviso: *"Work in progress: the agent's conversation memory is still being improved, and it may mix in earlier topics."*.
- **CLI:** sin cambios (`answer` y `chat` siguen con el agente por defecto, D7).
- **Cambia D7 solo en la web** hasta que la mejora del plan B (7b) se mida y funcione.

## 7a.3 — "about" fuera de la web hasta calibrarlo

Con la API reiniciada después de indexar "about", ese dominio entró en el router **sin calibrar**. Ejemplo tuyo con el 1.7B: a "Chrystian Donaire Villén Que me estas contando" respondió con tu fecha de nacimiento y añadió *"la respuesta se presenta con el agente por defecto (D7)"*. Los changelogs contienen transcripciones de las pruebas (por ejemplo, `FASE_6.md` §5 cita respuestas del CV) y jerga interna, y el router los eligió.
- **`RAG_API_DOMAINS`:** lista de los dominios que sirve la web (vacía: todos los indexados). `make api` usa `API_DOMAINS ?= vllm,xquad,cv` hasta terminar los pasos 4–5 de la 7a. `RagTools.load` acepta la lista de dominios (opcional; sin ella, como antes).
- **Pendiente para el paso 4:** decidir si las transcripciones de pruebas de los changelogs se quedan en el índice de "about" o se excluyen, porque meten respuestas del CV dentro de "about".

## 7a.4 — Documentación en dos idiomas (decisión tuya, 2026-10-24)

Igual que con la biografía (ES + EN), los documentos existen en los dos idiomas, para que "about" responda bien en ambos y para que los recruiters lean el flujo de trabajo en inglés.
- **`docs/es/`:** los originales en español, movidos con `git mv` (conserva el historial). Siguen siendo **la versión de trabajo**. También `PLANING.md`, `RESPUESTA.md` y `Elements_frontend.md`, que no se traducen.
- **`docs/`:** la traducción al inglés de `ROADMAP.md`, `BENCHMARK_REPORT.md`, `decisions.md` y los changelogs. Se actualiza **al cerrar cada fase**. Donde el original habla de "tú", la traducción dice "the author".
- **`docs/es/README.md`:** traducción al español del README, con los enlaces ajustados a su carpeta.
- **`CLAUDE.md`** carga las normas y el roadmap desde `docs/es/`.
- **Las rutas** que citan el código y la config (`docs/changelog/FASE_4.md`…) siguen siendo válidas: ahora apuntan a la versión en inglés.

## 7a.5 — Benchmark de "about" con la documentación bilingüe

**Corrección de algo que te dije mal:** afirmé que el evaluador de 42 da por buena *cualquier* fuente del ground truth. No es así: calcula la **fracción** de fuentes encontradas (`found / len(gt_sources)` en `src/evaluation/evaluator.py`). Con dos fuentes por pregunta (la evidencia en inglés y la española), encontrar una sola puntúa 0.5. Lo comprobé al ver bajar el recall (`71-about-bilingual`).

**Lo aplicado:** el ground truth en el idioma de la pregunta, como en el CV. `questions.json` lleva `file`/`evidence` (inglés) y `file_es`/`evidence_es` (español, en `docs/es/`); el código, sin traducción, vale para los dos. Fuente "about" reindexada con los dos idiomas: 67 ficheros, 721 padres y 2.039 hijos.

| Ejecución | Ground truth | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 |
|---|---|---|---|
| `70-about-base` | solo el README en inglés (docs solo en español) | 0.50 / 0.50 / 0.78 / 0.78 | 0.11 / 0.22 / 0.22 / 0.33 |
| `71-about-bilingual` | las dos versiones a la vez (mal planteado, ver arriba) | 0.14 / 0.31 / 0.31 / 0.42 | 0.25 / 0.31 / 0.39 / 0.47 |
| `72-about-gt-per-language` | la del idioma de la pregunta | 0.28 / 0.50 / 0.50 / 0.72 | 0.44 / 0.50 / 0.67 / 0.72 |

**Por qué el inglés baja en `72`:** ahora las preguntas en inglés también encuentran la traducción inglesa de los changelogs y del ROADMAP, que cuentan lo mismo que el README, y el README queda detrás. Una métrica de "una única fuente válida" no refleja bien un corpus donde varios documentos dicen lo mismo.

**Métrica complementaria (la misma que en el CV, Fase 4b):** ¿contiene alguna de las k primeras fuentes la respuesta? No toca el evaluador de 42.

| | @1 | @3 | @5 |
|---|---|---|---|
| EN | 0.67 | 0.78 | **0.89** |
| ES | 0.78 | 0.83 | **0.89** |

**Lectura:** la recuperación de "about" funciona en los dos idiomas: en el 89 % de las preguntas la respuesta está en las 5 primeras fuentes. Lo que falta de la 7a es calibrar el umbral, pasar `route-bench` (el riesgo de robar preguntas a vLLM y al CV) y la web.

## Decisiones (tuyas, 2026-10-24)

- **README en inglés.**
- **P11, juez del CV: Groq**, hasta agotar los tokens gratuitos. Es una excepción expresa a la regla de la Fase 4b ("el juez externo no se usa con datos personales salvo que lo decidas"): las fuentes y respuestas del CV se mandan a Groq, con los datos de contacto privados enmascarados. Si hace falta, se repite con Qwen3-4B como juez local.
