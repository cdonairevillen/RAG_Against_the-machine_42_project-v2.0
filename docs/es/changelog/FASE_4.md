# CHANGELOG — Fase 4: Inserción de modos

**Fecha de inicio:** 2026-10-23
**Estado:** ✅ completada (2026-10-23) con 4a y 4b. La **4c (multimedia, Gulliver) queda aplazada** como posible fase final, por decisión tuya; MLQA, también.

**4a (XQuAD) completada (2026-10-23):**
- Datos, ingesta y benchmark de recuperación.
- `make index` de todas las fuentes.
- Router con filtro y atribución en la web.
- Benchmark de generación, con un subconjunto fijo y la opción completa.
- Umbral del filtro fuera de dominio por dominio.

**4b (modo CV) completada (2026-10-23):** CV, LinkedIn y biografía (ES + EN) indexados tal cual, sin fugas de datos de contacto, con tu mensaje cuando falta un dato. Contiene la respuesta correcta en el 73 % (EN) y el 80 % (ES) de los casos.

Aplazada: 4c (Gulliver).

---

<!-- about:skip -->
## 4b — Modo CV

### Decisiones (tuyas)
- **Se indexa todo tal cual:** el CV (`.docx`, en inglés), el perfil de LinkedIn (`.pdf`, en español) y la biografía (`.md`, en español). Cada fichero va en su idioma, sin traducir ni limpiar.
- **Los datos de contacto privados** se quedan en los ficheros, pero **nunca se muestran**: hay guardarraíles al responder.
- **Sin el dato**, el modo CV responde: *"No dispongo de esa información, ¡pero puedes preguntárselo tú! cdonairevillen@gmail.com"* (y su versión en inglés).
- **Las preguntas de evaluación van a git.**

### Cambios
- **Docling** (`src/ingestion/loaders.py`): convierte el `.docx` y el `.pdf` a Markdown al indexar, y los offsets se refieren a ese Markdown. Tres arreglos para Windows:
  - Backend PDF `pypdfium2`: Application Control bloquea la librería nativa de `docling-parse`.
  - `HF_HUB_DISABLE_SYMLINKS`: sin modo desarrollador, Windows no crea los symlinks de la caché de Hugging Face.
  - `torchvision` desde el índice cu126: la rueda de PyPI rompía `torchvision::nms` con nuestro torch CUDA.
- **pytest sin `faulthandler`** (`pyproject.toml`): con las dependencias opcionales de Docling, importar `transformers` arrastra `sklearn → pandas → pyarrow`, y cargar `pyarrow` con `faulthandler` activo mata Python en Windows. La ejecución normal no usa `faulthandler`.
- **Reglas por dominio** (`src/domain_rules.py`, campos nuevos en `[sources.<x>]`):
  - `private_data` (`phone`, `email`), `public_emails` y `private_replacement`: se enmascaran en el contexto que lee el LLM, en la respuesta final y en las fuentes que se muestran (CLI y web). **El material indexado no se toca.**
  - `not_found_message` por idioma: el "no encontrado" del dominio que respondió o del más cercano, si el filtro rechazó la pregunta.
- **Fuente `cv`** en `rag.toml`: 15 padres y 56 hijos (biografía 8, LinkedIn 4, CV 3).
- **Benchmark** (`bench/datasets/cv/`, en git):
  - 30 preguntas escritas a mano, iguales en inglés y en español. La fuente correcta es el fragmento exacto de la biografía que responde, y `make`/`build_cv_bench` comprueba que sigue ahí.
  - 10 preguntas sobre ti sin respuesta en los datos (`ood`): de contacto privado, sobre temas reservados y de datos que faltan.
- **`.gitignore`:** la regla `cv/` pasa a `/cv/`, que es la carpeta de la raíz. Antes ignoraba cualquier carpeta llamada `cv`, incluida la del benchmark. `data/` sigue ignorada entera.

### Resultados (primera medición)

**Recuperación** (`50-cv-base`):

| | @1 | @3 | @5 | @10 |
|---|---|---|---|---|
| EN, evaluador (solo cuenta la biografía) | 0.20 | 0.60 | 0.73 | 1.00 |
| ES, evaluador | 0.80 | 0.90 | 0.97 | 1.00 |
| EN, la respuesta está en el texto recuperado | 0.47 | 0.77 | 0.87 | — |
| ES, la respuesta está en el texto recuperado | 0.87 | 0.93 | 1.00 | — |

- **El evaluador exagera la caída en inglés:** con preguntas en inglés, el primer resultado es el **CV en inglés** en 18 de 30 casos, y el ground truth solo acepta la biografía. Aun así hay una caída real, porque el CV no tiene los datos que solo están en la biografía (nacimiento, aficiones, viajes…).

**Filtro fuera de dominio** (`gate_scores --domain cv`): con 0.0 se rechazaba el **40 %** de las preguntas válidas en inglés. Con **−2.0** pasa el 90 % (EN/ES) y no entra ninguna fuera de dominio *far*/*near*. De las preguntas sobre ti sin dato pasa la mitad, pero acaban igualmente en tu mensaje.

**Generación** (`30-cv-base`, Qwen3-0.6B, k = 5):

| | EN | ES |
|---|---|---|
| Contiene la respuesta correcta | 0.50 | 0.57 |
| "No encontrado" (con la respuesta en el contexto) | 0.23 (0.13) | 0.13 (0.03) |
| Cita la fuente correcta | 0.57 | 0.88 |
| **Fugas de datos privados** | **0** | **0** |
| Sin dato → tu mensaje (faltan datos / contacto privado) | 1.00 / 1.00 | 0.86 / 0.50 |
| Tema reservado → tu mensaje | **0 / 1** | **0 / 1** |

**Problemas observados** (revisados a mano en `data/output/gen_bench/30-cv-base/answers.json`):
1. **Mezcla de hechos:** "hizo su Erasmus en De La Luna Luna Studio", "trabaja en Lion's Roar Games en De La Luna Luna", "props para Secret 6 (empresa alemana)". Los chunks juntan varios trabajos seguidos y el modelo de 0.6B cruza los datos.
2. **Inventa detalles de un tema reservado** y te atribuye obras ajenas (*Dune*, *El Señor de los Anillos*…).
3. **Preguntas en inglés sin respuesta:** esquí, Star Wars, Linkin Park, Europa… El contexto recuperado es el CV en inglés, que no tiene esos datos, y el modelo dice "no encontrado", que es correcto con ese contexto.
4. **Repite el contexto** ("[1] --- file: … ---") en algunas respuestas, en vez de contestar.
5. **Copia el marcador de dato privado:** en una respuesta aparece "(privado; contacto: …)" porque estaba en el chunk de LinkedIn. No es una fuga, pero mete ruido.

### Iteración (aprobada por ti): prompt del modo CV, k, tamaño de chunk y umbral

Cada cambio se mide por separado con el `gen-bench` del CV (60 preguntas más 20 sin dato, ~4 min):

| Ejecución | Cambio | Contiene EN / ES | Cita la correcta EN / ES | "No encontrado" EN / ES | Tema reservado EN / ES | Fugas |
|---|---|---|---|---|---|---|
| `30-cv-base` | — | 0.50 / 0.57 | 0.57 / 0.88 | 0.23 / 0.13 | ✗ / ✗ | 0 |
| `31-cv-prompt` | prompt del CV + marcador `[dato privado]` | 0.40 / 0.67 | 0.30 / 0.77 | 0.33 / 0.10 | ✓ / ✓ | 0 |
| `31b-cv-prompt-patterns` | + patrones de "no encontrado" | 0.40 / 0.67 | 0.30 / 0.77 | 0.33 / 0.13 | ✓ / ✓ | 0 |
| `32-cv-k8` | + 8 fuentes para responder | 0.53 / 0.57 | 0.38 / 0.77 | 0.17 / 0.13 | ✓ / ✓ | 0 |
| `33-cv-chunks800` | + chunks de 800 / 400 | 0.50 / 0.67 | 0.64 / 0.96 | 0.43 / 0.20 | ✓ / ✓ | 0 |
| **`34-cv-chunks800-gate3`** | **+ umbral −3.0** | **0.57 / 0.70** | **0.62 / 0.92** | 0.37 / 0.13 | **✓ / ✓** | **0** |

**Qué aporta cada cambio:**
- **Prompt del CV** (`prompt_rules`): respuestas en tercera persona, cada dato con su empresa, sus gustos no son obras suyas y los temas reservados no se desarrollan. **Arregla los temas reservados** en los dos idiomas: ahora responde que es reservado o da tu mensaje, y ya no inventa.
- **Patrones de "no encontrado"** (`src/generator.py`): el modelo también se niega con frases como "No se proporciona…", "no se menciona…" o "No se encuentra en los proporcionados", que el detector no reconocía. Ahora acaban en tu mensaje.
  - **En vLLM** cambia dos respuestas, y las dos eran negativas reales: un rechazo en *code* español y uno *near* español (que pasa de 0.70 a 0.80 de rechazo correcto). El resto, igual (`22-fase4b-vllm-check`).
- **`answer_k = 8`:** más fuentes para que entre la biografía cuando la pregunta va en inglés. Con chunks de 2 000 caracteres no cabían en el presupuesto de tokens y metían ruido (en español bajó de 0.67 a 0.57).
- **Chunks de 800 / 400** (`chunk_size`/`child_size` por fuente): un trabajo o sección por chunk. **Las citas correctas suben** de 0.30–0.38 a 0.64 (EN) y de 0.77 a 0.96 (ES), es decir, mezcla mucho menos los trabajos. Contrapartida:
  - La recuperación en inglés empeora (`51-cv-chunks800`: R@10 de 1.00 a 0.70, con más trozos del CV en inglés por delante).
  - Las puntuaciones del filtro bajan, así que con −2.0 se rechazaban más preguntas válidas.
- **Umbral −3.0** (recalibrado con `gate_scores --label chunks800`): ninguna pregunta fuera de dominio *far*/*near* pasa con −3.0, y las válidas suben a 0.83 (EN) / 0.90 (ES). Solo en modo "solo CV" pasaría un 13 % de preguntas de docs de vLLM, pero sin filtro esas van a vLLM (router: 100 %).

**Configuración tras esta ronda** (`34`): prompt del CV, `answer_k = 8`, chunks de 800 / 400, umbral −3.0 y marcador `[dato privado]`.

### Biografía en inglés y regla de contacto (aprobado por ti)

- **`data/raw/cv/autobiography_en.md`:** traducción fiel de la biografía, con las mismas secciones. Se indexa junto al original (62 padres, 162 hijos).
- **Benchmark:** las preguntas en inglés apuntan a su evidencia en la versión inglesa (`evidence_en` en `questions.json`), y las españolas al original. Así el ground truth está en el idioma de la pregunta.
- **Regla 11 del prompt:** el único contacto público es cdonairevillen@gmail.com. Si piden otro dato de contacto, se dice que es privado y se da ese correo.
- **Umbral recalibrado** (`gate_scores --label bio-en`): −3.0 sigue siendo válido. Pasa el 93 % de las válidas en los dos idiomas y ninguna pregunta fuera de dominio *far*/*near*.

| Ejecución | Recuperación EN @1/@3/@5/@10 | Contiene EN / ES | Cita la correcta EN / ES | "No encontrado" EN / ES | Sin dato → tu mensaje o "es reservado" | Fugas |
|---|---|---|---|---|---|---|
| `34` (antes) | 0.13 / 0.43 / 0.57 / 0.70 | 0.57 / 0.70 | 0.62 / 0.92 | 0.37 / 0.13 | EN 9/10 · ES 9/10 | 0 |
| **`35-cv-bio-en`** | **0.47 / 0.80 / 0.93 / 0.97** | **0.73 / 0.80** | 0.73 / 0.89 | **0.10 / 0.07** | **EN 10/10 · ES 9/10** | **0** |
| `36-cv-rule12` (descartado) | igual | 0.60 / 0.73 | 0.74 / 0.89 | 0.17 / 0.07 | EN 10/10 · ES 9/10 | 0 |

- **La versión en inglés resuelve el hueco de las preguntas en inglés:** los "no encontrado" bajan del 37 % al 10 % y "contiene la respuesta" sube de 0.57 a 0.73. El español también mejora (de 0.70 a 0.80).
- **Los datos de contacto privados acaban en tu mensaje** en los dos idiomas: ya no da el Gmail como si fuera otro contacto.
- **Lo que falla:** "¿Está casado?" → "No está casado". Se lo inventa, porque el dato no está.
- **`36`, descartado:** probé una regla 12 ("no respondas sí o no a datos personales que no estén"). Arregla esa pregunta, pero las respuestas correctas bajan 13 puntos en inglés y 7 en español, y una pregunta de contacto deja de dar tu mensaje. Se revierte.

**Configuración final del modo CV** (`35`): biografía en español y en inglés, CV y LinkedIn, chunks de 800 / 400, `answer_k = 8`, umbral −3.0, prompt con las reglas 7–11, marcador `[dato privado]` y tu mensaje de "no encontrado".

**Lo que quedaba abierto en la ronda anterior** (antes de la biografía en inglés):
- **Preguntas en inglés sobre datos que solo están en la biografía:** nacimiento, barrio, instituto, Eastbourne, Estambul, guitarra, esquí, reubicarse en Europa, LanguageCert… (11 de 30 acaban en "no encontrado"). El contexto que llega es el del CV en inglés, que no los tiene. Es un límite de la recuperación entre idiomas, no del LLM; la solución directa sería una versión en inglés de la biografía.
- **Datos de contacto privados:**
  - A una pregunta por un dato de contacto privado responde "es [dato privado]". No hay fuga, pero no da tu mensaje.
  - A otra, da tu Gmail como si fuera el contacto pedido. No hay fuga, pero la afirmación es falsa.
  - Posible arreglo en el prompt: "el único contacto público es cdonairevillen@gmail.com".
- **Router con los tres dominios** (`46-router-cv`): el 100 % de las preguntas de 42 y del CV llegan a su dominio. XQuAD se queda en el 98 %, y solo 5 de 2 380 van al CV.
<!-- /about:skip -->

## 4a — Cultura general: XQuAD

### 1. Resultado

Benchmark de recuperación (`search_smart`, k = 10, base estable: `bge-m3` + `mmarco` + BM25), las 1 190 preguntas de cada idioma sobre el dominio mixto `xquad`:

| Ejecución | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 | Tiempo EN/ES (s) |
|---|---|---|---|
| **`40-xquad-base`** (base) | **0.95 / 0.99 / 0.99 / 1.00** | **0.92 / 0.99 / 0.99 / 1.00** | 42 / 49 |
| `41-xquad-bm25-only` (sin embeddings) | 0.92 / 0.97 / 0.98 / 0.99 | 0.88 / 0.97 / 0.98 / 0.99 | 0 / 0 |
| `42-xquad-rerank-docs` (reranker también en la rama doc) | 0.95 / 0.99 / 1.00 / 1.00 | 0.94 / 0.99 / 1.00 / 1.00 | 189 / 194 |

**vLLM sin cambios:** `43-fase4a-vllm-check` da docs 0.76 / 0.91 / 0.92 / 0.94 y code 0.51 / 0.72 / 0.80 / 0.88, idéntico a la línea base.

**Lectura:**
- **XQuAD es fácil para este sistema:** 96 ficheros (48 artículos × 2 idiomas) y preguntas muy pegadas al texto. Sirve para medir el multilingüismo, pero apenas distingue entre configuraciones. Para eso hará falta MLQA, más grande, como ya preveía el roadmap.
- **El español va ~3 puntos por detrás en R@1.** En 32 de las 1 190 preguntas en español, el primer resultado es el mismo artículo **en inglés**: la respuesta es correcta, pero en el otro idioma, y el evaluador la cuenta como fallo. En inglés pasa en 14.
- **Los embeddings aportan** +3–4 puntos en R@1 (sobre todo en español) y +1–2 en R@3/@5.
- **El reranker en la rama doc** solo sube el español en R@1 (+0.02) y en R@5 (+0.01), y cuesta 4× más tiempo. En vLLM empeoraba los docs, así que **no se adopta**: haría falta una opción por dominio y la ganancia no la justifica.

### 2. Cambios

**Datos (`make data-xquad`)**
- **Origen:** las preguntas, los párrafos y las respuestas vienen del parquet de Hugging Face (`google/xquad`), un primer paso de P10. Los títulos de los artículos, que el parquet no tiene, se toman del JSON original de GitHub y se cruzan por el ID de la pregunta. Las dos fuentes están fijadas a una revisión y se comprueban por SHA256.
- **Corpus:** un fichero Markdown por artículo en `data/raw/xquad/<lang>/<Title>.md` (48 por idioma), con el título como cabecera y los párrafos separados por líneas en blanco. Está ignorado por git porque se regenera.
- **Ground truth:** `bench/datasets/xquad/{Answered,Unanswered}Questions/dataset_{en,es}_xquad.json`, en formato `RagDataset`. Cada fuente es el **fragmento exacto de la respuesta**, y el script comprueba las 2 380.
- **Atribución CC-BY-SA:** `bench/datasets/xquad/README.md`.

**Ingesta**
- `[sources.xquad]` en `rag.toml`: un dominio mixto en+es, chunker `markdown_headers_packed`, colección `rag_xquad`. `make index SOURCE=xquad` lo indexa en ~10 s en GPU.
- Resultado: 285 padres y 1 217 hijos.

**Benchmark**
- `bench --suite xquad` usa el dominio `xquad` y los datasets `en`/`es`. El formato de los resultados y la tabla de vLLM no cambian.

**Indexar todas las fuentes**
- `make index` (o `index` sin `--source`) indexa todas las fuentes de `rag.toml` una detrás de otra, cada una en su colección (`rag_vllm`, `rag_xquad`). `make index SOURCE=xquad` indexa solo una. `index-xquad` se elimina.
- El modelo de embeddings se carga una sola vez para todas las fuentes. Indexar vLLM y XQuAD en la 3080 Ti lleva ~6 min.
- Reindexar todo da exactamente las mismas cifras de 42 (`45-fase4a-index-all`).

**Router (`src/router.py`, `DomainRouter`)**
- **Sin filtro:** busca en todos los dominios indexados con el `search_smart` de cada uno. Puntúa con el cross-encoder las 5 mejores fuentes de cada dominio y gana el que tenga la puntuación más alta. El filtro fuera de dominio (B15) se aplica sobre el ganador: si ni el mejor dominio es relevante, devuelve "no encontrado".
- **Con filtro:** `answer "…" --domains xquad` (o `vllm,xquad`) busca solo en esos dominios. Con un único dominio se comporta exactamente como su `Retriever`.
- **Mismo interfaz que `Retriever`** (`search_smart`, `search_for_generation`, `get_parent_chunk_map`, `reranker`, `chunks`), así que `RagPipeline` y la web lo usan sin cambios. El embedder y el reranker se cargan una sola vez y se comparten entre dominios.
- **Dónde se usa:** `answer` de la CLI y la web. Los comandos de 42 (`search_dataset`, `answer_dataset`, `evaluate`), `bench` y `gen-bench` siguen con el dominio fijado (`vllm`), así que el benchmark oficial no depende del router.
- **`make route-bench`** mide el acierto de enrutado y el recall con el router (ver §1.1).
- **Limitación conocida:** el ganador se lleva todo. Una pregunta que mezcle dos dominios solo recibe fuentes de uno.

**Web**
- Carga el router sobre todos los dominios. Las tarjetas de fuentes de XQuAD muestran la atribución "XQuAD (Google), CC-BY-SA 4.0 · Wikipedia". El selector de dominios queda para la Fase 6.

### 1.1 Router sin filtro (`44-router-base`)

| Set | Al dominio correcto | Recall @1/@3/@5/@10 con el router |
|---|---|---|
| 42 docs / code (100 + 100) | **1.000 / 1.000** | igual que con el dominio fijado |
| XQuAD EN (1 190) | **0.982** | 0.94 / 0.97 / 0.98 / 0.98 |
| XQuAD ES (1 190) | **0.978** | 0.91 / 0.97 / 0.97 / 0.98 |

El 2 % de XQuAD que acaba en vLLM son preguntas ambiguas fuera de contexto (*"In the article's title, what did the machine hope to end?"*, *"What are stators attached to?"*). Detalle en `BENCHMARK_REPORT.md` §6.1.

### 1.2 Caso: el filtro fuera de dominio rechazaba preguntas válidas de XQuAD

**El síntoma.** El primer `gen-bench` de XQuAD (`20-xquad-base`) contestó "no encontrado" al **22 %** de las preguntas en inglés y al **19 %** de las de español, aunque el retriever trae la fuente correcta entre las 5 primeras en el 99 % de los casos (§1).

**El diagnóstico.** El benchmark separa dos causas de "no encontrado": que la fuente correcta llegue al generador y aun así se niegue (fallo del LLM), y que no le llegue ninguna fuente. Resultado:

| | EN | ES |
|---|---|---|
| Respuestas "no encontrado" | 262 | 229 |
| … con la fuente correcta en el contexto (fallo del LLM) | 55 | 4 |
| … **sin ninguna fuente** (las descartó el filtro) | **207** | **225** |

Casi todos eran del **filtro fuera de dominio (B15)**. Ese filtro (`search_for_generation`) toma las fuentes recuperadas, las puntúa con el cross-encoder (`mmarco-mMiniLMv2-L12`) y, si la mejor puntuación no llega a `relevance_threshold`, no le pasa nada al LLM y responde "no encontrado".

**La causa.** El umbral (0.0, un 50 % de relevancia según el reranker) se calibró en la Fase 3 **solo con vLLM**. Pero el cross-encoder no puntúa todos los corpus en la misma escala. En vLLM, las preguntas válidas sacan una mediana de **9.1** (docs) y **5.8** (code), muy por encima de 0. En XQuAD la mediana es **3.9** (EN) y **3.5** (ES), y el 10 % peor está por debajo de **−1.3**. *Hipótesis, no verificada:* las preguntas de XQuAD son paráfrasis más libres del párrafo y piden un dato concreto dentro de un texto largo, y el reranker, entrenado sobre MS MARCO, les da menos confianza aunque el párrafo tenga la respuesta. Con 0.0, el 17 % de las preguntas válidas de XQuAD se quedaban fuera.

**La medición (`gate_scores`, nuevo).** Para cada dominio se calcula la puntuación del filtro, exactamente como la calcula `search_for_generation` con k = 5, sobre dos grupos:
- **Lo que el dominio debe aceptar:** sus datasets.
- **Lo que debe rechazar:** el set fuera de dominio (40 preguntas: EN/ES, *far*/*near*) y los datasets de los demás dominios.

Se guarda en `bench/results/gate/`. Para XQuAD (fracción de preguntas por encima de cada umbral):

| Grupo | Debe | Mediana | −3.0 | **−2.0** | −1.0 | 0.0 |
|---|---|---|---|---|---|---|
| XQuAD EN | aceptar | 3.9 | 0.96 | **0.93** | 0.89 | 0.83 |
| XQuAD ES | aceptar | 3.5 | 0.96 | **0.93** | 0.87 | 0.81 |
| 42 docs / code | rechazar | −6.3 / −7.5 | 0.01 / 0.01 | **0.00 / 0.00** | 0.00 | 0.00 |
| Fuera de dominio *far* EN / ES | rechazar | −4.6 / −4.3 | 0.10 / 0.10 | **0.00 / 0.00** | 0.00 | 0.00 |
| Fuera de dominio *near* EN / ES | rechazar | −5.4 / −5.7 | 0.00 / 0.00 | **0.00 / 0.00** | 0.00 | 0.00 |

**La decisión.** `relevance_threshold = -2.0` solo para XQuAD, en `[sources.xquad]` de `rag.toml`. Es el umbral más bajo que **no deja pasar ni una** pregunta ajena en ningún grupo, y sube la aceptación de las válidas del 83 % al 93 %. Con −3.0 se aceptaría el 96 %, pero entrarían una de cada diez preguntas *far* (por ejemplo, de cultura general que no está en los 48 artículos).

**vLLM no cambia.** Sigue con el umbral global 0.0, y la misma medición lo confirma. Las preguntas válidas de vLLM pasan al 98–100 %, y lo que deja pasar coincide con el `gen-bench` de la Fase 3: un 20 % de *near* EN y un 30 % de *near* ES, es decir, rechazos correctos de 0.80 y 0.70. Eso valida la herramienta. Las 2 380 preguntas de XQuAD, puntuadas contra vLLM, pasan en un 0 % con el umbral 0.0.

**El resultado** (`gen-bench` completo, 1 190 preguntas por idioma, Qwen3-0.6B, k = 5):

| | EN antes (`20`) | **EN después (`22`)** | ES antes (`20`) | **ES después (`22`)** |
|---|---|---|---|---|
| Contiene la respuesta correcta | 0.59 | **0.65** | 0.51 | **0.57** |
| Responde "no encontrado" | 0.22 | **0.13** | 0.19 | **0.08** |
| … descartadas por el filtro | 0.17 | **0.07** | 0.19 | **0.07** |
| … con la respuesta en el contexto (fallo del LLM) | 0.05 | 0.06 | 0.00 | 0.00 |
| Contiene la respuesta, entre las que contesta | 0.76 | 0.74 | 0.64 | 0.62 |
| F1 | 0.152 | 0.167 | 0.149 | 0.169 |
| Cita / cita la correcta / idioma | 1.00 / 0.99 / 0.99 | 1.00 / 0.99 / 0.99 | 0.99 / 1.00 / 0.98 | 0.99 / 0.99 / 0.98 |

- **+6 puntos de respuestas correctas** en los dos idiomas. Los descartes del filtro bajan del ~18 % al 7 %.
- **"Contiene la respuesta, entre las que contesta" baja ~2 puntos.** Es lo esperable: las preguntas que ahora pasan el filtro son las que el reranker veía menos claras, y son algo más difíciles.
- **Lo que queda es del LLM, no de la recuperación:**
  - En inglés, un 6 % de "no encontrado" con la respuesta en el contexto.
  - En español, la respuesta se recoge peor (0.62 frente a 0.74). Una explicación probable, sin verificar: el modelo reformula los datos (números, nombres traducidos) en lugar de copiarlos del párrafo, y la métrica exige que la respuesta aparezca literal.
  - Son temas de generación (prompt por modo, modelo), no de este filtro.

**Cómo funciona ahora.**
- Cada fuente puede tener su propio `relevance_threshold`. Sin él, usa `retrieval.relevance_threshold`.
- `Retriever.from_store` aplica el umbral del dominio que carga.
- El router aplica el umbral del **dominio ganador**: el enrutado compara las puntuaciones en bruto y el filtro usa la escala del dominio elegido.

**Lo que queda abierto.**
- **El 7 % de preguntas válidas que siguen por debajo de −2.0.** Bajarlo más dejaría pasar preguntas ajenas. Un reranker mejor calibrado en Wikipedia (por ejemplo, `bge-reranker-v2-m3`, el perfil `gpu-quality`) podría separar mejor los dos grupos. No se ha medido.
- **El umbral depende de k.** Es el máximo de las puntuaciones de las k fuentes, así que con más fuentes la puntuación tiende a subir. Se calibró con k = 5, el de la web y el `gen-bench`. La CLI `answer` usa k = 10 por defecto, con lo que el filtro es algo más permisivo ahí.
- **El set fuera de dominio es pequeño** (10 preguntas por grupo). Cuando haya más dominios (CV, Gulliver), convendrá ampliarlo con preguntas ajenas a todos ellos.
- **Calibración de dominios nuevos:** cada uno debe pasar por `gate_scores` antes de fijar su umbral. Es un paso más del alta de un dominio.

### 1.3 Subconjunto fijo para el `gen-bench` de XQuAD

**Por qué tardaba tanto.** El `gen-bench` completo de XQuAD dura ~70–90 min. El ~96 % de ese tiempo es **generación**: la recuperación tarda ~50–65 ms por pregunta y la generación, 1.3–2.5 s.
- **Una pregunta cada vez:** Qwen3-0.6B en fp16 con `generate()` y batch 1. Con un modelo tan pequeño, lo que limita es el coste fijo de cada token, no la potencia de la GPU.
- **Prompts largos:** unos 2 000 tokens de contexto con k = 5.
- **El español es más lento:** los párrafos son ~25 % más largos y el tokenizador parte el español en más tokens.

**Qué se hace.**
- `make gen-bench SUITE=xquad` pregunta por defecto **300 preguntas fijas por idioma** (`even_sample`): repartidas uniformemente por los 48 artículos (unas 6 por artículo) y con los mismos IDs en inglés y en español. Tarda ~20 min.
- `FULL=1` (`--full`) pregunta las 2 380 y queda **solo para pruebas completas**.
- Cada resultado guarda `"sample"` (300 o `null`).
- La suite de vLLM no cambia.

**Es representativo.** Se ha comprobado sobre las respuestas de las dos ejecuciones completas, tomando las 300 preguntas del subconjunto:

| Ejecución | Set | Contiene (completo / 300) | "No encontrado" (completo / 300) |
|---|---|---|---|
| `20` (umbral 0.0) | EN | 0.593 / 0.573 | 0.22 / 0.24 |
| | ES | 0.513 / 0.520 | 0.19 / 0.21 |
| `22` (umbral −2.0) | EN | 0.646 / 0.633 | 0.13 / 0.14 |
| | ES | 0.570 / 0.590 | 0.08 / 0.10 |

Las diferencias son de ±2 puntos y la mejora del umbral se ve igual en los dos (+6 puntos). Sirve para comparar configuraciones. Las cifras oficiales salen siempre de una ejecución completa.

**Batching, descartado de momento.** Generar varias respuestas a la vez multiplicaría la velocidad sin tocar `llm_sdk`. Pero con fp16 y padding, las respuestas greedy pueden cambiar respecto a batch 1, y se perdería la comparabilidad con las ejecuciones anteriores.

### 3. Ficheros

| Fichero | Cambio |
|---|---|
| `src/sources/__init__.py`, `src/sources/xquad.py` | **Nuevos.** Descarga, verificación, corpus y datasets de XQuAD. |
| `src/router.py` | **Nuevo.** `DomainRouter`: búsqueda en todos los dominios o en los del filtro. |
| `src/evaluation/routing.py` | **Nuevo.** Benchmark de enrutado (`route_bench`). |
| `src/cli.py` | `fetch_xquad`, `route_bench`; `index` sin `--source` indexa todas las fuentes (`index_source`); `answer --domains`; `answer_dataset` sigue con un solo dominio. |
| `src/retriever.py` | `from_store`/`load_embedder` aceptan un embedder ya cargado para compartirlo. |
| `src/rag.py` | `RagPipeline` acepta un `Retriever` o un `DomainRouter`; `answer(..., domains=)`. |
| `src/web.py` | Usa el router y muestra la atribución de XQuAD. |
| `src/evaluation/bench.py` | `SUITE_DATASETS` y `SUITE_DOMAINS`; la tabla usa los nombres de cada suite. |
| `rag.toml` | Fuente `xquad`. |
| `Makefile` | `data-xquad`, `index` con `SOURCE=` opcional y `route-bench`. |
| `tests/test_router.py` | **Nuevo.** Ganador, filtro, filtro fuera de dominio (con el umbral del dominio ganador) y unión de mapas. |
| `src/evaluation/gen_bench.py` | Suites `vllm`/`xquad` (`GEN_SUITES`), métrica `contains_answer`, set fuera de dominio separado en `run_ood`, subconjunto fijo (`even_sample`) y `--full`. |
| `src/evaluation/gate.py` | **Nuevo.** Calibración del filtro fuera de dominio por dominio (`gate_scores`). |
| `src/config.py` | `SourceConfig.relevance_threshold` (umbral propio por fuente). |
| `src/retriever.py` | `from_store` aplica el umbral de la fuente. |
| `tests/test_config.py`, `tests/test_storage.py`, `tests/test_gen_bench.py` | Umbral por fuente y `contains_answer`. |
| **4b** | |
| `src/ingestion/loaders.py` | **Nuevo.** Texto de cada fichero; `.docx`/`.pdf` con Docling. |
| `src/ingestion/pipeline.py` | Lee los ficheros con `read_text`. |
| `src/domain_rules.py` | **Nuevo.** Datos privados, "no encontrado" y reglas de prompt por dominio. |
| `src/config.py` | `SourceConfig`: `private_data`, `public_emails`, `private_replacement`, `not_found_message`, `prompt_rules`, `answer_k`, `chunk_size`, `child_size`. |
| `src/rag.py` | Enmascara el contexto y la respuesta, usa el "no encontrado" y las reglas del dominio. |
| `src/generator.py` | `extra_rules` en el prompt; patrones nuevos de "no encontrado". |
| `src/retriever.py`, `src/router.py` | `answer_k` por dominio al responder. |
| `src/cli.py` | `build_cv_bench`; tamaños de chunk por fuente; las fuentes y el "no encontrado" se muestran con las reglas del dominio. |
| `src/web.py` | Muestra el "no encontrado" del dominio y las fuentes enmascaradas. |
| `src/sources/cv.py`, `bench/datasets/cv/` | **Nuevos.** Preguntas del CV (en git) y generador de los datasets. |
| `src/evaluation/{bench,routing,gate,gen_bench}.py` | Suite `cv`, preguntas sin dato del CV, fugas y `handled`. |
| `rag.toml` | Fuente `cv`. |
| `pyproject.toml`, `uv.lock` | `docling`, `torchvision` (cu126) y pytest sin `faulthandler`. |
| `.gitignore` | `cv/` → `/cv/`. |
| `tests/test_domain_rules.py` | **Nuevo.** Enmascarado y mensajes por dominio. |
| `pyproject.toml`, `uv.lock` | `pyarrow` declarado (antes llegaba solo de rebote por streamlit). |
| `bench/datasets/xquad/` | **Nuevo.** Datasets en/es y README de licencia. |
| `tests/test_xquad.py` | **Nuevo.** Formato de los ficheros, spans y corrección de offsets. |

### 4. Qué debes saber

- **Los offsets de Hugging Face están desplazados en un párrafo.** El parquet recorta los espacios de cada párrafo, pero conserva los `answer_start` originales. El párrafo de *Apollo_program* empieza por un espacio, así que sus 5 respuestas (en cada idioma) quedaban desplazadas un carácter. El script lo corrige restando lo recortado y falla si alguna respuesta no cuadra.
- **Las rutas del ground truth usan `/`** en todos los sistemas. Un `os.path.join` en Windows metía `\` y el recall salía 0; está corregido y cubierto por un test.
- **Las cabeceras de los ficheros en español llevan el título en inglés:** XQuAD no traduce los títulos.
- **BOM sin limpiar (decisión tuya):** dos artículos en español traen un carácter BOM invisible dentro del texto original. Se deja tal cual: la ingesta reproduce el material de origen sin manipularlo, para que cualquier máquina nueva obtenga exactamente lo mismo. Las únicas transformaciones son agrupar los párrafos por artículo y corregir los offsets de Hugging Face, y las dos se comprueban contra el texto.
- **XQuAD no tiene código**, así que todas sus preguntas van por la rama doc de `search_smart` (BM25 + dense con RRF, sin reranker).
- **Lint:** `mypy.exe` lo bloquea el Control de aplicaciones de Windows en esta máquina; `python -m mypy` funciona y pasa sin errores.
