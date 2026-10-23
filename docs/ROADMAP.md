# ROADMAP — RAG Against the Machine v2.0

Planificación del roadmap de la mejora del proyecto RAG. Todo lo que se discuta y acepte de aquí al futuro del proyecto se actualizará aquí donde corresponda.

**Documentos relacionados** (todos en `docs/`):
- `PLANING.md`: objetivos, propuestas, limitaciones y normas.
- `RESPUESTA.md`: análisis técnico, bugs detectados (B1–B13) y opciones valoradas. B14 y B15 están en `changelog/FASE_0.md`.
- `ROADMAP.md` (este): **documento vigente**. Si algo contradice a `RESPUESTA.md`, manda este.
- `changelog/FASE_N.md`: un changelog por fase, según las normas de `PLANING.md`.
- `BENCHMARK_REPORT.md`: comparativa de modelos y configuraciones (se crea en la Fase 2).

---

# Respuestas #

Tus respuestas a las dudas de `RESPUESTA.md` §7, con lo que implica cada una para el roadmap.

| Duda | Respuesta | Consecuencia en el roadmap |
|---|---|---|
| **D1** Datasets privados | Eran propios de la corrección. Con los públicos basta para tener una idea del rendimiento. | Los targets `test-*` del Makefile se eliminan en la Fase 0. La línea base se mide **solo** con los datasets públicos. |
| **D2** URLs del Makefile | Cambiaron en su momento. Actualizadas aquí; se cambiarán en el repo real más adelante. | El cambio del Makefile entra en el primer commit de la Fase 0. |
| **D3** Hardware | NVIDIA RTX 3080 Ti en local. La idea es que funcione en los ordenadores de 42 (tienen gráfica, poco potente, modelo desconocido). | **Valores por defecto ligeros** (deben correr en 42 y en CPU). Los modelos grandes son opcionales y se prueban en la 3080 Ti. Está pendiente averiguar la GPU de 42.<br>**Actualizado 2026-10-23:** las GPU de 42 no aceptan CUDA (indexar vLLM ahí lleva ~10 h), así que **se descarta indexar en 42**. Toda la ingesta se hace en la 3080 Ti y el proyecto se sirve **en línea**. En las presentaciones a empresas en 42 se enseña la web desplegada o se da el enlace. Los valores por defecto siguen siendo ligeros porque el despliegue gratuito es en CPU. |
| **D4** Evaluación | Los recalls se hacen **solo** sobre los datasets de 42. Cualquier test extra es bienvenido. Se puede usar una key gratuita para tests de respuesta. | El evaluador de 42 es la referencia y no se toca. Las métricas extra (MRR, nDCG, set manual, juez LLM por API gratuita) son complementarias. |
| **D5** Frontend | FastAPI + React, pero **la estética debe quedarse igual que la actual**. | Fase 6: React reproduce el diseño de `src/web.py` (colores, tipografías, tarjetas). |
| **D6** Idioma y dominios | Multilenguaje. Además, más datasets, no solo vLLM. Este repo es sobre todo para tener las marcas de recall claras. | Embeddings y reranker **multilingües** desde la Fase 2. La ingesta multi-dominio se prepara en la Fase 1 y se usa en la Fase 4. vLLM sigue siendo el **benchmark**. |
| **D7** Agente | Dicotomía: agente propio como intermediario, pero también acceso directo al RAG. **A discutir.** | La arquitectura soporta **ambos** caminos desde el diseño. La decisión de qué es lo por defecto se toma antes de la Fase 5.<br>**Decidido (2026-10-23): agente por defecto**, como en un RAG real, y con memoria de sesión. El acceso directo sigue disponible como opción. |
| **D8** Permiso Fase 0 | Sí, permiso para arreglar el código. Curiosidad por ver cómo evolucionan los recalls. | Se mide antes y después de cada fix, y se documenta en `changelog/FASE_0.md`. |
| **D9** Multimedia | Quiero que acepte todo lo posible. Videos y audios sobre todo. La idea es que funcione igual que algo destinado a produccion de alto standing. | La Fase 4b **deja de ser opcional**, con prioridad para **vídeo y audio**:<br>• Transcripción con marcas de tiempo.<br>• Imágenes con OCR + captions.<br>• Búsqueda de imágenes por texto (CLIP/SigLIP, nivel B).<br>El VLM generativo (nivel C) solo en local.<br>⚠️ "Producción de alto standing" choca con el despliegue gratuito en CPU: la ingesta se hace offline en la 3080 Ti y en producción solo se sirve lo ya indexado. |

**Nota:** tendríamos que hacer una comparativa del funcionamiento de los modelos propuestos para ver cuáles nos son más funcionales, igual que el `BENCHMARK_REPORT.md` de AgentSmith. Solo así podremos comprobar qué nos conviene más.

→ Se crea `docs/BENCHMARK_REPORT.md` en la Fase 2 (embeddings y rerankers) y se amplía en la Fase 3 (LLMs) y en la Fase 5 (agente frente a acceso directo).

---

# Puntualizaciones #

Dado que vamos a hacer un frontend real, podríamos plantear la **modularización** del proyecto: elegir qué modelo usar en cada momento, si usar o no el intermediario… cambiando la navegación dentro de la página web. **Tendremos que discutirlo.**

**Cómo lo preparamos sin cerrar la discusión:**
- Cada pieza del pipeline (chunker, embeddings, reranker, LLM, agente sí/no) se elige por **configuración**, no por código. Un fichero de config más un override por petición de la API.
- Las mismas opciones están disponibles en la CLI, en la API y en la web. La web solo muestra lo que la API permite.
- Qué opciones se exponen al usuario de la web, y cómo se navega entre ellas, se decide en la Fase 6.

---

# ROADMAP #

**Regla común a todas las fases:**
- Al cerrar cada fase se ejecuta `make bench` sobre los datasets públicos de 42.
- **Los recalls no pueden empeorar** respecto a la mejor marca anterior. Si empeoran, se justifica en el changelog o se revierte.
- **Prioridad de métricas: R@5 > R@10 > R@3 > R@1.** Un cambio que sube R@1 a costa de las demás no se adopta.
- Cada fase cierra con su `changelog/FASE_N.md`: qué se ha cambiado, lista de ficheros, por qué, en qué afecta y qué debes saber de la arquitectura.

```
Fase 0 ─► Fase 1 ─► Fase 2 ─► Fase 3 ─► [Pruebas 42] ─► Fase 4 ─► Fase 5 ─► Fase 6
saneam.   ingesta   híbrido   generac.    checkpoint     modos    agente+   web +
                                                                  MCP       deploy
```

## Fase 0 — Saneamiento y profesionalización del repositorio

**Objetivo:** dejar una base limpia y una **línea base medida y reproducible**.

- **Repositorio**
  - `.gitignore`.
  - Sacar `__pycache__/*.pyc` del control de versiones.
  - Commit de las URLs nuevas del Makefile (D2).
- **Makefile portable**
  - La ruta de caché pasa a ser una variable: `/goinfre` por defecto en 42, ruta local fuera de 42.
  - Eliminar los `test-*` (D1) y corregir `.PHONY`.
  - Retirar `index-embed` hasta la Fase 2 (hoy no hace nada).
- **Línea base "antes"**
  - Medir el recall público con el código tal cual, **antes** de tocar nada.
  - Se mide con `search_smart` (el modo evaluado en 42), no con `answer_dataset`.
- **Bugs** (permiso D8; cada uno se mide por separado):
  - **B1**: arreglar la señal CamelCase del clasificador.
  - **B2**: quitar la expansión por símbolos que no hace nada y que además recorre todo el corpus en cada query.
  - **B3**: una sola ruta de evaluación. `search-docs` y `search-code` pasan a usar `search_dataset`.
  - **B10**: centralizar los mensajes de "not found".
  - **B13**: limpieza de imports y constantes sin uso.
- **`make bench`**
  - Ejecuta búsqueda y evaluación de docs y code.
  - Guarda la config y las métricas en `bench/results/<fecha>_<etiqueta>.json`.
  - Imprime una tabla comparativa con las ejecuciones anteriores.
- **Tests mínimos** (`pytest`): evaluador, offsets de chunks y deduplicación hijo→padre. No buscan cobertura completa, sino servir de red de seguridad para las fases siguientes.
- **Lint**: se mantienen flake8 + mypy (los de 42).

**Cierre:** tabla "antes / después de cada fix" en `changelog/FASE_0.md`. La línea base oficial del v2.0 es el "después".

> ✅ **Completada (2026-10-18).** Línea base oficial v2.0 (`search_smart`, datasets públicos):
> - **Docs:** 0.64 / 0.83 / 0.85 / 0.85.
> - **Code:** 0.45 / 0.62 / 0.64 / 0.72 (R@10 de code sube desde 0.68).
>
> Detalle en `changelog/FASE_0.md`. Pendiente de tu commit.

## Fase 1 — Modificación de la ingesta

**Objetivo:** pasar de JSON sueltos a una **base de datos** con un modelo de datos que aguante todo lo que viene: multi-dominio, multilingüe, modos y multimedia.

- **Interfaz `Chunker`**, con implementaciones intercambiables por config:
  - **Código**: chunker AST propio, con los offsets corregidos (B7).
  - **Docs**: `langchain-text-splitters` (`MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`), comparado con el chunker actual.
  - **PDF/DOCX**: Docling, que se integra cuando llegue el CV (Fase 4).
- **Qdrant en modo local**:
  - IDs estables.
  - Payload con `domain` (vllm, cv, …), `chunk_type`, `modality` (text de momento), `lang`, `file_path`, rangos y `parent_id`.
- **BM25 (`bm25s`) se mantiene** como índice sparse, enlazado por el mismo ID.
- **Ingesta multi-dominio** (D6): `index --source vllm` (y en el futuro otros). Cada fuente declara su chunker y su colección o dominio.
- **Sistema de configuración** (base de la modularización): un fichero de config + variables de entorno, validado con pydantic.

**Cierre:** es un refactor, así que **los recalls deben ser iguales** a los de la Fase 0, salvo la variación por el fix de offsets (B7), que se documenta.

> ✅ **Completada (2026-10-18).** Detalle en `changelog/FASE_1.md`. Cambios respecto al plan:
> - **Qdrant en servidor (Docker)**, no en modo local: el modo local tardaba ~9 min en escribir los chunks.
> - **Chunker de docs:** tu versión empaquetada (`markdown_headers_packed`), no LangChain.
> - **`split_by_size()` arreglado (B16 + B17):** sin texto perdido, sin trozos duplicados y empezando en salto de línea.
>
> Línea base oficial (`search_smart`, ejecución `20-fix-b16-b17-v2`):
> - **Docs:** 0.67 / 0.84 / 0.87 / 0.89.
> - **Code:** 0.43 / 0.59 / 0.64 / 0.71. ⚠️ R@3 y R@10 quedan por debajo de la Fase 0 (0.62 / 0.72); se recupera en la Fase 2.

## Fase 2 — Retrieval híbrido

**Objetivo:** demostrar con números si el híbrido mejora, ahora que los embeddings se implementan bien (ver `RESPUESTA.md` §3).

- ✅ **Tokenizador code-aware** (B8 + B14): modo `code` (partes de identificadores solo en chunks e índices de code). Code 0.49 / 0.70 / 0.75 / 0.83; docs 0.72 / 0.91 / 0.93 / 0.94.
- **Embeddings de chunks y de query** con el mismo modelo y el prefijo de instrucción correcto.
  - Candidatos **multilingües** (D6): `multilingual-e5-small`, `bge-m3`, `Qwen3-Embedding-0.6B`.
  - Referencia: `bge-small-en-v1.5`.
  - La ingesta pesada se hace en la 3080 Ti. Los valores por defecto deben poder ejecutarse en 42 (D3).
  - ✅ torch con CUDA 12.6 configurado; `device = "auto"` cae a CPU sin GPU (probado).
- ✅ **Rutas unificadas**: `search_for_generation` = filtro de relevancia + `search_smart`.
- ✅ **Code recuperado** con la fusión RRF por listas y el reranker siempre activo: code 0.45 / 0.63 / 0.67 / 0.72 (supera la Fase 0) y docs 0.72 / 0.90 / 0.93 / 0.95.
- **Búsqueda por vectores contra Qdrant** (vectores con nombre en los mismos puntos de `rag_<dominio>`). Hoy el retriever carga todos los chunks en memoria.
- **Volver a medir el chunker de LangChain** tras el híbrido (está en *Posibilidades* de `PLANING.md`), por si se busca subir R@1.
- **Fusión con RRF**, con ablaciones por separado en docs y en code (BM25 / dense / híbrido).
- **Rerankers**:
  - `ms-marco-MiniLM` (referencia actual).
  - `bge-reranker-v2-m3` (multilingüe).
  - `Qwen3-Reranker-0.6B`.
- **Reglas manuales**: ✅ `skip_rerank_score` (ahora `inf`) y ✅ mínimo de 2 docs (eliminado al unificar). El umbral 5.5 está medido como mala señal; pasa a la Fase 3 (B15). Pendiente: revisar el clasificador doc/code.
- **Métricas complementarias**: MRR y nDCG@10. El evaluador de 42 queda intacto.

**Entregable:** `docs/BENCHMARK_REPORT.md`, sección *Retrieval* (tabla de configuraciones × recall docs/code × latencia).

> ✅ **Completada (2026-10-19).** Detalle en `changelog/FASE_2.md` y `docs/BENCHMARK_REPORT.md`.
> - **Línea base oficial:** docs **0.76 / 0.91 / 0.92 / 0.94**, code **0.51 / 0.72 / 0.80 / 0.88**. Las dos rutas son idénticas.
> - **Configuración:** BM25 code-aware + embeddings `bge-m3` (en las dos ramas) + reranker `mmarco-mMiniLMv2-L12` con RRF + clasificador con señales en inglés y español.
> - **Hecho:** CUDA con CPU como alternativa, rutas unificadas, tokenizador code-aware, embeddings, rerankers y clasificador.
> - **No hecho, pasa a pendientes:**
>   - Métricas MRR/nDCG.
>   - Volver a medir LangChain.
>   - Clasificador semántico.

## Fase 3 — Mejoras en la generación de respuesta

**Objetivo:** respuestas más naturales, con fuentes estructuradas y modelos intercambiables.

- **Backend de LLM** (`src/llm/`):
  - Qwen3-0.6B vía `llm_sdk` como **base y valor por defecto**. `llm_sdk` no se toca.
  - Backend HF genérico para los modelos opcionales.
- **Prompt**:
  - Chat template oficial con `enable_thinking=False`.
  - Presupuesto de contexto en tokens (B9).
  - Citas `[n]` enlazadas a las fuentes estructuradas.
  - Prompts por modo.
  - **Responder en el idioma de la pregunta** (hoy Qwen contesta en inglés a preguntas en español, aunque la recuperación ya es multilingüe).
  - **B15**: guardarraíles fuera de dominio. Hoy *"What is the capital of France?"* responde "Paris", aunque es literalmente el ejemplo de rechazo del prompt.
- **Streaming de tokens**, que prepara la API de la Fase 6.
- **Comparativa de LLMs** en la 3080 Ti: Qwen3-0.6B frente a Qwen3-1.7B / Qwen3-4B, SmolLM3-3B y Phi-4-mini.
  - Set de preguntas manual + juez LLM con una key gratuita (D4).
  - Se mide calidad y latencia.

**Entregable:** `BENCHMARK_REPORT.md`, sección *Generación*.

> ✅ **Completada (2026-10-19).** Detalle en `changelog/FASE_3.md` y `BENCHMARK_REPORT.md` §5.
> - **Benchmark de generación** (`make gen-bench`) y **juez** (`make judge`, Groq `gpt-oss-120b`, con caché).
> - **Prompt nuevo:** chat template oficial, citas `[n]`, idioma de la pregunta (ES: 90–100 %) y presupuesto en tokens (B9).
> - **B15 resuelto:** filtro con el reranker; rechaza el 100 % de lo claramente ajeno.
> - **Flujo único** (`src/rag.py`) para CLI, web y benchmark, con streaming.
> - **LLM:** Qwen3-0.6B como base; Qwen3-1.7B, Qwen3-4B y Phi-4-mini como perfiles (SmolLM3 descartado).
> - Evaluadores agrupados en `src/evaluation/`.

## Pruebas 42 — Checkpoint

No deben empeorar los resultados obtenidos durante la evaluación.

- `make bench` completo sobre los datasets públicos y comparativa contra la línea base de la Fase 0.
- Comprobar que el formato de salida sigue siendo compatible con la moulinette (`search_dataset`, `answer_dataset`, `evaluate`).
- Etiqueta `v2.0-core` si se supera. A partir de aquí se **añaden** funcionalidades; el núcleo medido no se toca sin volver a pasar este checkpoint.

> ✅ **Superado (2026-10-19).** Detalle en `changelog/CHECKPOINT_42.md`.
> - **Recall frente a la v1:** docs R@5 +0.07 (0.92) y code R@5 +0.17 (0.80).
> - **Comandos de 42:** compatibles.
> - **Sin GPU:** mismas métricas.
> - Se añade al prompt la regla de "dónde".

## Fase 4 — Inserción de modos

**Objetivo:** el RAG deja de ser "solo vLLM": cultura general multilingüe, tu CV y multimedia, cada uno como dominio propio y con su forma de medirse.

**Orden decidido:** 4a cultura general → 4b modo CV → 4c multimedia. El **router** se construye en 4a, en cuanto exista un segundo dominio, y crece con cada uno.

### 4a — Cultura general: XQuAD (después, MLQA)

- **Dataset:** XQuAD (Google, CC-BY-SA 4.0). Las **mismas** preguntas, sobre los mismos párrafos de Wikipedia, traducidas profesionalmente a 12 idiomas, entre ellos **inglés y español**.
  - Según su ficha, ~1 190 preguntas sobre ~240 párrafos; **a verificar** al descargarlo.
- **Por qué:** permite medir el multilingüismo con exactitud: *recall en inglés frente a español con las mismas preguntas y las mismas fuentes*. Es la versión a escala del set complementario de 20 preguntas.
- **Benchmark como el de 42:** se convierte al formato `RagDataset` (pregunta, respuesta y pasaje fuente con offsets), así que `make bench` y `make gen-bench` funcionan igual. El evaluador de 42 no se toca.
- **Ingesta:** dominio `xquad`, con su propia colección en Qdrant (`rag_xquad`) y un chunker adecuado para párrafos de Wikipedia.
- **Router:** decide entre `vllm` y `xquad` (y después los demás) según la pregunta o el modo elegido.
- **Licencia:** CC-BY-SA exige **citar la fuente** de forma visible en la web y publicar los derivados con la misma licencia.
- **Después:** MLQA (Meta, CC-BY-SA 3.0, miles de preguntas por idioma) como corpus más grande y exigente.

> ✅ **Completada (2026-10-23).** Detalle en `changelog/FASE_4.md` y `BENCHMARK_REPORT.md` §6.
> - **Hecho:** datos (HF + títulos de GitHub, con SHA256), un fichero por artículo, ground truth con el fragmento de la respuesta, dominio mixto `xquad` y `bench --suite xquad`.
> - **Hecho:** `make index` indexa todas las fuentes, router sin filtro o con `--domains` y atribución CC-BY-SA en la web.
> - **Recall:** EN 0.95 / 0.99 / 0.99 / 1.00, ES 0.92 / 0.99 / 0.99 / 1.00. vLLM sin cambios.
> - **Router:** el 100 % de las preguntas de 42 y ~98 % de las de XQuAD llegan a su dominio.
> - **Generación:** contiene la respuesta correcta en el 65 % (EN) y el 57 % (ES); cita la fuente correcta en el 99 %.
> - **Umbral del filtro fuera de dominio por dominio:** XQuAD usa −2.0, calibrado con `gate_scores`; vLLM sigue con 0.0. Sin ese umbral se descartaba el 18 % de las preguntas válidas.
> - **`gen-bench` de XQuAD:** subconjunto fijo de 300 preguntas por idioma; `FULL=1` para pruebas completas.
> - **Pendiente para más adelante:** MLQA.

### 4b — Modo CV

- **Material** (en `data/raw/cv/`, **ignorado por git**; se movió desde la raíz, donde se habría subido con `git add .`):
  - CV en `.docx` y perfil de LinkedIn en PDF.
  - `autobiography.md`, una autobiografía con gustos, aficiones y viajes, **por escribir juntos más adelante**.
- **Ingesta:** Docling para el `.docx` y el PDF; Markdown para la autobiografía. Colección `cv`.
- **Multilingüe**, con guardarraíles: si algo no está en los datos, no se inventa y se ofrece contacto.
- **Revisión de privacidad antes de indexar:** qué datos personales entran y cuáles no. Lo decides tú.
- **El juez externo (Groq) no se usa con datos personales** salvo que lo decidas expresamente.


> ✅ **Completada (2026-10-23).** Detalle en `changelog/FASE_4.md` (4b) y `BENCHMARK_REPORT.md` §7.
> - **Indexado:** CV (`.docx`, EN), LinkedIn (`.pdf`, ES) y biografía (ES + versión EN), con Docling.
> - **Privacidad:** el teléfono y el Hotmail se enmascaran al responder, sin tocar los ficheros. 0 fugas en todas las pruebas.
> - **Sin dato**, responde: *"No dispongo de esa información, ¡pero puedes preguntárselo tú! cdonairevillen@gmail.com"*.
> - **Prompt del modo CV** con tercera persona, sin mezclar trabajos, mundo literario secreto y contacto. Chunks de 800, 8 fuentes y umbral −3.0.
> - **Resultado:** contiene la respuesta correcta en el 73 % (EN) y el 80 % (ES); el router manda el 100 % de las preguntas del CV a su dominio.

- **Futuro, módulo de textos propios:** algunos relatos tuyos podrán ingestarse como parte del modo CV (o como dominio aparte). El mundo literario que estás creando es secreto por ahora: la biografía solo dice que existe, y el RAG no debe inventar detalles sobre él.

### 4c — Multimedia: *Los viajes de Gulliver* (1939) frente a la novela de Swift (1726)

> ⏸️ **Aplazada (2026-10-23, decisión tuya):** queda como posible fase al final del proyecto. El plan de abajo se conserva tal cual. Ya están descargados el libro y la película en `data/raw/gulliver/`, con URL y SHA256 en la checklist. Propuesta pendiente de aprobar cuando se retome: transcripción en Markdown con una cabecera por ventana de tiempo (`## 00:12:30`) en lugar del mapa de offsets a segundos.

- **Objetivo:** ingestar una misma historia en dos formatos, novela y película, y comparar qué recupera de cada uno. Un recruiter debe poder ver el código y todos los archivos usados en la ingesta.
- **Requisitos:**
  - La película debe tener **sonido**, para que la transcripción con Whisper aporte texto real.
  - Libro y película deben poder descargarse y publicarse sin problemas de derechos.
  - Todo **reproducible**: quien clone el repo obtiene los mismos datos.
- **Por qué Gulliver:** película de Fleischer, animada, en color, con diálogo y canciones, que **solo adapta la parte de Liliput**. Así se pueden probar tres tipos de preguntas:
  - **Solo libro:** Brobdingnag, Laputa, los Houyhnhnms. Sirven para comprobar que el RAG no inventa la respuesta a partir del vídeo.
  - **Solo película:** lo que la película añade, como la boda de la princesa Glory con el príncipe David o el personaje de Gabby.
  - **Ambos:** Liliput, Blefuscu, la guerra.
- **Descartados:**
  - *El Señor de los Anillos*: libros y películas con derechos de autor.
  - *Drácula* frente a *Nosferatu* (1922): las dos son de dominio público, pero *Nosferatu* es **muda**. Whisper no sacaría nada y habría que recurrir al OCR de los intertítulos.
  - *Drácula* de Universal (1931): tiene sonido, pero no es de dominio público.
- **Reservas** (si Gulliver falla por calidad de la copia o del audio):
  - *The Little Princess* (1939) + Burnett, Gutenberg #146.
  - *Scrooge* (1935) + Dickens, *A Christmas Carol*. Falta verificar la copia en archive.org y el número de Gutenberg.
- **Material:**
  - Novela: Gutenberg **#829**, en Plain Text UTF-8, quitando la cabecera y el pie de licencia antes de trocear.
  - Película: Internet Archive. Se elige la copia más ligera con buen audio y se anotan su URL y su SHA256.
- **Ingesta multimedia (nivel A del análisis), offline en la 3080 Ti:**
  - **Transcripción con Whisper** (`faster-whisper` con filtro VAD) y marcas de tiempo. La película tiene muchas canciones, y Whisper tiende a inventarse texto en los tramos de música; se comprueba con una prueba de 5 minutos.
  - **Descripción de escenas:** keyframes (PySceneDetect) + captions con un modelo de visión pequeño. La frecuencia de keyframes y el modelo se deciden en la prueba.
  - Cada chunk guarda su **modalidad** (libro, transcripción, caption) y su **posición** (capítulo o timestamp). Las fuentes enlazan al minuto exacto de la película.
  - **Propuesta a validar:** la transcripción se guarda como texto derivado más un mapa de offsets → segundos. Así `Chunk` y el evaluador siguen trabajando con offsets de caracteres, y la web convierte el offset al minuto.
  - Búsqueda de imágenes por texto con CLIP/SigLIP (nivel B) como opcional.
- **Evaluación:** el benchmark de 42 no cubre multimedia. Hace falta un set propio de 10–15 preguntas: solo libro, solo película y ambos. Las preguntas en español sobre el audio en inglés miden el multilingüismo.
- **Publicación:**
  - **Código** en GitHub: pipeline, `scripts/fetch_data.py` (URLs fijas + SHA256) y un GIF o keyframes del resultado en el README.
  - **Datos** en un **Hugging Face Dataset**: vídeo, `.txt` del libro y artefactos derivados (transcripción, captions, chunks en JSONL). Una dataset card con la fuente y la licencia de cada archivo. GitHub no acepta ficheros de más de 100 MB sin LFS, y el vídeo los supera.
  - **Demo:** la web de la Fase 6 (FastAPI + React), no una app aparte en Gradio o Streamlit.
- **Nota legal:** las películas candidatas son de dominio público en **EE. UU.**, no necesariamente en España, donde una película se protege 70–80 años desde la muerte del director, el guionista y el compositor. Publicarlas en plataformas estadounidenses (Hugging Face, Internet Archive) es la práctica habitual en proyectos de portfolio, pero **no es una garantía legal**. Las tres novelas son de dominio público en todo el mundo.
- **Plan B**, sin dudas legales en ningún país: películas abiertas de Blender con diálogo y licencia CC-BY (*Sprite Fright*, *Tears of Steel*) o audiolibros de LibriVox con el texto de Gutenberg. A cambio, se pierde la comparativa libro frente a película de la misma historia.
- **Checklist:**
  - [x] Localizar en archive.org la copia y anotar la URL y el SHA256 (2026-10-23, en `data/raw/gulliver/`, ignorado por git):
    - **Película:** `GulliversTravels720p_652` (CC0 según la ficha), `https://archive.org/download/GulliversTravels720p_652/GulliversTravels.mp4`. 720p h.264, 76:22, 475 808 316 bytes. SHA256 `a5c8ba9f5d6e57b307ea5398c5c4fefa8424da42fb6ea1d455fad0fc59dfdccd`; el SHA1 coincide con el que publica archive.org. Se descartó la copia más descargada (`gullivers_travels1939`) porque dura 72:39 y le faltan ~4 min.
    - **Novela:** `https://www.gutenberg.org/ebooks/829.txt.utf-8`, 613 946 bytes. SHA256 `fca36de3de0d8b831b7588cf1df84639ccf4c503172d6444ee61d1c1b2036edd`. Las marcas `*** START/END OF THE PROJECT GUTENBERG EBOOK ***` están en las líneas 27 y 9573. **Ojo:** Gutenberg puede revisar el fichero y cambiar el hash, así que la copia fija para reproducir será la del HF Dataset.
    - archive.org incluye además una transcripción automática (`GulliversTravels.asr.srt`) que puede servir de referencia para comparar con Whisper.
  - [ ] Comprobar qué hay que añadir al loader para el `.txt` y el vídeo.
  - [ ] Probar Whisper con 5 minutos: calidad de la transcripción y tiempo en la 3080 Ti.
  - [ ] Decidir la frecuencia de keyframes y el modelo de captioning.
  - [ ] Definir los metadatos de cada chunk: fuente, capítulo o timestamp, modalidad.
  - [ ] Escribir las 10–15 preguntas de evaluación.
  - [ ] Crear el dataset en Hugging Face con su dataset card.

## Fase 5 — Agentes y RAG como servidor MCP

**Objetivo:** acercarnos a cómo lo hacen las empresas, sin perder el acceso directo (D7).

- **Servidor MCP** (FastMCP, como en AgentSmith) con las herramientas `search(domain, query)`, `answer(...)` y `list_domains`.
- **Agente intermediario propio**:
  - Router, reescritura de la query y llamada a herramientas, con *fallback* determinista.
  - Bucle de varios pasos solo con los modelos opcionales grandes.
  - **Memoria** (petición tuya): historial de la conversación más memoria semántica recuperable. Se puede guardar en Qdrant (una colección `memory_*` con vectores) o, si hace falta algo relacional, motivar el paso a Postgres que se dejó abierto en la Fase 1.
- **Acceso directo al RAG** siempre disponible: se elige con un flag de config o de la petición.
- **Benchmark agente frente a acceso directo** (recall, calidad, latencia) en `BENCHMARK_REPORT.md`.
- ✅ **D7 decidido (2026-10-23):**
  - **Agente por defecto**, con acceso directo como opción.
  - **Todos los modelos pueden ser agente**, incluido Qwen3-0.6B, sin restringirlo. Los benchmarks dirán cuál se despliega.
  - **Memoria solo de sesión.**
- **Diseño:**
  - `src/server/tools.py` (herramientas del RAG).
  - Servidor MCP (`src/server/mcp_server.py`; FastMCP se llama `MCPServer` en `mcp` 2.x) sobre esas herramientas. ✅ Hecho: `make mcp`.
  - Agente en `src/agent/`: reescribe la pregunta con el historial, decide las búsquedas con el formato nativo de llamadas a herramientas del modelo (máximo 3 pasos) y da la respuesta final con el generador y las reglas de dominio actuales. Si falla, usa el flujo directo. ✅ Hecho: `answer` (agente por defecto), `chat` (con `/agent` para alternar) y `make agent-bench`.

## Fase 6 — Web deploy

**Objetivo:** una web pública para LinkedIn con los modos **CV** y **Demostración**.

- **Backend FastAPI**: `/chat` (streaming SSE), `/search`, `/sources/{id}`, `/metrics` y `/config` (modelos y opciones disponibles).
- **Frontend React** (Vite) con **la misma estética que la web actual** (D5):
  - Fondo `#0a0a0a` y acento `#ff3b3b`.
  - Tipografías JetBrains Mono + Inter.
  - Tarjetas de fuentes y barras de recall.
- **Navegación y selectores** (modelo, agente sí/no), según lo que se decida de la modularización.
  - **Interruptor "Con agente / Sin agente"** (petición tuya, 2026-10-23): un switch en la interfaz de chat que alterna entre el agente (por defecto: memoria de sesión, reescritura y herramientas) y la conversación directa con el RAG (el flujo actual, pregunta a pregunta). La API lo recibe como parámetro de la petición (`agent: true|false`); la Fase 5 deja los dos caminos listos detrás de ese mismo parámetro.
  - **Base ya preparada (Fase 2):** los perfiles de `rag.toml` (`available_profiles`) son las opciones que podría ofrecer un selector de ingesta, reranker o embeddings. La base estable sigue siendo la del benchmark. *A plantear en esta fase.*
- **Despliegue sin coste**:
  - Backend en un Hugging Face Space (Docker, CPU gratuito).
  - Frontend estático en GitHub Pages.
  - **Google Cloud no se toca.**
  - En el despliegue gratuito probablemente solo quepa un modelo cargado; el resto, en local.
  - **Índice preconstruido:** como no se indexa en 42 ni en el Space, el índice (snapshot de Qdrant + ficheros BM25) se construye en la 3080 Ti y el despliegue solo lo carga.
  - **Presentaciones en 42:** se enseña esta web desplegada o se da el enlace a los recruiters. No se instala nada en los ordenadores de 42.
  - **Datos en Hugging Face (a explorar, P10):** usar datasets de Hugging Face como fuente de la ingesta (por ejemplo, XQuAD) y, si se puede, alojar allí los nuestros: los de 42, los derivados de Gulliver y quizá el índice preconstruido.
- **README final**: se reescribe al terminar la mejora completa del proyecto.

---

# Decisiones pendientes #

| # | Tema | Cuándo hay que decidirlo |
|---|---|---|
| P1 | ~~D7: agente frente a acceso directo~~ → resuelto: agente por defecto, todos los modelos, memoria de sesión | Hecho |
| P2 | ~~Material multimedia~~ → resuelto: *Los viajes de Gulliver* (1939) frente a la novela de Swift (Gutenberg #829), con *The Little Princess* y *Scrooge* como reservas. Sustituye a *Nosferatu*/*Drácula*, que era muda. Copias descargadas el 2026-10-23 (URL y SHA256 en la checklist de la 4c) | Hecho |
| P7 | ~~`.gitattributes` para normalizar los finales de línea~~ → resuelto: todo LF y `llm_sdk/` intacto (commit `5a1cc4b`) | Hecho |
| P8 | ~~¿`bge-m3` por defecto aunque indexar en CPU lleve ~2 h?~~ → resuelto: `bge-m3` en la base y perfil `cpu-light` (`e5-small`) | Hecho |
| P9 | ~~`bge-reranker-v2-m3`~~ → resuelto: perfil opcional `gpu-quality` | Hecho |
| P3 | ~~Dominios nuevos~~ → resuelto: XQuAD (cultura general, en/es) y después MLQA | Hecho |
| P4 | Modularización: qué opciones se exponen en la web y cómo se navega | Antes de la Fase 6 |
| P5 | ~~GPU de los ordenadores de 42~~ → resuelto: no aceptan CUDA (vLLM tarda ~10 h en indexarse). Se descarta indexar en 42 y el proyecto se sirve en línea | Hecho |
| P10 | Hugging Face Datasets: usarlos como fuente de la ingesta y alojar allí los nuestros (los de 42, los derivados multimedia y quizá el índice). Falta revisar si la licencia de los datasets de 42 permite publicarlos | A desarrollar; antes de la Fase 6 (despliegue) o de la 4c si se retoma |
| P6 | Proveedor de la key gratuita para el juez LLM | Antes de la Fase 3 |

---

# Información sobre el roadmap #

(Aquí escribiremos puntualizaciones y decisiones que hacer durante la producción.)

- **2026-10-18**: creado el repo v2.0 (`RAG_Against_the-machine_42_project-v2.0`) con todo el historial. El estado entregado a 42 queda etiquetado como `v1.0-42`. Remotos: `origin` apunta al v2.0 y `v1` al repo original, que queda congelado.
- **2026-10-18**: la documentación de trabajo se mueve a `docs/`. El `README.md` sigue en la raíz y se reescribirá al final del proyecto. En la raíz queda un `CLAUDE.md` mínimo que importa `docs/PLANING.md` y `docs/ROADMAP.md`, para que Claude Code siga cargando las normas automáticamente.
- **2026-10-18**: el CDN de 42 devuelve 403 sin sesión. Los datasets públicos se versionan en `data/datasets/` (recuperados del historial) y vLLM 0.10.1 se descarga de la etiqueta oficial de GitHub. Verificado: las 200 fuentes de ground truth coinciden en ruta y offsets.
- **2026-10-18**: `llm_sdk` se importa de forma estándar (`from llm_sdk import ...`). El arreglo está en la config de mypy (`mypy_path = "llm_sdk"`), sin tocar la carpeta del SDK.
- **2026-10-18**: Fase 0 completada. Ver `changelog/FASE_0.md`.
- **2026-10-18**: **base de datos: Qdrant en servidor (Docker)**, decidido tras medir Qdrant local, Qdrant servidor, Postgres + pgvector, SQLite y LanceDB (esta última bloqueada por Windows). Postgres queda como opción si más adelante hace falta una base relacional (por ejemplo, la memoria del agente).
- **2026-10-18**: prioridad de métricas: R@5 > R@10 > R@3 > R@1.
- **2026-10-18**: LangChain descartado como chunker en esta versión (anotado en *Posibilidades*); el chunker de docs por defecto es el propio empaquetado.
- **2026-10-18**: el campo `lang` del payload, previsto en la Fase 1, no se ha añadido todavía: vLLM es solo inglés. Entra con el modo CV multilingüe (Fase 4).
- **2026-10-18**: Fase 1 completada. Ver `changelog/FASE_1.md`.
- **2026-10-18**: Fase 2 iniciada: CUDA 12.6 (con CPU como alternativa), fusión RRF del reranker y rutas unificadas. Ver `changelog/FASE_2.md`.
- **2026-10-19**: embeddings `bge-m3` por defecto (con `e5-small` como alternativa sin GPU); reranker `mmarco-mMiniLMv2-L12` (multilingüe); `Qwen3-Embedding` y `Qwen3-Reranker` descartados por coste; Jina descartado por licencia no comercial. Set complementario en inglés y español (20 preguntas) en `bench/datasets/`.
- **2026-10-19**: Fase 2 completada (pasos 3–5 hechos de forma autónoma con tu autorización, para revisarlos). Ver `changelog/FASE_2.md`.
- **2026-10-19**: perfiles: base estable (`bge-m3` + `mmarco` + Qwen3-0.6B) y modelos extra como opciones explícitas (`gpu-quality`, `cpu-light`, `llm-*`). Base para los selectores de la web (Fase 6).
- **2026-10-19**: el caso estrella de B15 ("capital of France") estaba en la documentación de vLLM como ejemplo de la API; no era una alucinación.
- **2026-10-19**: Fase 3 completada. Ver `changelog/FASE_3.md`.
- **2026-10-19**: checkpoint "Pruebas 42" superado; etiqueta `v2.0-core` (un marcador, no una rama: el proyecto sigue en `main`). Ver `changelog/CHECKPOINT_42.md`.
- **2026-10-19**: Fase 4 planificada: 4a cultura general (XQuAD; después MLQA), 4b modo CV y 4c multimedia (*Nosferatu*/*Drácula*). *El Señor de los Anillos*, descartado por derechos de autor. Innovatiana revisado: catálogo orientado a entrenar modelos de visión, sin datasets útiles para evaluar el RAG.
- **2026-10-19**: la carpeta del CV se movió de la raíz a `data/raw/cv/` (ignorada por git) y se añadió `cv/` al `.gitignore`, para que nunca se suban datos personales.
- **2026-10-18**: las cifras del README (docs 0.89 / code 0.75 en R@10) eran de los datasets **públicos**, aunque estuvieran etiquetadas como privadas, y salían de configuraciones anteriores que no se reproducen con `v1.0-42`. Se acepta como línea base oficial `04-fase0-final / smart`. La etiqueta del README se corrige en la reescritura final.
- **2026-10-18**: finales de línea normalizados a LF con `.gitattributes`, con `llm_sdk/` excluido (P7).
- **2026-10-23**: se **descarta indexar en el cluster de 42**: sus GPU no aceptan CUDA y vLLM tarda ~10 h. Toda la ingesta se hace en la 3080 Ti y el proyecto se aloja en línea. En las presentaciones a empresas se enseña la web desplegada o se da el enlace (P5).
- **2026-10-23**: 4c cambia de *Nosferatu*/*Drácula* a *Los viajes de Gulliver* (1939) frente a la novela de Swift. Al tener sonido se puede usar Whisper, y como solo adapta Liliput permite preguntas que solo responde el libro. Contenido tomado del documento "RAG 2 — Selección de fuentes multimedia", que se ha borrado tras integrarlo aquí. La demo sigue el roadmap (FastAPI + React), no Gradio ni Streamlit.
- **2026-10-23**: abierta la exploración de Hugging Face Datasets, como fuente de la ingesta y para alojar los nuestros (P10).
- **2026-10-23**: Fase 4a iniciada. XQuAD con un fichero por artículo, dominio mixto en+es, ground truth con el fragmento exacto de la respuesta y datos de HF con los títulos de GitHub (decisiones tuyas). Ver `changelog/FASE_4.md`.
- **2026-10-23**: router decidido: sin filtro busca en todos los dominios y responde desde el mejor; con filtro, solo en los elegidos. `make index` pasa a indexar todas las fuentes (`SOURCE=` para una sola). Los comandos y el benchmark de 42 siguen fijados a `vllm`.
- **2026-10-23**: umbral del filtro fuera de dominio **por dominio** (`relevance_threshold` en cada fuente). El reranker puntúa cada corpus en su propia escala, así que cada dominio nuevo se calibra con `gate_scores` antes de fijar su umbral.
- **2026-10-23**: el `gen-bench` de XQuAD usa un subconjunto fijo de 300 preguntas por idioma; la ejecución completa (`FULL=1`) queda para pruebas completas. Fase 4a completada.
- **2026-10-23**: descarga unificada: `make data` = vLLM (desde el repo de GitHub) + XQuAD. Se elimina `data-42`, que era redundante (mismo vLLM, datasets ya versionados, 403 fuera de 42). Ver `changelog/FASE_5.md` §5.
- **2026-10-23**: `src/` reorganizado en `rag/` (el RAG), `server/` (herramientas y MCP) y `agent/` (el agente), sin cambios de lógica. Ver `changelog/FASE_5.md`.
- **2026-10-23**: **D7 decidido** y Fase 5 iniciada: agente por defecto (como un RAG real), todos los modelos pueden ser agente, memoria solo de sesión y acceso directo como opción. El campo `lang` sale del plan: las respuestas ya siguen el idioma de la pregunta (90–100 %).
- **2026-10-23**: **4c (multimedia, Gulliver) aplazada** como posible fase final. La Fase 4 se cierra con 4a y 4b. MLQA, también opcional, se queda para el final.
- **2026-10-23**: biografía del modo CV, borrador v1 en `data/raw/cv/autobiography.md` (ignorado por git), con los datos pendientes marcados. Notas originales en `data/private_notes/`.
