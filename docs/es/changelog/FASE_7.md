# CHANGELOG — Fase 7: Opcionales y mejoras

Fase abierta el 2026-10-24, tras el commit `3378494` (Fase 6). **Cerrada el 2026-10-27** (lo pendiente pasa a la Fase 8, ver `ROADMAP.md`). El plan está en `ROADMAP.md` (Fase 7). Aquí se irá apuntando qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`.

## Estado

| Bloque | Estado |
|---|---|
| 7a — Dominio "about" (README, `docs/`, código) | ✅ Hecho: README, fuente, benchmark bilingüe, separación del CV (§7a.6), umbral y regla léxica (§7a.7), y web y bundle (§7a.8). Quedan 6 preguntas que se van a vLLM, sin palabras que las distingan |
| 7b — Calidad de las respuestas (Markdown, plan B del agente, formato, juez del CV) | Agente desactivado por defecto en la web, límite de tokens por modelo (§7b.1), detector de bucles (§7b.2), limpieza del eco (§7b.3), filtro de idioma (§7b.4, activado en §7b.8), forma de las respuestas (§7b.7) **solo Qwen, sin trampas** (§7b.8: Phi-4-mini, su reintento y `route_names` retirados, "about" reindexado) y fuera las citas de preguntas de prueba y respuestas incorrectas (§7b.9); el resto, planificado (P11 resuelto: Groq) |
| Despliegue | Plataforma cambiada a Oracle Cloud Always Free (DEC-19); guía en `deploy/README.md` |
| 7c — Visual (tarjetas que giran, scroll) | Planificado |
| 7d — Opcionales (Gulliver, MLQA) | Aparcados; `repetition_penalty` descartado (§7b.1). Un modelo opcional de otra familia que sustituya a Phi, sin probar (DEC-32) |

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

Con la API reiniciada después de indexar "about", ese dominio entró en el router **sin calibrar**. Ejemplo tuyo con el 1.7B: <!-- about:skip -->a "Chrystian Donaire Villén Que me estas contando" respondió con tu fecha de nacimiento y<!-- /about:skip --> añadió una frase de jerga interna sobre el agente por defecto (literal en `RESPUESTAS_ARCHIVADAS.md`). Los changelogs contienen transcripciones de las pruebas (por ejemplo, `FASE_6.md` §5 cita respuestas del CV) y jerga interna, y el router los eligió.
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

**Por qué se iban a otro dominio** (pregunta a pregunta, con el índice de §7a.6; los identificadores son los de `bench/datasets/about/questions.json`):

| Pregunta | Gana | Puntuación de "about" | ¿Tiene pista? |
|---|---|---|---|
| about-01 (EN / ES) | **cv** (8.3 / 8.0): tu CV menciona el proyecto | 6.7 / 6.4 | el nombre |
| about-02 (EN) | vllm (−2.06) | −2.25 | "the project" |
| about-11 (EN) | vllm (−0.24) | −2.91 | "the project" |
| about-03 y about-09 (EN y ES) | vllm | más baja | ninguna: vLLM también responde a eso |

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

- **Lo que arregla:** about-01 en los dos idiomas.
- **Lo que no arregla:** about-02 y about-11 (EN) sí tienen la pista, pero "about" no pasa su umbral (−2.25 y −2.91 frente a −1.0). La regla no las fuerza, y es lo que se buscaba.
- **El resto** (embeddings, código Python) son preguntas que la documentación de vLLM también responde, sin ninguna palabra que las distinga.

**Pruebas:** `test_a_hinted_domain_wins_when_it_passes_its_threshold` y `test_a_hint_alone_does_not_route` en `tests/test_router.py`. 109 tests; flake8 y mypy limpios.

## 7a.8 — "about" en la web y en el bundle (paso 5)

**Dominio fijo (`pinned`, nuevo en `SourceConfig`, activo en "about"):**
- **API:** un dominio fijo se añade a cualquier filtro de dominios (`ChatService.domains_for`). Sin filtro (`domains: null`), se busca en todos, como antes. `/config` marca cada dominio con `pinned`.
- **Web:** el chip de "about" sale siempre encendido, con un punto delante (`● about`), sin cursor de mano y con "(always on)" en el título. Pulsarlo no hace nada.
- **`make api`:** `API_DOMAINS` pasa a estar vacío, así que la web sirve todos los dominios indexados. El servidor de despliegue ya servía todo lo del bundle.
- **Textos de la web:** la presentación y el campo de pregunta mencionan el proyecto ("…and the project explaining itself").

**Preguntas de ejemplo** (`web/src/examples.ts`). Todas se han comprobado con el índice real, buscando en todos los dominios. Las preguntas sobre el proyecto se nombran por su identificador del banco abierto (`A-NN`, lista en `RESPUESTAS_ARCHIVADAS.md`):

| Ejemplo | Llega a | ¿Pasa el filtro? |
|---|---|---|
| vLLM, XQuAD (2), CV (2) y tres sobre el proyecto (A-04, A-12, A-14) | su dominio | sí |
| ~~"Which instrument does he play?"~~ | vllm (−3.77) | no. **Ya fallaba sin "about"**: suelta, la pregunta no dice quién es "he" |
| → "Which instrument does Chrystian play?" | cv (3.52) | sí |
| ~~Un ejemplo sobre los modelos del proyecto~~ (literal en `RESPUESTAS_ARCHIVADAS.md`) | vllm (−0.83) | no |
| → A-13 | about (1.09) | sí |

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

| Pregunta (texto y salida literales en `RESPUESTAS_ARCHIVADAS.md`) | Cómo degenera |
|---|---|
| L-1, guía para servir un modelo con vLLM (EN) | Desde el paso 26, la misma línea una y otra vez |
| L-2, opciones de línea de comandos (EN) | Dos líneas que se alternan desde la opción 29 |
| L-3, guía de vLLM en tres palabras (ES) | En prosa, sin saltos de línea, la misma frase con el ordinal cambiado. **Cambia palabras en cada vuelta**, como habías visto: por eso penalizar la repetición no sirve |
| Las tres | Terminan con la misma palabra repetida hasta el límite |

**Microsoft** recomienda en la ficha del modelo lo mismo que ya hacemos: *greedy* (`do_sample=False`) y un máximo de 500 tokens. La propia ficha avisa de que Phi-4 "puede generar respuestas repetitivas".

**Idea: detector de bucles por similitud de frases.** En lugar de comparar n-gramas exactos (descartado en `FASE_6.md` §6g: saltaba en 32 de 3.933 respuestas buenas), compara **frases y líneas enteras** con una similitud aproximada:
- **Unidad:** cada línea y cada frase, normalizadas (sin numeración de lista ni citas `[n]`).
- **Ventana:** en las últimas 8 unidades, si 5 o más son casi copias (similitud ≥ 0.95, `difflib`) de una anterior de la ventana, es un bucle. *(Ventana 12 desde DEC-28, §7b.7.)*
- **Fuera de la comparación:** tablas, HTML, logs, código y bloques sangrados, que repiten su forma por naturaleza.
- **Además:** la misma palabra 12 veces seguidas.
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
| L-3 | 1.500 tokens, 67 s | **419 tokens, 34 s** |
| L-1 | 1.500 tokens, 69 s | **661 tokens, 47 s** |
| L-2 | 1.500 tokens, 73 s | **499 tokens, 35 s** |
| Las otras 3 | 133 / 248 / 493 tokens | **idénticas, carácter a carácter** |

Las respuestas recortadas terminan en una línea completa. La de prosa conserva algunas frases ya repetitivas, que son las que el detector usa de referencia antes de confirmar el bucle.

**Benchmarks:** no cambian. Con 150 tokens no hay bucles (0 de 11.550 respuestas marcadas).

**Límite de la web: 1.024 tokens para todos los modelos** (decisión tuya, 2026-10-24), en `make api` y en la imagen del servidor. Antes eran 512, y 640 para Phi-4-mini (§7b.1). Ya no es la defensa contra los bucles, solo una red de seguridad. ⚠️ En CPU (servidor gratuito) el 0.6B escribe a ~1–1.5 tokens/s: una respuesta muy larga puede tardar varios minutos, aunque el streaming la va mostrando y el botón Stop la corta.

**Pruebas:** `tests/test_loops.py` (6 tests: línea repetida, dos líneas alternas, frases con una palabra cambiada, palabra repetida, y tablas, código y respuestas buenas sin falso positivo).

**Caso visto de paso:** L-3 (corta y ambigua) va a "about" (3.13 frente a 2.09 de vLLM), porque la documentación habla del "paso a paso" del RAG. Con una formulación completa ("Explícame paso a paso cómo usar vLLM") va a vLLM (3.0 frente a 1.2). No se toca el router por un caso límite.

## 7b.3 — Respuestas que copian el prompt (eco)

**Sesión autónoma de la noche del 24 al 25** (decisiones DEC-20 a DEC-26 en `decisions.md`). Regla: ningún caso puede empeorar. Línea base `80-*`, tomada al empezar con el código del commit `02ff464`:
- **0.6B:** vllm (50 preguntas por set), xquad (300 por idioma), cv y about.
- **1.7B, Phi-4-mini y 4B:** vllm (25 por set), cv y about.

**Lo que viste:**
- Con Phi y A-04, la "respuesta" eran las 5 fuentes copiadas con sus cabeceras, y la respuesta de verdad (tras `ANSWER:`) llegaba al final, cortada por el límite de tokens (literal en `RESPUESTAS_ARCHIVADAS.md`).
- La etiqueta mal puesta de la fuente [4] era una copia equivocada de Phi; el índice estaba bien (comprobado).
- El 0.6B hace lo mismo a pequeña escala: acaba repitiendo nuestra última instrucción del prompt.

**Medirlo (DEC-20):** suite `about` en `gen-bench` y dos métricas nuevas, `echo` y `bad_citation` (`src/evaluation/gen_bench.py`). Eco en la línea base:

| | vllm docs | vllm code | xquad EN / ES | cv EN | about EN |
|---|---|---|---|---|---|
| Qwen3-0.6B | 0.00 | 0.02 | 0.03 / 0.01 | 0.10 | 0.06 |
| Phi-4-mini | 0.16 | 0.04 | — | 0.00 | 0.17 |
| Qwen3-1.7B y 4B | 0.00 | 0.00 | — | 0.00 | 0.00 |

**Prompts probados (DEC-21), con la matriz completa:**

| Estilo | Qué cambia | Caídas frente a `80` | Lectura |
|---|---|---|---|
| `v4` (`81-*`) | Idioma y regla anti-copia en el sistema; el usuario acaba con la pregunta | **112** | Dejan de citar: 0.6B "cites" en vLLM docs 0.90 → 0.16, Phi 0.92 → 0.40. Baja el idioma. El eco de Phi en about/en sí baja (0.17 → 0) |
| `v6` (`82-*`) | `v3` más solo la regla anti-copia | **75** | Cambios pequeños en todas direcciones; el eco no baja |
| `v5` | `v4` más "ignora las fuentes que no responden" | no probado | Hereda lo que rompe `v4` |

**Conclusión:** la instrucción final es lo que hace citar y responder en el idioma pedido. El prompt se queda en `v3` y el código de los estilos se retiró.

**Limpieza (DEC-22), `strip_echo` en `clean_output`** (`src/rag/generator.py`):
1. Tras una copia de las fuentes, se queda con lo que sigue al último `ANSWER:`.
2. Quita la instrucción repetida.
3. Si la respuesta abre copiando una fuente, conserva el texto sin la cabecera y lo cita `[n]`.
4. Las demás cabeceras pasan a `[n] (ruta)`.

Como la generación no cambia, se midió sobre las respuestas guardadas:

| Matriz | Respuestas | Cambiadas | Eco antes → después | Pierden la respuesta de referencia | F1 |
|---|---|---|---|---|---|
| `80` (`v3`) | 1.554 | 25 | 25 → 0 | **0** | +0.86 (suma) |
| `82` (`v6`) | 1.554 | 35 | 35 → 0 | 0 | +1.04 |
| `81` (`v4`) | 1.554 | 78 | 78 → 0 | 0 | +2.70 |

Tu caso con Phi queda en *"RAG against the Machine is a multi-domain Retrieval-Augmented Generation system with an agent, an MCP server, and a web interface. …"*.

**Pruebas:** `test_strip_echo_keeps_only_the_answer` y `test_strip_echo_handles_copied_source_headers` (`tests/test_generator.py`).

## 7b.4 — Fuentes de "about" en un solo idioma (implementado, desactivado)

Para una pregunta en inglés, "about" devolvía copias en español del mismo documento (`docs/es/…`), que ocupaban huecos del contexto.

**Implementado** (`Retriever.search_smart`, `src/rag/retriever.py`): con `translations` (pares de prefijos [inglés, español]) en una fuente, se piden el doble de candidatos, se quita la copia del otro idioma de los ficheros traducidos y se corta a `k`. `translation_languages` dice a qué idioma de pregunta se aplica. Sin `translations`, `search_smart` es exactamente el de antes (`search_smart_all`), así que vLLM, XQuAD y CV no cambian.

**Medido con el mismo índice** (`79-about-c-*` y `data/output/night/about_contains.py`):

| Filtro | Recall 42 EN @1/@3/@5/@10 | ES | Contiene la respuesta EN @1/@3/@5 | ES | Fuentes del otro idioma (top 5, EN / ES) |
|---|---|---|---|---|---|
| Sin filtro | 0.28 / 0.44 / 0.50 / 0.72 | 0.33 / 0.44 / 0.61 / 0.67 | 0.67 / 0.72 / 0.83 | 0.72 / 0.89 / 0.94 | 16 / 5 de 90 |
| Ambos idiomas | 0.28 / 0.50 / 0.56 / 0.72 | 0.33 / 0.44 / 0.61 / 0.72 | 0.67 / 0.78 / 0.83 | 0.72 / **0.83 / 0.83** | 3 / 0 |
| **Solo inglés** | 0.28 / 0.50 / 0.56 / 0.72 | idéntico | 0.67 / 0.78 / 0.83 | idéntico | 3 / 5 |

- **Por qué "ambos idiomas" pierde en español:** la sección inglesa recuperada a veces contiene la respuesta y la sección española recuperada es otra. Por ejemplo, para about-01 en español se quitaba el fragmento del `README.md` inglés que contiene "Retrieval-Augmented Generation".

**Generación** (filtro "solo inglés" `83-*` frente a sin filtro `84-*`, mismo índice):

| Modelo | about/en | about/es |
|---|---|---|
| Qwen3-0.6B | contiene 0.44 → **0.61**, citas 0.23 → 0.29, idioma 0.93 → 1.00 | = |
| Qwen3-1.7B | citas correctas 0.43 → 0.33, cita 0.93 → 0.80 | = |
| Phi-4-mini | citas correctas 0.33 → 0.17, "no encontrado" 0.17 → 0.28; idioma 0.80 → 0.92 | = |
| Qwen3-4B | contiene 0.61 → 0.67; "no encontrado" 0.22 → 0.28 | = |

**Decisión (DEC-23):** queda **desactivado** en `rag.toml` (comentado), porque empeora métricas de los modelos opcionales. Es muy bueno para el 0.6B, el que se despliega: activarlo es descomentar dos líneas, sin reindexar. *(Activado en §7b.8, DEC-34.)*

**Pruebas:** `test_translated_copies_are_recognised` (`tests/test_retriever.py`).

## 7b.5 — Preguntas que nombran el proyecto o al autor

*(Retirado en §7b.8, DEC-33.)*

**A-02** (pedir que hable del RAG, sin nombrarlo) iba a vLLM (1.04 frente a −1.85 de "about"), y aunque hubiera ido a "about", su filtro (−1.0) la habría rechazado.

**`route_names`** (nuevo en `SourceConfig`; `DomainRouter.named` en `src/rag/router.py`): expresiones que nombran el dominio sin ambigüedad. Si coinciden, ese dominio gana **y su filtro no se aplica**, en el enrutado y también cuando es el único dominio del filtro.
- **En "about":** "rag against the machine", "este/esta/tu/vuestro + rag/proyecto/sistema/chatbot/asistente/web/aplicación" y "this/your + rag/project/system/chatbot/assistant/website/app".
- **"The project" y "el proyecto"** siguen como pista débil (`route_hints`): deben pasar el umbral, por la pregunta de XQuAD que dice "the project".
- **Comprobado:** ningún patrón coincide con preguntas de los demás benchmarks (vLLM, XQuAD, CV, fuera de dominio, conversaciones).

**8 preguntas que nombran el proyecto** (`named.py`; identificadores del banco abierto), antes (commit) y ahora:

| Pregunta | Antes | Ahora |
|---|---|---|
| A-02 | vLLM, no encontrado | about |
| A-03 | vLLM (3.91) | about |
| A-06 | XQuAD | about |
| A-07 | CV | about |
| A-08 | about, no encontrado | about |
| A-09 | about, no encontrado | about |
| A-10 | XQuAD | about |
| A-11 | about, no encontrado | about |

**El autor, para el CV** (pista débil `\b(chrystian|donaire)\b` en `[sources.cv]`): con un índice de "about" más grande, una pregunta del CV por el correo de contacto acababa en "about" (0.17), que la respondía con código. Con la pista, si la pregunta nombra al autor y el CV pasa su umbral (−3.0), gana el CV. Solo coinciden preguntas del CV.

**Route-bench** (`85-night-final` frente a `76-about-hints`, el estado del commit): mismo enrutado en todos los conjuntos. Con el índice nuevo de "about" (antes de restaurarlo, `79-cv-name-hint`), la pista del CV devolvió el CV a 0.967 / 0.967 desde 0.933 / 0.933.

**Pruebas:** `test_a_named_domain_wins_and_skips_its_gate` y `test_a_named_single_domain_skips_its_gate` (`tests/test_router.py`).

## 7b.6 — Índice de "about" y verificación final

**El índice de "about" crece y empeora.** Reindexado esta noche (753 padres, +35, por la documentación del día 24), la generación de "about" baja frente a la línea base **sin cambiar el código** (`84-*` frente a `80-*`; por ejemplo, el 1.7B en ES contiene 0.67 → 0.56), y una pregunta de "about" en ES pasa a vLLM.
- **Decisión (DEC-25):** se **restaura el índice de la línea base** desde `deploy/bundle` (718 padres, SHA256 comprobado). La documentación nueva no entra en "about" hasta reindexar, y habrá que decidir qué partes ve (`about:skip`) antes del despliegue. *(Reindexado en §7b.8, DEC-37.)*
- **Preparado sin efecto hasta reindexar:** `deploy/space/README.md` (la ficha antigua del Space) sale de "about".

**Verificación final** (estado en que lo dejo: prompt `v3`, `strip_echo`, `route_names`, pista del CV, filtro de idioma desactivado e índice de la línea base):

| Comprobación | Resultado |
|---|---|
| `make bench` de 42 (`85-night-final`) | **Idéntico:** docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88 |
| Route-bench (`85-night-final`) | Mismo enrutado que el commit. XQuAD/ES R@1 0.9059 → 0.9050 (una pregunta, por la búsqueda vectorial aproximada tras restaurar el bundle) |
| `gen-bench` de about (`85-*`, cuatro modelos) | Idéntico a `80`, con el eco a 0. Phi about/en: idioma 1.00 → 0.93, por una respuesta que queda en código tras la limpieza (mismo contenido) |
| `gen-bench` de vllm, xquad y cv | Sin cambios de generación (mismo prompt e índices); la limpieza solo actúa en las respuestas con eco (§7b.3) |
| 8 preguntas que nombran el proyecto | 8 de 8 en "about" (antes, 0) |

**Pruebas:** 122 tests; flake8 y mypy limpios.

## 7b.7 — Forma de las respuestas: preguntas abiertas, eco de Phi y bucles (sesión del 25 al 26)

**Lo que viste en la web tras la noche anterior:**
- **Phi-4-mini:** sigue copiando fuentes con A-01 y con A-04, y la segunda respuesta sale cortada.
- **0.6B:** A-01 no da ninguna respuesta.
- **1.7B:** responde bien.

Regla de la sesión: ningún caso puede empeorar. Decisiones DEC-27 a DEC-31 en `decisions.md`.

**Por qué no funcionaba:**
- **0.6B, respuesta vacía:** la limpieza de la instrucción repetida (`INSTRUCTION_ECHO`, §7b.3) iba de "citing the sources by number" hasta el último punto, atravesando los dos puntos, así que cuando el 0.6B repetía la instrucción seguida de dos puntos y la respuesta, se comía toda la respuesta.
  - **Arreglo:** el patrón no cruza los dos puntos, y si la limpieza deja la respuesta vacía, se devuelve la original.
  - **Comprobado:** 0 cambios en las 4.662 respuestas guardadas de `80`/`81`/`82`.
- **Phi:** en la web hay dos fallos que `strip_echo` no puede arreglar.
  - **(a)** Copia las fuentes y la pregunta, y se para sin responder.
  - **(b)** Copia las cinco fuentes y se queda sin tokens antes de escribir la respuesta.

  En los dos casos la respuesta empieza por `[1] --- file:`.

**Medirlo como en la web (DEC-27):**
- **`gen-bench`:** métricas `cut` (respuesta a media frase o al 95 % del límite), `tokens` (media) y `tokens_max`.
- **Banco de 34 preguntas abiertas** (`data/output/night2/open_bench.py`): about, CV, vLLM, XQuAD y fuera de dominio, incluidos tus casos y los ejemplos de la web.
  - Pasa por el mismo camino que la web (`RagService.chat`, todos los dominios, 1.024 tokens y recorte).
  - Mide respuestas cortadas, eco, bucles, frases repetidas, vacías e idioma.
- **Línea base `90-*`:** la matriz de `gen-bench` a 1.024 tokens más el banco abierto, con el código de la noche anterior más el arreglo del 0.6B.

**Cambios:**
1. **Detector de bucles, ventana 8 → 12** (DEC-28). Un bucle de Phi de 4 frases no se detectaba, porque en una ventana de 8 nunca hay 5 copias. Con 12 se detectan ciclos de hasta 7 frases.
   - 4 de 7 bucles reproducidos, frente a 3 de 7 con ventana 8.
   - 0 falsos positivos en 14.261 respuestas y 299 documentos.
2. **Reintento cuando Phi copia las fuentes** (DEC-29, `EchoStart` en `src/rag/generator.py`). *(Retirado en §7b.8, DEC-32.)*
   - **Cuándo:** la respuesta empieza con una cabecera de fuente o una etiqueta (`[n] ---`, `SOURCES:`, `QUESTION:`) y llega a copiar una segunda.
   - **Qué hace:** se para y se genera otra vez, sin dejar empezar por `[` y sin dejar escribir cabeceras ni etiquetas.
   - **En la web:** el principio de la respuesta se retiene hasta saber que no es un eco, así que la copia nunca llega a la pantalla.
   - **Coste:** tarda el doble, pero solo en estos casos.
   - **Por qué hace falta una segunda copia:** la versión que reintentaba con la primera cabecera (`91-*`) mejoraba la forma de ~11 respuestas del 0.6B, pero perdía una (una pregunta de XQuAD/ES que pasaba a dar una fecha equivocada; literal en `RESPUESTAS_ARCHIVADAS.md`).
3. **Bloques repetidos** (DEC-30, `repeated_block` en `src/rag/loops.py`): 6 o más frases seguidas que repiten las de un poco antes, con un ciclo de hasta 40 frases.
   - Detecta los ciclos largos de Phi (14 frases sobre la búsqueda híbrida, hasta 1.016 tokens) y la respuesta escrita dos veces, con la instrucción repetida en medio.
   - Con bloques de 4 daba falsos positivos en 4 documentos de vLLM; con 5 o más, ninguno. Se usa 6 por margen.
   - En 15.793 respuestas y 299 documentos solo cambian las de Phi que repetían.

**Resultado (`92-*` frente a `90-*`):**

| | `gen-bench` (todas las suites de la matriz) | Preguntas abiertas (34) |
|---|---|---|
| Qwen3-0.6B | Idéntico (0 cambios en vllm, xquad, cv y about) | Idéntico |
| Qwen3-1.7B | Idéntico | Idéntico |
| Qwen3-4B | Idéntico | Sin medir en `92` (ver abajo) |
| Phi-4-mini | 3 cambios, los tres a mejor (abajo) | 5 cambios: cortadas 2 → 0, eco 1 → 0, máximo 1.016 → 606 tokens, media 239 → 203 |

**Cambios de Phi:**
- **Commit de Triton (vLLM):** pasa de copiar 1.461 caracteres de la documentación a *"…is `e5be006` [1]"*.
- **A-04:** pasa de 49 tokens cortados a media frase a una respuesta completa.
- **A-05:** deja de escribir la respuesta dos veces (773 → 375 tokens).
  - Por eso bajan dos métricas de about/ES de Phi: "cites" 0.93 → 0.86 y "citation ok" 0.38 → 0.33.
  - Las citas de esa respuesta (`[1][2][3][4][5]`) solo estaban al final de la copia.
- **A-15:** 1.016 → 307 tokens, sin el ciclo.
- **A-09:** de un trozo de changelog copiado a una respuesta redactada.
- **A-01:** de copiar 873 tokens de fuentes a "no encontrado".

**Lo que queda:**
- **A-01:** el 0.6B da una respuesta ya no vacía pero mala (repite la instrucción y cita la propia pregunta; literal en `RESPUESTAS_ARCHIVADAS.md`), y Phi dice que no lo encuentra.
  - Con esa pregunta, las fuentes que llegan son pobres: secciones sueltas del ROADMAP y los changelogs.
  - Si se busca con el nombre del proyecto en lugar de la forma en que lo nombra A-01, las fuentes mejoran para las preguntas generales, pero empeoran para las concretas (reranker, agente, web). No aplicado.
- **Phi en "about" sigue siendo prolijo:** resume cada fuente una tras otra.
  - Repite datos falsos de `deploy/space/README.md` (la ficha antigua del Space: el despliegue y el agente por defecto), que sigue en el índice restaurado (DEC-25).
  - Se arregla al reindexar "about" (ya está excluida en `rag.toml`); es tu decisión pendiente.
- **Banco abierto del 4B en `92`:** el 4B no carga en el proceso del banco abierto (llm_sdk descarga parte a la CPU con 12 GB; en `90` sí cargó).
  - Sus respuestas no pueden cambiar: en `90` no tiene eco ni bloques repetidos, y en `gen-bench` es idéntico.
  - Lo deduzco de los datos, no lo he medido.
- **Incidencia:** una prueba de Phi que debía ir en CPU usó la GPU y bloqueó la línea base de 00:45 a 14:05. No afecta a ningún resultado (generación determinista), solo a los tiempos de `90-q06-xquad`.

**Pruebas:** 129 tests (nuevos: el reintento y los bloques repetidos); flake8 y mypy limpios. `make bench` de 42 (`93-session-final`) **idéntico**: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88.

## 7b.8 — Solo Qwen, sin trampas (sesión del 26 al 27)

**Punto de partida:** el commit `644c455` (checkpoint de §7b.7) y tus decisiones de esa tarde:
- **Phi-4-mini fuera** ("el problema de Phi ya es insalvable"): se queda la familia Qwen3.
- **Limpieza encima del commit actual**, no volver a una versión anterior: se conserva lo que funciona (métricas, banco abierto y detector de bucles).
- **Quitar las trampas**, aunque empeoren las preguntas poco concretas.
- **El filtro de idioma se queda**, y si se le puede dar al LLM una pista del idioma, mejor.
- **Toda la documentación al día**, sin contradicciones.

Decisiones DEC-32 a DEC-38 en `decisions.md`.

### Qué ha cambiado

| Fichero | Cambio | Por qué |
|---|---|---|
| `src/rag/generator.py` | Vuelve a la versión de `02ff464` (sin el reintento por eco de Phi: `EchoStart`, constantes `ECHO_*`, streaming retenido) más `strip_echo` con el arreglo del 0.6B | DEC-32, DEC-35 |
| `src/rag/router.py`, `src/config.py`, `src/rag/retriever.py` | Fuera `route_names` (`DomainRouter.named`, el campo de `SourceConfig` y su compilación) | DEC-33 |
| `rag.toml` | Fuera el perfil `llm-phi4-mini`, `route_names` y la pista del CV; las pistas de "about" vuelven a las de `8ff05d0`; `translations` y `translation_languages = ["en"]` activados | DEC-32, DEC-33, DEC-34 |
| `Makefile` | `API_MODELS ?= default,llm-qwen3-1.7b` | DEC-32 |
| `web/src/App.tsx` | Fuera la nota de Phi del selector (web recompilada) | DEC-32 |
| `tests/test_generator.py`, `tests/test_router.py` | Fuera los tests del reintento y de `route_names` | — |
| `src/agent/toolcalls.py`, `src/api/app.py`, `src/rag/loops.py` | Solo comentarios y docstrings (Phi como opción hasta la Fase 7; referencias de sección) | Que el código no contradiga a los documentos |
| `bench/datasets/about/` | Ground truth regenerado con `build_about_bench`; about-11 responde ahora "Oracle" (decía "Hugging Face") y about-17 apunta a la firma actual de `stopping_criteria` | DEC-37 |
| `README.md`, `docs/es/README.md` | Cuatro dominios (con "about"), solo modelos Qwen, sección "Modelos" con la retirada de Phi, despliegue en Oracle (ya no Hugging Face), agente desactivado en la web, chip "about" siempre activo | Contradicciones encontradas en el diagnóstico (abajo) |
| `deploy/README.md`, `deploy/space/README.md` | Dominios y modelos al día; la ficha del Space avisa de que el despliegue real está en Oracle | Ídem |
| `docs/es/DETECTOR_BUCLES.md` | Ventana 12, bloques repetidos y §8 con la actualización | Seguía describiendo la ventana 8 |
| `docs/es/ROADMAP.md`, `docs/ROADMAP.md`, `BENCHMARK_REPORT.md`, `decisions.md`, este changelog (ES y EN) | Estado de la sesión; el inglés, sincronizado con todo lo que faltaba desde `8ff05d0` (§7a.6–7b.8, DEC-19 a DEC-38) | Tu encargo |

### Diagnóstico previo: ¿las preguntas vagas o los datos duplicados rompen "about"?

Me preguntaste las dos cosas antes de decidir. Medido solo con la recuperación (API, índice restaurado de DEC-25):
- **Las preguntas concretas fallan por sí solas**, no por culpa de las vagas: con el filtro de la web, 6 de 36 se van a vLLM o XQuAD; solo con "about", su umbral (−1.0) rechaza 7 de 36 (por ejemplo, about-02 en inglés, −2.07).
- **Las copias EN/ES sí ocupan sitio:** en 5 de 18 preguntas en inglés, la copia en español de un documento ocupa huecos del top 5 (1 de 18 en español). Es lo que arregla el filtro de idioma (DEC-34).
- **Había contradicciones de verdad en el índice:**
  - El README decía "Hugging Face Space" y "agente por defecto" (cierto en la CLI, no en la web).
  - "Oracle" solo aparecía en `docs/es`.
  - Un fichero fantasma, `docs/nextstep.md` (19 trozos), estaba en el índice aunque ya no existe en disco ni estuvo nunca en git.
  - La ficha antigua del Space (`deploy/space/README.md`) seguía dentro del índice restaurado.
- **El historial pesa mucho:** el README son 44 de los 1.613 puntos de Markdown del índice (contando padres e hijos; 2.726 puntos en total). En el índice nuevo, el historial (changelogs, `decisions.md`, `DETECTOR_BUCLES.md`) son 1.121 de los 1.623 trozos de documentación.

### Mediciones

Misma matriz que §7b.7 (`gen-bench` a 1.024 tokens; banco abierto de 34 preguntas; `route-bench`), un cambio cada vez. Hasta `96`, con el mismo índice:

| Ejecución | Cambio | `gen-bench` frente a la anterior | Banco abierto | Route-bench |
|---|---|---|---|---|
| `94` | Limpieza (sin Phi, sin reintento, sin `route_names` ni pista del CV), filtro apagado | **Idéntico a `92`** en las 10 ejecuciones de los Qwen | 9 respuestas cambian por modelo (0.6B y 1.7B), todas preguntas que nombraban el proyecto (DEC-33) | **Idéntico** a `76` y `85` |
| `95` | + filtro de idioma | Solo cambia about/EN (DEC-34) | 2 cambios por modelo, a mejor o igual | about/EN R@5 0.39 → 0.44, R@10 0.61 → 0.56 |
| `96` | + pista de idioma (opción A de DEC-36) | 22 métricas bajan; 158 respuestas cambian en XQuAD/ES del 0.6B; idioma de about/ES del 0.6B 1.00 → 0.86 | — | — |
| `97` | `95` (sin la pista) + "about" reindexado | vLLM, XQuAD y CV idénticos a `95`; cambia "about" (ver `98`) | 12 de 34 cambian por modelo (DEC-37) | Igual salvo CV y "about" (ver `98`) |
| `98` | `97` con el ground truth de "about" regenerado | about/ES mejora (contiene 0.61–0.78), about/EN baja una pregunta por modelo | — | about R@5 EN 0.33, ES 0.67; CV enrutado 0.933 / 0.900 |
| `99` | Experimento: "about" sin historial (revertido) | Contiene EN sube con los tres modelos (0.44–0.67 → 0.61–0.72); ES baja (0.61–0.78 → 0.50–0.67) | 0.6B: unas 7 de 12 a mejor, sin eco ni idioma mal; 1.7B: responde en inglés a 3 preguntas en español | about R@5 EN 0.50, ES 0.78; es/docs de 42 enrutado 0.9 → 1.0; XQuAD/ES −2 preguntas |
| `100` | Estado final, tras escribir la documentación | Contiene EN / ES: 0.6B 0.44 / 0.50, 1.7B 0.56 / 0.72, 4B 0.72 / 0.83; "no encontrado" falso en ES a 0 | 12 de 34 cambian frente a `97` por modelo; **7 de las 12 preguntas sobre el proyecto se responden citando notas de los changelogs y de `decisions.md`**, también las de esta sesión | about enrutado EN 0.889 · ES 0.944, R@5 EN 0.33 · ES 0.61; XQuAD/EN, una pregunta más a "about"; el resto, como `98` |

**`96`, la pista de idioma:** no se adopta (DEC-36). Empeora justo lo que quería mejorar: el idioma del 0.6B en about/ES (a about-01 responde solo con una cita, sin texto) y, de rebote, XQuAD/ES y el mensaje del CV en preguntas privadas (sin fugas). Queda abierta otra forma de dar la pista (opción C).

**`97`–`98`, el reindexado:** detalle en DEC-37. Tres cosas a saber:
- **El ground truth de "about" guarda offsets de caracteres.** Al editar el README se movieron 16 de los 18 pasajes; `97` daba un recall falso (EN R@5 0.28). Regenerado con `python -m src build_about_bench` (`98`). Hay que repetirlo cada vez que se edite la documentación.
- **El español mejora y el inglés baja un poco.** Pero se duplican las respuestas que cambian de idioma a mitad (10 → 20 en toda la matriz, todas las nuevas en about/ES y en el banco abierto), y el CV pierde 1–2 preguntas de enrutado frente a "about".
- **La documentación se cita a sí misma:** los changelogs copiaban las preguntas de prueba, y la búsqueda devolvía la cita en lugar de la respuesta (ejemplos literales en `RESPUESTAS_ARCHIVADAS.md`). Medido sin el historial en `99`; arreglado en §7b.9.

**`99`, "about" sin el historial:** los changelogs, `decisions.md` y `DETECTOR_BUCLES.md` son 1.121 de los 1.623 trozos de documentación. Sin ellos, el recall de "about" sube mucho y la autocita casi desaparece, pero el español pierde material en su idioma ("contiene" y el idioma bajan). Sin un ganador claro: se revierte y queda como decisión tuya (tabla completa y opciones en DEC-37).

**`100`, el estado final:** "about" reindexado con toda esta documentación (2.616 trozos, 892 padres). El `gen-bench` en español sube con el 1.7B y el 4B (0.72 y 0.83), pero el banco abierto empeora: documentar la autocita la agrava, porque §7b.8 y DEC-37 citan otra vez las preguntas. A A-09 los dos modelos responden con el texto de DEC-37. Es el argumento más fuerte para la opción B (DEC-37). *(Al final se eligió otra vía: §7b.9.)*

**El 4B en el banco abierto:** como en `92`, no carga en ese proceso (llm_sdk manda parte del modelo a la CPU). Su `gen-bench` sí se mide.

**Pruebas:** 123 tests (fuera los 6 del reintento y de `route_names`), flake8 y mypy limpios. 42 (`97-final`) idéntico: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88.

**Pendiente de ti:** ~~el historial dentro de "about" (DEC-37)~~ → resuelto en §7b.9 sin sacarlo del índice; otro modelo de otra familia (DEC-32), la opción C de la pista de idioma (DEC-36) y rehacer el bundle antes de desplegar (DEC-38).

## 7b.9 — Fuera las citas de preguntas de prueba y respuestas incorrectas (2026-10-27, decisión tuya)

**Lo que viste en la web con el estado de §7b.8:** a A-04 el 1.7B respondió explicando `clean_output` y `strip_echo` con el texto de `decisions.md`, y a A-13 el 0.6B dijo "no encontrado". Es la autocita de DEC-37, la misma que había medido en el banco abierto de `100` y que no traduje en "esto se nota en la web".

**Tu decisión:** quitar todas las citas de respuestas incorrectas y guardarlas, si se quieren conservar, en un fichero fuera de la indexación. Detalle y opciones en DEC-39.

### Qué ha cambiado

| Fichero | Cambio |
|---|---|
| `docs/es/RESPUESTAS_ARCHIVADAS.md` | **Nuevo, fuera del índice.** Las preguntas de prueba y las respuestas incorrectas al pie de la letra, con la sección de origen de cada una, y las listas de identificadores: `A-01`…`A-16` (banco abierto), `about-01`…`about-18` (benchmark de "about") y `L-1`…`L-3` (bucles de Phi) |
| `rag.toml` | `docs/es/RESPUESTAS_ARCHIVADAS.md` en `exclude_paths` de `[sources.about]` |
| `docs/es/changelog/FASE_7.md`, `docs/es/decisions.md` y sus traducciones | Las preguntas sobre el proyecto se nombran por su identificador y las respuestas malas se describen sin copiarlas (unas 35 sustituciones por fichero) |
| `docs/es/DETECTOR_BUCLES.md` | Los bucles de ejemplo se describen; las salidas literales pasan al archivo |
| `docs/es/ROADMAP.md`, `docs/ROADMAP.md`, `FASE_6.md` (ES y EN) | Las menciones sueltas (la pregunta abierta pendiente, las frases de `route_names`, el bucle de la revisión de la web) |
| `bench/datasets/about/` | Ground truth regenerado (`build_about_bench`), porque cambian los offsets del ROADMAP |

**Qué se ha quitado y qué no:** todas las respuestas incorrectas copiadas, y el texto de todas las preguntas de prueba sobre el proyecto (también las bien respondidas), porque lo que atrae a la búsqueda es la pregunta. Se quedan: las preguntas de vLLM, XQuAD y CV citadas sin respuesta mala, las respuestas correctas, los textos de la interfaz y del prompt, y "capital of France" → "Paris", que no es incorrecta (B15). Las transcripciones del CV ya estaban fuera con `about:skip`. El código no se toca. Lista completa en el §8 del archivo.

**Comprobado:** un script recorre todo lo que indexa "about" y no encuentra ninguna de las 36 preguntas del benchmark ni de las 16 del banco abierto (ni sus formas cortas). "about" reindexado: 894 padres y 2.630 hijos (1.846 de documentación y 784 de código).

### Mediciones (`101` frente a `100`)

| | `100` | `101` |
|---|---|---|
| Banco abierto 0.6B: respuestas que citan el historial | 7 de las 12 preguntas del proyecto | **0** |
| Banco abierto 0.6B: respondidas · eco · idioma mal | 30 · 2 · 1 | 29 · **0 · 0** |
| Banco abierto 1.7B: respondidas · eco · idioma mal · frases repetidas | 31 · 1 · 2 · 1 | 29 · **0 · 0 · 0** |
| Cambio de idioma a mitad (about + banco abierto) | 4 de 165 | **1 de 150** |
| `gen-bench` about, contiene EN / ES: 0.6B | 0.44 / 0.50 | 0.44 / 0.50 |
| 1.7B | 0.56 / 0.72 | 0.56 / **0.61** |
| 4B | 0.72 / 0.83 | **0.67 / 0.72** |
| "No encontrado" falso EN / ES (0.6B · 1.7B · 4B) | 0.11 / 0 · 0.06 / 0 · 0.06 / 0 | 0.17 / 0.11 · 0.17 / 0.11 · 0.22 / 0.11 |
| Route-bench about/EN, enrutado · R@1/@3/@5/@10 | 0.889 · 0.11 / 0.28 / 0.33 / 0.67 | **0.778** · 0.17 / 0.28 / 0.28 / 0.56 |
| Route-bench about/ES | 0.944 · 0.39 / 0.50 / 0.61 / 0.67 | 0.944 · **0.44** / 0.50 / **0.67** / 0.67 |
| Route-bench CV EN / ES, enrutado | 0.933 / 0.900 | **0.967** / 0.900 |
| Route-bench 42, es/docs, es/code, XQuAD | — | Igual (XQuAD/EN, una pregunta menos a "about") |

**`102`, con el índice final** (reindexado tras escribir esta sección y DEC-39, 913 padres y 2.700 hijos; solo el 0.6B y el `route-bench`): `gen-bench` about EN / ES 0.50 / 0.50; banco abierto, 3 respuestas cambian frente a `101` (el agente, el modelo y el recall), las tres al tema y ninguna cita el historial; `route-bench` igual que `101` salvo about/ES R@5 0.67 → 0.61. Después de anotar esta línea se reindexa "about" una vez más, sin volver a medir.

**En el banco abierto, las respuestas de la web:**
- **0.6B:** A-04 y A-13 vuelven a responder bien (el proyecto y Qwen3-0.6B). A-07, A-14 y A-15 explican el proyecto en lugar de copiar notas del historial o de `FASE_0.md`. A-09 y A-02 pasan a "no encontrado", que es mejor que contestar con DEC-37.
- **1.7B:** igual: A-05, A-07, A-13 y A-15 responden al tema, sin repetir la pregunta ni copiar notas; A-09 y A-02 pasan a "no encontrado".
- **Lo que sigue mal, sin autocita:** A-01 habla de la técnica RAG en general (fuentes de vLLM) y A-06 responde con el contrato de obra de XQuAD. Es la recuperación de las preguntas que no nombran el proyecto (DEC-33).
- **El 4B** no carga en el proceso del banco abierto, como desde `92`.

**Por qué baja el `gen-bench` de "about":** las preguntas que pierden son about-02 (modelo de lenguaje), about-04 (reranker) y about-11 (despliegue). Ahora dan "no encontrado": su mejor fuente ya no pasa el filtro de "about" (−1.0). Antes lo pasaban gracias a la nota del historial que copiaba la pregunta, y varias respuestas "acertadas" eran esa misma cita (por ejemplo, la de about-02 en español empezaba repitiendo la pregunta). Es el problema del umbral apuntado en DEC-38, que la autocita tapaba. Por la misma razón, about-02 y about-04 en inglés se van a vLLM en el `route-bench`.

**Pruebas:** 123 tests, flake8 limpio. Solo cambian documentos y `rag.toml` (una ruta excluida).

**Pendiente:** recalibrar el umbral de "about" con `gate_scores` ahora que la documentación no cita las preguntas (DEC-39). No lo he hecho: cambia el enrutado de todos los dominios y hay que volver a pasar el `route-bench`.

## Decisiones (tuyas, 2026-10-24)

- **README en inglés.**
- **P11, juez del CV: Groq**, hasta agotar los tokens gratuitos. Es una excepción expresa a la regla de la Fase 4b ("el juez externo no se usa con datos personales salvo que lo decidas"): las fuentes y respuestas del CV se mandan a Groq, con los datos de contacto privados enmascarados. Si hace falta, se repite con Qwen3-4B como juez local.
