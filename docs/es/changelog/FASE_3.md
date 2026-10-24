# CHANGELOG — Fase 3: Mejoras en la generación de respuesta

**Fecha de inicio:** 2026-10-19
**Estado:** ✅ completada (2026-10-19). Benchmark de generación, prompt nuevo, guardarraíl fuera de dominio (B15), flujo de respuesta unificado, streaming, LLM opcionales con comparativa y juez, revisión de código muerto y evaluadores agrupados en `src/evaluation/`.

---

## 1. Resultado hasta ahora

Benchmark de generación (`make gen-bench`): 50 preguntas de cada dataset oficial, las 20 del set en español y 40 fuera de dominio. Qwen3-0.6B, k = 5, decodificación greedy, 150 tokens de salida.

| Set | Métrica | v1 (`00`) | **Actual (`06`/`07`)** |
|---|---|---|---|
| Oficial docs | F1 frente a la respuesta de 42 | 0.480 | **0.497** |
| | Falsos "no encontrado" | 0.02 | **0.00** |
| | Cita alguna fuente / cita la correcta | 0.82 / 0.75 | **0.90 / 0.80** |
| Oficial code | F1 | 0.426 | **0.437** |
| | Falsos "no encontrado" (con la respuesta en el contexto) | 0.12 (—) | 0.12 (**0.04**) |
| | Cita alguna fuente / cita la correcta | 0.86 / 0.82 | **1.00 / 0.84** |
| Español docs | Responde en español | 0.62 | **0.90** |
| | Falsos "no encontrado" | 0.20 | **0.00** |
| Español code | Responde en español | 0.70 | **1.00** |
| Fuera de dominio | Rechazo correcto: ajenas EN / ES | 0.80 / 0.90 | **1.00 / 1.00** (`07`, set corregido) |
| | Rechazo correcto: casi del dominio EN / ES | 1.00 / 0.70 | 0.90 / 0.70 |

**Notas de lectura:**
- **El F1 de los sets en español no es fiable:** compara con la respuesta de referencia de 42, que está en inglés, así que una respuesta correcta en español puntúa bajo. En español valen el idioma, las citas y los rechazos.
- **"Con la respuesta en el contexto"** separa los fallos del generador de los de la recuperación: si la fuente correcta no llegó al contexto, decir "no encontrado" es lo honesto.
- El F1 de tokens es una medida aproximada (gratuita y reproducible); el juez LLM queda como complemento.

---

## 2. Qué se ha cambiado y por qué

### 2.1 Benchmark de generación (nuevo)

- **`src/gen_bench.py`** + `make gen-bench` (`--limit`, `--k`). Por cada pregunta guarda la respuesta, las fuentes y las métricas en `data/output/gen_bench/<label>/answers.json`; el resumen va a `bench/results/gen/`.
- **Métricas:**
  - F1 de tokens estilo SQuAD.
  - Si la respuesta cita una fuente (por nombre de fichero o `[n]`) y si es la del ground truth.
  - Idioma de la respuesta.
  - Falsos "no encontrado", separando si la respuesta estaba en el contexto (mismo criterio de solapamiento que el evaluador de 42).
  - Rechazo correcto fuera de dominio.
  - Latencia.
- **Set fuera de dominio** (`bench/datasets/ood/questions.json`): 40 preguntas, 20 en inglés y 20 en español. La mitad son "ajenas" (geografía, cocina, deporte…) y la otra mitad "casi del dominio" (nginx, PyTorch Lightning, Keras, Kubernetes…).
  - **Corrección (`07`):** *"What is the capital of France?"* **sí está en el corpus**. La documentación de vLLM la usa, con su respuesta, como ejemplo de la API (`openai_compatible_server.md`; aparece en 79 ficheros), así que responder "Paris" citándola es correcto. Se sustituyó por la del Everest. Todos los términos del set se han comprobado contra la parte indexada del corpus (incluido `benchmarks/`).
  - Esto **matiza B15**: el caso estrella de "alucinación" desde la Fase 0 estaba, en realidad, en la documentación.

### 2.2 Prompt nuevo (`src/generator.py`)

Medido paso a paso: `01` prompt v2, `04` regla de "no encontrado" suavizada (descartada), `05` solo la regla de código (adoptada).

- **Chat template oficial** de Qwen3 con `enable_thinking=False`, en lugar del prompt escrito a mano con `/no_think`. En la v1 se colaban restos del razonamiento (`</think>`).
- **Fuentes numeradas** `[1]…[n]` y citas con `[n]`. El ejemplo de la v1 (*"Source: \<filename\>"*) hacía que el modelo copiara literalmente `<filename>`.
- **Idioma explícito:** se detecta el idioma de la pregunta (`src/language.py`) y se pide *"Answer in Spanish/English"*.
- **Regla para leer código:** *"Sources may be code: read default values, conditions and return values directly from it."* Bajó los rechazos de code con la respuesta en el contexto de 0.12 a 0.04.
- **Regla de "no encontrado" estricta (la de v2):** la versión suavizada (`04`) mejoraba code pero empeoraba docs (2 falsos "no encontrado" y menos citas). Al separar los dos cambios (`05`) se vio que la mejora venía de la regla de código.
- **Presupuesto de contexto en tokens (B9):** las fuentes se recortan para que el prompt quepa en 3072 tokens; **la pregunta nunca se trunca**. La v1 truncaba por caracteres y luego, al tokenizar, por la derecha, que es donde estaba la pregunta.
- **Limpieza de la salida** (`clean_output`): restos de razonamiento y frases de "no encontrado" en inglés y español.
- `max_new_tokens` se mantiene en 150 para comparar sin mezclar efectos (las respuestas de referencia tienen una mediana de 31 palabras).

### 2.3 Guardarraíl fuera de dominio (B15)

- **Puntuación del reranker** en lugar del umbral BM25: la ruta de generación devuelve "no encontrado" si el mejor de los fragmentos recuperados tiene un logit del reranker inferior a `relevance_threshold = 0.0` (probabilidad 0.5 de "relevante").
- **Medido** sobre 220 preguntas legítimas y 40 fuera de dominio:

| Umbral | Legítimas rechazadas | Fuera de dominio rechazadas |
|---|---|---|
| −3 | 0.0 % | 60.0 % |
| **0** | **0.9 %** | **82.5 %** |
| 2 | 5.0 % | 87.5 % |

- **Por qué 0:** es la frontera natural del modelo (logit 0 = 50 %), no un valor ajustado a mano a nuestras 40 preguntas.
- **Por qué hacía falta:** con el prompt nuevo, Qwen se lanzaba más a responder fuera de dominio (`01`: rechazo de 0.50–0.80). Un modelo de 0.6B no es un buen guardarraíl; el filtro va **antes** del LLM.
- **Coste:** 2 preguntas legítimas de code se rechazan por error (sobre `OvisConfig` y la atención de Triton). En la ruta de la web, code R@5 pasa de 0.80 a 0.78. **El benchmark oficial no cambia** (`search_dataset` no usa el filtro).
- El umbral BM25 (`bm25_score_floor`) queda solo como respaldo si no hay reranker cargado.

### 2.4 Un único flujo de respuesta (tu propuesta)

- **`src/rag.py` (nuevo): `RagPipeline.answer()`**, que hace recuperación (`search_for_generation`: `search_smart` + filtro) → bloques de contexto → generación, con streaming opcional (`on_piece`). Devuelve un `RagAnswer` (texto, fuentes en orden `[n]`, `not_found` y tiempos).
- **Lo usan todos:** `answer` y `answer_dataset` de la CLI, la web y el benchmark de generación. Antes había cuatro copias de la misma secuencia.
- **Un solo punto de medición por cosa:** `make bench` mide el recall (benchmark oficial) y `make gen-bench` el flujo de respuesta completo, filtro incluido. **Eliminados** el modo `generation` de `bench` y `make bench-gen`.
- **Verificado:** las 160 respuestas del benchmark son idénticas antes y después de unificar (`05` = `06`).

### 2.5 Streaming

- `Generator.stream_answer()` usa `TextIteratorStreamer` de transformers, con la generación en otro hilo; mismo prompt y misma decodificación que `answer_with_text()`.
- **CLI:** `answer` muestra la respuesta según se genera (`--stream False` para desactivarlo).
- **Web:** la respuesta se pinta mientras se genera, y después aparecen las tarjetas de fuentes `[1]…[n]`.

### 2.6 Web

- Usa `RagPipeline` con streaming.
- **B6 resuelto:** la respuesta se escapa antes de pintarla como HTML; el código citado con `<…>` ya no rompe la página.
- **Probada de verdad** con `streamlit.testing.AppTest` (ejecuta la página sin navegador, escribe una pregunta y pulsa el botón): la pregunta en español se responde en español con su cita `[1]` y 5 tarjetas de fuentes.
- ⚠️ **En tu equipo, el Control de aplicaciones de Windows bloquea `streamlit.exe`** (el lanzador de pip, como pasó con `pyarrow`). Funciona con `python -m streamlit run src/web.py`, y **`make web` ya lo lanza así**.
- **Sigue pendiente B5:** el modelo se carga por sesión de navegador; se resuelve en la reescritura de la web (Fase 6).

### 2.7 Revisión de código muerto (a petición tuya)

Tras las reestructuraciones (ingesta a `src/ingestion/`, flujo único en `src/rag.py`, fin del modo `generation`) se revisó el código con **`vulture`** (análisis estático, ejecutado puntualmente con `uvx`, sin añadirlo al proyecto) y se comprobó a mano cada hallazgo.

**Eliminado:**

| Qué | Por qué |
|---|---|
| `Embedder.dimension` | Nunca se usó (la dimensión se lee del propio vector) |
| `Generator.MODEL_NAME` | El modelo viene ahora de `[generation]` en `rag.toml` |
| `Generator(repo_root=…)` | Se mantenía "por compatibilidad", pero ya nadie lo pasaba |
| `Retriever.search_no_rerank()` | Era un alias de `search()`; queda solo `search()` |
| `bench --mode` y `MODES` | Desde que se unificaron las rutas solo quedaba `smart`. Se mantiene `"mode": "smart"` en los resultados para no romper la comparación con los 90 ya guardados |
| Copias de `build_context_blocks` / `is_not_found` en la CLI y la web | Sustituidas por el flujo único (`src/rag.py`) |

**Convertido en algo útil:** `TOKEN_MODES` describía los modos válidos de `code_aware_tokens`, pero nada los comprobaba. Ahora el tipo de la configuración es `Literal[...]`, así que un valor mal escrito (`"cod"`) da un error claro en lugar de comportarse como `"none"` sin avisar.

**Se queda, aunque `vulture` lo marca:**
- Los comandos de la CLI (`search_dataset`, `evaluate`, `bench`…): Fire los invoca por nombre.
- `max_context_length` en `evaluate`: compatibilidad con la llamada de la moulinette de 42.
- `question_str`: formato JSON de 42.
- `Chunk.modality`: se guarda en Qdrant y es la base de la Fase 4b.
- `available_profiles`: lista para el selector de la web (Fase 6), con test.

**Documentación desactualizada corregida:** la docstring de `Retriever` describía `search_for_generation` como "BM25 + reranker over the unified index", que era la ruta antigua.

**Verificado:** recall idéntico a `49-fase2-final` (`52-deadcode-check`), 58 tests, lint limpio, y `search` y `answer` probados desde la CLI.

### 2.8 LLM opcionales y juez

- **`[generation]` en `rag.toml`:** modelo, `max_new_tokens`, `max_input_tokens` y `trust_remote_code`. La base es `Qwen/Qwen3-0.6B`. **Todos los modelos se cargan a través de `llm_sdk`** (que acepta `model_name`), sin tocar la carpeta del SDK.
- **El generador ya no da por hecho que el modelo es Qwen:** los tokens de fin de respuesta se toman de la configuración de cada modelo (antes estaba fijo `<|im_end|>`).
- **Perfiles** (decisión tuya tras la comparativa): `llm-qwen3-1.7b`, `llm-qwen3-4b` y `llm-phi4-mini`. **SmolLM3-3B, medido y descartado.** Resultados en `docs/BENCHMARK_REPORT.md` §5.
- **Dos problemas resueltos al medir:**
  - **Phi-4-mini:** el código de su repositorio importa nombres que ya no existen en transformers 5 (`LossKwargs`). Con `trust_remote_code = false` se usa la implementación nativa de transformers (arquitectura `phi3`).
  - **Qwen3-4B:** no cabe en 12 GB junto con `bge-m3` y el reranker (accelerate intenta mover parte del modelo a la CPU y el SDK no lo permite). Su perfil pone la recuperación en CPU, que ya se comprobó que da los mismos resultados.
- **Juez (`src/judge.py`, `make judge LABEL=…`):**
  - LLM como juez sobre una API compatible con OpenAI (Groq, `openai/gpt-oss-120b`), con nota 0–2 frente a la respuesta de referencia de 42.
  - **Solo se ejecuta a petición**, sobre las respuestas ya guardadas por `gen-bench`; el programa normal nunca lo usa.
  - **Ahorro de cuota:** caché en disco (`data/output/judge_cache.json`), las respuestas "no encontrado" no se envían, pausa entre peticiones y reintentos ante 429. En total, unas 190 llamadas para comparar los cinco modelos.
  - Lee `JUDGE_BASE_URL`, `JUDGE_MODEL` y `GROQ_API_KEY` del `.env` (ignorado por git); la clave nunca se imprime. Sin dependencias nuevas (`urllib`).
  - **Resuelve el problema del F1 en español:** el juez evalúa el significado, no el idioma.

### 2.8 bis Regla de "dónde" (añadida en el checkpoint)

**Regla 5 del prompt:** *"If the question asks where to find something, give the file path shown in that source's header."* La razón y la medición están en `CHECKPOINT_42.md` §3: el juez de docs EN sube de 1.00 a 1.30.

### 2.9 Evaluadores agrupados en `src/evaluation/`

- `evaluator.py` (recall de 42), `bench.py`, `gen_bench.py` y `judge.py` pasan de `src/` a **`src/evaluation/`**: se distingue a simple vista qué es el RAG y qué son las herramientas para medirlo. Movidos con `git mv` para conservar el historial; `judge.py` era nuevo y se movió normalmente.
- **Sin cambios de comportamiento:** los comandos (`make bench`, `make gen-bench`, `make judge`, `evaluate`/`search_dataset` de 42) son los mismos. Verificado con el recall idéntico a `49` (`53-evaluation-package`), los comandos de 42, el juez (con 0 llamadas a la API gracias a la caché), 61 tests y lint limpio.

---

## 3. Ficheros

| Fichero | Cambio |
|---|---|
| `src/rag.py` | **Nuevo**: `RagPipeline`, `RagAnswer`, `build_context_blocks` |
| `src/evaluation/gen_bench.py` | **Nuevo**: benchmark de generación |
| `src/evaluation/judge.py` | **Nuevo**: juez LLM (Groq), con caché |
| `src/evaluation/` | `evaluator.py` y `bench.py` movidos aquí (§2.9) |
| `src/language.py` | **Nuevo**: detección de idioma (es/en) |
| `src/generator.py` | Chat template oficial, fuentes `[n]`, idioma, presupuesto en tokens, `clean_output`, `stream_answer` |
| `src/retriever.py` | Filtro de relevancia con el reranker (`top_relevance`) |
| `src/config.py`, `rag.toml` | `relevance_threshold = 0.0`; `[generation]`; perfiles `llm-qwen3-1.7b`, `llm-qwen3-4b` y `llm-phi4-mini`; `code_aware_tokens` validado |
| `src/cli.py` | `answer`/`answer_dataset` vía `RagPipeline`, streaming, `gen_bench` |
| `src/bench.py`, `Makefile` | Fuera el modo `generation` y `bench-gen`; añadido `gen-bench`; `make web` con `python -m streamlit` |
| `src/web.py` | `RagPipeline` + streaming; respuesta escapada (B6) |
| `bench/datasets/ood/questions.json` | **Nuevo**: set fuera de dominio |
| `tests/test_generator.py`, `tests/test_gen_bench.py`, `tests/test_judge.py` | **Nuevos** |
| `llm_sdk/**` | **Sin tocar** |

**Tests:** 61. Lint limpio.

---

## 4. Pendiente en la Fase 3

1. ~~`make web` con `python -m streamlit`~~ → hecho.
2. ~~Capa de LLM y perfiles opcionales~~ → hecho (§2.8).
3. ~~Comparativa de LLMs con juez~~ → hecho (§2.8 y `BENCHMARK_REPORT.md` §5).
4. ~~Cierre: `BENCHMARK_REPORT.md` y roadmap~~ → hecho.

**Para revisar contigo:**
- **Modelo recomendado en la web:** se decide en la Fase 6.
- **Velocidad en CPU de los LLM opcionales:** no medida. Te parece aceptable que aumente.
- **Las 2 preguntas legítimas de code que rechaza el filtro** (§2.3): si se quieren recuperar, el umbral es configurable (`relevance_threshold`).
