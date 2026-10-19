# CHANGELOG — Fase 3: Mejoras en la generación de respuesta

**Fecha de inicio:** 2026-10-19
**Estado:** 🟡 en curso. Hecho: benchmark de generación, prompt nuevo, guardarraíl fuera de dominio (B15), flujo de respuesta unificado y streaming. Pendiente: capa de LLM con modelos opcionales, comparativa de LLMs y juez.

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

---

## 3. Ficheros (hasta ahora)

| Fichero | Cambio |
|---|---|
| `src/rag.py` | **Nuevo**: `RagPipeline`, `RagAnswer`, `build_context_blocks` |
| `src/gen_bench.py` | **Nuevo**: benchmark de generación |
| `src/language.py` | **Nuevo**: detección de idioma (es/en) |
| `src/generator.py` | Chat template oficial, fuentes `[n]`, idioma, presupuesto en tokens, `clean_output`, `stream_answer` |
| `src/retriever.py` | Filtro de relevancia con el reranker (`top_relevance`) |
| `src/config.py`, `rag.toml` | `relevance_threshold = 0.0` |
| `src/cli.py` | `answer`/`answer_dataset` vía `RagPipeline`, streaming, `gen_bench` |
| `src/bench.py`, `Makefile` | Fuera el modo `generation` y `bench-gen`; añadido `gen-bench`; `make web` con `python -m streamlit` |
| `src/web.py` | `RagPipeline` + streaming; respuesta escapada (B6) |
| `bench/datasets/ood/questions.json` | **Nuevo**: set fuera de dominio |
| `tests/test_generator.py`, `tests/test_gen_bench.py` | **Nuevos** |
| `llm_sdk/**` | **Sin tocar** |

**Tests:** 58. Lint limpio.

---

## 4. Pendiente en la Fase 3

1. ~~`make web` con `python -m streamlit`~~ → hecho.
2. Capa de LLM: Qwen3-0.6B vía `llm_sdk` como base, y modelos opcionales como perfiles (como en la Fase 2).
3. Comparativa de LLMs (Qwen3-1.7B / 4B, SmolLM3-3B, Phi-4-mini) en la 3080 Ti, con el juez `openai/gpt-oss-120b` (Groq) como complemento, con caché y pocas preguntas para no gastar la cuota gratuita.
4. Cierre: `BENCHMARK_REPORT.md` (sección de generación) y roadmap.
