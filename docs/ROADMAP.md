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
| **D3** Hardware | NVIDIA RTX 3080 Ti en local. La idea es que funcione en los ordenadores de 42 (tienen gráfica, poco potente, modelo desconocido). | **Valores por defecto ligeros** (deben correr en 42 y en CPU). Los modelos grandes son opcionales y se prueban en la 3080 Ti. Está pendiente averiguar la GPU de 42. |
| **D4** Evaluación | Los recalls se hacen **solo** sobre los datasets de 42. Cualquier test extra es bienvenido. Se puede usar una key gratuita para tests de respuesta. | El evaluador de 42 es la referencia y no se toca. Las métricas extra (MRR, nDCG, set manual, juez LLM por API gratuita) son complementarias. |
| **D5** Frontend | FastAPI + React, pero **la estética debe quedarse igual que la actual**. | Fase 6: React reproduce el diseño de `src/web.py` (colores, tipografías, tarjetas). |
| **D6** Idioma y dominios | Multilenguaje. Además, más datasets, no solo vLLM. Este repo es sobre todo para tener las marcas de recall claras. | Embeddings y reranker **multilingües** desde la Fase 2. La ingesta multi-dominio se prepara en la Fase 1 y se usa en la Fase 4. vLLM sigue siendo el **benchmark**. |
| **D7** Agente | Dicotomía: agente propio como intermediario, pero también acceso directo al RAG. **A discutir.** | La arquitectura soporta **ambos** caminos desde el diseño. La decisión de qué es lo por defecto se toma antes de la Fase 5. |
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

**Objetivo:** el RAG deja de ser "solo vLLM".

- **Modo CV**:
  - Tus datos en Markdown/YAML + el PDF del CV vía Docling, en la colección `cv`.
  - Multilingüe.
  - Guardarraíles: si algo no está en los datos, no se inventa y se ofrece contacto.
  - Revisión de privacidad antes de indexar.
- **Nuevos dominios** (D6): ingesta de otros datasets con la infraestructura de la Fase 1. Están pendientes de elegir cuáles.
- **Router de modo/dominio**: decide la colección según el modo activo o la pregunta.
- **4b — Multimedia** (D9: todo lo posible, prioridad vídeo y audio). Ver `RESPUESTA.md` §4.2.1.
  - **Audio y vídeo**:
    - Transcripción con `faster-whisper` y marcas de tiempo; las fuentes enlazan al minuto exacto.
    - Escenas clave con PySceneDetect + captions.
    - Diarización (quién habla) como opcional; las licencias y el acceso a los modelos están **a verificar**.
  - **Imágenes**: OCR + captions (nivel A), más búsqueda de imágenes por texto con CLIP/SigLIP (nivel B, vectores con nombre en Qdrant).
  - **VLM generativo** (nivel C): solo como opción local en la 3080 Ti.
  - **Ingesta offline**; en producción solo se sirven el índice y las miniaturas. Los vídeos se alojan fuera (YouTube o similar) y se enlazan con `&t=`.
  - Set de evaluación propio (el workbench de 42 no cubre multimedia).

## Fase 5 — Agentes y RAG como servidor MCP

**Objetivo:** acercarnos a cómo lo hacen las empresas, sin perder el acceso directo (D7).

- **Servidor MCP** (FastMCP, como en AgentSmith) con las herramientas `search(domain, query)`, `answer(...)` y `list_domains`.
- **Agente intermediario propio**:
  - Router, reescritura de la query y llamada a herramientas, con *fallback* determinista.
  - Bucle de varios pasos solo con los modelos opcionales grandes.
  - **Memoria** (petición tuya): historial de la conversación más memoria semántica recuperable. Se puede guardar en Qdrant (una colección `memory_*` con vectores) o, si hace falta algo relacional, motivar el paso a Postgres que se dejó abierto en la Fase 1.
- **Acceso directo al RAG** siempre disponible: se elige con un flag de config o de la petición.
- **Benchmark agente frente a acceso directo** (recall, calidad, latencia) en `BENCHMARK_REPORT.md`.
- ⚠️ **D7 se discute antes de empezar esta fase.**

## Fase 6 — Web deploy

**Objetivo:** una web pública para LinkedIn con los modos **CV** y **Demostración**.

- **Backend FastAPI**: `/chat` (streaming SSE), `/search`, `/sources/{id}`, `/metrics` y `/config` (modelos y opciones disponibles).
- **Frontend React** (Vite) con **la misma estética que la web actual** (D5):
  - Fondo `#0a0a0a` y acento `#ff3b3b`.
  - Tipografías JetBrains Mono + Inter.
  - Tarjetas de fuentes y barras de recall.
- **Navegación y selectores** (modelo, agente sí/no), según lo que se decida de la modularización.
  - **Base ya preparada (Fase 2):** los perfiles de `rag.toml` (`available_profiles`) son las opciones que podría ofrecer un selector de ingesta, reranker o embeddings. La base estable sigue siendo la del benchmark. *A plantear en esta fase.*
- **Despliegue sin coste**:
  - Backend en un Hugging Face Space (Docker, CPU gratuito).
  - Frontend estático en GitHub Pages.
  - **Google Cloud no se toca.**
  - En el despliegue gratuito probablemente solo quepa un modelo cargado; el resto, en local.
- **README final**: se reescribe al terminar la mejora completa del proyecto.

---

# Decisiones pendientes #

| # | Tema | Cuándo hay que decidirlo |
|---|---|---|
| P1 | D7: agente frente a acceso directo, y qué es lo por defecto | Antes de la Fase 5 |
| P2 | ~~D9: alcance de la ingesta multimedia~~ → resuelto: todo lo posible, prioridad vídeo y audio. **Queda por concretar qué material y cuánto** | Antes de la Fase 4 |
| P7 | ~~`.gitattributes` para normalizar los finales de línea~~ → resuelto: todo LF y `llm_sdk/` intacto (commit `5a1cc4b`) | Hecho |
| P8 | ~~¿`bge-m3` por defecto aunque indexar en CPU lleve ~2 h?~~ → resuelto: `bge-m3` en la base y perfil `cpu-light` (`e5-small`) | Hecho |
| P9 | ~~`bge-reranker-v2-m3`~~ → resuelto: perfil opcional `gpu-quality` | Hecho |
| P3 | Qué datasets o dominios nuevos se añaden (D6) | Antes de la Fase 4 |
| P4 | Modularización: qué opciones se exponen en la web y cómo se navega | Antes de la Fase 6 |
| P5 | GPU de los ordenadores de 42 (para fijar los valores por defecto) | Durante la Fase 2 |
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
- **2026-10-18**: las cifras del README (docs 0.89 / code 0.75 en R@10) eran de los datasets **públicos**, aunque estuvieran etiquetadas como privadas, y salían de configuraciones anteriores que no se reproducen con `v1.0-42`. Se acepta como línea base oficial `04-fase0-final / smart`. La etiqueta del README se corrige en la reescritura final.
- **2026-10-18**: finales de línea normalizados a LF con `.gitattributes`, con `llm_sdk/` excluido (P7).
