# CHANGELOG — Fase 7: Opcionales y mejoras

Fase abierta el 2026-10-24, tras el commit `3378494` (Fase 6). El plan está en `ROADMAP.md` (Fase 7). Aquí se irá apuntando qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`.

## Estado

| Bloque | Estado |
|---|---|
| 7a — Dominio "about" (README, `docs/`, código) | ✅ Hecho: README, fuente, benchmark bilingüe, separación del CV (§7a.6), umbral y regla léxica (§7a.7), y web y bundle (§7a.8). Quedan 6 preguntas que se van a vLLM, sin palabras que las distingan |
| 7b — Calidad de las respuestas (Markdown, plan B del agente, formato, juez del CV) | Agente desactivado por defecto en la web, límite de tokens por modelo (§7b.1) y detector de bucles (§7b.2); el resto, planificado (P11 resuelto: Groq) |
| Despliegue | Plataforma cambiada a Oracle Cloud Always Free (DEC-19); guía en `deploy/README.md` |
| 7c — Visual (tarjetas que giran, scroll) | Planificado |
| 7d — Opcionales (Gulliver, MLQA) | Aparcados; `repetition_penalty` descartado (§7b.1) |

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

Con la API reiniciada después de indexar "about", ese dominio entró en el router **sin calibrar**. Ejemplo tuyo con el 1.7B: <!-- about:skip -->a "Chrystian Donaire Villén Que me estas contando" respondió con tu fecha de nacimiento y<!-- /about:skip --> añadió *"la respuesta se presenta con el agente por defecto (D7)"*. Los changelogs contienen transcripciones de las pruebas (por ejemplo, `FASE_6.md` §5 cita respuestas del CV) y jerga interna, y el router los eligió.
- **`RAG_API_DOMAINS`:** lista de los dominios que sirve la web (vacía: todos los indexados). `make api` usa `API_DOMAINS ?= vllm,xquad,cv` hasta terminar los pasos 4–5 de la 7a. `RagTools.load` acepta la lista de dominios (opcional; sin ella, como antes).
- **Pendiente para el paso 4:** decidir si las transcripciones de pruebas de los changelogs se quedan en el índice de "about" o se excluyen, porque meten respuestas del CV dentro de "about".

## 7a.4 — Documentación en dos idiomas (decisión tuya, 2026-10-24)

Los documentos existen en los dos idiomas, para que "about" responda bien en ambos y para que los recruiters lean el flujo de trabajo en inglés.
- **`docs/es/`:** los originales en español, movidos con `git mv` (con `git mv`; Git solo lo registra como renombrado en `PLANING.md`, `RESPUESTA.md` y `Elements_frontend.md`. En los demás, la traducción reutiliza la ruta antigua, así que su historial en español se consulta con `git log docs/<fichero>` y no con `--follow` sobre `docs/es/`). Siguen siendo **la versión de trabajo**. También `PLANING.md`, `RESPUESTA.md` y `Elements_frontend.md`, que no se traducen.
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

## 7a.6 — "about" deja de competir con el CV

**Problema (`73-router-about`, primer route-bench con "about"):** "about" se quedaba 5 de 60 preguntas del CV, y 8 de 36 preguntas sobre el proyecto se iban a vLLM. La documentación hablaba del contenido del modo CV: transcripciones de las pruebas, "autobiografía con gustos, aficiones y viajes", "¿Dónde nació…?". Con preguntas en las que el CV puntuaba bajo, ganaba un documento que hablaba del tema sin tener la respuesta: el router compara puntuaciones en bruto (−9.2, −1.2 y −4.2 en las tres del CV en inglés).

**Lo aplicado:**
1. **`skip_marked`** (nuevo en `SourceConfig`, activo en "about"): en los `.md`, las regiones entre `<!-- about:skip -->` y `<!-- /about:skip -->` se sustituyen por espacios antes de trocear. La longitud y los saltos de línea no cambian, así que los offsets del resto siguen siendo exactos. Una sección que queda en blanco no genera chunks, y un marcador sin cerrar es un error. Los marcadores son comentarios HTML, así que en GitHub no se ven y el documento se lee entero.
2. **Documentación simplificada** (decisión tuya: redirigir, no repetir):
   - **`ROADMAP.md` 4b:** una línea con el enlace a `FASE_4.md` §4b y `BENCHMARK_REPORT.md` §7.
   - **Notas de la biografía:** fuera del ROADMAP.
   - **Idea de "textos propios":** pasa a 7d.
3. **Marcado con `about:skip`** (en los dos idiomas):
   - `FASE_4.md` §4b y `BENCHMARK_REPORT.md` §7, enteros.
   - Las filas de pruebas del CV en `FASE_6.md` (§5 y §6).
   - Los ejemplos con preguntas personales de `FASE_5.md` y `FASE_7.md`.
   - **Se queda:** el README dice que existe el dominio `cv` y quién es el autor. "About" debe poder contestar eso.
4. **Comprobado:** todos los marcadores están emparejados, y tras el blanqueo no queda vocabulario personal en "about", salvo el nombre del autor en el README y en el crédito de uso de IA.

"about" reindexado: 718 padres y 2.008 hijos (1.258 de documentación y 750 de código).

**Route-bench** (`74-about-cv-skip` frente a `73-router-about`):

| Conjunto | Enrutado 73 → 74 | Se las queda "about" | R@1/@3/@5/@10 en 74 |
|---|---|---|---|
| 42 docs / code | 0.99 → 0.99 | 1 / 1 | 0.76 / 0.91 / 0.92 / 0.94 · 0.51 / 0.72 / 0.80 / 0.88 (igual) |
| XQuAD EN / ES | 0.981 / 0.975 → igual | 2 / 5 | igual |
| **CV EN** | **0.90 → 0.967** | 3 → 1 | R@5 0.87 → **0.90**, R@10 0.90 → **0.93** |
| **CV ES** | **0.933 → 0.967** | 2 → 1 | R@3 0.77 → **0.80**, R@5 0.90 → **0.93**, R@10 0.93 → **0.97** |
| About EN | 0.667 → 0.722 | — (se van a vLLM 5 → 4) | 0.17 / 0.33 / 0.33 / 0.56 |
| About ES | 0.778 → 0.833 | — (se van a vLLM 3 → 2) | 0.28 / 0.33 / 0.44 / 0.50 |

**Lectura:**
- Sin tocar el router, el CV recupera 3 de sus 5 preguntas y ningún conjunto empeora. El benchmark de 42 no cambia.
- El recall de "about" en esta tabla es el del evaluador de 42 con una sola fuente válida (ver §7a.5), así que sale bajo aunque la respuesta esté.
- **Queda pendiente:** las preguntas del proyecto que se van a vLLM (4 + 2), el umbral propio de "about" y la web.

## 7a.7 — Umbral propio de "about" y regla léxica del proyecto

**Umbral** (`gate_scores`, `75-about-cv-skip`, con el índice de §7a.6). Porcentaje que pasa el filtro de "about":

| Umbral | About EN / ES | Fuera de dominio lejano / cercano (EN) | CV sin respuesta EN / ES |
|---|---|---|---|
| 0.0 (global, el de antes) | 0.67 / 0.67 | 0 / 0 | 0.10 / 0.10 |
| **−1.0** ✅ | **0.83 / 0.78** | 0 / 0.10 | 0.20 / 0.30 |
| −1.5 | 0.83 / 0.89 | 0.10 / 0.10 | 0.20 / 0.30 |
| −2.0 | 0.83 / 0.89 | 0.20 / 0.10 | 0.20 / 0.50 |

- **Por qué −1.0:** recupera la mayoría de las preguntas válidas sin abrir la puerta a lo ajeno. Por debajo, el filtro empieza a aceptar preguntas lejanas.
- **Aviso:** son solo 18 preguntas por idioma, así que cada pregunta vale 0.06.
- **Las preguntas de 42 no importan aquí:** puntúan alto contra "about" porque la documentación habla de vLLM, pero el router las manda a vLLM (99 %), y el umbral de "about" solo actúa cuando gana "about".

**Por qué se iban a otro dominio** (pregunta a pregunta, con el índice de §7a.6):

| Pregunta | Gana | Puntuación de "about" | ¿Tiene pista? |
|---|---|---|---|
| What is / ¿Qué es RAG against the Machine? | **cv** (8.3 / 8.0): tu CV menciona el proyecto | 6.7 / 6.4 | el nombre |
| Which language model does the project use by default? | vllm (−2.06) | −2.25 | "the project" |
| Where is the project deployed? | vllm (−0.24) | −2.91 | "the project" |
| Modelo de embeddings y cómo se divide el código Python (EN y ES) | vllm | más baja | ninguna: vLLM también responde a eso |

**La regla (`route_hints`, nuevo en `SourceConfig`):** expresiones regulares que nombran un dominio.
- **Cuándo actúa:** si la pregunta coincide **y** ese dominio pasa su propio umbral, va primero. Si no pasa el umbral, el enrutado sigue como antes.
- **Por qué exige el umbral:** "the project" aparece también en una pregunta de XQuAD por idioma ("…undertake the project from design to construction"), y una pista sola la habría mandado a "about".
- **En "about":** `\b(this|the|your) project\b`, `\b(este|el|tu) proyecto\b` y `rag against the machine`. Los demás dominios no tienen pistas, así que no cambian.
- **Código:** `DomainRouter.hinted` (`src/rag/router.py`), y `Retriever.route_hints` compila los patrones.

**Route-bench** (`76-about-hints` frente a `74-about-cv-skip`):

| Conjunto | Enrutado | R@1/@3/@5/@10 |
|---|---|---|
| 42, XQuAD y CV | igual | igual |
| About EN | 0.722 → **0.778** (se van a vLLM: 4) | 0.17 / 0.33 / 0.33 / 0.56 → 0.22 / 0.39 / 0.39 / 0.61 |
| About ES | 0.833 → **0.889** (se van a vLLM: 2) | 0.28 / 0.33 / 0.44 / 0.50 → 0.33 / 0.39 / 0.50 / 0.56 |

- **Lo que arregla:** "¿Qué es RAG against the Machine?" en los dos idiomas.
- **Lo que no arregla:** "Which language model does the project use by default?" y "Where is the project deployed?" sí tienen la pista, pero "about" no pasa su umbral (−2.25 y −2.91 frente a −1.0). La regla no las fuerza, y es lo que se buscaba.
- **El resto** (embeddings, código Python) son preguntas que la documentación de vLLM también responde, sin ninguna palabra que las distinga.

**Pruebas:** `test_a_hinted_domain_wins_when_it_passes_its_threshold` y `test_a_hint_alone_does_not_route` en `tests/test_router.py`. 109 tests; flake8 y mypy limpios.

## 7a.8 — "about" en la web y en el bundle (paso 5)

**Dominio fijo (`pinned`, nuevo en `SourceConfig`, activo en "about"):**
- **API:** un dominio fijo se añade a cualquier filtro de dominios (`ChatService.domains_for`). Sin filtro (`domains: null`), se busca en todos, como antes. `/config` marca cada dominio con `pinned`.
- **Web:** el chip de "about" sale siempre encendido, con un punto delante (`● about`), sin cursor de mano y con "(always on)" en el título. Pulsarlo no hace nada.
- **`make api`:** `API_DOMAINS` pasa a estar vacío, así que la web sirve todos los dominios indexados. El servidor de despliegue ya servía todo lo del bundle.
- **Textos de la web:** la presentación y el campo de pregunta mencionan el proyecto ("…and the project explaining itself").

**Preguntas de ejemplo** (`web/src/examples.ts`). Todas se han comprobado con el índice real, buscando en todos los dominios:

| Ejemplo | Llega a | ¿Pasa el filtro? |
|---|---|---|
| vLLM, XQuAD (2), CV (2), "What is RAG against the Machine?", "How does the router choose a domain?", "¿Cómo se mide el recall?" | su dominio | sí |
| ~~"Which instrument does he play?"~~ | vllm (−3.77) | no. **Ya fallaba sin "about"**: suelta, la pregunta no dice quién es "he" |
| → "Which instrument does Chrystian play?" | cv (3.52) | sí |
| ~~"¿Qué modelos usa el proyecto?"~~ | vllm (−0.83) | no |
| → "¿Qué modelo de lenguaje usa el proyecto?" | about (1.09) | sí |

**Tarjetas de recall: "about" no sale.** Su recall con el evaluador de 42 es bajo (R@5 0.39 / 0.50), aunque la respuesta está entre las 5 primeras fuentes en el 89 % de las preguntas (§7a.5). La tarjeta daría una idea equivocada.

**Bundle regenerado** (`make bundle`): vllm, xquad, cv y about, 405 MB y 58 ficheros con SHA256.

**Pruebas:** `test_a_pinned_domain_joins_every_filter` y `test_config_marks_pinned_domains` en `tests/test_api.py`. 111 tests; flake8 y mypy limpios; la web compila. Captura con Chrome headless: el chip fijo y los cuatro dominios en el panel de sistema.

## 7b.1 — Límite de tokens por modelo y bucles de Phi-4-mini

**Límite por modelo en la web.** Antes era 1024 para todos (`FASE_6.md` §6g). Ahora cada modelo tiene el suyo, ajustado a lo medido: la respuesta válida más larga fue de 464 tokens con Phi-4-mini (10 fuentes) y de 321 con Qwen3-1.7B. Lo que pasaba de ahí era el bucle de Phi, que así se corta antes.
- **`RAG_API_MAX_TOKENS`** (nuevo, en `ModelPool`): un número para todos los modelos o un valor por modelo (`default=512,llm-phi4-mini=640`). Los ids desconocidos se ignoran, y los modelos que no aparecen conservan su `max_new_tokens`. Sustituye a `RAG_GENERATION_MAX_NEW_TOKENS` en `make api`.
- **`make api`:** 512 para el 0.6B y el 1.7B y 640 para Phi-4-mini (decisión tuya: se queda en 640).
- **Space:** `RAG_API_MAX_TOKENS=512` (allí solo se sirven los modelos pequeños).
- **Sin cambios:** `rag.toml` mantiene 150 para los benchmarks; la respuesta cortada se recorta en la última frase y el botón Stop sigue funcionando igual.

**Plantilla y final de generación de Phi-4-mini (comprobado a petición tuya).** Una causa típica de los bucles es no usar la plantilla oficial o no parar en el token de fin de turno. Aquí no es el caso:
- El prompt sale de `apply_chat_template`: `<|system|>…<|end|><|user|>…<|end|><|assistant|>`, el formato oficial, sin tokens de inicio duplicados.
- `generate()` para con los dos tokens que declara el modelo, `<|end|>` (200020) y `<|endoftext|>` (199999) (`Generator.stop_token_ids`).

El bucle es la degeneración de la generación *greedy* en respuestas largas: el modelo nunca llega a querer cerrar el turno.

**`repetition_penalty`: descartado (decisión tuya).** En sus bucles, Phi cambia palabras en cada vuelta, así que penalizar la repetición no los corta, y ya se vio que no funcionaba. Queda abierto cómo dar total libertad de longitud al LLM (ROADMAP 7b).

**Pruebas:** `test_max_tokens_per_model` y `test_the_pool_applies_the_caps` en `tests/test_api.py`.

## 7b.2 — Bucles de Phi-4-mini: detector integrado (aprobado por ti)

**Reproducción** (Phi-4-mini, 10 fuentes, límite de 1.500 tokens, 6 preguntas de "paso a paso" y listas): 3 de las 6 agotan el límite. Las otras tres terminan solas en 133–493 tokens.

| Pregunta | Cómo degenera |
|---|---|
| "Give me a step-by-step guide to serve a model with vLLM" | Desde el paso 26, la misma línea una y otra vez ("For more information… [1]") |
| "List all the command-line options of vllm serve" | Dos líneas alternas (`--help=serve=ApiServerCount` / `--help=serve=Headless`) desde la opción 29 |
| "Paso a paso de vLLM" | En prosa, sin saltos de línea: "En la séptima etapa…", "En la décima etapa…", "En la decimotercera…". **Cambia palabras en cada vuelta**, como habías visto: por eso penalizar la repetición no sirve |
| Las tres | Terminan con "step step step…" hasta el límite |

**Microsoft** recomienda en la ficha del modelo lo mismo que ya hacemos: *greedy* (`do_sample=False`) y un máximo de 500 tokens. La propia ficha avisa de que Phi-4 "puede generar respuestas repetitivas".

**Idea: detector de bucles por similitud de frases.** En lugar de comparar n-gramas exactos (descartado en `FASE_6.md` §6g: saltaba en 32 de 3.933 respuestas buenas), compara **frases y líneas enteras** con una similitud aproximada:
- **Unidad:** cada línea y cada frase, normalizadas (sin numeración de lista ni citas `[n]`).
- **Ventana:** en las últimas 8 unidades, si 5 o más son casi copias (similitud ≥ 0.95, `difflib`) de una anterior de la ventana, es un bucle.
- **Fuera de la comparación:** tablas, HTML, logs, código y bloques sangrados, que repiten su forma por naturaleza.
- **Además:** la misma palabra 12 veces seguidas ("step step step…").
- **Al detectarlo:** se para la generación y se recorta la respuesta donde empieza la repetición, conservando lo bueno.

**Medido** (prototipo en `data/output/loop_detector/`, fuera de git):

| | Resultado |
|---|---|
| Bucles reproducidos | **3 de 3** detectados. Conserva 1.828–2.328 caracteres buenos de cada uno |
| Falsos positivos en documentos largos (202 `.md` de vLLM, `docs/`, README y XQuAD) | **0** |
| Falsos positivos en respuestas guardadas (11.550, todos los `gen-bench` y `agent-bench`) | **0** |
| Variante más agresiva (4 repeticiones) | 1 documento y 4 respuestas: descartada |

**Qué permitiría:** quitar el límite fijo de tokens de la web (o subirlo mucho) y dejar que el LLM escriba lo que necesite, parando solo cuando degenera. Responde a la "libertad de longitud" de 7b.

**Integrado** (con tu aprobación, 2026-10-24):
- **`src/rag/loops.py`** (nuevo): `find_loop` (la regla de arriba) y `cut_loop`.
- **`Generator.stopping_criteria`:** un criterio `Looping` que solo decodifica y comprueba el texto cuando el último token cierra una línea o una frase, y para la generación cuando hay bucle. Funciona en la web, la CLI, los benchmarks y el agente.
- **`clean_output`:** recorta el bucle donde empieza, con o sin streaming. La web sustituye el texto que se ha ido mostrando por la respuesta final, así que la parte repetida desaparece al terminar.
- **Una corrección de paso:** un número de lista ("5. ") ya no cuenta como final de frase. Lo encontró un test: el corte dejaba un "5." colgando.
- **Sin interruptor:** con 0 falsos positivos medidos, no hace falta poder apagarlo. Las respuestas sin bucle no cambian.

**Prueba de extremo a extremo** (Phi-4-mini en GPU, las 6 preguntas, límite de 1.500 tokens; `data/output/loop_detector/repro_guard.json`):

| Pregunta | Antes | Con el detector |
|---|---|---|
| Paso a paso de vLLM | 1.500 tokens, 67 s | **419 tokens, 34 s** |
| Step-by-step guide to serve a model | 1.500 tokens, 69 s | **661 tokens, 47 s** |
| Command-line options of vllm serve | 1.500 tokens, 73 s | **499 tokens, 35 s** |
| Las otras 3 | 133 / 248 / 493 tokens | **idénticas, carácter a carácter** |

Las respuestas recortadas terminan en una línea completa. La de prosa conserva algunas frases ya repetitivas ("séptima… décima etapa"), que son las que el detector usa de referencia antes de confirmar el bucle.

**Benchmarks:** no cambian. Con 150 tokens no hay bucles (0 de 11.550 respuestas marcadas).

**Límite de la web: 1.024 tokens para todos los modelos** (decisión tuya, 2026-10-24), en `make api` y en la imagen del servidor. Antes eran 512, y 640 para Phi-4-mini (§7b.1). Ya no es la defensa contra los bucles, solo una red de seguridad. ⚠️ En CPU (servidor gratuito) el 0.6B escribe a ~1–1.5 tokens/s: una respuesta muy larga puede tardar varios minutos, aunque el streaming la va mostrando y el botón Stop la corta.

**Pruebas:** `tests/test_loops.py` (6 tests: línea repetida, dos líneas alternas, frases con una palabra cambiada, palabra repetida, y tablas, código y respuestas buenas sin falso positivo).

**Caso visto de paso:** "Paso a paso de vLLM" (corta y ambigua) va a "about" (3.13 frente a 2.09 de vLLM), porque la documentación habla del "paso a paso" del RAG. Con una formulación completa ("Explícame paso a paso cómo usar vLLM") va a vLLM (3.0 frente a 1.2). No se toca el router por un caso límite.

## Decisiones (tuyas, 2026-10-24)

- **README en inglés.**
- **P11, juez del CV: Groq**, hasta agotar los tokens gratuitos. Es una excepción expresa a la regla de la Fase 4b ("el juez externo no se usa con datos personales salvo que lo decidas"): las fuentes y respuestas del CV se mandan a Groq, con los datos de contacto privados enmascarados. Si hace falta, se repite con Qwen3-4B como juez local.
