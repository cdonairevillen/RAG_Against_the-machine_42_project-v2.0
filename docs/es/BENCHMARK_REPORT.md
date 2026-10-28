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
- **Phi-4-mini** como alternativa de otra familia. **Retirado el 2026-10-27** (DEC-32 en `decisions.md`, `FASE_7.md` §7b.8): con respuestas largas, como en la web, copiaba las fuentes y entraba en bucles. Sus filas de este informe quedan como histórico.
- **SmolLM3-3B descartado:** el F1 más bajo y el doble de falsos rechazos en code que la base.
- **Qué modelo se recomienda en la web:** se decide en la Fase 6.
- **Velocidad en CPU de los opcionales: no medida.** Por tamaño, los de 3–4B serán bastante más lentos sin GPU.

---

## 6. Cultura general: XQuAD en/es (Fase 4a)

Las mismas 1 190 preguntas, en inglés y en español, sobre un dominio mixto (`xquad`: 48 artículos de Wikipedia × 2 idiomas, indexados juntos). La fuente correcta es el fragmento exacto de la respuesta en el fichero del idioma de la pregunta. `search_smart`, k = 10.

| Configuración | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 | Tiempo EN/ES (s) |
|---|---|---|---|
| BM25 solo | 0.92 / 0.97 / 0.98 / 0.99 | 0.88 / 0.97 / 0.98 / 0.99 | 0 / 0 |
| **Base (BM25 + `bge-m3`)** | **0.95 / 0.99 / 0.99 / 1.00** | **0.92 / 0.99 / 0.99 / 1.00** | 42 / 49 |
| Base + reranker en la rama doc | 0.95 / 0.99 / 1.00 / 1.00 | 0.94 / 0.99 / 1.00 / 1.00 | 189 / 194 |

**Lectura:**
- **Corpus casi saturado:** a partir de R@3 todas las configuraciones superan 0.97. XQuAD sirve para medir el multilingüismo, no para elegir entre configuraciones (para eso, MLQA).
- **Diferencia EN–ES de ~3 puntos en R@1:** en 32 preguntas en español el primer resultado es el mismo artículo en inglés (en 14 en el caso contrario). Es una respuesta correcta en el idioma equivocado.
- **El reranker en la rama doc no se adopta:** +0.02 en R@1 en español a cambio de 4× más tiempo, y en vLLM empeoraba los docs.

### 6.1 Router sin filtro (`44-router-base`)

Cada pregunta se busca en **todos** los dominios indexados (`vllm`, `xquad`). Gana el dominio cuya mejor fuente (entre sus 5 primeras) tiene la puntuación más alta del cross-encoder, que es la misma señal que el filtro fuera de dominio (B15).

| Set | Preguntas | Al dominio correcto | Recall @1/@3/@5/@10 con el router |
|---|---|---|---|
| 42 docs | 100 | **1.000** | 0.76 / 0.91 / 0.92 / 0.94 (igual que con el dominio fijado) |
| 42 code | 100 | **1.000** | 0.51 / 0.72 / 0.80 / 0.88 (igual) |
| Complemento ES docs / code | 10 / 10 | 1.000 / 1.000 | 0.60 / 0.80 / 0.80 / 0.90 · 0.50 / 0.70 / 0.80 / 0.90 |
| XQuAD EN | 1 190 | **0.982** | 0.94 / 0.97 / 0.98 / 0.98 (frente a 0.95 / 0.99 / 0.99 / 1.00) |
| XQuAD ES | 1 190 | **0.978** | 0.91 / 0.97 / 0.97 / 0.98 (frente a 0.92 / 0.99 / 0.99 / 1.00) |

**Lectura:**
- **Ninguna pregunta de 42 se desvía.** El benchmark oficial sigue fijando `vllm`, así que sus cifras no dependen del router.
- **El 2 % de XQuAD que acaba en vLLM** son preguntas que, fuera de contexto, son ambiguas o suenan técnicas. Por ejemplo, *"In the article's title, what did the machine hope to end?"*, *"What is one way in which graphs can be encoded?"* o *"What are stators attached to?"*. Es el coste de no filtrar; con el filtro del dominio, el recall vuelve al de §6.
- **Coste:** cada pregunta se busca en los dos dominios y se puntúan 10 pares con el cross-encoder.

### 6.2 Generación sobre XQuAD (Qwen3-0.6B, k = 5, 1 190 preguntas por idioma)

Las respuestas de referencia de XQuAD son fragmentos cortos (por ejemplo, "308") y el modelo contesta con frases completas, así que el F1 penaliza cada palabra de más. La métrica principal es **"contiene la respuesta"**: si la referencia normalizada aparece dentro de la respuesta.

| Configuración | Contiene EN / ES | "No encontrado" EN / ES | Descartadas por el filtro EN / ES | F1 EN / ES |
|---|---|---|---|---|
| Umbral global 0.0 (`20-xquad-base`) | 0.59 / 0.51 | 0.22 / 0.19 | 0.17 / 0.19 | 0.152 / 0.149 |
| **Umbral propio −2.0 (`22-xquad-gate-2`)** | **0.65 / 0.57** | **0.13 / 0.08** | **0.07 / 0.07** | 0.167 / 0.169 |

- **El filtro fuera de dominio estaba calibrado solo para vLLM.** Con el umbral propio de XQuAD (calibrado con `gate_scores`; caso completo en `changelog/FASE_4.md` §1.2) se recuperan 6 puntos sin dejar pasar ninguna pregunta ajena.
- **Citas e idioma:** cita la fuente correcta en el 99 % de las respuestas y contesta en el idioma de la pregunta en el 98–99 %.
- **Lo que falta es de generación:**
  - En inglés, un 6 % de rechazos con la respuesta en el contexto.
  - En español, la respuesta se recoge peor (0.62 frente a 0.74 entre las que contesta).
- **Tiempo:** 1.4–2.5 s por respuesta, el 96 % en generación. Las iteraciones usan un subconjunto fijo de 300 preguntas por idioma (~20 min, ±2 puntos frente al completo).

---

<!-- about:skip -->
## 7. Modo CV (Fase 4b)

Corpus: CV (`.docx`, inglés), perfil de LinkedIn (`.pdf`, español) y biografía (español + versión en inglés). Benchmark propio: 30 preguntas iguales en inglés y en español, más 10 sobre ti sin respuesta en los datos (contacto privado, temas reservados, datos que faltan). Qwen3-0.6B.

| Ejecución | Cambio | Contiene EN / ES | Cita la correcta EN / ES | Sin dato bien resuelto EN / ES | Fugas |
|---|---|---|---|---|---|
| `30-cv-base` | primera versión | 0.50 / 0.57 | 0.57 / 0.88 | 9/10 · 7/10 | 0 |
| `31`–`31b` | prompt del CV + patrones de "no encontrado" | 0.40 / 0.67 | 0.30 / 0.77 | — | 0 |
| `32-cv-k8` | 8 fuentes | 0.53 / 0.57 | 0.38 / 0.77 | 10/10 · 9/10 | 0 |
| `33-cv-chunks800` | chunks de 800 / 400 | 0.50 / 0.67 | 0.64 / 0.96 | 9/10 · 9/10 | 0 |
| `34` | umbral −3.0 | 0.57 / 0.70 | 0.62 / 0.92 | 9/10 · 9/10 | 0 |
| **`35-cv-bio-en`** | **biografía en inglés + regla de contacto** | **0.73 / 0.80** | 0.73 / 0.89 | **10/10 · 9/10** | **0** |
| `36` (descartado) | regla "no respondas sí/no" | 0.60 / 0.73 | 0.74 / 0.89 | 10/10 · 9/10 | 0 |

- **Recuperación EN con la biografía en inglés:** de 0.13 / 0.43 / 0.57 / 0.70 a **0.47 / 0.80 / 0.93 / 0.97**. ES: 0.70 / 0.83 / 0.97 / 1.00.
- **Umbral del filtro fuera de dominio:** −3.0. Pasa el 93 % de las válidas (EN/ES) y ninguna pregunta fuera de dominio.
- **Router con 3 dominios** (`46-router-cv`): el 100 % de las preguntas de 42 y del CV llegan a su dominio; XQuAD, el 98 %.
- **Las mayores ganancias vienen de los datos** (la versión en inglés) y del **tamaño del chunk** (menos mezcla de trabajos). Las reglas de prompt arreglan casos concretos (los temas reservados, el contacto), pero con un modelo de 0.6B cada regla de más puede costar aciertos (`36`).

---

<!-- /about:skip -->

## 8. Agente frente a acceso directo (Fase 5)

`make agent-bench` (`src/evaluation/agent_bench.py`): cada pregunta se responde con el agente y con el flujo directo, con el mismo LLM (el del perfil) y `k = 5`. Sets:
- **Conversaciones:** 12 diálogos (12 primeras preguntas + 18 seguimientos que dependen de los turnos anteriores).
- **CV:** 30 + 30 (EN/ES).
- **XQuAD:** 50 + 50, muestra fija.
- **vLLM:** 25 docs + 25 code.

En vLLM la métrica útil es el F1 (las respuestas de 42 son frases largas, así que "contiene la respuesta" sale ~0 en los dos modos).

**Dos rondas:**
- **`01-agent-*`:** el agente tal como salió del diseño (§4 de `changelog/FASE_5.md`).
- **`02-agent-nets-*`:** con las dos redes de seguridad (`docs/decisions.md`, DEC-03):
  1. Si las consultas del modelo no encuentran nada, se busca la pregunta original.
  2. Si el modelo restringió dominios y no encontró nada, se repite dentro del filtro del usuario (sin filtro, en todos), nunca fuera.

### 8.1 Contiene la respuesta, agente / directo

| Set | 0.6B r1 | **0.6B r2** | 1.7B r1 | 1.7B r2 | 4B r1 | 4B r2 | Phi-4-mini r1 | Phi-4-mini r2 |
|---|---|---|---|---|---|---|---|---|
| Conversaciones: 1.ª pregunta | 1.00 / 1.00 | **1.00 / 1.00** | 0.83 / 0.92 | 0.92 / 0.92 | 0.92 / 0.92 | 0.92 / 0.92 | 0.83 / 0.92 | 0.83 / 0.92 |
| **Conversaciones: seguimientos** | 0.44 / 0.33 | **0.78 / 0.33** | 0.28 / 0.33 | **0.83** / 0.33 | 0.89 / 0.39 | **1.00** / 0.39 | 0.78 / 0.33 | 0.78 / 0.33 |
| CV EN | 0.70 / 0.73 | 0.70 / 0.73 | 0.80 / 0.90 | 0.90 / 0.90 | 0.80 / 0.90 | 0.87 / 0.90 | 0.83 / 0.87 | 0.83 / 0.87 |
| CV ES | 0.80 / 0.80 | 0.80 / 0.80 | 0.73 / 0.90 | 0.87 / 0.90 | 0.87 / 0.93 | 0.90 / 0.93 | 0.90 / 0.90 | 0.90 / 0.90 |
| XQuAD EN | 0.50 / 0.62 | 0.58 / 0.62 | 0.46 / 0.78 | 0.76 / 0.78 | 0.80 / 0.78 | 0.80 / 0.78 | 0.72 / 0.74 | 0.74 / 0.74 |
| XQuAD ES | 0.64 / 0.70 | **0.70 / 0.70** | 0.50 / 0.70 | 0.68 / 0.70 | 0.86 / 0.88 | 0.88 / 0.88 | 0.60 / 0.68 | 0.64 / 0.68 |
| vLLM docs (F1) | 0.52 / 0.52 | 0.52 / 0.52 | 0.51 / 0.51 | 0.51 / 0.51 | 0.58 / 0.57 | 0.58 / 0.57 | 0.43 / 0.46 | 0.45 / 0.46 |
| vLLM code (F1) | 0.43 / 0.44 | 0.43 / 0.44 | 0.51 / 0.51 | 0.51 / 0.51 | 0.50 / 0.50 | 0.50 / 0.50 | 0.45 / 0.42 | 0.45 / 0.42 |

Los valores del modo directo no cambian entre rondas (el flujo directo no se ha tocado), lo que confirma que la comparación es justa.

### 8.2 "No encontrado", latencia y uso de las redes (ronda 2)

| Modelo | "No encontrado" en seguimientos, agente / directo | s/respuesta, agente / directo (1.ª preg. · seguim. · XQuAD EN) | Redes usadas (seguim. · XQuAD EN · CV EN) |
|---|---|---|---|
| **Qwen3-0.6B** | **0.11 / 0.50** | 3.4/1.6 · 4.3/1.0 · 3.5/1.6 | 39 % · 24 % · 7 % |
| Qwen3-1.7B | 0.06 / 0.50 | 3.1/1.5 · 4.1/1.3 · 3.2/1.5 | 56 % · 42 % · 17 % |
| Qwen3-4B | 0.00 / 0.44 | 6.0/3.5 · 7.2/3.6 · 6.7/4.1 | 11 % · 8 % · 10 % |
| Phi-4-mini | 0.17 / 0.50 | 3.4/2.5 · 5.7/1.7 · 5.3/2.3 | 6 % · 12 % · 3 % |

Tiempos en la 3080 Ti; en la CPU del Space serán varias veces mayores.

⚠️ **La columna "tool calls" de la tabla de consola cambia de significado en la ronda 2.** En la ronda 1 contaba las respuestas con al menos una llamada válida a la herramienta. En la ronda 2 cuenta las que **no** acabaron en el plan B determinista, que ahora también se usa cuando las búsquedas del modelo y la red 1 no encuentran nada. Por eso baja (0.6B: de 1.00 a 0.67 en seguimientos) sin que el modelo llame peor a la herramienta. La métrica que mide las redes es `safety_net_rate` (en los JSON).

### 8.3 Lectura

- **El agente gana donde tiene que ganar: en los seguimientos.** Sin memoria, "¿Y en qué año?" no se puede responder (directo: 0.33, con un 50 % de "no encontrado"). Con el agente, Qwen3-0.6B llega a **0.78** y Qwen3-4B, a **1.00**.
- **Las redes de seguridad arreglan lo que el agente perdía en preguntas sueltas.** En la ronda 1, el 0.6B y el 1.7B perdían en XQuAD (hasta −0.32 con el 1.7B) porque sus reescrituras en palabras sueltas no pasaban el filtro de relevancia, o porque restringían mal el dominio. En la ronda 2 el agente queda **a la par del directo (±0.04)** en todos los sets de preguntas sueltas con los cuatro modelos. Con el 1.7B, los seguimientos pasan de 0.28 a 0.83.
- **El filtro del usuario se respeta siempre** (test `test_user_filter_is_never_exceeded`): los reintentos de la red 2 nunca salen de él.
- **vLLM:** el agente no aporta ni quita (F1 igual); son preguntas autocontenidas.
- **Coste:** el agente añade 1–3 s por respuesta con los modelos pequeños (una llamada de planificación y otra para decir DONE) y ~3 s con el 4B.
- **Qué modelo desplegar** (propuesta, a decidir contigo):
  - **Qwen3-0.6B**, la base (`PLANING.md`): con las redes, el agente ya no pierde frente al directo, mejora mucho los seguimientos y es el más ligero para la CPU gratuita del Space.
  - **Qwen3-1.7B** es el candidato claro si la CPU lo aguanta: misma latencia en GPU y mejor en CV (0.90 / 0.87 frente a 0.70 / 0.80) y XQuAD EN (0.76 frente a 0.58). Su latencia en la CPU del Space **no está medida**.
  - **Qwen3-4B** es el mejor agente (1.00 en seguimientos), pero tarda ~2× en GPU. En CPU previsiblemente sería demasiado lento para una web (sin medir).
  - **Phi-4-mini** no compensa: llamadas a la herramienta menos fiables (44 % en XQuAD ES) y peor F1 en vLLM docs.
  - **Lo que se decidió después (Fase 8, hoy vigente):** la web ofrece Qwen3-1.7B (por defecto), Qwen3-0.6B e IBM Granite 4.0 Micro, todos con y sin agente. Qwen3-4B y Phi-4-mini no están en la web (§10).

### 8.4 Latencia en la CPU del despliegue (Fase 6)

Imagen del Space en local con los límites del plan gratuito simulados (`docker run --cpus=2 --memory=16g`), Qwen3-0.6B y 4 preguntas (CV, seguimiento, vLLM y XQuAD). Detalle en `changelog/FASE_6.md` §6.

| Modo | Primer token | Respuesta completa |
|---|---|---|
| Directo | 9.6–17.5 s | 14.3–24.0 s |
| Agente | 18.2–27.5 s | 22.0–31.7 s |

- **Con los hilos de torch sin ajustar** (12 hilos sobre 2 vCPU), todo era ~3.5× más lento: 48–88 s directo y 84–123 s con el agente. Se ajustan en `entrypoint.sh` (DEC-17).
- **En CPU, el agente cuesta ~8 s más por respuesta.** En la 3080 Ti eran ~2 s.

---

## 9. Dominio "about" y forma de las respuestas (Fase 7)

### 9.1 El benchmark de "about"

18 preguntas sobre el proyecto, en inglés y en español (`bench/datasets/about/`, `make bench SUITE=about`). Cada una tiene su evidencia en el README, el ROADMAP o el código, en el idioma de la pregunta. El ground truth se genera con `python -m src build_about_bench`, que busca cada evidencia en su fichero: **hay que regenerarlo cada vez que se editan esos documentos**, porque guarda offsets de caracteres (DEC-37).

- **Umbral del filtro fuera de dominio:** −1.0, calibrado con `gate_scores`.
- **Recall bajo con el evaluador de 42, aunque la respuesta llega:** el evaluador solo acepta el pasaje exacto de referencia, y la documentación repite cada dato en varios sitios (README, ROADMAP, changelogs). Con la métrica "la respuesta está en las 5 primeras fuentes", llegaba al 89 % (EN y ES) en la Fase 7a.

### 9.2 Estado final (`100`, "about" reindexado, Qwen)

Router sin filtro (`route-bench`):

| Conjunto | Enrutado a su dominio | R@1 / R@3 / R@5 / R@10 |
|---|---|---|
| 42 docs / code | 1.000 / 0.990 | 0.76 / 0.91 / 0.92 / 0.94 · 0.51 / 0.72 / 0.80 / 0.88 |
| XQuAD EN / ES | 0.980 / 0.975 | 0.94 / 0.97 / 0.97 / 0.98 · 0.91 / 0.97 / 0.97 / 0.97 |
| CV EN / ES | 0.933 / 0.900 | 0.47 / 0.77 / 0.87 / 0.90 · 0.67 / 0.80 / 0.87 / 0.90 |
| about EN | 0.889 | 0.11 / 0.28 / 0.33 / 0.67 |
| about ES | 0.944 | 0.39 / 0.50 / 0.61 / 0.67 |

Generación sobre "about" (`gen-bench`, k = 5, hasta 1.024 tokens):

| Modelo | Contiene EN / ES | "No encontrado" falso EN / ES | Cita la correcta EN / ES | Idioma EN / ES |
|---|---|---|---|---|
| Qwen3-0.6B | 0.44 / 0.50 | 0.11 / 0.00 | 0.17 / 0.27 | 1.00 / 1.00 |
| Qwen3-1.7B | 0.56 / 0.72 | 0.06 / 0.00 | 0.35 / 0.39 | 1.00 / 0.94 |
| Qwen3-4B | 0.72 / 0.83 | 0.06 / 0.00 | 0.29 / 0.44 | 1.00 / 1.00 |

- **"Cita la correcta" infravalora:** compara con el fichero de la respuesta de referencia, y el mismo dato está en varios ficheros.
- **El historial ocupa la mayor parte de "about"** (1.121 de los 1.623 trozos de documentación al medirlo en `99`) y los changelogs citan las preguntas de prueba al pie de la letra, así que la búsqueda devuelve la cita en lugar de la respuesta: en el banco abierto de `100`, 7 de las 12 preguntas sobre el proyecto (DEC-37, con la medida sin el historial). Arreglado en §9.4.

### 9.3 Forma de las respuestas

| Medida | Resultado |
|---|---|
| Detector de bucles (`src/rag/loops.py`), falsos positivos | 0 en 11.550 respuestas guardadas (§7b.2); ventana 12 y bloques repetidos desde §7b.7 |
| Limpieza del eco (`strip_echo`) | Eco a 0 en las 4.662 respuestas medidas, sin perder ninguna (§7b.3); con los Qwen limpia 17 respuestas de una matriz completa (DEC-35) |
| Respuestas que cambian de idioma a mitad (`lang_mix`) | 10 de 1.105 con el índice de DEC-25 (`95`); **20 de 1.117** con "about" reindexado (`97`): las 10 nuevas son de about/ES y del banco abierto. En el estado final (`100`, solo "about" y el banco abierto): 4 de 165 |
| Pista de idioma en el prompt | No adoptada: el idioma del 0.6B en about/ES baja de 1.00 a 0.86 (DEC-36) |

### 9.4 Sin citas de preguntas de prueba en la documentación (`101`)

La documentación indexada ya no copia las preguntas de prueba sobre el proyecto ni las respuestas incorrectas (DEC-39, `FASE_7.md` §7b.9). Esta tabla sustituye a la §9.2 como estado vigente de "about":

| | `100` | `101` |
|---|---|---|
| `gen-bench` about, contiene EN / ES: 0.6B · 1.7B · 4B | 0.44 / 0.50 · 0.56 / 0.72 · 0.72 / 0.83 | 0.44 / 0.50 · 0.56 / 0.61 · 0.67 / 0.72 |
| Route-bench about, enrutado EN · ES | 0.889 · 0.944 | 0.778 · 0.944 |
| Route-bench about, R@1/@3/@5/@10 EN · ES | 0.11 / 0.28 / 0.33 / 0.67 · 0.39 / 0.50 / 0.61 / 0.67 | 0.17 / 0.28 / 0.28 / 0.56 · 0.44 / 0.50 / 0.67 / 0.67 |
| Route-bench CV EN / ES, enrutado | 0.933 / 0.900 | 0.967 / 0.900 |
| Banco abierto: respuestas que citan el historial (0.6B) | 7 de 12 | 0 |
| Banco abierto: eco · idioma mal (0.6B · 1.7B) | 2 · 1 · 1 · 2 | 0 · 0 · 0 · 0 |
| Cambio de idioma a mitad (about + banco abierto) | 4 de 165 | 1 de 150 |

Las cifras de `100` estaban infladas por la autocita: tres preguntas (about-02, about-04 y about-11) solo pasaban el filtro de "about" gracias a la nota que las citaba. 42, XQuAD y CV no cambian.

Phi-4-mini se retiró el 2026-10-27 (DEC-32): necesitaba parches (reintento por eco, detector de bucles) para dar respuestas limpias con el límite de la web. Sus filas de §5 y §8 quedan como histórico.

## 10. Granite 4.0 Micro y la longitud de las respuestas (Fase 8)

Detalle en `changelog/FASE_8.md` (§8a y §8g). `gen-bench` a 1.024 tokens, como en la web; juez de Groq (`gpt-oss-120b`) sobre vLLM, 25 preguntas por conjunto (70 en total).

**Modelos** (contiene la respuesta, EN / ES; juez: correctas de 70):

| | Qwen3-0.6B | Qwen3-1.7B | Qwen3-4B | IBM Granite 4.0 Micro |
|---|---|---|---|---|
| CV | 0.73 / 0.80 | 0.90 / 0.90 | 0.90 / 0.93 | 0.87 / 0.93 |
| about | 0.50 / 0.50 | 0.56 / 0.61 | 0.67 / 0.72 | 0.67 / 0.83 |
| XQuAD | 0.64 / 0.59 | 0.79 / 0.68 | — | 0.81 / 0.74 |
| Juez vLLM, correctas de 70 | 33 | 47 | — | 52 |
| Agente, seguimientos (0.6B y 4B: Fase 5; 1.7B y Granite: `110`) | 0.78 | 0.78 | 1.00 | 0.89 |
| Tokens por respuesta, banco abierto (media) | 78 | 130 | — | 179 |
| En la web | Sí | Sí, por defecto | No (CLI y benchmarks) | Sí |

Granite es el mejor modelo de la web en calidad y como agente, y el más lento (con el agente, 11–14 s hasta el primer token). Tiene una regla propia del CV para no presentar el Gmail público como otro correo (§8a.2). 0 fugas de datos privados con todos los modelos.

**Longitud de las respuestas (§8g):** seis versiones de la regla 6 del prompt ("Be direct and concise") probadas en el 1.7B, y una en Granite y el 0.6B. La mejor, S5 en el 1.7B, alarga las respuestas (176 frente a 130 tokens) y sube las correctas del juez (50 frente a 47), pero empeora code (con el agente, el doble de "no encontrados" falsos). Las reglas largas hacen que el CV invente negaciones, así que el CV mantiene siempre la regla corta. **No se adopta ninguna**; S5 queda comentada en `rag.toml`.
