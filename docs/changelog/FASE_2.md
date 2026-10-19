# CHANGELOG — Fase 2: Retrieval híbrido

**Fecha de inicio:** 2026-10-18
**Estado:** ✅ completada (2026-10-19).
- **Paso 1** (recuperar code y unificar rutas): commit `acab947`.
- **Paso 2** (tokenizador code-aware, B8 + B14): commit `1a91f74` (§6).
- **Pasos 3–5** (embeddings, rerankers, clasificador) y cierre: commit "Autosave" (§7–§11). Hechos de forma autónoma con tu autorización, para que los revises.

> **Resumen de la fase (ruta oficial):**
> - **Docs R@5:** 0.87 → **0.92**.
> - **Code R@5:** 0.64 → **0.80**.
> - **Code R@10:** 0.71 → **0.88**.
>
> Todas las comparativas de modelos están en `docs/BENCHMARK_REPORT.md`.

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

## 5. Plan de la fase tras el paso 1 (todo resuelto)

1. ~~Tokenizador code-aware (B8 + B14)~~ → §6 y §7.
2. ~~Embeddings multilingües en Qdrant, medidos en CPU y en GPU~~ → §8 (`bge-m3`).
3. ~~Rerankers~~ → §9 (`mmarco`; `Qwen3-Reranker` descartado y `bge-reranker-v2-m3` pendiente de medir el recall).
4. ~~Clasificador doc/code~~ → §10.
5. ~~`docs/BENCHMARK_REPORT.md`~~ → creado.

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

---

## 7. Paso 2 (revisión): modos de tokenización con clasificador neutral

A raíz de tu pregunta ("¿por qué no hay un modo solo para docs?"):

- **Error mío corregido:** el clasificador usaba la tokenización "de docs" pensando que siempre sería la consulta sin descomponer, y eso solo es cierto en el modo `code`. Ahora usa **siempre** la consulta sin descomponer, sea cual sea el modo. En el modo `code` (el de por defecto), el resultado es idéntico (`39-tokens-code-plain-classifier` = `36`).
- **Modo `doc` añadido** (partes de identificadores solo en chunks e índice de docs) y medido. Comparación justa, sin embeddings:

| Modo | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| **`code`** (por defecto) | 0.72 / **0.91 / 0.93** / 0.94 | 0.49 / 0.70 / 0.75 / **0.83** |
| `both` | **0.73** / 0.88 / 0.92 / 0.94 | 0.49 / 0.70 / 0.75 / 0.82 |
| `doc` | 0.72 / 0.87 / 0.92 / 0.94 | 0.42 / 0.61 / 0.65 / 0.69 |

- **Conclusión:** añadir partes de identificadores a la documentación empeora docs (R@3 −0.03/−0.04, R@5 −0.01). Se mantiene `code`.

---

## 8. Paso 3: embeddings (búsqueda híbrida)

### Qué se ha implementado

- **`src/embeddings.py` (nuevo):** `Embedder` con los prompts correctos de cada familia, verificados en Hugging Face:
  - E5: `query: ` y `passage: `.
  - Qwen3: el prompt `query` declarado por el modelo.
  - bge-m3: sin instrucciones.
  - El mismo modelo y la misma normalización para documentos y consultas, que era lo que fallaba en la v1 (allí se cruzaban índices de dos listas distintas).
- **Qué se embebe:** los **chunks hijo** (la misma unidad que BM25), como "ruta + texto". La consulta se embebe **sin expandir**.
- **Qdrant:** los vectores van como **vector con nombre** en los mismos puntos de `rag_vllm` (un nombre por modelo, distancia coseno). Búsqueda filtrada por nivel (`child`) y tipo (`code`/`doc`).
- **Fusión:** dentro de cada lista (candidatos de code y documentos de respaldo, o lista de docs), BM25 y vectores se fusionan con **RRF** (`rrf_merge`) antes del reranker.
- **Seguridad:** el manifest registra `embedding_model`, y el retriever se niega a arrancar si la configuración usa otro modelo.
- **`[embeddings]`** en `rag.toml`: `enabled`, `model`, `batch_size`, `dense_k` y `dense_in_doc_branch`. En el código está **desactivado por defecto**, para que los tests y los entornos ligeros no descarguen 2 GB; `rag.toml` lo activa.

### Resultados y decisión

Todas las tablas están en `docs/BENCHMARK_REPORT.md` §1. En resumen:
- **`bge-m3`** es el mejor en el benchmark oficial: code R@10 0.86, frente a 0.84 de e5-small y 0.83 de Qwen3, con R@5 empatado a 0.79.
- **Docs en español sin embeddings cae a R@10 0.50**; con `bge-m3`, 0.90.
- **Velocidad en CPU:** `bge-m3` tarda unas 2 h en indexar el corpus (estimado) y 141 ms por consulta. `Qwen3-Embedding` es inviable sin GPU (~19 h de indexado y 0,8 s por consulta). `e5-small` es la **alternativa para máquinas sin GPU** (~13 min).
- **Embeddings en las dos ramas** (tu decisión): en docs cambian −0.01 de R@5 por +0.03 de R@1 y +0.01 de R@3, y aportan la capacidad multilingüe.

### Set complementario multilingüe (nuevo)

- **`bench/datasets/es/`:** 20 preguntas de los datasets públicos (una de cada diez: 10 docs y 10 code), traducidas por mí al español con el **mismo ground truth** y el mismo `question_id`. Los nombres de código se dejan tal cual.
- **`bench/datasets/en/`:** las mismas 20 en inglés, para comparar sobre el mismo subconjunto.
- `make bench` admite `--suite public|en|es`, y cada ejecución registra su `suite`.
- **Cada pregunta vale 0.10**: las diferencias de 0.10 son una sola pregunta. Es un set complementario (D4); los recalls oficiales siguen siendo solo los de 42.

---

## 9. Paso 4: rerankers

Todas las tablas están en `docs/BENCHMARK_REPORT.md` §2.

- **Medidos:** `ms-marco-MiniLM-L-6-v2` (v1, solo inglés), `mmarco-mMiniLMv2-L12-H384-v1` (multilingüe, 118M) y la latencia de `bge-reranker-v2-m3` (multilingüe, 568M).
- **Descartados sin medir el recall:**
  - `jina-reranker-v2-base-multilingual`, por su licencia **CC-BY-NC-4.0** (no comercial).
  - `Qwen3-Reranker-0.6B`, según tu criterio: necesita un adaptador propio y es pesado; solo compensaría con un beneficio muy alto. Queda en *Posibilidades*.
- **`bge-reranker-v2-m3`:** la primera ejecución se detuvo por falta de memoria del sistema. **Relanzada después (`46`), en primer plano:**
  - **Resultado:** code **0.52 / 0.83 / 0.86 / 0.87** (R@5 +0.06 y R@3 +0.11 frente a `mmarco`; R@10 −0.01); docs 0.78 / 0.92 / 0.92 / 0.94.
  - **Coste:** 439 s el dataset de code (~4,4 s por pregunta en GPU) y ~23 s por consulta en CPU.
  - **Memoria:** pico de memoria comprometida de 39,1 GB sobre 67,9 GB; la causa de la primera parada no se ha podido determinar.
  - **Decisión (tuya):** perfil opcional `gpu-quality`; `mmarco` sigue en la base (§12).
- **Rerank en la rama de docs** (`rerank_doc_branch`): sigue perjudicando con los dos rerankers medidos; se queda desactivado.
- **Decisión: `mmarco-mMiniLMv2-L12` por defecto.** En el benchmark oficial empata en R@5 y gana en R@10 de code (+0.02); en español, docs R@5 pasa de 0.70 a 0.90. Cuesta el doble que `ms-marco`, pero sigue siendo viable en CPU (1,8 s por consulta).

---

## 10. Paso 5: clasificador doc/code

Tablas en `docs/BENCHMARK_REPORT.md` §3.

- **Diagnóstico medido:** el clasificador enviaba a la rama de code **25 de 100** preguntas de docs oficiales y **10 de 10** de docs en español. Las señales de "pregunta de documentación" estaban solo en inglés y se comparaban sin quitar la puntuación (`¿cómo` nunca coincidía).
- **Cambios:**
  - Señales en español (`DOC_SIGNAL_TERMS_ES`), seleccionables con `doc_signal_languages = ["en", "es"]`.
  - Limpieza de puntuación, incluidos `¿` y `¡`.
- **Resultado:** docs oficial **+0.01 en R@1, R@3 y R@5, con code idéntico** (mejora estricta). Enrutado: docs oficial 23/100 y docs ES 8/10 mal enrutadas.
- **Pesos y margen sin cambios:** cada pregunta de docs que se deja de mandar a code se paga con preguntas de code mal enrutadas (code R@5 hasta 0.66).
- ⚠️ **En el set español**, docs pierde una pregunta en R@3 y R@5 (0.90 → 0.80): dos preguntas pasan a la rama de docs, que no tiene reranker, y una sale peor. Se acepta porque el benchmark de referencia es el oficial.
- **Límite:** el clasificador léxico no da más de sí. Un clasificador semántico, aprovechando los embeddings, queda como mejora futura.

---

## 11. Cierre de la fase

### Resultado final (`49-fase2-final`)

| Set | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| **Oficial (42)** (smart y generation, idénticos) | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |
| Español (20) | 0.60 / 0.80 / 0.80 / 0.90 | 0.50 / 0.70 / 0.80 / 0.90 |

### Ficheros (pasos 3–5)

| Fichero | Cambio |
|---|---|
| `src/embeddings.py` | **Nuevo**: `Embedder`, prompts por modelo, nombre del vector |
| `src/storage/base.py`, `src/storage/qdrant_store.py` | Vectores con nombre y `search_dense` filtrado |
| `src/retriever.py` | `rrf_merge`, búsqueda densa en las dos ramas, `load_embedder` (comprueba el manifest), rerank opcional en la rama de docs, clasificador siempre neutral y con señales en inglés y español |
| `src/ingestion/pipeline.py` | Manifest con `embedding_model` |
| `src/ingestion/tokens.py` | Modo `doc` |
| `src/cli.py` | `index` embebe los hijos si los embeddings están activos; `bench --suite` |
| `src/bench.py` | Sets `public` / `en` / `es` |
| `src/config.py`, `rag.toml` | `[embeddings]`; reranker `mmarco`; `rerank_doc_branch`; `doc_signal_languages` |
| `bench/datasets/en/`, `bench/datasets/es/` | **Nuevos**: set complementario de 20 preguntas |
| `tests/test_dense.py` | **Nuevo**: `rrf_merge`, prompts y búsqueda densa con Qdrant en memoria |
| `tests/test_retriever.py`, `tests/test_tokens.py` | Clasificador en español; modo `doc` |
| `docs/BENCHMARK_REPORT.md` | **Nuevo** |
| `bench/results/*.json` | Ejecuciones 36–49 |
| `llm_sdk/**` | **Sin tocar** |

**Tests:** 47. Lint limpio.

### Qué debes saber de la arquitectura

- **Indexar ahora embebe 37 381 hijos con `bge-m3`:** ~6 min en la 3080 Ti y **~2 h en CPU** (estimado). En máquinas sin GPU, la alternativa es `RAG_EMBEDDINGS_MODEL=intfloat/multilingual-e5-small make index` (~13 min).
- **Cambiar de modelo de embeddings obliga a reindexar**; el retriever lo exige mediante el manifest.
- **RAM:** con `bge-m3` y el reranker cargados, el proceso usa varios GB. Una medición pesada (`bge-reranker-v2-m3`) se paró por falta de memoria del sistema.
- **Lo que la fase no ha resuelto:**
  - El clasificador sigue enviando 23 de 100 preguntas de docs a code (léxico en su límite).
  - El filtro de relevancia BM25 (B15) pasa a la Fase 3.
- **Prueba de punta a punta:** `answer "¿Qué endpoint HTTP se usa para cargar dinámicamente un adaptador LoRA en vLLM?"` encuentra `lora.md` y responde bien, **pero en inglés**: el prompt no pide contestar en el idioma de la pregunta. Pasa a la Fase 3.

### Pendiente para revisar contigo

1. ~~`bge-reranker-v2-m3`~~ → resuelto: perfil opcional `gpu-quality`, con `mmarco` en la base (§12).
2. ~~¿`bge-m3` aunque indexar en CPU lleve ~2 h?~~ → resuelto: `bge-m3` en la base (resultados estables) y perfil `cpu-light` con `e5-small` (§12). El índice preconstruido sigue en *Posibilidades*.
3. **La pregunta de docs en español** que empeora con el clasificador nuevo (§10).

---

## 12. Perfiles: base estable y modelos extra como opciones

**Tu criterio:** el sistema debe comportarse igual en cualquier ordenador; los modelos extra son opciones y en la web podrían ofrecerse con selectores (ingesta, reranker, embeddings). Eso se planteará en su fase.

- **Base estable:** lo que hay en `rag.toml` fuera de `[profiles.*]` (`bge-m3` + `mmarco`). Es lo que usa el benchmark oficial y **no cambia según la máquina** (no hay selección automática por GPU), así que los números son reproducibles y comparables con otros RAG de 42.
- **Perfiles** (`[profiles.<nombre>]` en `rag.toml`): solo sobrescriben lo que declaran.
  - **Cómo se elige:** `--profile <nombre>`, `RAG_PROFILE=<nombre>` o `make <target> PROFILE=<nombre>`.
  - **Precedencia:** variables de entorno > perfil > base de `rag.toml` > valores por defecto del código.
  - **`gpu-quality`:** reranker `bge-reranker-v2-m3` (code R@5 0.86 frente a 0.80, pero ~4,4 s por pregunta en GPU y ~23 s en CPU).
  - **`cpu-light`:** embeddings `e5-small`, para indexar sin GPU en ~13 min en lugar de ~2 h. Necesita `make index PROFILE=cpu-light`; el manifest impide mezclar índices.
- **`bench` registra el perfil** de cada ejecución, y la configuración expone `available_profiles`, que es lo que necesitaría un selector en la web (Fase 6).
- **Verificación:** la base da resultados idénticos a `49-fase2-final` (`50-base-check`). Tests: 51 (+4 de perfiles).
- **Ficheros:** `src/config.py` (`deep_merge`, perfiles en `load_config`), `src/cli.py` (`--profile`), `src/bench.py`, `Makefile` (`PROFILE=`), `rag.toml`, `tests/test_config.py`.
