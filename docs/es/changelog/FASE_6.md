# CHANGELOG — Fase 6: Web y despliegue

**Estado:** preparada y probada en local **hasta el punto de despliegue** (tu encargo). Falta lo que depende de tus cuentas: crear el dataset privado y el Space en Hugging Face, poner los secretos y, si quieres, lanzar GitHub Pages. Los pasos están en `deploy/README.md`.

Hecho de forma autónoma durante la noche del 2026-10-23/24. Las decisiones que tomé sin consultarte están en **`docs/decisions.md`** (DEC-04 a DEC-16), con las opciones y por qué elegí cada una.

**Commit:** `3378494` ("Phase 6: Frontend and deployment"), tras las revisiones de §6b–6g. El despliegue en Hugging Face queda pendiente de tus cuentas.

---

## 1. Arquitectura

```
navegador ──► FastAPI (src/api) ──► RagTools (src/server/tools.py) ──► router + retrievers + generador
   │              │                         ▲
   │              ├── /chat ── Agent (src/agent) por sesión ─┘   (o flujo directo)
   │              └── sirve web/dist (React) en "/"
   └── React (web/), la misma estética que src/web.py
```

- **La API es una capa fina sobre las mismas herramientas** que usan la CLI y el servidor MCP (`RagTools`). No hay lógica de RAG nueva: el agente y el flujo directo son los de la Fase 5.
- **Una sola URL:** la API sirve también la web compilada. GitHub Pages queda como opción (DEC-08).
- **Despliegue:** un Hugging Face Space (Docker, CPU gratuito) con Qdrant dentro del contenedor. El índice llega en un bundle desde un dataset **privado** de HF (DEC-09, por privacidad).

## 2. Backend: `src/api/`

| Endpoint | Qué hace |
|---|---|
| `GET /health` | `{"status": "ok", "loaded": bool}`. Los modelos se cargan en segundo plano al arrancar, así que la web puede mostrar "cargando" en vez de colgarse. |
| `GET /config` | Modelo, perfil, dominios (con descripción y número de chunks), modos (`demo`, `cv`), agente por defecto y `k`. |
| `POST /chat` | **Streaming SSE** (DEC-04). Eventos: `token` (cada trozo de texto), `done` (respuesta, fuentes, `session_id`, dominio y traza) y `error`. |
| `POST /chat/reset` | Olvida la conversación de una sesión. |
| `POST /search` | Búsqueda sin generación (la herramienta `search` del MCP). |
| `GET /sources/{chunk_id}` | El texto completo de una fuente, **enmascarado**. 404 si no existe. |
| `GET /metrics` | Recalls del último `bench` de cada suite y el último `agent-bench`, leídos de `bench/results/` (para las barras de la web). |

**Petición de `/chat`:**
```json
{"message": "...", "session_id": "opcional", "agent": true, "mode": "demo|cv", "domains": ["vllm"]}
```
- **`agent`** es el interruptor "With agent / Direct RAG" (petición tuya). Por defecto, `true` (D7).
- **`mode: "cv"`** fija el filtro en `["cv"]`. En `demo`, `domains` filtra (los desconocidos se ignoran); sin filtro, busca en todos.
- **`message`**: de 1 a 1 000 caracteres (422 fuera de ese rango).

**Detalles:**
- **Sesiones** (DEC-05): un `Agent` por `session_id` (lo genera el servidor), en memoria, con un máximo de 500 sesiones y 30 min de inactividad. No se guarda nada en disco.
- **Una generación a la vez** (DEC-06): un candado serializa las llamadas al LLM.
- **Fuentes:** índice `[n]`, dominio, ruta corta (`docs/x.md` en vez de `data/raw/vllm-0.10.1/docs/x.md`), offsets, una vista previa enmascarada de 400 caracteres y el **crédito CC-BY-SA** en las de XQuAD.
- **CORS:** `RAG_ALLOWED_ORIGINS` (por ejemplo, la URL de Pages). Sin la variable, se permite cualquier origen.
- **Ejecución:** `make api` (`python -m src.api`, uvicorn en `127.0.0.1:8000`).

## 3. Frontend: `web/` (Vite 6 + React 19 + TypeScript)

- **La misma estética que `src/web.py`** (D5): fondo `#0a0a0a`, acento `#ff3b3b`, JetBrains Mono + Inter, tarjetas de fuentes y barras de recall. CSS propio, sin librería de componentes (DEC-07).
- **Pestañas de modo:** *Demo* (todos los dominios, con chips para filtrar) y *CV* (solo el CV).
- **Interruptor** "With agent (memory)" / "Direct RAG".
- **Conversación** con *streaming*. Cada respuesta muestra:
  - Una línea de traza: dominio y modo, más las consultas reescritas y las redes usadas en modo agente.
  - Tarjetas de fuentes plegables, con "show full source" (`/sources/{id}`).
- **Panel de métricas** con los recalls de `/metrics`. Un indicador de estado consulta `/health` mientras cargan los modelos.
- **Pie:** GitHub, el correo público (`cdonairevillen@gmail.com`, el único contacto que se muestra) y el crédito de XQuAD.
- **Interfaz en inglés** (DEC-07); las respuestas siguen el idioma de la pregunta.
- **URL de la API:** `VITE_API_URL`. En desarrollo, `http://127.0.0.1:8000`; compilada, la misma URL que la sirve.
- **Comandos:** `make web-dev` (Vite en `:5173`) y `make web-build` (`web/dist`, 232 KB de JS / 73 KB comprimido). `npm run lint` pasa.

## 4. Despliegue

| Pieza | Fichero | Qué hace |
|---|---|---|
| **Bundle del índice** | `src/deploy/bundle.py` (`make bundle`) | **Export:** snapshot de cada colección por la API HTTP de Qdrant (crear, descargar y borrar del servidor), más una copia de `data/processed/<dominio>` (BM25 y chunks) y un `bundle.json` con el SHA256 de cada fichero. **Restore** (`bundle_restore`): comprueba los SHA256, sube cada snapshot a `/collections/{c}/snapshots/upload` y copia BM25. |
| **Imagen del Space** | `deploy/space/Dockerfile` | Binario de Qdrant v1.19.1 (la misma versión que `docker-compose.yml`, DEC-10), `python:3.12-slim`, `uv sync --frozen --no-dev` (DEC-11), modelos descargados al construir (DEC-12), usuario uid 1000 y puerto 7860. |
| **Contexto de build** | `deploy/space/Dockerfile.dockerignore` | Lista blanca: `data/` (con el CV), `.venv` y `node_modules` nunca salen de la máquina (DEC-16). |
| **Arranque** | `deploy/space/entrypoint.sh` | Qdrant (almacenamiento en `/tmp`), el bundle (montado en local o descargado de `RAG_BUNDLE_REPO` con `HF_TOKEN`), `bundle_restore` y la API. |
| **Ficha del Space** | `deploy/space/README.md` | Metadatos del Space (Docker, puerto 7860) y descripción. Sin licencia (DEC-14). |
| **Contenido del Space** | `make space-stage` | `deploy/stage/`: el Dockerfile en la raíz y solo el código necesario, listo para hacer `push` al git del Space. |
| **Prueba local** | `make space-build`, `make space-run` | La imagen, y su ejecución en `:7860` con `deploy/bundle` montado. |
| **GitHub Pages** | `.github/workflows/pages.yml` | **Manual** (`workflow_dispatch`): compila la web con `VITE_API_URL = vars.RAG_API_URL` y la publica. |
| **Guía** | `deploy/README.md` | Paso a paso, en español. |

**Privacidad (DEC-09):** el enmascarado ocurre al responder, pero el índice guarda el material del CV sin enmascarar. Por eso:
- El bundle va a un dataset **privado**, no a la imagen.
- `deploy/bundle/` y `deploy/stage/` están en `.gitignore`.
- El token del Space es un secreto de solo lectura.

## 5. Pruebas

**Tests** (`tests/test_api.py`, 7 nuevos, con un RAG falso):
- *Streaming* SSE (`token`… `done`).
- El modo CV restringe al dominio `cv` y se ignoran los dominios desconocidos.
- Las sesiones del agente conservan la memoria.
- Fuentes enmascaradas y 404.
- Límite de longitud del mensaje.
- `short_path`.

**Total:** 94 tests pasan; flake8 y mypy limpios.

**Prueba de la API real** (índice completo, Qwen3-0.6B en la 3080 Ti):

| Prueba | Resultado |
|---|---|
| `/health` hasta `loaded: true`; `/config` | ✅ 3 dominios (vllm 37 381 chunks, xquad 1 217, cv 162) |
| "¿Dónde nació Chrystian?" (CV, agente) | ✅ "…nació el 20 de enero de 1996 en Madrid. [3]", con 14 eventos de *streaming* y la cita en la biografía |
| Seguimiento "¿Y en qué año?" con el mismo `session_id` | ✅ El agente reescribe la consulta ("¿Y en qué año? Chrystian Donaire Villén nació en Madrid.") y responde con el año |
| Pregunta por un dato de contacto privado | ✅ "I don't have that information, but you can ask him yourself! cdonairevillen@gmail.com" |
| **Fugas** en todas las respuestas, fuentes y vistas previas | ✅ **0** (la vista previa del CV muestra `[dato privado]`) |
| "How do I enable prefix caching in vLLM?" (directo) | ✅ `enable_prefix_caching=True`, con 5 fuentes de vLLM (router: vllm 10.2, xquad −5.2, cv −5.9) |
| "¿Quién ganó la Super Bowl 50?" (filtro `xquad`) | ✅ "…los Broncos", con el crédito CC-BY-SA en la fuente |
| "What is the capital of France?" | ⚠️ Responde "Paris", citando `docs/serving/openai_compatible_server.md`: es el caso conocido de la Fase 3 (está en la documentación de vLLM como ejemplo de la API), no una alucinación |
| `/search`, `/metrics` y `GET /` (la web compilada) | ✅ |

**Nota:** con `curl` desde Git Bash en Windows, un JSON con tildes escrito en la propia línea de comandos llega mal codificado (400 "error parsing the body"). Es un problema de la consola, no de la API: el mismo cuerpo enviado desde un fichero UTF-8 funciona.

**Prueba del despliegue en local:** ver §6.

## 6. Prueba de la imagen del Space

**Bundle** (`make bundle`): 358 MB.
- Snapshots: vllm 327 MB, xquad 16 MB, cv 3 MB.
- Más BM25 y `bundle.json` con los SHA256.

**Imagen** (`make space-build`):
- Construye bien. El contexto enviado a Docker es de 2.17 MB gracias a la lista blanca (DEC-16).
- **Tamaño real ~13.5 GB:**
  - venv 7.3 GB, de los que 3.6 GB son librerías `nvidia-*` y 0.9 GB `triton`, por el torch con CUDA del lock (DEC-11).
  - Modelos 6.2 GB. De ellos, bge-m3 ocupa 4.3 GB porque su caché tiene dos ficheros de pesos de 2.2 GB, y solo uno está en el snapshot que usa el modelo.
  - `docker images` dice 23.1 GB porque cuenta también las capas comprimidas.
- **Optimizable más adelante:** torch de CPU en un lock de despliegue (unos −4.5 GB) y descargar solo los ficheros de pesos que se usan (unos −2.2 GB). No lo he tocado: es un cambio de dependencias que conviene decidir contigo.

**Arranque** (`make space-run`, con el bundle montado):
- Qdrant arranca y los SHA256 se comprueban. Se restauran las 3 colecciones, con los mismos chunks que en local (37 381 / 1 217 / 162).
- La API está lista (`loaded: true`) en **33 s** sin límites y en **39–47 s** con 2 vCPU.
- Memoria en uso: ~4–5.7 GB de 16 GB.

**Mismas pruebas que con la API local**, ahora en CPU dentro del contenedor:
- Las mismas respuestas que en GPU.
- **0 fugas** en `/chat`, `/search` y `/sources`. Los chunks padre con datos privados salen enmascarados por `/sources`. Los hijos dan 404, porque `/sources` solo sirve los padres que citan las respuestas.
- La web, en `GET /`.

**Latencia con los límites del Space gratuito simulados** (`docker run --cpus=2 --memory=16g`). Primer token / respuesta completa, en segundos:

| Pregunta | Directo (12 hilos) | Agente (12 hilos) | **Directo (2 hilos)** | **Agente (2 hilos)** |
|---|---|---|---|---|
| ¿Dónde nació Chrystian? (CV) | 25.1 / 47.9 | 61.3 / 84.2 | **10.6 / 14.4** | **18.2 / 22.0** |
| ¿Y en qué año? (CV, seguimiento) | 24.4 / 53.2 | 67.8 / 90.9 | **9.6 / 14.3** | **19.8 / 23.6** |
| How do I enable prefix caching in vLLM? | 38.8 / 88.3 | 74.4 / 123.4 | **15.7 / 24.0** | **23.4 / 31.7** |
| Who won Super Bowl 50? | 40.3 / 51.5 | 83.8 / 94.6 | **17.5 / 19.3** | **27.5 / 29.4** |

- **Hallazgo:** torch abría 12 hilos con una cuota de 2 vCPU (veía los 24 núcleos del host). **Arreglado en `entrypoint.sh`** (DEC-17): los hilos salen de la cuota del cgroup. La columna "2 hilos" es la imagen ya arreglada, sin variables a mano (`CPU threads: 2` en el log).
- La API arranca con `HF_HUB_OFFLINE=1`: 0 llamadas al Hub en el arranque.
- **Lectura:**
  - En el Space gratuito, una respuesta directa tarda ~15–25 s y una con agente ~22–32 s. Los primeros tokens llegan a los ~10–28 s.
  - El agente añade ~8 s (su llamada de planificación al LLM).
  - El directo, con la respuesta en su memoria, contesta mal al seguimiento ("En el año 2017, dejó su formación…"); el agente lo resuelve bien.
  - **No he desglosado** cuánto de los ~10 s previos al primer token es búsqueda (embeddings y reranker) y cuánto la lectura del prompt por el LLM.
- **Ojo:** es una simulación en mi máquina. La CPU real del Space puede ser más lenta o más rápida.

## 6b. Cambios tras tu primera revisión de la web (2026-10-24)

| Petición tuya / fallo | Cambio |
|---|---|
| **La página se quedaba gris** con cualquier botón | `useEffect(() => bottom.current?.scrollIntoView(...))` devolvía el resultado de `scrollIntoView`, y los Chrome recientes devuelven ahí una Promise. React la tomaba como función de limpieza (`destroy is not a function`) y desmontaba la app entera. Arreglado poniendo el cuerpo del efecto entre llaves. |
| Modos Demo/CV redundantes con los filtros | **Se quitan los modos** de la web y de la API (`mode` y `/config.modes`). Quedan solo los filtros de dominio. |
| Poder apagar todos los filtros | Con todos apagados, la API responde sin buscar *"Activa alguno de los filtros para poder buscar en mi base de datos."* o *"Turn on at least one of the filters to search my database."*, según el idioma de la pregunta. En la API: `domains` omitido = todos; `[]` = ninguno. |
| Retrievals poco estéticos | Un bloque por dominio buscado (máximo 3, uno encima de otro), con **flechas** para pasar sus fuentes una a una. Va primero el dominio con el que se ha respondido (borde rojo, "used in the answer", con las citas `[n]` de la respuesta) y después los demás ("not used"), con lo que encontraron. Solo aparecen los dominios con el filtro activo. |
| Quitar las preguntas "Try" | Fuera de la página. Se conservan en `web/src/examples.ts` hasta decidir dónde van. |
| (encontrado al probar) Con un solo filtro activo y el modo directo, la traza llevaba `NaN` | Python lo acepta, pero no es JSON válido y el navegador habría fallado. La puntuación de un dominio único sale ahora como `null`. |

- **Para el panel por dominio,** `DomainRouter` guarda en `last_ranked` lo que encontró cada dominio en la última búsqueda (antes solo se quedaba el ganador). Es solo registro: la búsqueda, el enrutado y lo que se mide no cambian.
- **En modo agente,** los bloques son los de la última búsqueda del agente. Si el modelo restringe la búsqueda a un dominio, solo sale ese.
- **Pruebas:** 95 tests (nuevos: los filtros, el mensaje sin filtros en ES/EN, `null` en lugar de `NaN` y los retrievals por dominio). Además, un recorrido en Chrome headless sin errores en la página: pregunta, seguimiento, flechas, "New", todos los filtros apagados y un solo filtro en directo.
- **Ojo con preguntas muy cortas** ("hola"): no hay texto suficiente para detectar el idioma, así que el mensaje sin filtros sale en inglés.

## 6c. Segunda revisión: chat a pantalla completa y selectores (2026-10-24)

**Por qué no veías los cambios:** la API (`:8000`) sirve la web **compilada** (`web/dist`), que era de la noche anterior. Los cambios solo se veían en el servidor de desarrollo (`:5173`), y además la API seguía con el código viejo, porque no se recarga sola. Ahora `web/dist` está recompilado, y la web tolera una API antigua (sin `retrievals`) en lugar de romperse.

| Petición tuya | Cambio |
|---|---|
| El switch cambiaba de posición | Primero el texto (de longitud variable) y después el interruptor, pegado al borde derecho. Medido: la misma posición encendido y apagado. |
| Chat como en las webs de IA actuales | La página ocupa la ventana y **solo se desplaza la conversación**. La caja de escritura queda siempre abajo: crece con el texto, Enter envía y Shift+Enter hace salto de línea. Sin conversación, la descripción aparece en el centro. El pie pasa a la columna derecha. En móvil (<860 px) vuelve al scroll normal. |
| **Selector de modelo** junto a la caja | Desplegable hacia arriba. Opciones: la base (Qwen3-0.6B) y los perfiles `llm-*` de `rag.toml` (Qwen3-1.7B, Qwen3-4B, Phi-4-mini), con una nota de cada uno sacada del benchmark. |
| **Selector de profundidad** | Cuántas fuentes recibe el LLM: *Auto* (lo de cada dominio: 5, y 8 en el CV) o 3, 5 y 10 forzadas. |

**Cómo funciona por dentro (`src/api/app.py`):**
- **`ModelPool`:**
  - Un modelo se carga la primera vez que se elige, y solo hay uno cargado a la vez: al cambiar se descarga el anterior.
  - Variables: `RAG_API_MODELS` limita los modelos que se ofrecen (en el Space solo cabrá uno o dos) y `RAG_API_MAX_LOADED` deja más de uno cargado.
  - Si un modelo no cabe, la API vuelve a cargar el anterior y responde con un mensaje claro.
  - La memoria de la conversación (agente) se conserva al cambiar de modelo.
- **Profundidad:** durante la petición se sustituye el `answer_k` de cada dominio, y se restaura al acabar. Las peticiones van una a una (candado), y no se toca el código de búsqueda ni lo que se mide.
- **`Agent`** acepta el `generator` que le da la API (parámetro opcional; por defecto, el de siempre).
- **La traza** de cada respuesta incluye el modelo que la escribió.

**Probado:**
- 96 tests: los nuevos cubren el modelo por defecto, un modelo desconocido y que la profundidad se aplica y se restaura.
- Recorrido en Chrome headless: menús, profundidad 3 → 3 fuentes, la página sin scroll (solo se desplaza la conversación) y 0 errores en la página.
- ⚠️ **Cargar Qwen3-1.7B falló en mi prueba** porque había dos APIs en la GPU (la tuya y la mía): 11.5 de 12 GB ocupados. `llm_sdk` reparte parte del modelo a la CPU cuando no cabe y luego falla al moverlo (`You can't move a model that has some modules offloaded`). `llm_sdk` no se toca. Con una sola API debería caber el 1.7B; **el 4B (~8 GB) irá muy justo junto a la búsqueda (~2.7 GB)**. Queda por medir con una sola API.

## 6d. Tercera revisión: modelos que no cargaban, recall en tarjetas y ejemplos (2026-10-24)

**Por qué el 1.7B y el 4B "no tenían memoria" y Phi-4-mini sí** (Phi es más grande que el 1.7B):
- **Fallo mío.** Al cambiar de modelo, el agente de tu conversación seguía apuntando al anterior mientras se cargaba el nuevo, así que el anterior no se liberaba.
- **Arreglo:** los agentes sueltan el modelo **antes** de cargar otro (test `test_switching_model_releases_the_old_one_first`).
- **Segundo fallo:** si una carga fallaba, la excepción retenía el modelo a medio cargar, y el mensaje acababa hablando del modelo anterior. Arreglado.

**Medido con la API sola en la 3080 Ti**, una conversación con agente que pasa por los cuatro modelos. Tiempo de la respuesta, incluida la carga, y GPU ocupada al acabar:

| Modelo | Resultado | Tiempo | GPU |
|---|---|---|---|
| Qwen3-0.6B | ✅ | 3.5 s | 5.1 GB |
| Qwen3-1.7B | ✅ (seguimiento bien resuelto) | 7.2 s | 7.8 GB |
| Qwen3-4B | ❌ no cabe: ~8 GB de modelo + ~4 GB de búsqueda. Mensaje claro y vuelta al modelo anterior | 7.5 s | 7.6 GB |
| Qwen3-1.7B (otra vez) | ✅ | 2.7 s | 7.7 GB |
| Phi-4-mini | ✅ muy justo | 8.7 s | 11.3 GB |
| Qwen3-0.6B (vuelta) | ✅ | 5.8 s | 5.2 GB |

**Cambios de la web:**
- **Recall en tarjetas:** una por dominio (vLLM, XQuAD, CV), una debajo de otra. Cada una pasa entre sus conjuntos con flechas (docs/code; EN/ES), como los retrievals del chat.
- **Preguntas de ejemplo** sobre la caja de escritura, con un interruptor (apagado por defecto). Solo salen las de los filtros activos, y al pulsar una se pregunta.
- **Profundidad:** 3, 5 o 10 fuentes, **5 por defecto** (la `k` que evalúa 42). Desaparece "Auto". ⚠️ En el CV, esto cambia las 8 fuentes calibradas en la Fase 4b (`32-cv-k8`) por 5. Se puede elegir 10.
- **Barras de scroll oscuras**, provisionales hasta que elijas un estilo.

**Probado:** 97 tests; flake8 y mypy limpios; Chrome headless sin errores.

## 6e. Cuarta revisión (2026-10-24)

- **Qwen3-4B fuera de la lista en local:** `make api` pasa `RAG_API_MODELS=$(API_MODELS)` (0.6B, 1.7B y Phi-4-mini). No cabe en 12 GB con la búsqueda en la GPU (§6d). El Space define su propia lista.
- **Retrievals de un solo dominio:** se ve el dominio del que sale la respuesta. Los demás dominios buscados quedan plegados en una línea ("also searched: xquad (−4.32), vllm (−7.68)") que se despliega al pulsarla: así se sigue viendo cómo eligió el router.
- **"No encontrado" en el idioma de la pregunta:**
  - **Antes:** fuera del CV, el mensaje genérico solo existía en inglés ("Not found in the provided sources."), así que una pregunta en español sin respuesta se contestaba en inglés.
  - **Ahora:** `not_found_for()` (en `src/rag/generator.py`) da "No se encuentra en las fuentes proporcionadas." en español. El pipeline y el agente lo usan cuando el dominio no tiene mensaje propio. El prompt sigue pidiendo la frase en inglés, como hasta ahora.
  - **Patrón nuevo:** "…no está disponible en las fuentes…" (visto con Qwen3-1.7B) ya se reconoce como "no encontrado", y en el CV se sustituye por tu mensaje con el correo.
  - **Recall y benchmarks:** sin efecto. El benchmark de 42 es en inglés, y la frase en español ya la reconocían los patrones.
- **Respuesta en inglés a una pregunta en español con 1.7B:** no reproducida. Con 5 preguntas sobre el CV en español, todas las respuestas con contenido salieron en español. Queda pendiente con tu pregunta exacta.
- **Pruebas:** 99 tests; flake8 y mypy limpios; Chrome headless sin errores.

## 6f. Respuestas cortadas y en inglés (2026-10-24)

**Respuestas en inglés a preguntas en español.** Tu pregunta era "Experiencia laboral de Chrystian". Ninguna de sus palabras estaba entre los marcadores del detector de idioma (`src/rag/language.py`): devolvía "?", no se pedía ningún idioma y el modelo seguía el de las fuentes, que es el inglés.
- **Nuevos marcadores en español:** "de", "y", "en", "sobre", "mi", "tu", "quién".
- **Nuevos marcadores en inglés:** "in", "an", "his", "about", "from", "who", "where".
- **Señal extra:** las tildes, la ñ y ¿¡ cuentan como español.
- **Comprobado con todas las preguntas de los benchmarks:** ninguna cambia a un idioma equivocado. XQuAD ES pasa de 2 mal detectadas y 13 sin idioma a 0 y 0. XQuAD EN pasa de 20 sin idioma a 3.

**Respuestas cortadas.** El límite era de 150 tokens nuevos (`rag.toml`). Medido con 4 preguntas:

| Modelo | Tokens por respuesta con un límite de 600 |
|---|---|
| Qwen3-0.6B | 12–61: nunca llega al límite |
| Qwen3-1.7B | 20–145, pero "Experiencia laboral de Chrystian" necesita **265** (12.9 s en la 3080 Ti) |

- **La web sube el límite a 400** (`API_MAX_TOKENS` en `make api`; `RAG_GENERATION_MAX_NEW_TOKENS=400` en la imagen del Space).
- **`rag.toml` mantiene 150,** para que `gen-bench` siga siendo comparable con las fases anteriores.

**Pruebas:** 100 tests; flake8 y mypy limpios.

## 6g. Botón Stop, límite alto y esquinas de puntos (2026-10-24)

**Objetivo (tuyo):** que el LLM escriba lo que necesite, sin cortar respuestas válidas y sin quedar atrapado en bucles.

**Medido antes de decidir:**
- Con 6 preguntas complejas y sin límite práctico, la respuesta válida más larga fue de **464 tokens** (Phi-4-mini con 10 fuentes). El 1.7B no pasó de 321.
- Phi-4-mini entró una vez en **bucle** con el "paso a paso de vLLM": a partir del paso ~20 repite una plantilla y se inventa opciones (`--response-func`…) hasta agotar el límite.
- **Un detector de bucles automático no es fiable:** una regla de "parar si se repite la misma secuencia de N palabras" salta en 32 de 3.933 respuestas buenas guardadas (código, listas…), y el bucle de Phi solo repite su secuencia 5 veces.
- **Penalizar la repetición** cambiaría todas las respuestas y obligaría a repetir `gen-bench`. Descartado por ahora.

**Lo aplicado (opción 1):**
- **Límite de la web: 1024 tokens**, solo como red de seguridad (`API_MAX_TOKENS` en `make api`; también en la imagen del Space). `rag.toml` mantiene 150 para los benchmarks.
- **Si se llega al límite,** la respuesta se recorta en la última frase completa con "…" y se cierra un bloque de código que haya quedado abierto. La traza lo indica: "cut at the length limit".
- **Botón Stop:** mientras se escribe, el botón de enviar pasa a ser ■. Al pulsarlo, la web corta la conexión y la API para la generación de verdad. Se hace con un criterio de parada (`Generator.cancel`, comprobado en cada token) que solo se activa así, de modo que no cambia ninguna respuesta normal ni los benchmarks.
  - **Arregla además un problema que no teníamos presente:** antes, cerrar la pestaña a mitad de una respuesta dejaba al servidor generando y bloqueando al siguiente visitante. Ahora también para.
  - **La API manda el `session_id` al empezar** (evento `start`), así que una conversación parada antes de su primera respuesta conserva su memoria.
  - **Medido en Chrome headless:** Stop corta en 48 ms y la siguiente pregunta empieza a responder a los 2.9 s. Sin parar, habría esperado los ~45 s del bucle.

**Web:**
- **Esquinas de puntos** en las tarjetas de retrieval (la variante `dots` de tu documento, adaptada a CSS normal): cuatro rejillas de 3×3 puntos que se apagan hacia dentro, rojas en la del dominio de la respuesta y grises en las demás.
- **Preguntas de ejemplo:** el desplegable flota encima del interruptor, que ya no se mueve al abrirlo (medido: la misma posición).

**Pruebas:** 102 tests; flake8 y mypy limpios.

## 7. Qué debes saber

- **Los ejemplos de los tests y comentarios del enmascarado usan datos ficticios** (DEC-18).
- **Latencia en el Space gratuito:** ~15–25 s (directo) y ~22–32 s (agente) por respuesta (§6). El agente iba por defecto (D7), pero con este coste quizá prefieras otro valor por defecto en la web pública. **Resuelto en la Fase 7:** directo por defecto en la web, con el agente marcado como trabajo en curso. La web toma el valor por defecto de `/config` (`agent_default` en `src/api/app.py`), y el campo `agent` de la petición tiene el mismo valor por defecto.

- **Antes de desplegar, decide** qué LLM va al Space (propuesta en `BENCHMARK_REPORT.md` §8.3) y si te vale la estrategia de privacidad (DEC-09) o prefieres un índice ya enmascarado (opción C).
- **La web de Streamlit sigue funcionando** (`make web`), como legacy (DEC-13). Se puede borrar cuando hayas revisado la nueva.
- **Para actualizar el despliegue:** `make index` → `make bundle` → volver a subir el bundle y reiniciar el Space. El código y la web se actualizan con `make space-stage` y un `push`.
- **Lo que no he hecho, a propósito:** crear repos en Hugging Face, subir el bundle, publicar Pages o cualquier `push`. Es el "hasta el punto de deploy" que pediste.

## 8. Ficheros

| Fichero | Cambio |
|---|---|
| `src/api/app.py`, `metrics.py`, `__main__.py` | **Nuevos.** API FastAPI. |
| `src/deploy/bundle.py` | **Nuevo.** Export y restore del índice. |
| `src/cli.py` | Comandos `bundle_export` y `bundle_restore`. |
| `web/**` | **Nuevo.** Frontend React (`node_modules` y `dist` ignorados por git). |
| `deploy/README.md`, `deploy/space/**` | **Nuevos.** Guía, Dockerfile, `.dockerignore`, `entrypoint.sh` y ficha del Space. |
| `.github/workflows/pages.yml` | **Nuevo.** Workflow manual de GitHub Pages. |
| `Makefile` | `api`, `web-dev`, `web-build`, `bundle`, `space-build`, `space-run` y `space-stage`. |
| `.gitignore` | `deploy/bundle/` y `deploy/stage/`. |
| `pyproject.toml`, `uv.lock` | `fastapi`, `uvicorn`; `httpx` en `dev` (DEC-15). |
| `tests/test_api.py` | **Nuevo.** |
| `docs/decisions.md` | **Nuevo.** Decisiones tomadas por necesidad. |
| `src/rag/domain_rules.py`, `tests/test_domain_rules.py` | Datos de ejemplo ficticios (DEC-18). Sin cambios de lógica. |
| `web/README.md` | Sustituye la plantilla de Vite. |
