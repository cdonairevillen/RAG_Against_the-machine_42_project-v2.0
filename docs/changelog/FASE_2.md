# CHANGELOG — Fase 2: Retrieval híbrido

**Fecha de inicio:** 2026-10-18
**Estado:** 🟡 en curso.
- **Paso 1** (recuperar code y unificar rutas): completado, commit `acab947`.
- **Paso 2** (tokenizador code-aware, B8 + B14): completado, sin commit (ver §6).

**Prioridad de métricas: R@5 > R@10 > R@3 > R@1.**

---

## 1. Resultado del paso 1

Datasets públicos de 42, `k = 10`, evaluador original. Las ejecuciones están en `bench/results/` y cada una registra sus parámetros de recuperación y el dispositivo.

| Ejecución | Qué se prueba | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|
| `20-fix-b16-b17-v2` | Línea base (cierre Fase 1) | 0.67 / 0.84 / 0.87 / 0.89 | 0.43 / 0.59 / 0.64 / 0.71 |
| `21-cuda-check` | Igual, con el reranker en GPU | idéntico | idéntico |
| `22-sin-gpu` | Igual, con la GPU oculta (simula 42) | idéntico | idéntico |
| `23-skip-rerank-1000` | Reranker siempre activo, orden del reranker | 0.73 / 0.90 / 0.93 / 0.95 | 0.44 / 0.59 / 0.62 / 0.67 |
| `25-rrf-skip-1000` | Fusión RRF ingenua (una sola lista) | 0.64 / 0.79 / 0.83 / 0.90 | 0.46 / 0.64 / 0.68 / 0.72 |
| `26-rrf3-skip-1000` | **RRF por listas** (BM25 code + BM25 docs + reranker) | 0.72 / 0.90 / 0.93 / 0.95 | 0.45 / 0.63 / 0.67 / 0.72 |
| **`29-rrf-default` smart** | **Estado actual (config por defecto)** | **0.72 / 0.90 / 0.93 / 0.95** | **0.45 / 0.63 / 0.67 / 0.72** |
| **`29-rrf-default` generation** | Ruta de la web, ya unificada | **0.72 / 0.90 / 0.93 / 0.95** | **0.45 / 0.63 / 0.67 / 0.71** |

**Neto en la ruta oficial frente a la línea base:**
- **Docs:** +0.05 / +0.06 / +0.06 / +0.06.
- **Code:** +0.02 / +0.04 / +0.03 / +0.01.

Mejora **en todos los cortes de los dos datasets**, y code supera también a la Fase 0 (0.45 / 0.62 / 0.64 / 0.72).

**Ruta de la web frente a cómo estaba:**
- **Docs:** 0.69 / 0.85 / 0.89 / 0.93 → 0.72 / 0.90 / 0.93 / 0.95.
- **Code:** 0.25 / 0.53 / 0.66 / 0.72 → 0.45 / 0.63 / 0.67 / 0.71. R@1 casi se duplica; R@10 baja 0.01 (ver §2.5).

---

## 2. Qué se ha cambiado y por qué

### 2.1 CUDA, sin depender de él

- **torch con CUDA 12.6** (índice `pytorch-cu126` en `pyproject.toml`). Se elige 12.6 porque funciona con drivers antiguos, lo que importa para los ordenadores de 42, cuya GPU no conocemos.
  - El índice de CUDA trae **torch 2.14.1** (PyPI tenía la 2.12.1).
  - torch se declara como dependencia directa del proyecto solo para elegir el build. `llm_sdk` no se toca.
- **`accelerate`** añadido: `llm_sdk` carga Qwen con `device_map="auto"` cuando hay GPU, y transformers lo exige. Sin GPU no se usa.
- **`[models] device = "auto"`** en `rag.toml`: CUDA si hay GPU y CPU si no. Se fuerza con `RAG_MODELS_DEVICE=cpu`.
- **Probado sin GPU:**
  - Ocultando la tarjeta con `CUDA_VISIBLE_DEVICES=-1`, el benchmark sale **idéntico** y `answer` funciona.
  - Ojo: en Windows, `CUDA_VISIBLE_DEVICES=""` **no** oculta la GPU, porque Windows elimina las variables vacías. Mi primera prueba no era válida por eso.
- **Velocidad:** code tarda 3 s con el reranker en GPU, frente a 36–40 s en CPU. Resultados idénticos en ambos.

### 2.2 Parámetros de recuperación en la configuración

- `classifier_margin`, `code_signal_weight`, `doc_signal_weight`, `skip_rerank_score`, `bm25_score_floor`, `reranker_model`, `rerank_fusion` y `rrf_k` pasan de constantes en el código a la sección `[retrieval]` de `rag.toml`.
- Se pueden barrer con variables de entorno (`RAG_RETRIEVAL_SKIP_RERANK_SCORE=12 make bench`).
- Verificado que, con los valores antiguos, la salida es idéntica a `20`.

### 2.3 El umbral para saltarse el reranker afectaba sobre todo a docs

- El barrido de `skip_rerank_score` (0, 6, 9, 12, 15, sin límite) mostró que **docs sube 6 puntos** si siempre se reranquea:
  - Muchas preguntas de docs se clasifican como code y van por la rama de code.
  - Ahí, el reranker es lo que sube los 4 documentos de respaldo al top.
- Pero en code, el orden del reranker (`ms-marco`, entrenado con texto web) es **peor que el de BM25** (R@10 0.71 → 0.67).

### 2.4 Fusión RRF por listas (la solución)

- **`rerank_fusion = "rrf"`:** en vez de sustituir el orden de BM25 por el del reranker, se fusionan ambos con *Reciprocal Rank Fusion*. Un candidato que BM25 pone arriba no se hunde si el reranker duda, y uno que el reranker sube puede entrar.
- **Por listas:** los candidatos de code y los documentos de respaldo vienen de **dos rankings BM25 distintos**, y cada uno conserva su propio puesto en la fusión.
  - La versión ingenua (`25`), con una sola lista, ponía los documentos en los puestos 31–34 y **hundía docs** (R@5 0.83).
- **`skip_rerank_score = inf`:** con la fusión, reranquear siempre es lo mejor.
- **Pregunta a pregunta, frente a `20`:**
  - **Docs:** mejoran 8 y empeora 1 (del 1.º al 2.º).
  - **Code:** mejoran 17 y empeoran 10, casi todas uno o dos puestos; se pierde una que estaba 9.ª.
- **Tests:** tres nuevos con un reranker falso (orden por sustitución, equilibrio RRF con el orden exacto esperado y uso de puestos por lista).

### 2.5 Rutas unificadas (pendiente desde la Fase 1)

- **`search_for_generation`** (la de la web y `answer`) pasa a ser: **filtro de relevancia + `search_smart`**. Antes tenía su propia lógica (forzar 2 documentos arriba y reranquear todo junto), que daba code R@1 0.25.
- Con la fusión RRF, la lógica antigua además hundía code R@1 a 0.13 (`27-gen-rrf3`), lo que confirmó que convenía unificar.
- **Única diferencia entre las dos rutas:** el filtro de relevancia (`bm25_score_floor = 5.5`), que descarta **2 preguntas legítimas de code**. Por eso la ruta de la web tiene code R@10 0.71 frente a 0.72.

### 2.6 El filtro de relevancia BM25 no sirve (se deja para la Fase 3)

| Pregunta | Puntuación BM25 máx. | ¿Pasa el umbral 5.5? |
|---|---|---|
| "…what endpoint … LoRA adapter in vLLM?" (legítima) | 13.56 | sí ✅ |
| "**What is the capital of France?**" (fuera de dominio) | **12.28** | **sí ❌** |
| "Who won the 2018 football World Cup?" (fuera de dominio) | 7.93 | sí ❌ |
| "…min_dynamic_patch … NemotronVL…" (legítima) | 5.40 | **no ❌** |
| "…max_position_embeddings … ChameleonSwinDecoderLayer?" (legítima) | 4.96 | **no ❌** |
| "How do I bake a chocolate cake?" (fuera de dominio) | 4.22 | no ✅ |

- Falla en las dos direcciones.
- **No se cambia aún:** quitarlo haría que preguntas como la de la tarta llegaran a Qwen, que hoy responde con su propio conocimiento (B15).
- Se sustituye en la **Fase 3** por una señal mejor, como la puntuación del reranker o un guardarraíl en la generación. Solo afecta a la ruta de la web, no al benchmark oficial.

---

## 3. Lista de ficheros (paso 1)

| Fichero | Cambio |
|---|---|
| `pyproject.toml`, `uv.lock` | torch con CUDA 12.6 (índice `pytorch-cu126`), `accelerate` |
| `rag.toml` | Secciones `[models]` y `[retrieval]`; RRF y reranker siempre activo por defecto |
| `src/config.py` | `RetrievalConfig`, `ModelsConfig` (`device = auto`) y sus overrides por entorno |
| `src/retriever.py` | Parámetros desde la config; reranker en el dispositivo configurado; fusión RRF por listas; `search_for_generation` unificada con `search_smart` |
| `src/bench.py` | Registra los parámetros de recuperación y el dispositivo de cada ejecución |
| `tests/test_retriever.py` | Tests de fusión con reranker falso |
| `bench/results/*.json` | Ejecuciones 21–29 |
| `llm_sdk/**` | **Sin tocar** |

**Tests:** 38. Lint limpio.

---

## 4. Qué debes saber de la arquitectura

- **Un único ranking** para el benchmark, la CLI y la web (`search_smart`); la web solo añade el filtro de relevancia.
- **El código de la ruta antigua de generación se ha eliminado** (sigue en git y en `v1.0-42`).
- **Reproducibilidad CPU frente a GPU:** con el reranker actual, las salidas son idénticas. Con modelos mayores podría haber diferencias mínimas en empates; `bench` registra el dispositivo usado.

---

## 5. Pendiente en la Fase 2

1. ~~**Tokenizador code-aware (B8) + descomposición de identificadores (B14)**~~ → hecho (§6).
2. **Embeddings** multilingües de chunks y consulta en Qdrant, fusionados con BM25: `multilingual-e5-small`, `bge-m3`, `Qwen3-Embedding-0.6B`. Se medirán en CPU y en GPU.
3. **Rerankers:** `ms-marco` (actual), `bge-reranker-v2-m3` y `Qwen3-Reranker-0.6B`.
4. Revisar el clasificador doc/code (`classifier_margin` y pesos), que sigue enviando preguntas de docs a la rama de code.
5. `docs/BENCHMARK_REPORT.md` con la comparativa de modelos.

---

## 6. Paso 2: tokenizador code-aware (B8 + B14)

### Resultado

| Ejecución | Modo | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|
| `29-rrf-default` | sin descomposición (antes) | 0.72 / 0.90 / 0.93 / 0.95 | 0.45 / 0.63 / 0.67 / 0.72 |
| `30-tokens-none` | `none` (refactor, **idéntico** a `29`) | 0.72 / 0.90 / 0.93 / 0.95 | 0.45 / 0.63 / 0.67 / 0.72 |
| `31-tokens-query` | `query`: solo la consulta (el B14 original) | 0.71 / 0.89 / 0.93 / 0.96 | 0.45 / 0.62 / 0.67 / 0.75 |
| `33-tokens-both` | `both`: corpus y consulta (B8 + B14) | 0.74 / 0.89 / 0.92 / 0.93 | 0.48 / 0.69 / 0.74 / 0.81 |
| `33-tokens-code` | `code`: solo chunks e índices de code | 0.72 / 0.90 / 0.92 / 0.94 | 0.50 / 0.71 / 0.76 / 0.84 |
| **`35-tokens-code-default`** | **`code` + clasificador sin descomponer** (por defecto) | **0.72 / 0.91 / 0.93 / 0.94** | **0.49 / 0.70 / 0.75 / 0.83** |

**Neto frente a `29`:**
- **Docs:** R@5 igual, R@3 +0.01, R@10 −0.01 (una pregunta).
- **Code:** **+0.04 / +0.07 / +0.08 / +0.11**.
- **La ruta de la web da ahora exactamente lo mismo que la oficial:** las dos preguntas legítimas que bloqueaba el filtro de relevancia (§2.6) lo superan, porque con las partes de los identificadores puntúan más alto.

### Qué se ha cambiado

- **`src/ingestion/tokens.py` (nuevo):** un único punto de tokenización para el corpus y la consulta, de modo que no puedan desincronizarse.
  - `split_identifier()`: `max_model_len` → max, model, len; `PagedAttention` → paged, attention; `RMSNorm` → rms, norm.
  - Se **conservan los identificadores originales**, así que las coincidencias exactas siguen contando.
  - `vLLM` se excluye: partirlo añadía "llm" a casi todo el corpus. Es la misma trampa que vimos en la Fase 0 con el clasificador.
- **`code_aware_tokens`** en `[retrieval]`, con cuatro modos medidos (`none`, `query`, `both`, `code`). Por defecto, **`code`**:
  - Las partes se añaden **solo a los chunks de código**; en la documentación eran sobre todo ruido (`both` bajaba docs R@10 −0.02).
  - La consulta se descompone al buscar en el índice de code y en el general, **nunca en el de docs**.
- **El clasificador doc/code usa la consulta sin descomponer** en los dos índices. Con las partes, el índice de code puntuaba más alto en general y enviaba preguntas de docs a la rama de code (`33-tokens-code`: docs R@5 0.92). Con la consulta sin descomponer, docs R@5 vuelve a 0.93.
- **Seguridad:** el manifest registra a qué chunks se añadieron partes (`identifier_parts`), y el retriever **se niega a arrancar** si no coincide con `code_aware_tokens` ("Run 'make index' again"). El test de integración lo detectó al cambiar el valor por defecto, que es justo para lo que está.

### Pregunta a pregunta (`29` → `35`)

- **Code:** mejoran 24 y empeoran 16. Se pierden 4 que estaban entre el 3.º y el 10.º puesto; el resto se mueve unos pocos puestos.
- **Docs:** cambian 3. La que se pierde (*"Where can I find information about using generative models in vLLM?"*, antes 6.ª) es un **fallo del clasificador**, no de la tokenización: se envía a la rama de code (code 7.41 frente a doc 6.09), donde solo entran 4 documentos de respaldo. Se revisa en el paso 4 (clasificador).
- **Decisión:** adoptado, justificado según la regla (R@5 no empeora en ningún dataset). Se revierte con `code_aware_tokens = "none"` y `make index`.

### Ficheros

| Fichero | Cambio |
|---|---|
| `src/ingestion/tokens.py` | **Nuevo**: descomposición de identificadores y tokenización común |
| `src/ingestion/pipeline.py` | El corpus BM25 añade partes según el tipo de chunk; manifest con `identifier_parts` |
| `src/retriever.py` | Tokenización por índice; clasificador con la consulta sin descomponer; comprobación del manifest |
| `src/cli.py` | `index` aplica el modo configurado |
| `src/config.py`, `rag.toml` | `code_aware_tokens = "code"` |
| `tests/test_tokens.py` | **Nuevo** (4 tests) |
| `tests/test_storage.py` | La integración indexa según la configuración |

**Tests:** 42. Lint limpio.
