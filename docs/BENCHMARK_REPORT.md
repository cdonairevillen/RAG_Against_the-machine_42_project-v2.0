# BENCHMARK REPORT — RAG Against the Machine v2.0

Comparativa de modelos y configuraciones del pipeline, con las mismas reglas en todas las mediciones:

- **Recall oficial:** datasets públicos de 42 (100 preguntas docs + 100 code), `k = 10`, evaluador original, ruta `search_smart` (`search_dataset`).
- **Prioridad de métricas:** R@5 > R@10 > R@3 > R@1.
- **Set complementario multilingüe:** 20 preguntas de los datasets públicos (una de cada diez: 10 docs y 10 code), en inglés (`--suite en`) y traducidas al español (`--suite es`) con el mismo ground truth. Cada pregunta vale 0.10. Sirve para medir lo que el benchmark de 42 no puede ver; **no sustituye a los recalls oficiales**.
- **Hardware:** NVIDIA RTX 3080 Ti (12 GB) y una CPU de 24 núcleos. Los tiempos en CPU de los ordenadores de 42 serán probablemente peores.
- Cada ejecución está en `bench/results/` con su configuración completa (chunking, recuperación, dispositivo).

---

## 1. Embeddings (Fase 2, paso 3)

Configuración común:
- Tokenización `code_aware_tokens = "code"`.
- Fusión RRF del reranker y reranker `ms-marco-MiniLM-L-6-v2`.
- Embeddings en las dos ramas.
- Se embeben los 37 381 chunks hijo (ruta + texto); la consulta, sin expandir y con el prefijo de cada modelo.

### 1.1 Recall oficial (datasets públicos de 42)

| Modelo | Parámetros | Dim. | Licencia | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|---|---|
| Sin embeddings (`36`) | — | — | — | 0.72 / 0.91 / **0.93** / 0.94 | 0.49 / 0.70 / 0.75 / 0.83 |
| `intfloat/multilingual-e5-small` (`37`) | 118M | 384 | MIT | 0.70 / 0.89 / 0.92 / 0.93 | 0.48 / 0.70 / **0.79** / 0.84 |
| **`BAAI/bge-m3`** (`40`) | 568M | 1024 | MIT | **0.75 / 0.92** / 0.92 / **0.94** | 0.52 / **0.71 / 0.79 / 0.86** |
| `Qwen/Qwen3-Embedding-0.6B` (`41`) | 596M | 1024 | Apache 2.0 | 0.71 / 0.90 / 0.92 / 0.94 | **0.55** / 0.66 / **0.79** / 0.83 |

**Variante `bge-m3` solo en la rama de code** (`42-bge-m3-code-branch-only`): docs 0.72 / 0.91 / 0.93 / 0.94 (igual que sin embeddings) y code igual que con embeddings en las dos ramas. Es decir, en docs los vectores cambian −0.01 de R@5 por +0.03 de R@1 y +0.01 de R@3. **Decisión (tuya): embeddings en las dos ramas**, por su valor multilingüe (§1.2).

### 1.2 Multilingüe (20 preguntas, inglés frente a español)

| Modelo | Docs EN | **Docs ES** | Code EN | Code ES |
|---|---|---|---|---|
| Sin embeddings | 0.80 / 0.90 / 1.00 / 1.00 | **0.30 / 0.50 / 0.50 / 0.50** | 0.50 / 0.80 / 0.90 / 0.90 | 0.60 / 0.80 / 0.80 / 0.90 |
| `e5-small` | 0.90 / 0.90 / 1.00 / 1.00 | 0.40 / 0.60 / 0.70 / 0.70 | 0.40 / 0.80 / 0.90 / 0.90 | 0.50 / 0.80 / 0.80 / 0.90 |
| `bge-m3` | 0.80 / 0.90 / 0.90 / 1.00 | 0.30 / 0.60 / 0.70 / **0.90** | 0.60 / 0.90 / 0.90 / 0.90 | 0.60 / 0.80 / 0.80 / 0.90 |
| `Qwen3-Embedding-0.6B` | 0.70 / 0.90 / 0.90 / 1.00 | 0.30 / 0.70 / 0.80 / 0.90 | 0.70 / 0.80 / 0.90 / 0.90 | 0.70 / 0.80 / 0.80 / 0.80 |

(Formato R@1 / R@3 / R@5 / R@10; ejecuciones `43-ml-*`.)

- **Sin embeddings, una pregunta de docs en español pierde la mitad de los aciertos** (R@10: 1.00 → 0.50): BM25 compara palabras, y "adaptador" no coincide con "adapter".
- Con `bge-m3` o Qwen3, docs en español vuelve a R@10 = 0.90.
- Code apenas cambia con el idioma: las preguntas conservan los identificadores (`get_num_new_matched_tokens`…), que BM25 sigue encontrando.
- Con 10 preguntas por set, una diferencia de 0.10 es **una sola pregunta**: Qwen3 y `bge-m3` están empatados en español.

### 1.3 Velocidad

| Modelo | Embeber el corpus en **GPU** (medido) | Embeber en **CPU** (hijos/s) | Corpus en CPU (estimado) | Consulta en CPU |
|---|---|---|---|---|
| `e5-small` | 45 s | 47.9 | ~13 min | 17 ms |
| `bge-m3` | 354 s | 5.0 | **~2 h** | 141 ms |
| `Qwen3-Embedding-0.6B` | 222 s | 0.6 | **~19 h** | 797 ms |

(CPU: muestra de 512 hijos reales; el corpus completo se extrapola a partir de ella.)

### 1.4 Decisión

**`BAAI/bge-m3` por defecto.**
- Es el mejor en el benchmark oficial con tu prioridad: code R@5 empata con los demás (0.79) y gana en R@10 (0.86 frente a 0.84 y 0.83), y docs tiene el mejor R@3.
- Es multilingüe, con docs en español a 0.90 en R@10.
- En CPU responde rápido (141 ms por consulta).
- **Su coste:** indexar sin GPU lleva unas 2 h. Para máquinas sin GPU (42) existe el perfil opcional **`cpu-light`** (`e5-small`, ~13 min en CPU: `make index PROFILE=cpu-light`), o se puede indexar en una máquina con GPU y llevar el índice ya hecho (ver *Posibilidades*).
- **Qwen3-Embedding-0.6B descartado:** no mejora a `bge-m3` en el benchmark oficial, empata en español y en CPU es inviable (19 h de indexado y 0,8 s por consulta).

---

## 2. Rerankers (Fase 2, paso 4)

### 2.1 Latencia (34 candidatos reales por consulta)

| Reranker | Parámetros | Licencia | Multilingüe | GPU | CPU |
|---|---|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L-6-v2` (v1) | 23M | Apache 2.0 | no | 57 ms | 0,9 s |
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | 118M | Apache 2.0 | sí | 97 ms | 1,8 s |
| `BAAI/bge-reranker-v2-m3` | 568M | Apache 2.0 | sí | 1,1 s | **23 s** |

- `jinaai/jina-reranker-v2-base-multilingual` se descarta por licencia (**CC-BY-NC-4.0**, no comercial).
- `Qwen3-Reranker-0.6B` no se mide: necesita un adaptador propio (se usa como LM causal), es más pesado en CPU y solo compensaría con un beneficio muy alto. Queda en *Posibilidades*.

### 2.2 Recall oficial (con `bge-m3`, fusión RRF)

| Reranker | Rerank también en la rama de docs | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|
| `ms-marco-MiniLM-L-6-v2` | no | 0.75 / **0.92 / 0.92** / 0.94 | 0.52 / 0.71 / 0.79 / 0.86 |
| `ms-marco-MiniLM-L-6-v2` | sí | 0.71 / 0.89 / 0.91 / 0.92 | 0.52 / 0.71 / 0.79 / 0.86 |
| **`mmarco-mMiniLMv2-L12`** | no | 0.75 / 0.90 / 0.91 / 0.94 | 0.51 / **0.72 / 0.80 / 0.88** |
| `mmarco-mMiniLMv2-L12` | sí | 0.70 / 0.88 / 0.90 / 0.93 | 0.51 / 0.72 / 0.80 / 0.88 |
| `bge-reranker-v2-m3` (`46`, medido después) | no | **0.78 / 0.92** / 0.92 / 0.94 | 0.52 / **0.83 / 0.86** / 0.87 |

- **Reranquear la rama de docs sigue perjudicando** con los dos rerankers (−0.01 a −0.02 en R@5), así que se queda desactivado (`rerank_doc_branch = false`), como en la v1.
- **`bge-reranker-v2-m3`:** la primera medición se detuvo por falta de memoria del sistema (Claude Code paró el proceso con la sesión inactiva). **Relanzada a petición tuya, en primer plano:**
  - **Resultado:** code R@5 +0.06 (0.80 → 0.86) y R@3 +0.11, con R@10 −0.01; docs R@1 +0.02 y R@3 +0.01.
  - **Coste:** 439 s el dataset de code (~4,4 s por pregunta en GPU), frente a 15 s con `mmarco`; ~23 s por consulta en CPU.
  - **Memoria:** pico de memoria comprometida de 39,1 GB sobre 67,9 GB; no estuvo cerca del límite. El proceso añade unos 16 GB a la carga del sistema.
  - **Decisión:** disponible como perfil opcional `gpu-quality` (`make bench PROFILE=gpu-quality`); la base sigue con `mmarco`.

### 2.3 Multilingüe (20 preguntas, con `bge-m3`)

| Reranker | Docs ES | Code ES | Docs EN | Code EN |
|---|---|---|---|---|
| `ms-marco` (solo inglés) | 0.30 / 0.60 / 0.70 / 0.90 | 0.60 / 0.80 / 0.80 / 0.90 | 0.80 / 0.90 / 0.90 / 1.00 | 0.60 / 0.90 / 0.90 / 0.90 |
| **`mmarco` (multilingüe)** | **0.60 / 0.90 / 0.90 / 0.90** | 0.50 / 0.70 / 0.80 / 0.90 | 0.80 / 0.90 / 0.90 / 1.00 | 0.50 / 0.70 / 0.80 / 0.90 |

**Hallazgo:** la rama de docs no usa reranker, así que si el reranker cambia docs en español es porque **esas preguntas se enviaban a la rama de code** (ver §3).

### 2.4 Decisión

**`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` por defecto.**
- En el benchmark oficial empata con `ms-marco` en R@5 (+0.01 en code, −0.01 en docs) y gana en R@10 (code +0.02). Pierde 0.02 en R@3 de docs.
- En español mejora mucho docs (R@5 0.70 → 0.90).
- Cuesta el doble que `ms-marco` (97 ms frente a 57 ms en GPU, 1,8 s frente a 0,9 s en CPU), y sigue siendo viable en CPU.

---

## 3. Clasificador doc/code (Fase 2, paso 5)

El clasificador léxico decide la rama (docs o code) comparando las puntuaciones BM25 de los dos índices más unas señales de vocabulario.

### 3.1 Errores de enrutado

| Configuración | Docs oficial → code | Code oficial → docs | Docs ES → code | Code ES → docs |
|---|---|---|---|---|
| v1 (señales solo en inglés, sin limpiar puntuación) | 25/100 | 1/100 | **10/10** | 0/10 |
| + limpieza de puntuación (incl. `¿¡`) | 23/100 | 1/100 | 10/10 | 0/10 |
| **+ señales en español** (por defecto) | **23/100** | **1/100** | **8/10** | **0/10** |
| señales de docs ×2 (peso 1.0) | 18/100 | 7/100 | 7/10 | 1/10 |
| señales de docs ×3 (peso 1.5) | 11/100 | 17/100 | 5/10 | 1/10 |
| señales ×2 + margen 1.5 | 8/100 | 19/100 | 5/10 | 1/10 |

### 3.2 Recall oficial

| Configuración | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| v1 (`47-defaults`) | 0.75 / 0.90 / 0.91 / 0.94 | 0.51 / 0.72 / 0.80 / 0.88 |
| **+ español + puntuación** (`48-cls-w0.5-m0.5`) | **0.76 / 0.91 / 0.92** / 0.94 | 0.51 / 0.72 / 0.80 / 0.88 |
| señales ×2 (`48-cls-w1.0-m0.5`) | 0.76 / 0.91 / 0.92 / 0.94 | 0.47 / 0.68 / 0.76 / 0.84 |
| señales ×3 (`48-cls-w1.5-m0.5`) | 0.77 / 0.91 / 0.93 / 0.95 | 0.42 / 0.61 / 0.68 / 0.75 |
| señales ×2 + margen 1.5 (`48-cls-w1.0-m1.5`) | 0.77 / 0.91 / 0.93 / 0.95 | 0.41 / 0.59 / 0.66 / 0.73 |

### 3.3 Decisión

- **Señales en español + limpieza de puntuación: adoptadas.** Son una mejora estricta en el benchmark oficial (docs +0.01 en R@1, R@3 y R@5; code idéntico).
- **Pesos y margen: sin cambios.** Cada pregunta de docs que se deja de mandar a code se paga con preguntas de code mal enrutadas, y code se hunde (R@5 hasta 0.66).
- ⚠️ **En el set en español**, docs pierde una pregunta en R@3 y R@5 (0.90 → 0.80): las señales mandan dos preguntas a la rama de docs, que no tiene reranker, y una sale peor allí. El benchmark de referencia es el oficial (D4).
- El clasificador léxico está en su límite. Un clasificador semántico (por ejemplo, con los embeddings ya calculados) queda como mejora futura.

---

## 4. Estado final de la Fase 2 (`49-fase2-final`)

| Set | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| **Oficial (42), ruta smart** | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |
| Oficial, ruta generation (web) | 0.76 / 0.91 / 0.92 / 0.94 | 0.51 / 0.72 / 0.80 / 0.88 |
| Inglés (20) | 0.80 / 0.90 / 0.90 / 1.00 | 0.50 / 0.70 / 0.80 / 0.90 |
| Español (20) | 0.60 / 0.80 / 0.80 / 0.90 | 0.50 / 0.70 / 0.80 / 0.90 |

**Evolución en la ruta oficial:**

| | Docs R@5 | Docs R@10 | Code R@5 | Code R@10 |
|---|---|---|---|---|
| v1 (Fase 0, línea base) | 0.85 | 0.85 | 0.64 | 0.72 |
| Fin de la Fase 1 | 0.87 | 0.89 | 0.64 | 0.71 |
| **Fin de la Fase 2** | **0.92** | **0.94** | **0.80** | **0.88** |

**Configuración por defecto:** BM25 code-aware (`code`) + `bge-m3` (en las dos ramas) + reranker `mmarco-mMiniLMv2-L12` con fusión RRF, el reranker siempre activo en la rama de code y clasificador con señales en inglés y español.

---

## 5. Generación: comparativa de LLMs (Fase 3)

**Condiciones comunes:**
- La recuperación por defecto (`bge-m3` + `mmarco` + filtro de relevancia) y el mismo prompt (v3a), k = 5, decodificación greedy y 150 tokens de salida.
- **`gen-bench` con 25 preguntas** de cada dataset oficial, las 20 del set en español y las 40 fuera de dominio.
- **Juez:** `openai/gpt-oss-120b` vía Groq, nota 0–2 frente a la respuesta de referencia de 42, sobre **10 respuestas por set**. Cada respuesta mueve la media del set en 0.1–0.2: solo las diferencias grandes son fiables.
- Ejecuciones `10-llm-*` en `bench/results/gen/` y `bench/results/judge/`.

| Modelo | Juez (media 0–2) | F1 docs / code | Falsos "no encontrado" en code | s/respuesta (docs / code, GPU) | Descarga | Licencia |
|---|---|---|---|---|---|---|
| **Qwen3-0.6B** (base) | 1.25 | 0.471 / 0.450 | 0.12 | 3.9 / 2.7 | ~1.2 GB | Apache 2.0 |
| Qwen3-1.7B | 1.53 | 0.497 / 0.494 | 0.08 | 4.0 / 3.1 | ~4 GB | Apache 2.0 |
| Qwen3-4B | **1.60** | **0.575 / 0.498** | **0.04** | 5.1 / 4.8 * | ~8 GB | Apache 2.0 |
| Phi-4-mini (3.8B) | 1.45 | 0.492 / 0.426 | 0.12 | 3.8 / 2.7 | ~7.7 GB | MIT |
| SmolLM3-3B (descartado) | 1.45 | 0.368 / 0.353 | 0.24 | 5.4 / 3.0 | ~6 GB | Apache 2.0 |

\* Qwen3-4B no cabe en 12 GB de GPU junto con `bge-m3` y el reranker: su perfil ejecuta la recuperación en CPU (mismos resultados, más latencia).

**Juez por set (0–2):**

| Modelo | Docs EN | Code EN | Docs ES | Code ES |
|---|---|---|---|---|
| Qwen3-0.6B | 1.00 | 1.20 | 1.70 | 1.10 |
| Qwen3-1.7B | 1.30 | 1.30 | 1.90 | 1.60 |
| Qwen3-4B | 1.60 | 1.30 | 1.80 | 1.70 |
| Phi-4-mini | 1.40 | 1.20 | 1.80 | 1.40 |
| SmolLM3-3B | 1.10 | 1.30 | 1.60 | 1.80 |

**Otros resultados:**
- Todos responden en el idioma de la pregunta (90–100 %) y rechazan el 100 % de las preguntas claramente ajenas (el filtro va antes del LLM).
- En las "casi del dominio" en español, Qwen3-4B (0.90) y Phi-4-mini (0.80) rechazan mejor que la base (0.70).

**Decisión (tuya):**
- **Familia Qwen3 completa:** 0.6B (base, obligatoria), y 1.7B y 4B como perfiles.
- **Phi-4-mini** como alternativa de otra familia.
- **SmolLM3-3B descartado:** el F1 más bajo y el doble de falsos rechazos en code que la base.
- **Qué modelo se recomienda en la web:** se decide en la Fase 6.
- **Velocidad en CPU de los opcionales: no medida.** Por tamaño, los de 3–4B serán bastante más lentos sin GPU.
