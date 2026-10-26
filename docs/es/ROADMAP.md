# ROADMAP — RAG Against the Machine v2.0

Planificación del roadmap de la mejora del proyecto RAG. Todo lo que se discuta y acepte de aquí al futuro del proyecto se actualizará aquí donde corresponda.

**Documentos relacionados** (todos en `docs/es/`, la versión de trabajo en español):
- `PLANING.md`: objetivos, propuestas, limitaciones y normas.
- `RESPUESTA.md`: análisis técnico, bugs detectados (B1–B13) y opciones valoradas. B14 y B15 están en `changelog/FASE_0.md`.
- `ROADMAP.md` (este): **documento vigente**. Si algo contradice a `RESPUESTA.md`, manda este.
- `changelog/FASE_N.md`: un changelog por fase, según las normas de `PLANING.md`.
- `BENCHMARK_REPORT.md`: comparativa de modelos y configuraciones (se crea en la Fase 2).
- `decisions.md`: decisiones tomadas por necesidad, con sus opciones.
- `README.md`: traducción al español del README del proyecto.

**Versión en inglés** (`docs/`, sin el `es/`): traducción de `ROADMAP.md`, `BENCHMARK_REPORT.md`, `decisions.md` y los changelogs, para GitHub y los recruiters. **Se trabaja en español** y la traducción se actualiza **al cerrar cada fase**. `PLANING.md`, `RESPUESTA.md` y `Elements_frontend.md` no se traducen (planteamiento inicial y notas de trabajo).

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
| **D7** Agente | Dicotomía: agente propio como intermediario, pero también acceso directo al RAG. **A discutir.** | La arquitectura soporta **ambos** caminos desde el diseño. La decisión de qué es lo por defecto se toma antes de la Fase 5.<br>**Decidido (2026-10-23): agente por defecto**, como en un RAG real, y con memoria de sesión. El acceso directo sigue disponible como opción.<br>**Cambiado en la web (2026-10-24):** directo por defecto, con el agente marcado como trabajo en curso (Fase 7). |
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
Fase 0 ─► Fase 1 ─► Fase 2 ─► Fase 3 ─► [Pruebas 42] ─► Fase 4 ─► Fase 5 ─► Fase 6 ─► Fase 7
saneam.   ingesta   híbrido   generac.    checkpoint     modos    agente+   web +     opcionales
                                                                  MCP       deploy    y mejoras
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

> ✅ **Completada (2026-10-23).** Dominio `cv`: el autor presentado por sus propios documentos, con los datos de contacto privados protegidos. Detalle en `changelog/FASE_4.md` (4b) y `BENCHMARK_REPORT.md` §7.

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

> ✅ **Completada (2026-10-24)**, pendiente de tu revisión. Detalle en `changelog/FASE_5.md` y `BENCHMARK_REPORT.md` §8.
> - **Redes de seguridad** (DEC-03 en `docs/decisions.md`): si la reescritura no encuentra nada, se busca la pregunta original; si el dominio elegido por el modelo no tiene nada, se repite dentro del filtro del usuario, **nunca fuera**.
> - **Agente frente a directo** (Qwen3-0.6B): seguimientos **0.78 frente a 0.33**; en preguntas sueltas queda a ±0.04 del directo con los cuatro modelos. Qwen3-4B llega a 1.00 en seguimientos.
> - **Recall de 42:** sin cambios. Los datasets de 42 pasan a `bench/datasets/public/` y el recall sale idéntico (`61-datasets-moved`).
> - **Pendiente de decidir:** qué LLM se despliega (propuesta: Qwen3-0.6B; Qwen3-1.7B si la CPU del Space lo aguanta).
> - **No hecho, a propósito:** memoria semántica en Qdrant (D7: solo de sesión).

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
  - ~~Backend en un Hugging Face Space (Docker, CPU gratuito).~~ → **Oracle Cloud Always Free** (DEC-19, 2026-10-24): desde julio de 2026, los Spaces de Docker son de pago.
  - Frontend estático en GitHub Pages.
  - **Google Cloud no se toca.**
  - En el despliegue gratuito probablemente solo quepa un modelo cargado; el resto, en local.
  - **Índice preconstruido:** como no se indexa en 42 ni en el Space, el índice (snapshot de Qdrant + ficheros BM25) se construye en la 3080 Ti y el despliegue solo lo carga.
  - **Presentaciones en 42:** se enseña esta web desplegada o se da el enlace a los recruiters. No se instala nada en los ordenadores de 42.
  - **Datos en Hugging Face (a explorar, P10):** usar datasets de Hugging Face como fuente de la ingesta (por ejemplo, XQuAD) y, si se puede, alojar allí los nuestros: los de 42, los derivados de Gulliver y quizá el índice preconstruido.
- **README final**: se reescribe al terminar la mejora completa del proyecto.

> 🟡 **Preparada hasta el punto de despliegue (2026-10-24)**, pendiente de tu revisión. Detalle en `changelog/FASE_6.md`, guía en `deploy/README.md` y decisiones en `docs/decisions.md` (DEC-04 a DEC-16).
> - **API FastAPI** (`src/api`): `/chat` (SSE, con `agent`, `domains`, `model` y `depth`), `/search`, `/sources/{id}`, `/metrics`, `/config` y `/health`. Probada con el índice real: 0 fugas.
> - **Web React** (`web/`), revisada contigo en varias rondas (`FASE_6.md` §6b–6g):
>   - Chat a pantalla completa y filtros de dominio (sin modos Demo/CV).
>   - Interruptor de agente, selectores de modelo y de profundidad (5 por defecto).
>   - Botón Stop y preguntas de ejemplo.
>   - Retrievals del dominio de la respuesta con carrusel y esquinas de puntos, y tarjetas de recall por dominio.
>   - La API sirve la web en `/`. Commit `3378494`.
> - **Despliegue:** Space de HF (Docker, CPU) con Qdrant dentro; índice en un bundle (`make bundle`, SHA256) en un **dataset privado**; Pages con un workflow manual.
> - **Queda en tus manos:** crear el dataset y el Space, poner los secretos y decidir el LLM del Space, la estrategia de privacidad (DEC-09) y si se borra Streamlit (DEC-13).
> - **P4 (modularización):** la web expone los filtros de dominio, el agente sí/no, el modelo (los perfiles `llm-*`, uno cargado a la vez) y la profundidad.

## Fase 7 — Opcionales y mejoras

**Objetivo:** pulir lo que ha salido al usar la web y recoger los opcionales aparcados. Fase abierta el 2026-10-24, tras el commit `3378494`. Changelog en `changelog/FASE_7.md`.

### 7a — Dominio "about": el proyecto habla de sí mismo (lo primero)
1. **Reescribir el `README.md`** (pendiente desde la Fase 0), pensado para GitHub y los recruiters. Será la fuente principal del dominio. Se revisa contigo antes de indexarlo.
2. **Fuente `about` en `rag.toml`:**
   - **Entran:** el README, `ROADMAP.md`, `BENCHMARK_REPORT.md`, `decisions.md`, los changelogs y el código de `src/` (chunker de código AST).
   - **Fuera:** `PLANING.md`, `RESPUESTA.md` (el planteamiento inicial, ya superado) y `Elements_frontend.md`.
   - **A comprobar:** si el cargador actual acepta esa selección de ficheros o necesita uno propio, como el del CV.
3. **Set de 15–20 preguntas** en inglés y español sobre el proyecto, para medir recall y generación.
4. **Umbral propio** calibrado con `gate_scores`, y **`route-bench`**: 42 → vLLM al 100 %, XQuAD ~98 %, CV 100 %. `docs/` habla mucho de vLLM y del CV, así que el riesgo de robarles preguntas es real.
5. **API y web:** chip "about" **siempre activo** (no se puede apagar), sus preguntas sugeridas en el desplegable de ejemplos, y el dominio dentro del bundle del despliegue.

**Avance (2026-10-24):**
- ✅ **1.** README reescrito en inglés y aprobado, con licencia MIT y copia en español (`docs/es/README.md`).
- ✅ **2.** Fuente `about` indexada. Hizo falta un campo nuevo, `exclude_paths`, para excluir `deploy/stage` sin perder `src/deploy`.
- 🟡 **3.** 18 preguntas EN/ES (`bench/datasets/about/`). Primera medida: EN R@5 0.78, ES 0.22. El español se hunde porque cada pregunta solo admitía una fuente (la del README), y las preguntas en español encuentran lo mismo en los documentos en español.
- **Decisión tuya:** documentación en dos idiomas (`docs/` en inglés y `docs/es/` en español) y varias fuentes válidas por pregunta.
- ✅ **3 (cont.).** Ground truth en el idioma de la pregunta; con la métrica "contiene la respuesta", la respuesta está en las 5 primeras fuentes en el 89 % (EN y ES).
- ✅ **4.** Lo personal del CV fuera de "about" (marcas `about:skip`, decisión tuya: redirigir y no repetir). Umbral −1.0 y regla léxica del proyecto (`route_hints`). Route-bench `76`: CV 0.97 / 0.97, about 0.78 / 0.89, y 42 y XQuAD sin cambios.
- ✅ **5.** Chip "about" fijo (`pinned`), ejemplos comprobados uno a uno y bundle con los cuatro dominios. Detalle en `FASE_7.md` §7a.6–7a.8.

### 7b — Calidad de las respuestas
- **Markdown en la web** (listas, negritas, código). Sin riesgo: no cambia ninguna respuesta.
- **Plan B del agente:** busca con la consulta anterior + la nueva, pero debe **responder a la pregunta original**. Con el 0.6B, responder a la mezcla da respuestas equivocadas en los seguimientos (medido, `FASE_6.md`). Se mide con `agent-bench` antes de adoptarlo.
- **Regla de formato** (listas y negritas) solo en la web, probada por modelo: con el 0.6B, cada regla de más en el prompt puede costar aciertos.
- **Juez de las respuestas, sobre todo las del CV:** para encontrar dónde fallan, no para mostrarlo en la web. **Decidido (P11): Groq**, hasta agotar los tokens gratuitos; si hace falta, se repite con Qwen3-4B como juez local.
- 🟡 **Libertad de longitud** (petición tuya, 2026-10-24): dejar que el LLM escriba lo que necesite sin quedarse en bucle. ✅ **Detector de bucles integrado** (`src/rag/loops.py`, `FASE_7.md` §7b.2): para la generación cuando el modelo empieza a repetir líneas o frases casi iguales. 0 falsos positivos en 11.550 respuestas, y los bucles de Phi pasan de 1.500 tokens a 419–661. Límite de la web subido a 1.024 tokens para todos los modelos (decisión tuya), ahora solo como red de seguridad.
- **Agente desactivado por defecto en la web** (decisión tuya, 2026-10-24), marcado como trabajo en curso hasta mejorar el plan B.
- ✅ **Respuestas que copian el prompt** (noche del 24 al 25, `FASE_7.md` §7b.3, DEC-21/22). Los prompts nuevos empeoraban las citas y el idioma, así que el prompt no cambia. Se limpian las respuestas: eco a 0 en las 4.662 respuestas medidas, sin perder ninguna.
- ⏸️ **Fuentes de "about" en un solo idioma** (§7b.4, DEC-23): implementado y desactivado. Muy bueno para el 0.6B (EN contiene 0.44 → 0.61), peor en citas para los opcionales. **A decidir por ti.**
- ✅ **Preguntas que nombran el proyecto** (§7b.5, DEC-24): "este rag", "this project"… van a "about" sin pasar su filtro (8 de 8; antes, 0), y el nombre del autor manda al CV.
- 🟡 **Qué documentación ve "about"** (§7b.6, DEC-25): al crecer la documentación, la generación de "about" baja. Se ha restaurado el índice anterior; antes del despliegue hay que decidir qué partes nuevas se marcan con `about:skip`.
- ✅ **Forma de las respuestas** (§7b.7, DEC-27 a DEC-31, sesión del 25 al 26): banco de preguntas abiertas como en la web, detector de bucles con ventana 12 y bloques repetidos, y reintento cuando Phi copia las fuentes. El 0.6B, el 1.7B y el 4B quedan idénticos; Phi pasa de 2 respuestas cortadas y 1 con eco a ninguna. Queda "Hablame sobre este rag" (las fuentes que llegan son pobres) y el índice de "about" (DEC-25). Pros y contras de volver a una versión anterior, al final de `decisions.md`.

### 7c — Visual
- Tarjetas de recall flotantes que giran al pasar de una a otra.
- Estilo definitivo de la barra de scroll.

### 7d — Opcionales aparcados
- **4c, Gulliver** (multimedia). El plan está en la Fase 4.
- **MLQA.**
- **Módulo de textos propios:** relatos del autor, como parte del modo CV o como dominio aparte.
- ~~**`repetition_penalty`**~~ → **descartado** (2026-10-24, decisión tuya): en sus bucles, Phi-4-mini cambia palabras en cada vuelta, así que penalizar la repetición no los corta. La plantilla oficial y los tokens de parada se comprobaron y están bien (`FASE_7.md` §7b.1).

**Nota sobre el despliegue:** Phi-4-mini no cabe en el Space gratuito (en CPU, en float32, ocuparía ~15 GB, y además está la búsqueda). Incluso cargado a media precisión, tardaría minutos por respuesta en 2 CPU (estimado, sin medir). En el Space, lo realista es el 0.6B y quizá el 1.7B. Phi sigue siendo una opción en local.

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
| P4 | ~~Modularización: qué opciones se exponen en la web~~ → resuelto en la revisión de la Fase 6: filtros de dominio, agente sí/no, modelo y profundidad | Hecho |
| P11 | ~~Juez de las respuestas del CV (Fase 7b)~~ → resuelto (2026-10-24, decisión tuya): **Groq**, también con las preguntas del CV, hasta agotar los tokens gratuitos. Si hace falta, se repite con Qwen3-4B como juez local | Hecho |
| P12 | LLM del servidor: el 0.6B (la base) o el 1.7B (mejor agente; su latencia en CPU está sin medir). En Oracle, el 1.7B cabría en memoria (estimado ~9.5 GB de 12) | Antes del despliegue |
| P5 | ~~GPU de los ordenadores de 42~~ → resuelto: no aceptan CUDA (vLLM tarda ~10 h en indexarse). Se descarta indexar en 42 y el proyecto se sirve en línea | Hecho |
| P10 | Hugging Face Datasets: usarlos como fuente de la ingesta y alojar allí los nuestros (los de 42, los derivados multimedia y quizá el índice). Falta revisar si la licencia de los datasets de 42 permite publicarlos. **Avance (2026-10-24):** con Oracle, el índice preconstruido va por `scp` a la máquina (DEC-19); el dataset **privado** de HF (DEC-09) queda como alternativa. Publicar los datasets de 42 sigue sin hacerse: la licencia no está revisada | A desarrollar; antes de la Fase 6 (despliegue) o de la 4c si se retoma |
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
- **2026-10-23**: datasets de 42 movidos de `data/datasets/` a `bench/datasets/public/`: `bench/` queda para lo versionado y `data/` para lo local (DEC-01). El evaluador de 42 se conserva como métrica de referencia.
- **2026-10-24**: redes de seguridad del agente (DEC-03) y benchmark de agente frente a directo con cuatro modelos (`BENCHMARK_REPORT.md` §8). Fase 5 completada, pendiente de revisión.
- **2026-10-24**: Fase 6 preparada hasta el punto de despliegue (API, web React, bundle del índice, imagen del Space, workflow de Pages), sin commits ni publicación. Decisiones tomadas por necesidad en `docs/decisions.md`.
- **2026-10-24**: revisión de la web contigo (`FASE_6.md` §6b–6g). Commit `3378494` ("Phase 6: Frontend and deployment"). El despliegue en Hugging Face queda pendiente de tus cuentas.
- **2026-10-24**: **agente desactivado por defecto en la web** (decisión tuya): con los modelos pequeños, su memoria mezcla temas o da respuestas demasiado básicas. Al encenderlo, un aviso "work in progress". La CLI mantiene D7. Se revisa tras la mejora del plan B (7b). El dominio "about" queda fuera de la web (`API_DOMAINS`) hasta calibrarlo. Ver `changelog/FASE_7.md`.
- **2026-10-24**: **documentación en dos idiomas** (decisión tuya). Los originales en español pasan a `docs/es/` (con `git mv`; Git solo lo registra como renombrado en `PLANING.md`, `RESPUESTA.md` y `Elements_frontend.md`. En los demás, la traducción reutiliza la ruta antigua, así que su historial en español se consulta con `git log docs/<fichero>` y no con `--follow` sobre `docs/es/`) y siguen siendo la versión de trabajo. `docs/` tiene la traducción al inglés, que se actualiza al cerrar cada fase. El README tiene su copia en español en `docs/es/README.md`. `CLAUDE.md` carga las normas desde `docs/es/`. Los dos idiomas se indexan en el dominio "about".
- **2026-10-24**: abierta la **Fase 7 (opcionales y mejoras)**. Empieza por el dominio "about" (el proyecto hablando de sí mismo, con el README reescrito, `docs/` y el código). El juez de las respuestas del CV queda pendiente de decidir (P11).
- **2026-10-24**: dominio "about" terminado y en la web (chip fijo). La información personal del CV deja de repetirse en la documentación: se redirige a `FASE_4.md` §4b y se excluye del índice de "about".
- **2026-10-24**: **despliegue en Oracle Cloud Always Free** en lugar de Hugging Face, que desde julio de 2026 cobra por los Spaces de Docker. Separado de Google Cloud (decisión tuya). Medido: 5.0 GB de pico de RAM con 2 CPU y 12 GB (DEC-19, `deploy/README.md`).
- **2026-10-25**: sesión autónoma nocturna (decisiones DEC-20 a DEC-26). Limpieza del eco, preguntas que nombran el proyecto y filtro de idioma (desactivado). Todo medido contra una línea base de los cuatro modelos; 42 idéntico. Sin commits. Ver `changelog/FASE_7.md` §7b.3–7b.6.
- **2026-10-26**: segunda sesión autónoma (DEC-27 a DEC-31): forma de las respuestas (cortadas, eco de Phi, bucles largos). Medido contra la línea base `90`: los Qwen idénticos y Phi mejor en todos sus casos; 42 idéntico. Checkpoint por petición tuya, con los pros y contras de volver atrás en `decisions.md` para discutirlo. Ver `changelog/FASE_7.md` §7b.7.
