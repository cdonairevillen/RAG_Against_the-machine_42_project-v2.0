# CHECKPOINT — Pruebas 42 (tras la Fase 3)

**Fecha:** 2026-10-19
**Resultado:** ✅ superado. El núcleo medido (recuperación + generación) mejora a la v1 en el benchmark oficial y sigue siendo compatible con la moulinette de 42.
**Etiqueta:** `v2.0-core`, un marcador sobre el commit del checkpoint, igual que `v1.0-42`. No es una rama: el proyecto sigue en `main`. Sirve para comparar (`git diff v2.0-core`) o volver a este punto.

Punto de partida: la v1 entregada a 42 (`v1.0-42`), medida con su propio código sobre los mismos datos (ejecución `00-baseline`).

---

## 1. Compatibilidad con 42

Todos los comandos, ejecutados con **la sintaxis exacta del Makefile de la v1**:

| Comando (v1) | Resultado | Tiempo (GPU) |
|---|---|---|
| `index --max_chunk_size 2000` | ✅ 16 716 padres y 37 381 hijos, embebidos con `bge-m3` | 414 s |
| `search "How to configure OpenAI server?" --k 10` | ✅ 10 fuentes | 21 s* |
| `search_dataset --dataset_path … --save_directory …` (docs, code) | ✅ | 30 s / 40 s* |
| `evaluate --student_answer_path … --dataset_path … --k 10 --max_context_length 2000` | ✅ mismo recall que `make bench` | 11 s |
| `answer_dataset … --skip_generation True` (docs, code) | ✅ | 33 s / 42 s* |
| `answer_dataset … --skip_generation False` (docs, 100 preguntas) | ✅ | 310 s |
| `answer "How to configure OpenAI server?" --k 10` | ✅ (respuesta pobre, ver §6) | 30 s* |

\* Incluye cargar los modelos en cada invocación.

**Formato de salida:** los 5 JSON generados validan contra `StudentSearchResults` / `StudentSearchResultsAndAnswer`.
- 100 preguntas cada uno, `k=10`, ninguna ruta con `\`.
- Claves `question_id`, `question_str`, `retrieved_sources` (y `answer` en el de respuestas).
- **`src/models.py` es idéntico al de `v1.0-42`** (la diferencia es solo de finales de línea). El cambio de `"question"` a `"question_str"` que se ve en salidas antiguas del historial lo hiciste en la propia v1 (commit "Final finalisimo", 18 de junio), antes de la entrega.

**Diferencia de comportamiento:** `answer_dataset --skip_generation True` deja **2 preguntas de code sin fuentes**, las 2 legítimas que rechaza el filtro de relevancia (Fase 3, §2.3). Ese comando usa la ruta de generación, igual que en la v1 (que tenía el filtro BM25). `search_dataset`, el del recall oficial, devuelve fuentes para todas.

---

## 2. Recall oficial (datasets públicos de 42, `k = 10`)

| | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| v1 original (`00-baseline`) | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.61 / 0.63 / 0.68 |
| Fin de la Fase 0 (`04`) | 0.64 / 0.83 / 0.85 / 0.85 | 0.45 / 0.62 / 0.64 / 0.72 |
| Fin de la Fase 1 (`20`) | 0.67 / 0.84 / 0.87 / 0.89 | 0.43 / 0.59 / 0.64 / 0.71 |
| **Checkpoint (`53`)** | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |
| **Diferencia con la v1** | +0.12 / +0.08 / **+0.07** / **+0.09** | +0.07 / +0.11 / **+0.17** / **+0.20** |

**Multilingüe** (set complementario de 20 preguntas): docs en español pasa de R@10 0.50 (solo BM25) a **0.90**.

---

## 3. Generación (Qwen3-0.6B; 160 preguntas: 50 + 50 oficiales, 20 en español y 40 fuera de dominio)

| | Prompt v1 (`00-gen-baseline`) | **Checkpoint (`08-where-rule`)** |
|---|---|---|
| F1 frente a la respuesta de 42 (docs / code) | 0.480 / 0.426 | **0.511 / 0.430** |
| Cita la fuente correcta (docs / code) | 0.75 / 0.82 | **0.87 / 0.86** |
| Falsos "no encontrado" (docs / code) | 0.02 / 0.12 | **0.00** / 0.12 (0.04 con la respuesta en el contexto) |
| Responde en español (docs / code) | 0.62 / 0.70 | **0.90 / 1.00** |
| Falsos "no encontrado" en español (docs) | 0.20 | **0.00** |
| Rechazo fuera de dominio: ajenas EN / ES | 0.80 / 0.90 † | **1.00 / 1.00** |
| Rechazo fuera de dominio: casi del dominio EN / ES | 1.00 / 0.70 | 0.80 / 0.70 |
| **Juez** `gpt-oss-120b` (media 0–2, 10 por set) | 1.20 | **1.30** |
| Juez: docs EN / code EN / docs ES / code ES | **1.40** / 0.90 / 1.30 / 1.20 | 1.30 / **1.10** / **1.60** / 1.20 |

† `00` usaba el set fuera de dominio antiguo, que incluía "capital of France" (que está en el corpus). La comparación de esa fila es solo orientativa.

### Regla nueva adoptada en el checkpoint: preguntas de "dónde"

- **Problema encontrado al comparar con la v1:** en docs EN el juez puntuaba peor el prompt nuevo (1.40 → 1.00). La causa estaba en las preguntas *"¿Dónde encuentro…?"*, cuya referencia es una **ruta de fichero**. La v1 escribía la ruta en el texto ("Source: docs/…"); con las citas `[n]`, la ruta solo aparecía en la tarjeta de la fuente, y la respuesta leída sola (como en el JSON de `answer_dataset`) quedaba incompleta.
- **Regla añadida al prompt:** *"If the question asks where to find something, give the file path shown in that source's header."*
- **Efecto (`07` → `08`):**
  - Juez docs EN de 1.00 a 1.30 y media de 1.25 a 1.30.
  - F1 docs de 0.497 a 0.511.
  - Cita correcta en docs de 0.80 a 0.87.
  - **Coste:** una pregunta "casi del dominio" en inglés más se cuela (0.90 → 0.80).
- **Decisión: adoptada (tuya).** Docs EN queda una décima por debajo de la v1 en el juez, lo que equivale a 1 respuesta de 10, dentro del ruido de la muestra.

---

## 4. Sin GPU (condiciones de 42)

- **Benchmark de recall completo** con la GPU oculta (`CUDA_VISIBLE_DEVICES=-1`): **las mismas métricas exactas**.
- **Tiempo:** 273 s en total (docs 55 s, code 194 s), frente a ~25 s con GPU.
- **Orden de las fuentes:** cambia en 12 de 200 preguntas (2 en docs y 10 en code; la mitad reordena las mismas fuentes) por la diferencia numérica entre CPU y GPU en los cálculos de `bge-m3`. **El recall no cambia.** En la Fase 2, sin embeddings, las salidas eran idénticas byte a byte.

---

## 5. Costes frente a la v1

| | v1 | Checkpoint |
|---|---|---|
| Indexar | 13 s (solo BM25) | **414 s con GPU; ~2 h estimadas sin GPU** (`bge-m3`). Perfil `cpu-light` (`e5-small`): ~13 min en CPU |
| Benchmark de recall (docs / code) | 8 s / 44 s (CPU) | 7 s / 16 s (GPU) · 55 s / 194 s (CPU) |
| Responder una pregunta (CLI, GPU) | ~2–3 s | ~2,5–3 s (con streaming) |
| Infraestructura | Ficheros JSON | Qdrant en Docker (~400 MB de RAM) |

---

## 6. Puntos débiles conocidos

- **Preguntas muy genéricas:** el ejemplo de la v1 *"How to configure OpenAI server?"* recupera documentación de perfilado y la respuesta es pobre. La recuperación optimiza para preguntas concretas (como las del dataset).
- **2 preguntas legítimas de code rechazadas** por el filtro de relevancia (umbral configurable).
- **El clasificador doc/code** sigue enviando 23 de 100 preguntas de docs a la rama de code (léxico en su límite; Fase 2 §10).
- **Las preguntas "casi del dominio" en español** se cuelan en un 30 %.

---

## 7. Cómo reproducirlo

```bash
make db-up && make index          # ~7 min con GPU
make bench LABEL=check            # recall oficial (debe dar la fila "Checkpoint")
make gen-bench LABEL=check        # generación
make judge LABEL=check            # juez (necesita .env; con caché)
CUDA_VISIBLE_DEVICES=-1 make bench LABEL=check-cpu   # condiciones sin GPU
```
