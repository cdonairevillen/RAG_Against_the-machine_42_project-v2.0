*Empezó como parte del currículo de 42 de cdonaire (RAG against the Machine). La versión 2.0 es una reelaboración personal de aquel proyecto hasta convertirlo en un sistema RAG completo, al estilo de producción.*

> Traducción al español del [README del proyecto](../../README.md).

# RAG against the Machine v2.0

Un sistema de **generación aumentada por recuperación** (RAG) multidominio, con un agente, un servidor MCP y una interfaz web. Responde a preguntas, con citas, a partir de cuatro bases de conocimiento:

| Dominio | Qué contiene | Tamaño |
|---|---|---|
| `vllm` | La documentación y el código fuente de vLLM 0.10.1 (el corpus del benchmark de 42) | 37 381 chunks |
| `xquad` | Cultura general: 48 artículos de Wikipedia de XQuAD, en inglés y en español | 1 217 chunks |
| `cv` | El CV del autor, su perfil de LinkedIn y su biografía (en inglés y en español) | 162 chunks |
| `about` | El propio proyecto: el README, la documentación de `docs/` (en inglés y en español) y el código de `src/` | ~3 000 chunks |

El modelo de lenguaje base es **Qwen3-0.6B**, el del proyecto original de 42, para que los resultados sigan siendo comparables con otros RAG de 42. Los modelos más grandes son perfiles opcionales: Qwen3-1.7B y Qwen3-4B, de la misma familia, e IBM Granite 4.0 Micro, de otra.

El proyecto se rehízo fase a fase, y cada cambio se midió antes de quedarse. La historia completa, con las cifras, está en [`docs/es/`](./).

**Demo en línea:** *próximamente*. <!-- TODO: enlace cuando esté desplegado -->

---

## Contenido

[Resultados](#resultados) · [Cómo funciona](#cómo-funciona) · [Interfaz web](#interfaz-web) · [Cómo ejecutarlo](#cómo-ejecutarlo) · [Despliegue](#despliegue) · [Estructura del proyecto](#estructura-del-proyecto) · [Documentación](#documentación) · [Créditos](#créditos) · [Licencia](#licencia)

---

## Resultados

### Recuperación en el benchmark oficial de 42

Los datasets públicos de 42 (100 preguntas de documentación y 100 de código), el evaluador original de 42 (un acierto es una fuente recuperada que se solapa con la de referencia en al menos el 5 % de sus caracteres) y `k = 10`:

| Versión | Docs R@1 / R@3 / R@5 / R@10 | Code R@1 / R@3 / R@5 / R@10 |
|---|---|---|
| v1, la entregada a 42 | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.61 / 0.63 / 0.68 |
| **v2.0** | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |

La prioridad de las métricas es R@5 > R@10 > R@3 > R@1. **El R@5 de docs subió 0.07 y el de code, 0.17.** Los comandos de 42 (`search_dataset`, `answer_dataset`, `evaluate`) siguen funcionando con el mismo formato de salida.

### Los otros dominios

| Conjunto | Medida | Resultado |
|---|---|---|
| XQuAD, 1 190 preguntas por idioma | Recuperación R@1 / R@3 / R@5 / R@10 | EN 0.95 / 0.99 / 0.99 / 1.00 · ES 0.92 / 0.99 / 0.99 / 1.00 |
| XQuAD (Qwen3-0.6B) | La respuesta contiene el dato correcto | EN 0.65 · ES 0.57; cita la fuente correcta en el 99 % de las respuestas |
| CV, 30 preguntas por idioma | Recuperación R@1 / R@3 / R@5 / R@10 | EN 0.47 / 0.80 / 0.93 / 0.97 · ES 0.70 / 0.83 / 0.97 / 1.00 |
| CV (Qwen3-0.6B) | La respuesta contiene el dato correcto | EN 0.73 · ES 0.80, con **0 fugas de datos de contacto privados** |
| Router, sin filtro | Preguntas que llegan a su dominio | 42: 99–100 % · XQuAD: ~98 % · CV: 90–93 % · about: 89 % (EN) · 94 % (ES) |

### Agente frente a RAG directo

Doce conversaciones de 2–3 turnos, en las que las preguntas de seguimiento solo tienen sentido con los turnos anteriores ("¿Y en qué año?"). La tabla muestra con qué frecuencia la respuesta contiene el dato correcto:

| Modelo | Seguimientos, agente | Seguimientos, directo |
|---|---|---|
| Qwen3-0.6B | **0.78** | 0.33 |
| Qwen3-1.7B | 0.83 | 0.33 |
| Qwen3-4B | **1.00** | 0.39 |

En preguntas sueltas y autocontenidas, el agente se queda a ±0.04 del flujo directo con todos los modelos. (También se midió Phi-4-mini, 0.78 / 0.33, que después se retiró: ver [Modelos](#modelos).)

Cada ejecución se guarda en [`bench/results/`](../../bench/results/) con su configuración completa. El análisis está en [`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md).

---

## Cómo funciona

```
pregunta ──► agente (opcional) ──► router ──► recuperación por dominio ──► generador ──► respuesta + fuentes
               │                     │          BM25 + bge-m3 (Qdrant)       Qwen3 (llm_sdk)
               │ memoria, reescritura│          RRF + cross-encoder          citas [n]
               │ llamadas a          │          filtro de relevancia         idioma de la pregunta
               │ herramientas        │
               └─ herramientas MCP ──┘
```

### Ingesta

- **Chunks padre/hijo.** Los padres guardan el contexto completo que llega al LLM; los hijos (hasta 600 caracteres) son lo que se indexa.
- **El código** (`.py`) se trocea con el módulo `ast` de Python: funciones y clases completas, y las clases largas divididas por método con la firma de la clase delante.
- **El Markdown** se divide por encabezados, juntando las secciones pequeñas para que ningún chunk sea un título suelto.
- **El CV** (`.docx`, `.pdf`) se convierte con Docling.
- **Almacenamiento:** Qdrant (en servidor, con Docker) guarda los chunks y sus vectores de `bge-m3`, con IDs estables y un payload por chunk (dominio, tipo, fichero, rango de caracteres, padre). Los índices BM25 (`bm25s`) van al lado, enlazados por los mismos IDs.

### Recuperación

- **Búsqueda híbrida por rama.** Un clasificador léxico con señales en inglés y español manda cada pregunta a la rama de documentación o a la de código. Cada rama combina BM25 (con un tokenizador que entiende el código y separa también los identificadores `snake_case` y `CamelCase`) y embeddings densos de `bge-m3`.
- **Reordenación (reranking).** En la rama de código, el cross-encoder multilingüe `mmarco-mMiniLMv2-L12-H384-v1` reordena los candidatos, fusionados con la primera etapa mediante Reciprocal Rank Fusion. La rama de documentación no lo usa, porque se midió que empeoraba la clasificación de la documentación en este corpus. El mismo cross-encoder puntúa los dominios para el router y el filtro de relevancia.
- **Router.** Sin filtro, se busca en todos los dominios y responde aquel cuyas mejores fuentes reciben la puntuación más alta del cross-encoder. Con filtro, solo participan los dominios elegidos.
- **Filtro de relevancia.** Si ni siquiera el mejor dominio es lo bastante relevante, no se llama al LLM y el sistema dice que no ha encontrado la respuesta. Cada dominio tiene su propio umbral, calibrado con sus propios datos, porque el cross-encoder puntúa cada corpus en una escala distinta.

### Generación

- **Qwen3-0.6B** a través del SDK del curso (`llm_sdk`, sin tocar), con la plantilla de chat oficial y el modo de razonamiento desactivado.
- **Respuestas fundamentadas:** fuentes numeradas y citadas como `[n]`, un presupuesto de contexto en tokens y una instrucción explícita de responder en el idioma de la pregunta.
- **Reglas por dominio** en `rag.toml`: un prompt adicional para el dominio del CV (tercera persona, no mezclar trabajos), el enmascarado de los datos de contacto privados en el contexto, en la respuesta y en las fuentes que se muestran, y un mensaje propio de "no encontrado" que ofrece el correo de contacto público.
- **Streaming,** token a token, en la CLI y en la web.
- **Forma de las respuestas:** un detector de bucles para la generación cuando el modelo empieza a repetir líneas, frases o bloques enteros, y se recorta la parte repetida. Las respuestas que copian el prompt se limpian. La web admite hasta 1.024 tokens nuevos, solo como red de seguridad.

### Modelos

- **Qwen3-0.6B:** la base, el modelo de 42. Lo usan los benchmarks, la CLI y las comparativas con otros RAG de 42.
- **Qwen3-1.7B:** el modelo por defecto de la web.
- **Qwen3-4B:** CLI y benchmarks. Estuvo un tiempo en la web (con la recuperación en la CPU para caber en una GPU de 12 GB, y sin agente); en la Fase 8 lo sustituyó IBM Granite.
- **IBM Granite 4.0 Micro** (`ibm-granite/granite-4.0-micro`, 3B, Apache 2.0): añadido en la Fase 8 como modelo de otra familia. Calidad de respuesta al nivel de Qwen3-4B, buen agente y cabe en la GPU con el agente encendido; es el modelo más lento de la web. Tiene una regla propia del CV para no presentar nunca el Gmail público como otro correo ([`changelog/FASE_8.md`](changelog/FASE_8.md)).

Phi-4-mini fue una opción de otra familia hasta la Fase 7; se retiró porque sus respuestas copiaban las fuentes y entraban en bucles largos, y los arreglos que necesitaba eran parches que solo le servían a él ([`decisions.md`](decisions.md), DEC-32).

### Agente y MCP

- **El agente es el camino por defecto en la CLI**, como en los sistemas RAG de producción. En la web, de momento, se activa a mano (marcado como trabajo en curso), porque con modelos pequeños su memoria de la conversación puede mezclar temas anteriores.
  - Mantiene una **memoria solo de sesión** de la conversación (no se guarda nada).
  - Reescribe las preguntas de seguimiento como preguntas completas y busca con **llamadas nativas a herramientas** (el formato `<tool_call>` de Qwen, o un formato en el prompt para los modelos que no lo tienen). Hasta 3 búsquedas por pregunta.
  - **Redes de seguridad:** si la reescritura no encuentra nada, busca la pregunta original; si el dominio que eligió el modelo no tiene nada, repite la búsqueda dentro del filtro del usuario, nunca fuera de él. Un plan B determinista cubre a los modelos que no llaman a la herramienta.
  - La respuesta final usa el mismo generador y las mismas reglas de dominio que el flujo directo.
- **Servidor MCP** (`make mcp`): el RAG expuesto como herramientas `list_domains`, `search` y `answer`, por stdio o por HTTP (streamable HTTP), para cualquier cliente MCP.

---

## Interfaz web

Backend en FastAPI y frontend en React (Vite + TypeScript), con el estilo visual de la aplicación original en Streamlit:

- **Chat** con respuestas en streaming. Solo se desplaza la conversación, y un botón **Stop** detiene de verdad la generación en el servidor.
- **Filtros de dominio** (`vllm`, `xquad`, `cv`; `about` siempre activo), un interruptor **agente / directo** (directo por defecto; el agente es trabajo en curso) y selectores de **modelo** (Qwen3-1.7B por defecto, Qwen3-0.6B e IBM Granite 4.0 Micro) y de **profundidad** (cuántas fuentes lee el LLM: 3, 5 o 10).
- **Fuentes:** el dominio que respondió, con sus fuentes en un carrusel y el texto completo (enmascarado) a demanda; los demás dominios buscados quedan plegados en una línea, con sus puntuaciones del router.
- **Métricas de recuperación** leídas de las últimas ejecuciones de los benchmarks.
- **Preguntas de ejemplo** opcionales para los filtros activos.

### API

| Endpoint | Para qué sirve |
|---|---|
| `POST /chat` | Responde a un mensaje como Server-Sent Events (`start`, `token`…, `done`). Recibe `agent`, `domains`, `model`, `depth` y `session_id` |
| `POST /chat/reset` | Olvida una conversación |
| `POST /search` | Solo recuperación, sin generación |
| `GET /sources/{id}` | Texto completo de una fuente, con los datos privados enmascarados |
| `GET /config` · `GET /metrics` · `GET /health` | Modelos, dominios y opciones; cifras de los benchmarks; estado |

---

## Cómo ejecutarlo

### Requisitos

- Python 3.10+ y [uv](https://github.com/astral-sh/uv).
- Docker, para Qdrant.
- Node.js, para la web.
- La GPU es opcional. Todo funciona también en CPU y da los mismos resultados, solo que más despacio.

### Instalación

```bash
make install     # entorno virtual, dependencias y los datos públicos (vLLM + XQuAD)
make index       # construye todos los índices (unos 6 min en una RTX 3080 Ti; horas en CPU)
```

El dominio `cv` necesita material privado que no está en el repositorio.

### Uso

```bash
make api                 # la API en http://127.0.0.1:8000 (también sirve la web compilada)
make web-dev             # la web en modo desarrollo en http://localhost:5173
make run ARGS="answer 'How do I enable prefix caching in vLLM?'"   # con agente por defecto
make run ARGS="chat"     # conversación interactiva; /agent activa o desactiva el agente
make mcp                 # servidor MCP (stdio)
```

Modelos opcionales: `PROFILE=llm-qwen3-1.7b` (o `llm-qwen3-4b`) en la CLI. En la web, con el selector de modelo.

### Benchmarks

```bash
make bench                     # recall oficial de 42 (docs y code)
make bench SUITE=xquad         # otras suites: xquad, cv, en, es, about
make gen-bench SUITE=xquad     # calidad de las respuestas (subconjunto fijo de 300 preguntas; FULL=1 para todas)
make agent-bench               # agente frente a directo
make route-bench               # precisión del router
make judge LABEL=<run>         # juez LLM sobre una ejecución de gen-bench (key gratuita de Groq)
make test && make lint         # pytest, flake8, mypy
```

Los comandos originales de 42 no cambian: `make search-docs`, `make search-code`, `make eval-docs`, `make eval-code`.

---

## Despliegue

**Demo en línea:** *próximamente*. <!-- TODO: URL -->

**De momento, la web se sirve desde el ordenador del autor** (una RTX 3080 Ti) a través de un túnel, como parche: `make api-public` limita el servidor a 4 preguntas a la vez, y la API solo escucha en `127.0.0.1`, así que solo se llega a ella por el túnel. El túnel es Tailscale Funnel: los túneles rápidos gratuitos de Cloudflare no admiten el streaming que necesita el chat, y una URL fija de Cloudflare exige un dominio de pago. Guía: [`deploy/local/README.md`](../../deploy/local/README.md).

El servidor gratuito previsto, separado de los otros proyectos del autor en la nube:
- **Servidor:** una máquina ARM de **Oracle Cloud Always Free** (2 OCPU, 12 GB) con Docker. Corre la API y la web compilada, detrás de Caddy para el HTTPS. El plan era un Space de Hugging Face, pero desde julio de 2026 los Spaces de Docker son de pago.
- **Frontend:** lo sirve el mismo contenedor, u opcionalmente GitHub Pages.
- **Índice:** se construye en una GPU local y se copia a la máquina como un bundle (snapshots de Qdrant y ficheros BM25, comprobados con SHA256). No se publica nunca, porque contiene el material del CV sin enmascarar.

`make bundle`, `make space-build` y `make space-run` reproducen la imagen en local (se sigue construyendo desde `deploy/space/`). La guía paso a paso está en [`deploy/README.md`](../../deploy/README.md).

Medido con el contenedor limitado a 2 CPU y 12 GB: 5.0 GB de RAM de pico y 23–37 s por respuesta en x86, en streaming mientras se escribe. La velocidad en las CPU ARM de Oracle está sin medir.

---

## Estructura del proyecto

```
src/
  rag/          el RAG: ingesta, almacenamiento Qdrant/BM25, retriever, router, generador, pipeline
  agent/        el agente: bucle, formatos de llamadas a herramientas, memoria de sesión
  server/       el RAG como herramientas, y el servidor MCP
  api/          backend FastAPI de la web
  evaluation/   evaluador de 42, benchmarks, enrutado, benchmark del agente, juez LLM
  deploy/       exportación y restauración del bundle del índice
  cli.py        CLI con Fire (python -m src <comando>)
web/            frontend en React
deploy/         imagen del servidor (deploy/space), configuración de Oracle (deploy/oracle) y servicio local con túnel (deploy/local)
bench/          datasets versionados y todos los resultados de los benchmarks
docs/           roadmap, changelogs por fase, informe de benchmarks, decisiones (en inglés)
docs/es/        los mismos documentos en español, la versión de trabajo, y este README
rag.toml        configuración: fuentes, modelos y perfiles opcionales
```

Cada pieza del pipeline (chunker, embeddings, reranker, LLM, agente sí o no) se elige con `rag.toml`, variables de entorno o un perfil, no en el código.

---

## Documentación

- [`ROADMAP.md`](ROADMAP.md): el plan y el estado de cada fase, y el registro con fechas de las decisiones.
- [`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md): embeddings, rerankers, LLMs, dominios y el agente, comparados con cifras.
- [`changelog/`](changelog/): qué cambió en cada fase, por qué y en qué afecta.
- [`decisions.md`](decisions.md): decisiones tomadas por el camino, con las opciones que se valoraron.

Los documentos se escribieron en español mientras se construía el proyecto. Estos son los originales; las versiones en inglés, en [`docs/`](../), se actualizan al cerrar cada fase.

---

## Créditos

- **vLLM**, documentación y código (Apache-2.0), el corpus del benchmark de 42.
- **XQuAD** (Google, CC-BY-SA 4.0), basado en Wikipedia.
- Modelos: [Qwen3](https://huggingface.co/Qwen), [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3), [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1).
- Herramientas: Qdrant, bm25s, sentence-transformers, Docling, FastAPI, React, Vite, el SDK de MCP para Python, uv y Python Fire.

### Uso de IA

La versión 2.0 se actualizó junto con Claude (Anthropic), y Chrystian la revisó y la diseñó a mano. Las normas del proyecto están en [`PLANING.md`](PLANING.md): medir cada cambio, documentar cada fase y dejar todas las decisiones al autor.

---

## Licencia

El código y la documentación propios del proyecto se publican con la [licencia MIT](../../LICENSE). El contenido de terceros de este repositorio mantiene sus propias condiciones:
- **`bench/datasets/xquad/`:** derivado de XQuAD, con CC-BY-SA 4.0 (ver su README).
- **`bench/datasets/public/`:** los datasets públicos del proyecto de 42. **`bench/datasets/en/` y `bench/datasets/es/`:** un subconjunto de sus preguntas y su traducción al español. No los cubre la licencia MIT.
- **`llm_sdk/`:** el SDK del curso, proporcionado por 42. No lo cubre la licencia MIT.
- **Los corpus indexados** (vLLM, Wikipedia vía XQuAD) los descarga `make data`, no se guardan en el repositorio y mantienen sus licencias (Apache-2.0 y CC-BY-SA 4.0).

---

**Autor:** Chrystian Donaire Villén · [cdonairevillen@gmail.com](mailto:cdonairevillen@gmail.com)
