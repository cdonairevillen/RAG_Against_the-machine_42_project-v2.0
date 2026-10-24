# Decisiones tomadas por necesidad (sesión autónoma, 2026-10-23/24)

Encargo: cerrar las Fases 5 y 6 hasta el punto de despliegue mientras duermes. Este documento recoge las decisiones que he tomado sin consultarte, con las opciones que consideré y por qué elegí cada una, para revisarlas juntos.

**Cómo leerlo:**
- **Elegida:** la opción aplicada.
- **Reversible:** cuánto cuesta cambiarla.
- Si una decisión te parece mal, el número (`DEC-nn`) sirve para referirse a ella.

---

## DEC-01 — Dónde viven los datasets de evaluación

Tú propusiste unificar `data/` y `bench/`; decidí en qué sentido.

| Opción | Pros | Contras |
|---|---|---|
| **A. Todo en `bench/datasets/` (los de 42 en `bench/datasets/public/`)** ✅ | `bench/` = lo versionado (datasets y resultados); `data/` = lo local y regenerable (corpus, índices, salidas), ignorado entero sin excepciones | Cambian las rutas de ejemplo de los comandos de 42 (el comando no cambia: recibe la ruta por argumento) |
| B. Todo en `data/datasets/` | Se mantiene la ruta histórica de 42 | Habría que meter excepciones en `.gitignore` para cada dataset nuevo; mezcla lo versionado con lo regenerable |
| C. Dejarlo como estaba | Nada que cambiar | Dos sitios para lo mismo, que es lo que señalaste |

**Por qué A:** cada carpeta tiene un único significado y desaparece la excepción `!data/datasets/` del `.gitignore`. Comprobado: `make bench` da lo mismo (`61-datasets-moved`) y pasan los 84 tests. **Reversible:** sí, con un `git mv` y 6 rutas.

## DEC-02 — Contenido del commit "checkpoint"

| Opción | Elegida |
|---|---|
| **Todo lo que había en el árbol al acabar el benchmark** (reorganización de `src/`, agente, MCP, `make data`, resultados de los 4 modelos, changelog) | ✅ |
| Solo el código, sin los resultados del benchmark | |

**Por qué:** pediste el commit "cuando esto acabe", y los resultados son parte de lo que acababa (el proyecto versiona `bench/results/` a propósito). Comprobé antes del commit que no entraba ningún dato personal. Commit `680f21a`. **Después de ese commit no hay ninguno más:** todo lo demás queda sin commitear para revisarlo.

## DEC-03 — Redes de seguridad del agente (tus dos propuestas, acotadas)

Tú aprobaste la primera ("si la reescritura no encuentra nada, buscar la pregunta original"). La segunda la acotaste: nunca salir del filtro que elige el usuario.

| Opción | Pros | Contras |
|---|---|---|
| **A. Red 1: la pregunta original si la reescritura no encuentra nada. Red 2: si el modelo restringió dominios y no encontró nada, repetir dentro del filtro del usuario (sin filtro, en todos)** ✅ | Recupera los casos en que el 0.6B convierte la pregunta en palabras sueltas o elige mal el dominio; **nunca sale del filtro del usuario** | Una búsqueda más en esos casos (~50–100 ms) |
| B. Solo la red 1 | Más simple | El 0.6B restringe mal los dominios (en `c11` mandó la pregunta de los Panthers al CV) |
| C. Ignorar los dominios que elige el modelo | Nunca se equivoca de dominio | Desperdicia la información del modelo cuando acierta |

**Por qué A:** hay un test que lo garantiza (`test_user_filter_is_never_exceeded`): con filtro de usuario, todas las búsquedas, reintentos incluidos, se quedan dentro. Sin filtro, la red 2 busca exactamente lo mismo que el modo directo. Cada uso queda en la traza (`retries`). **Reversible:** sí.

**Resultado medido** (`BENCHMARK_REPORT.md` §8): con Qwen3-0.6B, los seguimientos pasan de 0.44 a 0.78 y XQuAD ES de 0.64 a 0.70 (igual que el directo). Con Qwen3-1.7B, XQuAD EN pasa de 0.46 a 0.76. Las redes actúan en el 7–56 % de las preguntas según el modelo y el set, y el agente queda a ±0.04 del directo en todas las preguntas sueltas.

## DEC-04 — Transporte de la respuesta en la API: SSE sobre POST

| Opción | Pros | Contras |
|---|---|---|
| **A. `POST /chat` que responde con Server-Sent Events** ✅ | *Streaming* de tokens con HTTP normal; atraviesa proxies (el de HF Spaces incluido); el roadmap pedía SSE | `EventSource` del navegador solo hace GET, así que el cliente lee el stream con `fetch` (30 líneas en `web/src/api.ts`) |
| B. WebSocket | Bidireccional | Más infraestructura para un flujo pregunta → respuesta |
| C. Sin *streaming* (respuesta entera) | Lo más simple | En CPU una respuesta tarda varios segundos: la web parecería colgada |

**Reversible:** sí, aunque el cliente y el servidor cambian a la vez.

## DEC-05 — Memoria de conversación en la API

| Opción | Elegida |
|---|---|
| **En memoria del proceso, por `session_id` (generado por el servidor), con un máximo de 500 sesiones y 30 min de inactividad** | ✅ |
| Guardada en Qdrant o en un fichero | ❌ D7: solo de sesión |
| Historial enviado por el cliente en cada petición | ❌ El cliente podría inyectar un historial falso |

**Por qué:** cumple D7 (no se guarda nada de los visitantes) y los límites impiden que una web pública llene la RAM. Al reiniciar el Space se pierden las conversaciones, que es lo esperado.

## DEC-06 — Una sola generación a la vez

La API serializa la generación con un candado. Con un solo LLM en una CPU gratuita, generar dos respuestas en paralelo las haría lentas a las dos y podría quedarse sin memoria. Si llegan varias visitas a la vez, esperan su turno; el *streaming* empieza cuando les toca. **Alternativa descartada:** una cola con un worker propio, más infraestructura para el mismo resultado con un solo modelo.

## DEC-07 — Frontend: Vite + React + TypeScript, sin librería de componentes

| Opción | Pros | Contras |
|---|---|---|
| **A. Vite 6 + React 19 + TS y CSS propio** ✅ | El roadmap pedía React con Vite; el CSS copia tal cual la paleta, tipografías, tarjetas y barras de `src/web.py` (D5); 73 KB comprimido | Los componentes (switch, pestañas) se escriben a mano |
| B. React + una librería de UI (MUI, Chakra…) | Componentes hechos | Tiene su propia estética: costaría más imitar la actual que escribirla |
| C. Mantener Streamlit | Ya existe | No sirve como web pública (sin *streaming* fino ni control del diseño); el roadmap pide React |

**El idioma de la interfaz es el inglés**, como la web actual y el público de LinkedIn. Las respuestas siguen el idioma de la pregunta, y los ejemplos incluyen preguntas en español. **Reversible:** traducir la interfaz es solo cambiar textos.

## DEC-08 — Topología: el Space sirve la API y la web; GitHub Pages es opcional

| Opción | Pros | Contras |
|---|---|---|
| **A. La API sirve también la web compilada (`web/dist`), y Pages queda como opción** ✅ | Una sola URL que funciona sola; sin CORS; si Pages no está configurado, la web existe igual | La web se sirve desde el Space (que se duerme si no hay uso) |
| B. Solo Pages + API en el Space (lo del roadmap) | La web carga al instante aunque el Space esté dormido | Dos sitios que configurar y CORS |

**Por qué A + B:** el roadmap pedía B, y queda lista (workflow `.github/workflows/pages.yml`). A es un respaldo que no cuesta nada. **El workflow de Pages es manual** (`workflow_dispatch`): nada se publica hasta que lo lances tú.

## DEC-09 — Cómo llega el índice al despliegue (privacidad)

**Problema detectado:** el enmascarado de los datos de contacto privados se hace al responder, pero el índice (Qdrant + BM25) guarda el material del CV sin enmascarar. Cualquiera que pudiera descargar el índice los leería.

| Opción | Pros | Contras |
|---|---|---|
| **A. Bundle (snapshots de Qdrant + BM25 con SHA256) en un dataset privado de HF; el Space lo descarga al arrancar con un token secreto** ✅ | El código es público y los datos no; se respeta tu decisión de indexar el material tal cual (sin manipularlo) | Un paso más al desplegar (crear el dataset y el secreto) |
| B. Meter el índice en la imagen del Space | Arranque más simple | En un Space público, la imagen y sus ficheros se pueden descargar: **fuga de datos privados** |
| C. Construir un índice "de despliegue" con el texto ya enmascarado | Nada sensible en ningún sitio | Contradice tu decisión de no manipular el material (BOM, "indexar tal cual") y obliga a mantener dos índices |
| D. Indexar en el arranque del Space | Sin bundle | Horas en CPU con `bge-m3` |

**Por qué A:** cumple a la vez la privacidad y tu criterio de reproducibilidad. Los ficheros llevan SHA256 y se comprueban al restaurar. `deploy/bundle/` está en `.gitignore`. **Pendiente de tu decisión:** si prefieres C (más paranoico), es un cambio acotado.

## DEC-10 — Qdrant en el despliegue: servidor dentro del contenedor

| Opción | Pros | Contras |
|---|---|---|
| **A. El binario oficial de Qdrant v1.19.1 (la misma versión que `docker-compose.yml`) dentro del contenedor del Space** ✅ | Mismo código y misma versión que en desarrollo; los snapshots se restauran por la API oficial | Dos procesos en un contenedor (`entrypoint.sh`) |
| B. Qdrant en modo local (embebido) | Un solo proceso | En la Fase 1 se midió que era mucho más lento y obligaría a otro camino en `QdrantChunkStore` |
| C. Qdrant Cloud (capa gratuita) | Sin gestionar Qdrant | Otra cuenta, y el índice con el CV fuera de tu control |

## DEC-11 — torch con CUDA en una imagen de CPU

| Opción | Elegida |
|---|---|
| **Usar el `uv.lock` tal cual (torch cu126, que funciona en CPU)** | ✅ |
| Un lock aparte con torch CPU para el despliegue | |

**Por qué:** un solo lock, la misma versión de todo que en el benchmark (los resultados son comparables) y nada que mantener por duplicado. **Coste:** la imagen pesa ~2 GB más, cosa que el Space aguanta. Se puede optimizar después con un perfil de dependencias para el despliegue.

## DEC-12 — Modelos dentro de la imagen

`bge-m3`, el reranker y Qwen3-0.6B se descargan **al construir** la imagen, no al arrancar. Así un arranque en frío no depende de Hugging Face Hub y es más rápido (el Space gratuito se duerme y se despierta a menudo). **Coste:** la imagen pesa más.

## DEC-13 — La web de Streamlit se queda como legacy

`src/web.py` y `make web` siguen funcionando: no los borro sin tu permiso. La web nueva es `make api` + `make web-dev` (o `make space-run`). Propuesta: borrar Streamlit cuando hayas revisado la nueva.

## DEC-14 — Sin licencia en la ficha del Space

El repo no tiene `LICENSE`. Había puesto `license: mit` en la ficha del Space y **lo quité**: elegir licencia es decisión tuya. Ojo: los datos de XQuAD son CC-BY-SA 4.0, y eso obliga a citar (ya se cita en la web y en la ficha) y a publicar los derivados con la misma licencia.

## DEC-15 — FastAPI y uvicorn como dependencias normales

| Opción | Elegida |
|---|---|
| **En `dependencies` (como `streamlit` o `mcp`)** | ✅ |
| En un grupo opcional (`[project.optional-dependencies] api`) | |

**Por qué:** el proyecto ya instala todo con un único `uv sync` (la web de Streamlit y el servidor MCP también son dependencias normales), y la imagen del Space usa ese mismo lock. Pesan poco (~2 MB). `httpx` entra solo en el grupo `dev`, porque solo lo usan los tests (`TestClient`). Las instalé **después** de que acabara el benchmark del agente, para no cambiar el entorno mientras se medía. **Reversible:** sí.

## DEC-16 — Contexto de `docker build` con lista blanca

`docker build` se lanza desde la raíz del repo, que contiene `data/` (corpus, índice y **el CV privado**), `.venv` y `node_modules`. Aunque el Dockerfile solo copia lo que necesita, Docker enviaría todo eso como contexto de construcción.

| Opción | Elegida |
|---|---|
| **`deploy/space/Dockerfile.dockerignore` con lista blanca (`*` y solo lo que se copia)** | ✅ |
| Un `.dockerignore` en la raíz | ❌ Afectaría también a `docker-compose.yml` y a cualquier otra imagen futura |
| Construir solo desde `deploy/stage/` (`make space-stage`) | ❌ Obligaría a preparar el stage incluso para una prueba local |

**Por qué:** BuildKit lee `<Dockerfile>.dockerignore` junto al Dockerfile, así que solo afecta a esta imagen. Con una lista blanca, un fichero nuevo nunca entra por accidente. `make space-stage` sigue copiando solo lo necesario para subir al Space.

## DEC-17 — Hilos de CPU según la cuota del contenedor

**Problema medido:** con el contenedor limitado a 2 vCPU (como el Space gratuito), torch veía los 24 núcleos del host y abría 12 hilos. Resultado: 48–88 s por respuesta directa y 84–123 s con el agente. Con 2 hilos, las mismas preguntas tardan **14–24 s y 22–32 s**, con respuestas idénticas.

| Opción | Pros | Contras |
|---|---|---|
| **A. `entrypoint.sh` calcula los hilos con la cuota del cgroup (`/sys/fs/cgroup/cpu.max`), o con `nproc` si no hay cuota; un `OMP_NUM_THREADS` explícito manda** ✅ | Se adapta si cambias el hardware del Space; no toca el código del RAG | Depende de cgroup v2 (si no está, usa `nproc`) |
| B. `ENV OMP_NUM_THREADS=2` fijo en el Dockerfile | Una línea | Infrautiliza un hardware mayor |
| C. `torch.set_num_threads()` en `src/` | Funciona también fuera de Docker | Cambia el código del RAG por un problema del despliegue |

**Además:** la API arranca con `HF_HUB_OFFLINE=1`. Los modelos están en la imagen (DEC-12), así que un arranque en frío no hace ninguna llamada al Hub. La descarga del bundle va antes y no se ve afectada.

**Ojo:** no sé si el Space gratuito limita la CPU con cgroup o con una VM. La opción A cubre los dos casos, pero solo lo he probado con `docker run --cpus=2` en local.

## DEC-18 — Datos de ejemplo ficticios

Los ejemplos de los tests y de los comentarios del enmascarado (`src/rag/domain_rules.py`, `tests/test_domain_rules.py`, `tests/test_api.py`) usan datos ficticios. El patrón de enmascarado es genérico, así que el comportamiento no cambia. Comprobado: ni el código ni `deploy/stage/` (lo que se sube al Space) contienen datos personales.
