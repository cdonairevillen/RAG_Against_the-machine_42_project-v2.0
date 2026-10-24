# CHANGELOG — Fase 5: Agentes y RAG como servidor MCP

**Fecha de inicio:** 2026-10-23
**Estado:** ✅ completada (2026-10-24). Decisiones de D7, reorganización de `src/`, herramientas del RAG, servidor MCP, agente (memoria, reescritura, bucle de herramientas, plan B y redes de seguridad), `chat` con el interruptor agente/directo y benchmark de agente frente a acceso directo con los cuatro modelos (§7).

---

## 1. Decisiones (tuyas)

- **D7 — agente por defecto**, como en un RAG real, y con memoria de sesión. El **acceso directo** se mantiene como opción. En la web será un **interruptor "Con agente / Sin agente"** (Fase 6), y la API lo recibirá como un parámetro de la petición.
- **Todos los modelos pueden ser agente**, incluido Qwen3-0.6B, sin limitarlo. Si un modelo falla, el benchmark lo enseñará, y los benchmarks decidirán qué modelo se despliega.
- **Memoria solo de sesión:** no se guarda nada de los visitantes de la web.
- **El campo `lang` del payload sale del plan:** las respuestas ya siguen el idioma de la pregunta (90–100 % en todos los sets).

## 2. Reorganización de `src/` (sin cambios de lógica)

`src/` estaba plano. Ahora separa el RAG, el RAG como servicio y el agente:

```
src/
├── __main__.py, cli.py     entradas (python -m src …; los comandos de 42 no cambian)
├── config.py, models.py    compartidos (models.py = formatos pydantic de 42)
├── rag/                    el RAG: indexar, recuperar y responder
│   ├── ingestion/  storage/  sources/
│   ├── retriever.py  router.py  embeddings.py
│   ├── generator.py  language.py  domain_rules.py
│   └── pipeline.py         (antes src/rag.py: el flujo de respuesta)
├── server/                 el RAG como servicio: tools.py + mcp_server.py
├── agent/                  el agente (en construcción)
├── evaluation/             benchmarks y evaluador de 42
└── web.py
```

| Antes | Ahora |
|---|---|
| `src/ingestion/`, `src/storage/`, `src/sources/` | `src/rag/ingestion/`, `src/rag/storage/`, `src/rag/sources/` |
| `src/{retriever,router,embeddings,generator,language,domain_rules}.py` | `src/rag/…` |
| `src/rag.py` | `src/rag/pipeline.py` |
| `src/tools.py`, `src/mcp_server.py` (nuevos) | `src/server/` |

- **Por qué `server/` y no dentro de `agent/`:** el servidor MCP es la puerta del RAG. Cualquier cliente lo usa, y nuestro agente es un cliente más. El agente solo depende de las herramientas, nunca de las tripas del RAG.
- **Comprobado:**
  - `make bench` da exactamente lo mismo (`60-fase5-restructure`: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88).
  - 78 tests, flake8 y mypy en verde.
  - `answer` y el servidor MCP funcionan de principio a fin.
- **Los changelogs anteriores** conservan las rutas de su momento; esta tabla las traduce.

## 3. Herramientas del RAG y servidor MCP

- **`src/server/tools.py` (`RagTools`):**
  - `list_domains()`: nombre, descripción y chunks de cada dominio. La descripción es un campo nuevo, `description`, en cada `[sources.<x>]` de `rag.toml`; la necesitan el agente y los clientes MCP para elegir dónde buscar.
  - `search(query, domains, k)`: dominio elegido, puntuación y fuentes con el **texto ya enmascarado**. Si no supera el filtro fuera de dominio, devuelve una lista vacía.
  - `answer(question, domains, k)`: el flujo directo, con sus fuentes.
- **`src/server/mcp_server.py`:** expone esas tres herramientas con el SDK oficial de MCP. En `mcp` 2.x, **FastMCP se llama `MCPServer`**: es la misma API con otro nombre.
  - El RAG se carga en la primera llamada, así el servidor responde al handshake al momento.
  - **Por stdio, la salida de progreso del RAG** ("Loaded … chunks") se redirige a stderr, porque stdout es el canal del protocolo.
- **Uso:**
  - `make mcp`: stdio, para clientes que lanzan el servidor (Claude Desktop, el agente…).
  - `make mcp MCP_TRANSPORT=streamable-http`: `http://127.0.0.1:8765/mcp`.
- **Prueba de punta a punta:** un cliente MCP real lanza el servidor por stdio, lista las tres herramientas y llama a `list_domains` y a `search`.
  - Con el CV, el texto sale enmascarado.
  - La pregunta sobre la Super Bowl va a XQuAD (puntuación 2.8).
  - Corregido: con un solo dominio, la puntuación salía `NaN`, que no es JSON válido; ahora sale `null`.

## 4. El agente (`src/agent/`)

Se inspira en AgentSmith: estructura del bucle, traza de pasos y plan B cuando el modelo no sigue el formato. Cambia lo que es distinto aquí: modelos locales en vez de una API, llamadas a herramientas nativas en vez de código, y una respuesta final redactada por el generador del RAG con sus guardarraíles.

**Flujo por pregunta** (`Agent.ask`):
1. **Planificar:** el LLM recibe los dominios (con su descripción), la conversación y la pregunta, y llama a `search` con una **pregunta completa**: aquí es donde se reescriben los seguimientos. Puede buscar hasta 3 veces y para cuando deja de llamar a la herramienta.
2. **Plan B determinista:** si no hace ninguna llamada válida, se busca la pregunta precedida de la última consulta que escribió el modelo. Así un seguimiento conserva su tema ("¿Dónde nació Chrystian? ¿Y en qué año?").
3. **Responder:** las fuentes reunidas van al **mismo generador del flujo directo**, con las reglas del dominio (citas, prompt del CV, datos privados, tu mensaje de "no encontrado") y en el **idioma del usuario**, aunque la búsqueda se haya reescrito en otro.
4. **Memoria:** el turno se añade a la sesión (`Session`, solo en memoria; D7).

**Cada modelo con su convención de herramientas** (`src/agent/toolcalls.py`):
- **`native`** (Qwen3): `apply_chat_template(..., tools=)`, y las llamadas salen como `<tool_call>{json}</tool_call>`.
- **`system_tools`** (Phi-4-mini): las herramientas van como JSON en un campo `tools` del mensaje de sistema (`<|tool|>…<|/tool|>`).
- **`prompt`** (cualquier otro modelo): se describen en el prompt de sistema y se pide el formato `<tool_call>`.
- **El parser acepta todos los envoltorios** y formas de JSON, incluso cortadas o con comillas simples.
- `Generator.complete()` devuelve la salida en bruto con esas marcas; `decode()` las quitaba.

**Ajustes medidos a mano con Qwen3-0.6B** (antes de los benchmarks):

| Problema | Arreglo |
|---|---|
| Con el historial como turnos de chat anteriores (usuario/asistente), en los seguimientos el modelo **copiaba el patrón y respondía sin buscar** | El historial va **dentro del turno del usuario** ("Conversation so far: … New question: …"), y así el patrón siempre es pregunta → herramienta |
| En los seguimientos respondía "DONE" sin buscar ("la conversación ya lo dice") | Regla del prompt: "toda pregunta nueva necesita al menos una búsqueda"; DONE solo después de buscar |
| El plan B encadenaba consultas ("¿Dónde nació…? ¿Y en qué año? ¿En qué barrio…?") y perdía el tema | El plan B usa la última consulta escrita por el **modelo**, no las de otros planes B |

**Redes de seguridad** (tras la ronda 1 del benchmark; tu propuesta, acotada; `docs/decisions.md`, DEC-03):

| Red | Cuándo actúa | Qué hace |
|---|---|---|
| **1. Pregunta original** | Ninguna búsqueda del modelo encontró fuentes (sus reescrituras en palabras sueltas no pasan el filtro de relevancia) | Busca la pregunta tal como la escribió el usuario, dentro de su filtro |
| **2. Dominios** | El modelo restringió dominios, el usuario **no** puso filtro y no se encontró nada | Repite la misma consulta en todos los dominios (exactamente lo que busca el modo directo) |

- **Nunca se sale del filtro del usuario:** con filtro, los dominios del modelo ya son ese filtro, y la red 2 no actúa. Lo garantiza `test_user_filter_is_never_exceeded`.
- **Si las dos fallan**, se usa el plan B determinista de siempre.
- **Cada uso queda en la traza** (`AgentAnswer.retries`: `"all-domains"`, `"original-question"`), visible en la web y en `chat`.

Con esto, Qwen3-0.6B reescribe de verdad: "¿Y en qué año?" → "¿Y en qué año? Chrystian Donaire Villén nació en Madrid."; "¿En qué barrio creció?" → "¿En qué barrio creció Chrystian Donaire Villén?"; "And which one unloads it?" → "which endpoint unloads a LoRA adapter in vLLM" (con `domains: vllm`).

**Uso:**
- `answer` usa el **agente por defecto** (D7); `--agent False` usa el flujo directo.
- **`chat`** es una conversación interactiva con memoria: `/agent` alterna agente/directo (el futuro interruptor de la web), `/reset` olvida la conversación y `/exit` sale.
- El **filtro de dominios del usuario** (por ejemplo, el modo CV de la web) manda sobre los dominios que elija el modelo.

**Benchmark** (`make agent-bench`, `src/evaluation/agent_bench.py`):
- Cada pregunta se responde con el agente y con el flujo directo.
- **Conversaciones:** `bench/datasets/conversations/conversations.json`, 12 diálogos de 2–3 turnos en inglés y español sobre CV, XQuAD y vLLM, uno de ellos con cambio de dominio. Los seguimientos ("¿Y cómo se llama el videojuego en el que trabaja allí?", "And which one unloads it?") necesitan los turnos anteriores.
- **Preguntas sueltas:** CV (30 + 30), XQuAD (50 + 50, muestra fija) y vLLM (25 docs + 25 code).
- **Métricas:** contiene la respuesta, F1, "no encontrado", segundos por respuesta y, solo para el agente, la proporción de llamadas válidas a la herramienta (sin plan B) y los pasos.
- **El LLM es el del perfil activo**, así que el mismo benchmark compara modelos: `make agent-bench PROFILE=llm-qwen3-4b`.

## 5. Descarga de datos unificada (`Makefile`, petición tuya)

| Target | Antes | Ahora |
|---|---|---|
| `make data` | Solo vLLM | **Todas las fuentes públicas:** `data-vllm` + `data-xquad` |
| `make data-vllm` | — | vLLM 0.10.1 desde la etiqueta de GitHub (el antiguo `data`) |
| `make data-xquad` | Igual | Igual |
| `make data-42` | Descarga original de 42 (vLLM + datasets) | **Eliminado.** Era redundante: su vLLM es idéntico al de la etiqueta de GitHub (comprobado en la Fase 0), los datasets públicos ya están versionados (ahora en `bench/datasets/public/`, ver más abajo) y el CDN de la intra da 403 sin sesión de 42. Se elimina también la variable `URL_42` |
| `make install` | Dependía de `data`, que corría antes de crear el venv | Crea el venv, instala y **después** ejecuta `data` (XQuAD se prepara con Python) |

- **No se descargan:** el CV (material privado) y Gulliver (4c, aplazada).
- **Comprobado:** `make data` regenera XQuAD idéntico (2 380 respuestas verificadas, los datasets versionados no cambian).

**`data/` y `bench/` unificados** (petición tuya; elegí el sentido, `docs/decisions.md` DEC-01):
- Los datasets públicos de 42 pasan de `data/datasets/` a **`bench/datasets/public/`** (`git mv`, sin cambiar los ficheros).
- **Ahora:** `bench/` es lo versionado (datasets y resultados) y `data/` es lo local y regenerable (corpus, índices, salidas), ignorado entero por git sin excepciones.
- **Rutas actualizadas:** `Makefile` (`DATASETS`), `SUITES` de `bench.py`, ejemplos de `cli.py`, el docstring del evaluador, `web.py` y el `README.md`.
- **El evaluador de 42 se conserva:** es la métrica de referencia (D4) que usan todos los benchmarks; no es código legacy. Se añade una nota en su docstring.
- **Comprobado:** `make bench` da lo mismo (`61-datasets-moved`: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88).

## 6. Ficheros

| Fichero | Cambio |
|---|---|
| `src/rag/**`, `src/server/**` | Movidos (§2) y nuevos `tools.py` y `mcp_server.py`. |
| `src/cli.py` | Comando `mcp`; imports nuevos. |
| `src/config.py` | `SourceConfig.description`. |
| `rag.toml` | Descripción de cada dominio. |
| `Makefile` | `make mcp` (`MCP_TRANSPORT`, `MCP_PORT`). |
| `pyproject.toml`, `uv.lock` | `mcp>=2.3.0`. |
| Resto de `src/` y `tests/` | Solo imports y rutas en comentarios. |
| `src/agent/agent.py`, `memory.py`, `toolcalls.py` | **Nuevos.** El agente, la memoria de sesión y las convenciones de herramientas. |
| `src/rag/generator.py` | `complete()` (salida en bruto) e idioma de respuesta opcional (`language`). |
| `src/cli.py` | `answer` con agente por defecto (`--agent`), `chat` interactivo y `agent_bench`. |
| `src/evaluation/agent_bench.py`, `bench/datasets/conversations/` | **Nuevos.** Benchmark de agente frente a acceso directo. |
| `Makefile` | `make agent-bench` (`SETS=`, `PROFILE=`); `data` unificado (§5). |
| `tests/test_agent.py` | **Nuevo.** Parser de cada convención, estilos, memoria y bucle del agente (llamada válida y plan B). Después, también las redes de seguridad y que el filtro del usuario nunca se supera. |
| `src/agent/agent.py` | Redes de seguridad y `AgentAnswer.retries` (después del checkpoint `680f21a`). |
| `src/evaluation/agent_bench.py` | `safety_net_rate`. |
| `data/datasets/` → `bench/datasets/public/` | Movidos (§5). Rutas en `Makefile`, `bench.py`, `cli.py`, `evaluator.py`, `web.py` y `README.md`; `.gitignore` sin la excepción `!data/datasets/`. |
| `docs/BENCHMARK_REPORT.md` | §8: agente frente a acceso directo. |

## 7. Resultados y cierre

Detalle completo en `BENCHMARK_REPORT.md` §8. Contiene la respuesta, agente / directo (ronda 2, con redes):

| Modelo | Seguimientos | CV EN / ES | XQuAD EN / ES |
|---|---|---|---|
| **Qwen3-0.6B** | **0.78** / 0.33 | 0.70 / 0.80 (directo 0.73 / 0.80) | 0.58 / 0.70 (directo 0.62 / 0.70) |
| Qwen3-1.7B | 0.83 / 0.33 | 0.90 / 0.87 | 0.76 / 0.68 |
| Qwen3-4B | **1.00** / 0.39 | 0.87 / 0.90 | 0.80 / 0.88 |
| Phi-4-mini | 0.78 / 0.33 | 0.83 / 0.90 | 0.74 / 0.64 |

- **El agente resuelve los seguimientos** (el directo no puede) y, con las redes, queda **a la par del directo** (±0.04) en preguntas sueltas con los cuatro modelos. En la ronda 1, el 0.6B perdía 0.12 en XQuAD EN y el 1.7B, hasta 0.32.
- **Recall de 42:** sin cambios (`61-datasets-moved`). El agente no toca el retrieval medido.
- **Tests:** 94 pasan; flake8 y mypy limpios.
- **Ronda 1** (`01-agent-*`) incluida en el commit de checkpoint; **ronda 2** (`02-agent-nets-*`) sin commitear.

> ✅ **Fase 5 completada (2026-10-24)**, a falta de tu revisión: agente por defecto con memoria de sesión, servidor MCP, acceso directo como opción y benchmark. **Pendiente de decidir:** qué LLM se despliega (propuesta en `BENCHMARK_REPORT.md` §8.3: Qwen3-0.6B, con Qwen3-1.7B como candidato si la CPU del Space lo aguanta).
