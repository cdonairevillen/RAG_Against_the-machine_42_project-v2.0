# RESPUESTA — Valoración del proyecto RAG_2

> Documento de respuesta a `PLANING.md`. Revisa lo que hay, valora cada punto, propone recursos y mejoras, y deja dudas abiertas para cerrar la hoja de ruta.
> Todo lo que aparece como **"a verificar"** es algo que no he podido comprobar desde aquí y no quiero dar por cierto.
>
> **Estado:** las dudas de §7 están respondidas en `ROADMAP.md`, que es el **documento vigente**. Este archivo se mantiene como análisis de referencia. Donde haya diferencias, manda `ROADMAP.md`.

---

## 1. Resumen ejecutivo

**Es viable, y sin gastar dinero.** Todas las piezas que pides tienen alternativas open source con licencia permisiva (MIT / Apache 2.0) que corren en CPU. La única pieza delicada es el **despliegue**: Qwen3-0.6B + reranker + embeddings en CPU necesita ~3–5 GB de RAM y arranques lentos. Lo resolvemos sin tocar tu app de Google Cloud (ver §4.8).

**El punto de partida es bueno**: tienes un pipeline completo (ingesta → retrieval → rerank → generación → evaluación) con métricas medidas. Pero hay **bugs reales** que hoy afectan al rendimiento y que conviene arreglar *antes* de meter tecnología nueva. Si no, compararemos contra una línea base que no es la real.

**Hallazgo más importante:** los embeddings **no fallaron por estar mal planteados conceptualmente**. La query sí se embebía. Fallaron por un **bug de índices** (§3.2). Es decir, la conclusión del README ("los embeddings empeoran el recall") no está demostrada. Hay que repetir el experimento bien hecho.

---

## 2. Revisión de lo que tenemos

### 2.1 Arquitectura actual

```
data/raw/vllm-0.10.1
      │
 [ingester.py]  AST para .py, headers para .md/.rst, padres (2000) → hijos (600)
      │         3 índices BM25 (bm25s): general, docs, code — guardados en JSON + .npy
      ▼
 [retriever.py] expand_query → classify_query (doc vs code) →
      │           docs: BM25 doc puro | code: BM25 + CrossEncoder ms-marco-MiniLM
      │           search_for_generation: BM25 + rerank + umbral 5.5
      ▼
 [generator.py] Qwen3-0.6B vía llm_sdk, prompt chat manual, greedy, 150 tokens
      ▼
 [evaluator.py] Recall@k con solape ≥5 % de caracteres
      ▼
 [cli.py] Fire  ·  [web.py] Streamlit
```

### 2.2 Puntos fuertes (a conservar)

- **Chunking AST con padres/hijos**: es una técnica real de la industria ("parent document retrieval" / "small-to-big"). No hay que tirarlo.
- **Separación doc/code con índices distintos**: medido y justificado.
- **Evaluador fiel al de 42**: es nuestro *workbench*. No debe cambiar, para poder comparar.
- **Generación con `model.generate()`** (KV-cache) en vez del bucle de logits del SDK.
- **README con decisiones de diseño razonadas**: buen material para enseñar a un reclutador.

### 2.3 Bugs y problemas detectados (verificados en el código)

| # | Gravedad | Dónde | Problema |
|---|---|---|---|
| B1 | **Alta** | `src/retriever.py:277-283` (`classify_query`) | `query_terms = set(query.lower().split())` y luego `t[0].isupper()`. Tras `.lower()` nunca hay mayúsculas: **la señal CamelCase del clasificador está muerta**. Las preguntas tipo "¿qué hace `RMSNorm`?" no suman como código. |
| B2 | **Alta** | `src/retriever.py:64-71` (`expand_query`) | La expansión por `symbols` **nunca añade nada**: solo añade un símbolo si ya está en la query, y luego el filtro `e.lower() not in query.lower()` lo elimina. Además recorre **todos los chunks en cada búsqueda** (coste O(N) inútil por query). |
| B3 | **Alta** | `Makefile` (`search-docs`, `search-code`) vs `test-*` | `search-docs/code` usan `answer_dataset` → `search_for_generation` (con umbral 5.5, puede devolver lista vacía). `test-*` usan `search_dataset` → `search_smart`. **Las métricas públicas y privadas salen de pipelines distintos.** |
| B4 | Media | `README.md:221-223` vs `src/web.py:476` | El README dice que la web usa `search_smart()`. La web usa `search_for_generation()`. |
| B5 | Media | `src/web.py:398-416` | El modelo y el reranker se guardan en `st.session_state`, que es **por sesión de navegador**. En un despliegue público, **cada visitante recarga Qwen + reranker** → la RAM se dispara. Hay que usar `st.cache_resource`. |
| B6 | Media (en público) | `src/web.py:514` | La respuesta del LLM se inyecta con `unsafe_allow_html=True` sin escapar. Si el contexto trae código con `<...>`, se rompe el HTML. En una web pública es además un vector de inyección. |
| B7 | Media | `src/ingester.py:261-278`, `:378-394` | Los offsets de chunks "enriquecidos" (firma de clase + método, título + tabla) se calculan sobre el texto con prefijo. Cuando se subdividen, `first/last_character_index` quedan **desplazados** respecto al fichero real. Afecta poco (se devuelven padres), pero ensucia el recall. |
| B8 | Media | `src/ingester.py:826-833` + `bm25s.tokenize` | El corpus no normaliza identificadores: `max_model_len` es **un solo token**. Una pregunta en lenguaje natural ("max model length") no lo encuentra. Un tokenizador *code-aware* (partir snake/Camel en corpus **y** query) es una mejora clásica y barata. |
| B9 | Baja | `src/generator.py:158-163` | `truncation=True, max_length=4096` trunca **por la derecha**: si el prompt se pasa, se corta la **pregunta**. Hoy lo evita `truncate_prompt` (10 000 chars), pero es frágil. Mejor usar `tokenizer.apply_chat_template(..., enable_thinking=False)` y presupuestar en tokens. |
| B10 | Baja | `generator.py`, `cli.py`, `web.py` | Tres listas distintas de frases "not found" y dos mensajes distintos. Hay que centralizarlas. |
| B11 | Baja | repo | No hay `.gitignore`: hay `__pycache__/*.pyc` versionados (el último commit los volvió a subir). |
| B12 | Baja | `Makefile` | Rutas `/goinfre` fijas y descarga desde `cdn.intra.42.fr`: no es portable a Windows / HF / Docker. `.PHONY` cita `index-fast` (no existe) y faltan los `test-*`. `index-embed` pasa `--use_embeddings True`, que hoy **no hace nada**. Hay cambios sin commitear en las URLs de descarga. |
| B13 | Baja | `retriever.py:8`, `generator.py:3` | `RRF_K` sin usar. `from llm_sdk.__init__ import` debería ser `from llm_sdk import` (no toca `llm_sdk`, solo el import). |

> Nada de esto se arregla sin tu permiso. Los marco como "Fase 0" en la propuesta de §6.

### 2.4 Sobre `llm_sdk`

Regla respetada: **no se toca**. El `Generator` usa sus atributos privados (`_model`, `_tokenizer`). Eso es legal (no modifica la carpeta), pero nos ata a su interfaz interna. Propongo envolverlo en un *backend* propio (§4.9), para que cambiar de modelo sea una opción y no un parche.

---

## 3. Sobre los embeddings (tu punto clave)

### 3.1 Tu diagnóstico

Dices: *"solo accionan sobre la ingesta, con lo cual al usarlos no sirven de nada"*.

**En el código histórico no era así.** En el commit `ad5b4a1`, `retrieve_from_embeddings` y `rerank_by_embeddings` sí hacían `embed_model.encode([query])`. La query se embebía.

### 3.2 La causa real: bug de espacio de índices

En `ad5b4a1`:

- `Ingester.build` genera `doc_embeddings` **solo para los padres de tipo doc** (`doc_parents`).
- `Retriever.from_disk` pasa esos `doc_embeddings` como `embeddings=` (el atributo genérico).
- `search_hybrid` fusiona con RRF:
  - los índices de BM25, que son posiciones en **`self.chunks` (todos los hijos)**;
  - los índices de `retrieve_from_embeddings`, que son posiciones en **la matriz de padres doc**.
- Y luego hace `self.chunks[idx]` con ambos.

**Resultado:** el "resultado semántico nº 5" apuntaba al **hijo nº 5 del corpus completo**, que no tiene nada que ver. Eso, sumado en RRF, mete ruido y **baja el recall**, que es justo lo que viste.

### 3.3 Qué propongo

Rehacerlo bien, como se hace en la industria:

1. Un único espacio de IDs. Cada chunk tiene `chunk_id` estable en la base de datos (§4.2).
2. Embeber los **hijos** (o los padres, a decidir con medida) **y** la query, con el **mismo modelo**.
3. Usar el prefijo de instrucción si el modelo lo requiere (los BGE/E5/Qwen3-Embedding piden un prefijo distinto para query y para documento).
4. Recuperación **híbrida**: BM25 (sparse) + dense, fusionadas con RRF, luego reranker.
5. Medir **por separado docs y code**, como ya hiciste con el reranker.

Puede que en code siga ganando BM25 (es normal con identificadores), pero será una conclusión medida y no un bug.

---

## 4. Valoración punto por punto

### 4.1 Chunkers externos

**Viable.** Pero ojo: tu chunker AST ya es mejor que muchos genéricos para código Python. Propuesta: **híbrido**.

| Herramienta | Licencia | Para qué |
|---|---|---|
| **Chonkie** | MIT | Chunkers ligeros: token, sentence, semantic, **code** (tree-sitter). Pocas dependencias. |
| **LlamaIndex node parsers** (`CodeSplitter`, `MarkdownNodeParser`, `SemanticSplitterNodeParser`) | MIT | Muy conocidos en la industria. Arrastran más dependencias. |
| **LangChain text splitters** (`RecursiveCharacterTextSplitter`, `MarkdownHeaderTextSplitter`, `Language.PYTHON`) | MIT | El estándar *de facto*. Dependencia pequeña (`langchain-text-splitters`). |
| **Docling** (IBM) | MIT | Para PDFs/DOCX (tu CV, certificados). Convierte a Markdown estructurado. |

**Recomendación:**
- Mantener el **AST propio** para `.py` (arreglando B7).
- Usar `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` de **langchain-text-splitters** para docs (dependencia mínima y nombre reconocible en un CV técnico).
- Usar **Docling** solo para el modo CV, si hay PDFs.
- Detrás de una interfaz `Chunker`, para poder comparar estrategias con el evaluador.

### 4.2 Guardar la ingesta en base de datos

**Muy recomendable.** Hoy son JSON gigantes + ficheros `.npy` sueltos.

| Opción | Licencia | Pros | Contras |
|---|---|---|---|
| **Qdrant** (modo local embebido de `qdrant-client`, y servidor en Docker si se necesita) | Apache 2.0 | Muy usado en empresas. Payload con metadatos, filtros (`chunk_type`, `collection`), vectores **sparse + dense** (híbrido nativo). | El modo local no está pensado para gran escala (nuestro corpus es pequeño, así que no importa). |
| **ChromaDB** | Apache 2.0 | Lo más sencillo. Embebido. | Menos "serio" de cara a empresa, y el híbrido es menos maduro. |
| **LanceDB** | Apache 2.0 | Embebido, en ficheros, rápido. Tiene FTS + vector. | Menos conocido. |
| **SQLite + FTS5 + sqlite-vec** | dominio público / MIT-Apache | Cero infraestructura, todo en un `.db`. | Más código a mano. |
| **PostgreSQL + pgvector** | PostgreSQL | El estándar empresarial. | Necesita servidor; en un despliegue gratis complica. |

**Recomendación: Qdrant en modo local**, con la misma API que un Qdrant en servidor (subir de nivel después es cambiar una URL).

- Colecciones: `vllm_docs`, `vllm_code`, `cv` (o una sola con filtro por payload).
- **Mantener `bm25s`** como índice sparse al principio (está medido y funciona) y fusionar fuera. Probar más adelante los sparse vectors de Qdrant como alternativa.
- Para el despliegue, el índice se construye **offline** y se empaqueta (es de solo lectura en producción).

### 4.2.1 Ingesta de imágenes y vídeos (multimodal)

**Viable, con matices.** La limitación clave es que **Qwen3-0.6B solo entiende texto**: no puede "ver" una imagen ni un vídeo. Por eso no hay que cambiar el generador. Lo que hay que decidir es **cómo convertimos el contenido multimedia en algo que el RAG pueda buscar y citar**. Hay tres niveles, de menor a mayor coste.

**Nivel A: multimedia → texto en la ingesta** (lo que hacen la mayoría de empresas)

Cada imagen o vídeo se convierte offline en texto indexable, y el resto del pipeline no cambia.

- **Imágenes**:
  - **OCR** para capturas, diplomas y diagramas con texto: Tesseract (Apache 2.0), RapidOCR/PaddleOCR (Apache 2.0) o EasyOCR (Apache 2.0).
  - **Descripción automática** (caption) con un modelo visión-lenguaje pequeño: Florence-2 (MIT, ~0.2–0.8 B) o SmolVLM2 (Apache 2.0, 256 M–2.2 B).
  - Ese texto se guarda como chunk con metadatos `modality=image`, `media_uri` y `thumbnail`.
- **Vídeos**:
  - **Transcripción del audio** con Whisper (MIT), mejor con `faster-whisper` (MIT), que es más rápido en CPU. Los segmentos llevan **marcas de tiempo**, así que cada chunk apunta a `video.mp4` entre `t=01:23` y `t=02:10`.
  - Opcionalmente, **fotogramas clave**: detectar cambios de escena con PySceneDetect (BSD-3) + ffmpeg, y describir cada escena con Florence-2/SmolVLM2. Útil si el vídeo enseña cosas que no se dicen (una demo en pantalla).
- **Ventajas**: Qwen responde con normalidad. Las fuentes enlazan a la imagen o al **minuto exacto** del vídeo, lo que luce mucho en una demo. Encaja con Qdrant y con lo que ya tenemos.
- **Coste**: la ingesta en CPU es lenta (sobre todo la transcripción y los captions), pero se hace **una vez, offline**. En producción no añade carga. Los tiempos concretos habría que medirlos con tu hardware (D3).

**Nivel B: embeddings multimodales** (buscar imágenes por texto)

Un modelo tipo CLIP/SigLIP pone texto e imágenes en el **mismo espacio vectorial**, así que "foto del proyecto X" recupera la imagen directamente, aunque no tenga texto.

- Modelos: `openai/clip-vit-base-patch32` (MIT), `google/siglip-base-patch16-224` (Apache 2.0), `sentence-transformers/clip-ViT-B-32-multilingual-v1` (Apache 2.0, consultas en español).
- Qdrant admite **varios vectores con nombre por punto** (`text`, `image`), así que cabe en el mismo diseño.
- Sirve para **mostrar** imágenes como resultado. El LLM sigue sin verlas: responde sobre su caption (nivel A).
- Viabilidad: **media**. Corre en CPU sin problema, pero es una pieza más que mantener y evaluar.

**Nivel C: generación multimodal** (un VLM que mira la imagen al responder)

Por ejemplo SmolVLM2 o un Qwen-VL pequeño (variantes, tamaños y licencias de la familia Qwen-VL **a verificar**: no todas son Apache 2.0).

- Sería **otro modelo opcional** (§4.9), nunca la base.
- En el despliegue gratuito en CPU lo veo **poco viable**: memoria y latencia altas. Lo dejaría como opción local de demostración.

**Dónde encaja de verdad:**

- **Modo CV**: es el mejor caso de uso. Fotos de proyectos, capturas, diplomas escaneados, vídeos de demos o charlas. El reclutador pregunta *"¿tiene algún proyecto con agentes?"* y la respuesta enlaza al minuto del vídeo donde lo enseñas.
- **vLLM**: la ingesta actual ignora las imágenes (`INCLUDE_EXTENSIONS` solo admite `.py/.pyi/.md/.rst/.txt`). Habría que comprobar cuántas imágenes con información útil hay en `docs/` (no lo he revisado). Sospecho que aportan poco frente al texto.

**Impactos en la arquitectura** (a tener en cuenta desde la Fase 1):

- El `Chunk` actual se basa en `first/last_character_index`, que no tiene sentido para una imagen o un vídeo. Propongo un campo `modality` y una referencia genérica (`char_range` | `time_range` | `bbox`).
- **`MinimalSource` y el evaluador de 42 no se tocan**: los resultados multimedia usan su propio modelo, así el workbench sigue siendo comparable.
- **Almacenamiento en el despliegue**: no subiría los vídeos al Space. Mejor alojarlos en YouTube (o similar) y enlazar con `&t=`. En el índice solo irían transcripciones, captions y miniaturas.
- **Evaluación**: el workbench de 42 **no cubre multimedia**. Habría que montar un set propio pequeño (~15–20 preguntas), que es justo el marco propio que querías evitar. Por eso lo propongo **acotado al modo CV**.
- **Privacidad**: los captions y transcripciones pueden recoger datos que no quieres publicar (caras de terceros, nombres, matrículas, audio de fondo). Hay que revisarlos antes de indexarlos.

**Recomendación:**

- **Nivel A** (OCR + captions + transcripción con marcas de tiempo) para el modo CV, como **fase opcional después del modo CV** (4b en §6).
- El **nivel B** (CLIP/SigLIP) solo si queremos la función de "enséñame imágenes de…".
- El **nivel C** queda fuera del despliegue.
- Diseñar el `Chunk` con `modality` desde la Fase 1 cuesta poco y evita rehacer la base de datos después.

### 4.3 Embeddings de ingesta **y** de query

Ver §3. Candidatos (todos CPU-friendly):

| Modelo | Tamaño aprox. | Licencia | Comentario |
|---|---|---|---|
| `BAAI/bge-small-en-v1.5` | ~33 M | MIT | Rápido. Buen baseline en inglés. |
| `intfloat/multilingual-e5-small` | ~118 M | MIT | **Multilingüe** (útil para el modo CV en español). |
| `BAAI/bge-m3` | ~568 M | MIT | Multilingüe, dense + sparse. Más pesado. |
| `Qwen/Qwen3-Embedding-0.6B` | 0.6 B | Apache 2.0 | **Familia Qwen**, coherente con tu narrativa. Pesado para CPU en la ingesta; a medir. |
| `jinaai/jina-embeddings-v2-base-code` | ~161 M | Apache 2.0 | Especializado en código. |

> **Decidido (D6): multilingüe.** Se priorizan `multilingual-e5-small`, `bge-m3` y `Qwen3-Embedding-0.6B`. `bge-small-en-v1.5` queda como referencia en inglés.

**Recomendación original:** empezar con `bge-small-en-v1.5` (vLLM) y `multilingual-e5-small` (CV). Comparar con `Qwen3-Embedding-0.6B` como experimento. **Entrenar uno propio no tiene sentido** en este alcance: hay modelos libres de sobra.

### 4.4 Generación de respuestas más natural

Problemas actuales:
- El prompt obliga a un formato rígido ("Source: <filename>" dentro del texto).
- `max_new_tokens=150` corta respuestas.
- El chat template está escrito a mano.

Propuestas:
1. `apply_chat_template(..., enable_thinking=False)` (forma oficial de Qwen3) en lugar del string manual.
2. Las **fuentes salen estructuradas** del pipeline (ya las tienes), no del texto del LLM. El LLM cita con `[1]`, `[2]` y la UI enlaza cada número a su tarjeta de fuente.
3. **Streaming** de tokens (`TextIteratorStreamer` de transformers) → la percepción de velocidad mejora muchísimo en la web.
4. Prompt por **modo** (vLLM técnico / CV cercano en primera persona / demo).
5. Presupuesto de contexto **en tokens**, no en caracteres (B9).
6. Ajustar `max_new_tokens` (~300) y `repetition_penalty` suave. Con 0.6B, greedy puro tiende a repetir.

Expectativa realista: **Qwen3-0.6B es pequeño**. Mejorará la forma, pero no hará milagros en razonamiento. Para eso está el modelo opcional (§4.9).

### 4.5 Reranker

Lo actual (`ms-marco-MiniLM-L-6-v2`) es correcto y rápido. Observaciones:

- Está entrenado en MS MARCO (web, inglés): **flojo con código** y **nada en español**. Eso explica en parte que penalizara docs y que no sirva para el modo CV.
- Reglas fijas (`SKIP_RERANK_SCORE = 9.0`, "mínimo 2 docs") calibradas a mano sobre el dataset. Funcionan, pero son frágiles.

Candidatos a comparar:
- `BAAI/bge-reranker-base` (MIT) o `BAAI/bge-reranker-v2-m3` (Apache 2.0, multilingüe).
- `Qwen/Qwen3-Reranker-0.6B` (Apache 2.0). Necesita un wrapper propio (se usa como LM causal, no como CrossEncoder clásico); a verificar el soporte actual en sentence-transformers.

**Recomendación:** mantenerlo como baseline y probar `bge-reranker-v2-m3` **después** de tener el híbrido. Con D6 (multilingüe), `bge-reranker-v2-m3` pasa a ser el candidato principal. Con mejor recuperación quizá los umbrales manuales sobren.

### 4.6 Agente intermediario

**Valoración honesta:**

- **AgentSmith** usa un bucle *Thought → Code → Observation* con **modelos grandes por API** (Groq Llama-3.3-70B, OpenRouter…), tool calls como código Python, sandbox y **MCP/FastMCP**. Es un buen diseño, pero pensado para modelos de 70B.
- **Qwen3-0.6B** tiene formato de tool-calling en su chat template, pero a 0.6B su fiabilidad para decidir herramientas en varios pasos es baja (no lo he medido; es una expectativa razonable que conviene comprobar).

**Propuesta en dos capas (lo que hacen las empresas, a escala académica):**

1. **RAG como servidor MCP** (FastMCP, que ya dominas por AgentSmith), con herramientas `search_vllm_docs`, `search_vllm_code`, `search_cv` y `answer`.
   - Cualquier agente (Claude Desktop, tu AgentSmith, otro) puede consumir el RAG. Es el patrón actual de la industria.
   - Coste casi nulo y reutiliza tu experiencia.
2. **Agente ligero propio** con Qwen3-0.6B:
   - **Router** que decide el modo/colección (o "fuera de dominio").
   - **Reescritura de la query** (multi-query o HyDE opcional).
   - **Una** llamada a herramienta, con *fallback* determinista si el JSON sale mal.
   - Sin bucle abierto de N pasos.
   - Con el modelo opcional más grande, se puede activar un bucle de 2–3 pasos.

Así enseñas *agente + MCP* sin depender de que un 0.6B sea un buen planificador.

### 4.7 Frontend con modos "CV" y "Demostración"

Streamlit sirve para prototipar, pero para una web que va en LinkedIn:

| Opción | Pros | Contras |
|---|---|---|
| **Streamlit mejorado** (con `st.cache_resource` y `st.write_stream`) | Rápido, ya existe. | Estética limitada. Cada visitante mantiene un websocket. |
| **Gradio** | Chat listo y nativo en HF Spaces. | Igual de "plantilla". |
| **FastAPI (backend) + frontend estático** (HTML/JS o React/Vite) | Profesional. La API la reutilizan la web, el MCP y la CLI. Streaming por SSE. | Más trabajo. |

> **Decidido (D5): FastAPI + React, manteniendo la estética actual de `src/web.py`.**

**Recomendación:** **FastAPI + frontend ligero**. El backend expone `/chat` (modo `cv` | `demo`, con streaming), `/sources/{id}` y `/metrics`. El frontend puede ir gratis en GitHub Pages y el backend en HF Spaces.

Si prefieres velocidad, Streamlit arreglado (B5, B6) es un buen paso intermedio.

**Modo Demostración**: chat sobre vLLM con las fuentes desplegables, un panel de métricas (Recall@k del workbench), selector de modelo (Qwen base / opcional) y un "explicador" del pipeline (qué chunks, qué scores, qué reranker).

**Modo CV**: chat en primera persona, en español/inglés, con preguntas sugeridas ("¿Qué estudió?", "Proyectos con IA", "Experiencia laboral").

### 4.8 Despliegue sin gastar dinero

- **Google Cloud**: tu limitación dice que, si choca con la app ya desplegada, se descarta. Cloud Run tiene capa gratuita mensual, pero la cuota se comparte con tu app actual, y un modelo cargado en memoria con instancias mínimas a 0 implica arranques en frío de decenas de segundos. **No lo recomiendo como primera opción.**
- **Hugging Face Spaces (CPU básico gratuito)**: suficiente para Qwen3-0.6B en CPU (lento pero usable con streaming). Se suspende tras un periodo de inactividad y tarda en despertar. Los límites concretos de RAM/CPU y el tiempo de suspensión están **a verificar** en la documentación actual en el momento de desplegar.
- **Frontend estático**: GitHub Pages (gratis).

**Recomendación:** backend en un **HF Space (Docker)** + frontend en **GitHub Pages**, con Google Cloud intacto. Mostrar un aviso tipo *"despertando el modelo…"* para el arranque en frío.

### 4.9 Otros modelos (opcionales)

Qwen3-0.6B sigue siendo **la base** y el valor por defecto. Interfaz propuesta:

```
src/llm/
  base.py          # class LLMBackend: generate(messages, stream=False)
  qwen_sdk.py      # envuelve llm_sdk.Small_LLM_Model (sin tocar llm_sdk)
  hf_generic.py    # cualquier modelo HF (AutoModelForCausalLM), fuera de llm_sdk
```

Se selecciona con `--model` o con una variable de entorno. Candidatos libres:

| Modelo | Licencia | Nota |
|---|---|---|
| `Qwen/Qwen3-1.7B` / `Qwen3-4B` | Apache 2.0 | Misma familia: comparativa limpia. 1.7B es viable en CPU. |
| `HuggingFaceTB/SmolLM3-3B` | Apache 2.0 | Pequeño y abierto. |
| `microsoft/Phi-4-mini-instruct` | MIT | Bueno en razonamiento. Pesado en CPU. |
| Llama 3.2 1B/3B, Gemma 3 1B | Licencias propias (no OSI) | Usables, pero con condiciones. Las menciono por completitud. |

En el despliegue gratuito probablemente solo quepa **un** modelo cargado. El selector tendría sentido en local, o cargando bajo demanda.

### 4.10 Ampliar a más campos

Con colecciones/namespaces en la DB es casi gratis: una colección por dominio y un router que elige. **No lo haría al principio**: primero vLLM (medible) y CV (diferenciador). Un tercer dominio solo si sobra tiempo.

### 4.11 Modo CV

- **Fuente de datos**: Markdown/YAML escritos por ti (estudios, experiencia, proyectos, gustos), más el PDF del CV vía Docling. Es mejor escribir tú los Markdown: datos limpios = respuestas limpias.
- **Privacidad**: nada de teléfono, dirección, DNI… solo lo que pondrías en LinkedIn. El modelo **repetirá** lo que reciba.
- **Detalle técnico**: el corpus CV será pequeño (unas pocas páginas). Con un solo chunker y embeddings multilingües basta; reranker multilingüe opcional.
- **Guardarraíles**: si preguntan algo que no está en los datos, responder "eso no lo tengo, contacta conmigo en…", nunca inventar.

### 4.12 ¿Repo nuevo o fork?

GitHub **no permite hacer fork de un repo propio en la misma cuenta**. Opciones:

1. **Repo nuevo conservando el historial** (recomendado): `git remote add new <url>` + `git push new main`. Antes, se etiqueta el estado evaluado por 42 (`v1.0-42`).
   - El repo original queda intacto como entrega académica.
   - El nuevo cuenta la evolución: "de proyecto 42 a producto".
2. Repo nuevo desde cero, con un enlace al original: más limpio, pero pierdes la narrativa del historial.
3. Rama `v2` en el mismo repo: lo más simple, pero mezcla la entrega con el producto.

Lo creas tú (yo no hago commits/push sin que me lo pidas).

### 4.13 Workbench de evaluación

Base sólida. Propuestas:
- **Una sola ruta de evaluación** (arreglar B3) y un comando `make bench` que saque docs + code en una tabla.
- Añadir **MRR** y **nDCG@10** además de Recall@k: es estándar y se calcula con los mismos datos. El evaluador oficial se mantiene intacto.
- Guardar cada ejecución (config + métricas) en un CSV/JSON en `bench/`, para comparar cada fase.
- **Calidad de respuesta**: RAGAS (Apache 2.0) necesita un LLM juez. Usar Qwen3-0.6B como juez no es fiable, y uno por API cuesta o tiene cuotas. Propongo al menos un set pequeño (~20 preguntas) revisado a mano, y RAGAS como opcional. Ver duda D4.

---

## 5. Stack propuesto (todo gratuito)

| Capa | Herramienta |
|---|---|
| Gestión | `uv`, `pyproject.toml`, `.gitignore`, `ruff` (o flake8 + mypy, como ahora) |
| Chunking | AST propio + `langchain-text-splitters` (+ Docling para CV) |
| Multimedia (opcional) | `faster-whisper` (audio→texto), Florence-2 / SmolVLM2 (captions), Tesseract/RapidOCR (OCR), PySceneDetect + ffmpeg (escenas), CLIP/SigLIP (nivel B) |
| Embeddings | `sentence-transformers` + modelo multilingüe (`multilingual-e5-small` / `bge-m3` / `Qwen3-Embedding-0.6B`) |
| Sparse | `bm25s` (con tokenizador code-aware) |
| DB | Qdrant (modo local) |
| Reranker | `ms-marco-MiniLM` (baseline) → `bge-reranker-v2-m3` |
| LLM | Qwen3-0.6B vía `llm_sdk` (base) + backend HF genérico (opcional) |
| Agente | Router propio + servidor **FastMCP** |
| API | FastAPI + SSE streaming |
| Frontend | React (Vite) estático en GitHub Pages, con la estética actual (D5) |
| Deploy | HF Spaces (Docker, CPU gratuito) |
| Eval | Evaluador 42 + MRR/nDCG + set manual (RAGAS opcional) |

---

## 6. Propuesta preliminar de fases (para discutir la hoja de ruta)

> **Superado por `ROADMAP.md`**, que tiene las fases aceptadas y desarrolladas. La tabla se conserva como referencia histórica.

Cada fase llevaría su `CHANGELOG` con: qué cambia, ficheros, por qué, impacto y notas de arquitectura.

| Fase | Contenido | Toca funcionamiento |
|---|---|---|
| **0. Saneamiento + línea base** | Repo nuevo, `.gitignore`, arreglar B1–B3, B10, B13, un único `make bench`, Makefile portable. **Medir la línea base real.** | Sí (B1/B2 cambian resultados) → necesita tu OK |
| **1. Base de datos** | Ingesta → Qdrant local con IDs estables. Arreglar offsets (B7). `Chunk` con campo `modality` preparado para multimedia. Mismos resultados que la Fase 0 (sin regresión). | Sí |
| **2. Retrieval híbrido** | Tokenizador code-aware (B8), embeddings bien hechos, RRF, comparativa de rerankers. | Sí |
| **3. Generación** | Chat template oficial, citas `[n]`, streaming, prompts por modo, backend de modelos opcional. | Sí |
| **4. Modo CV** | Ingesta de tus datos, colección `cv`, embeddings multilingües, guardarraíles. | No (añadido) |
| **4b. Multimedia (opcional)** | Nivel A sobre el material del CV: OCR + captions de imágenes, transcripción de vídeos con marcas de tiempo, fuentes enlazadas al minuto. Nivel B (CLIP) si se quiere búsqueda de imágenes. Set de evaluación propio pequeño. | No (añadido) |
| **5. Agente + MCP** | Router, reescritura de query, servidor FastMCP. | No (añadido) |
| **6. Web + deploy** | FastAPI + frontend con modos CV/Demo, HF Space, GitHub Pages. | No (nuevo) |

Las fases 0–3 son secuenciales (cada una se mide contra la anterior). La 4 puede ir en paralelo a la 3.

---

## 7. Dudas que necesito que resuelvas

> **Respondidas en `ROADMAP.md`** (sección *Respuestas*): D1–D6 y D8 están cerradas. **D7 queda a discutir** y **D9 está pendiente.**

- **D1. Datasets privados**: el Makefile (`test-*`) y el README citan `data/datasets/private/...`, pero `make install` no los descarga. ¿Los tienes? ¿Trabajamos solo con los públicos?
- **D2. Las URLs nuevas del Makefile** (sin commitear, `54681/54683`): ¿son versiones nuevas de los datasets/vLLM? Si cambiaron los datasets, la línea base del README ya no es comparable.
- **D3. Hardware de desarrollo**: ¿tienes GPU (CUDA) en local, o todo va en CPU? Cambia qué modelos de embeddings/reranker son razonables.
- **D4. Evaluación de respuestas**: ¿aceptas un set manual pequeño + RAGAS opcional? ¿O tienes acceso gratuito a algún LLM por API (Groq/OpenRouter como en AgentSmith) para usarlo **solo como juez**?
- **D5. Frontend**: ¿FastAPI + frontend propio (más profesional, más trabajo) o Streamlit arreglado (más rápido)?
- **D6. Idioma**: ¿la web/CV en español, en inglés o en ambos? Afecta a la elección de embeddings y reranker.
- **D7. Agente**: ¿te encaja el enfoque "MCP server + router ligero" o quieres un bucle agéntico completo tipo AgentSmith (que realmente solo funcionaría bien con el modelo opcional grande)?
- **D8. Fase 0**: B1 y B2 cambian el comportamiento del retrieval (y por tanto las métricas). ¿Me das permiso para arreglarlos en esa fase, midiendo antes y después?
- **D9. Multimedia**: ¿qué material tienes en mente (fotos de proyectos, diplomas, vídeos de demos o charlas…) y cuánto, más o menos (número de imágenes, minutos de vídeo)? ¿Los vídeos pueden estar en YouTube u otra plataforma pública, para enlazarlos en vez de alojarlos? ¿Lo limitamos al modo CV o quieres probarlo también con vLLM?
