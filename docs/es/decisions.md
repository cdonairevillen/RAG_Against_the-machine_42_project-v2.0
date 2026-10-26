# Decisiones tomadas por necesidad (sesiones autónomas)

Dos sesiones: la del 2026-10-23/24 (DEC-01 a DEC-18) y la noche del 2026-10-24/25 (DEC-20 a DEC-26, al final). DEC-19 (Oracle) se decidió contigo.

Primer encargo: cerrar las Fases 5 y 6 hasta el punto de despliegue mientras duermes. Este documento recoge las decisiones que he tomado sin consultarte, con las opciones que consideré y por qué elegí cada una, para revisarlas juntos.

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

El repo no tenía `LICENSE`. Había puesto `license: mit` en la ficha del Space y **lo quité**: elegir licencia es decisión tuya. Ojo: los datos de XQuAD son CC-BY-SA 4.0, y eso obliga a citar (ya se cita en la web y en la ficha) y a publicar los derivados con la misma licencia.

**Resuelto (2026-10-24, Fase 7):** pediste crear la licencia.
- **MIT** para el código y la documentación propios (`LICENSE`). La alternativa, Apache-2.0, solo añade una cláusula de patentes que no aporta nada a un portfolio.
- **Lo de terceros queda fuera, y se dice en el README:** `bench/datasets/xquad/` (CC-BY-SA 4.0), los datasets de 42 (`public/`, y su subconjunto traducido en `en/` y `es/`) y `llm_sdk/`.
- **La ficha del Space** vuelve a llevar `license: mit`, y `make space-stage` copia el `LICENSE`.

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

## DEC-19 — Plataforma de despliegue: Oracle Cloud Always Free (2026-10-24, decisión tuya)

**Problema:** desde julio de 2026, Hugging Face exige un plan de pago (PRO) para crear Spaces de Docker o Gradio; solo los estáticos son gratis. El plan de la Fase 6 (Space de Docker en CPU gratuito) deja de ser gratuito. Además, Google Cloud queda fuera: ya tiene un servicio tuyo y quieres entornos separados.

| Opción | Pros | Contras |
|---|---|---|
| **A. VM ARM de Oracle Cloud Always Free (2 OCPU, 12 GB, 200 GB de disco) con Docker + Caddy** ✅ | Gratis y siempre encendida; la misma imagen del Space; separada de Google | Pide tarjeta para verificar; a veces no hay capacidad ARM; la velocidad en ARM está sin medir |
| B. Tu PC + Cloudflare Tunnel | Gratis y con GPU | Solo funciona con tu PC encendido |
| C. Google Cloud Run | Ya tienes cuenta | La cuota gratuita da pocas horas con 8–16 GB de RAM; mezcla con tu otro servicio |
| D. Hugging Face PRO | Lo preparado funciona sin cambios | 9 $/mes |

**Medido para elegir A:** la imagen con `--cpus=2 --memory=12g` ocupa 4.2 GB tras cargar y 5.0 GB de pico respondiendo. El `uv.lock` tiene torch para `aarch64`, así que la imagen se construye en la máquina ARM.

**Cambios respecto a DEC-08 y DEC-09:**
- **DEC-08:** el contenedor sigue sirviendo la API y la web, y Pages sigue siendo opcional. Delante va Caddy, que pone el HTTPS (necesario para que Pages pueda llamar a la API), con un subdominio gratuito de DuckDNS.
- **DEC-09:** el bundle se copia con `scp` a tu máquina y se monta en el contenedor. El dataset privado de Hugging Face ya no hace falta, aunque `entrypoint.sh` lo sigue aceptando.

**Ficheros:** `deploy/oracle/` (`compose.yml`, `Caddyfile`, `.env.example`) y la guía `deploy/README.md`. `make space-stage` incluye `deploy/oracle/`.

**Reversible:** sí. `deploy/space/` sigue intacto para un Space de pago.

---

# Sesión autónoma 2026-10-24/25 (noche)

Encargo: arreglar los fallos que viste en la web con Phi-4-mini (respuestas que copian las fuentes, "Háblame sobre este rag" mandado a vLLM, fuentes de "about" mezcladas de idioma), con vía libre y una sola regla: **ningún caso puede empeorar respecto a lo que había**. Sin commits. Todo está medido contra una línea base tomada al empezar, con el código del commit `02ff464` (`80-*`, `gen-bench` de los cuatro modelos). El detalle está en `changelog/FASE_7.md` §7b.3–7b.5.

**Resumen:**

| DEC | Qué | Estado |
|---|---|---|
| 20 | Medir antes de tocar: suite `about` y métricas `echo` y `bad_citation` en `gen-bench` | ✅ Aplicada |
| 21 | Prompt: se mantiene `v3`; los prompts nuevos (`v4`, `v6`) se descartan y `v5` no se prueba | ✅ Aplicada (no cambia nada) |
| 22 | Eco: limpieza de la respuesta (`strip_echo`) en lugar de cambiar el prompt | ✅ Aplicada |
| 23 | Filtro de idioma en "about" | ⏸️ Implementado y **desactivado**: decides tú |
| 24 | Preguntas que nombran el proyecto (`route_names`) y el nombre del autor para el CV | ✅ Aplicada |
| 25 | Índice de "about": se restaura el de la línea base y no se reindexa con la documentación nueva | ✅ Aplicada, provisional |
| 26 | Lo que no he tocado | — |

## DEC-20 — Medir antes de tocar

`gen-bench` no tenía suite para "about" ni forma de contar las respuestas que copian el prompt.

| Opción | Pros | Contras |
|---|---|---|
| **A. Añadir la suite `about` (18 preguntas EN + 18 ES) y dos métricas: `echo` (la respuesta copia una cabecera `--- file:`, una etiqueta `SOURCES:`/`QUESTION:`/`ANSWER:` o la instrucción final) y `bad_citation` (citas como `[texto](1)`)** ✅ | Convierte tus dos ejemplos en números comparables entre modelos y versiones | Solo cambia la herramienta de medida |
| B. Probar a mano con tus dos preguntas | Rápido | No dice si un arreglo empeora otra cosa |

**Línea base (`80-*`):** el eco aparece en el 16 % de las respuestas de Phi en vLLM docs, en el 17 % de las de "about" en inglés, en el 10 % de las del 0.6B en el CV (EN) y en el 3 % de las de XQuAD (EN). Ninguna cita mal formada en los benchmarks: lo de `[langchain](1)` salió con una pregunta abierta que no está en ellos.

**Reversible:** sí, aunque no hay motivo: no toca el sistema.

## DEC-21 — Prompt: se mantiene `v3`

Tu primer caso (Phi copiando las fuentes) apuntaba al prompt: el mensaje del usuario acababa con una instrucción ("Answer in English, citing the sources by number."), y el 0.6B a veces la repetía tal cual. Probé tres variantes, cada una con la matriz completa (0.6B en vllm, xquad, cv y about; 1.7B, Phi-4-mini y 4B en vllm, cv y about):

| Opción | Qué cambia | Resultado (frente a `80`) |
|---|---|---|
| **A. `v3`, el actual** ✅ | Nada | — |
| B. `v4` | El idioma y una regla de "no copies las fuentes ni estas reglas" pasan al mensaje de sistema; el usuario acaba con la pregunta | **112 caídas.** Los modelos dejan de citar (0.6B en vLLM docs: "cites" 0.90 → 0.16) y bajan el idioma correcto y "contiene la respuesta". El eco de Phi en about/en sí baja de 0.17 a 0 |
| C. `v6` | `v3` intacto más solo la regla anti-copia | **75 caídas**, y el eco ni siquiera baja |
| D. `v5` | `v4` más "ignora las fuentes que no responden" (contra el resumen de todas las fuentes) | **No probado:** contiene el cambio de `v4` que rompe las citas |

**Por qué A:** con estos modelos pequeños, cualquier cambio en el prompt mueve las respuestas en todas direcciones, y la regla de no empeorar descarta todos los probados. La instrucción final es justo lo que hace que citen y respondan en el idioma correcto. El eco se ataca de otra forma (DEC-22). El código de los estilos se retiró para no dejar opciones muertas; los resultados quedan en `bench/results/gen/81-*` y `82-*`.

**Reversible:** las variantes se pueden reconstruir desde el changelog.

## DEC-22 — Eco: limpiar la respuesta

| Opción | Pros | Contras |
|---|---|---|
| **A. `strip_echo` en `clean_output` (para todas las respuestas): se queda con lo que sigue al último `ANSWER:`; quita la instrucción repetida; si la respuesta empieza copiando una fuente, conserva su texto sin la cabecera y lo cita como `[n]`; las demás cabeceras pasan a `[n] (ruta)`** ✅ | Solo cambia las respuestas con eco. Medido sobre las respuestas guardadas de las tres matrices (4.662): cambian 25, 35 y 78, el eco queda a 0 y **ninguna pierde la respuesta de referencia** (el F1 sube) | Si Phi copia las 5 fuentes y se le acaba el límite antes de escribir `ANSWER:`, queda el texto de las fuentes sin cabeceras: mejor que antes, pero no es una respuesta |
| B. Cambiar el prompt | Atacaría la causa | Descartado por los datos (DEC-21) |
| C. Detectar el eco al empezar a generar, parar y reintentar | Evitaría gastar tokens copiando | Duplica el tiempo justo en los casos malos, y el reintento puede volver a copiar. Sin implementar |

**Por qué A:** es lo único medido sin pérdidas. Tu ejemplo de "What is RAG against the Machine?" con Phi queda en *"RAG against the Machine is a multi-domain Retrieval-Augmented Generation system with an agent, an MCP server, and a web interface. …"*.

**Reversible:** sí, una línea en `clean_output`.

## DEC-23 — Filtro de idioma en "about": implementado y desactivado

Para una pregunta en inglés, 2 de las 5 fuentes salían en español: el mismo contenido en `docs/` y en `docs/es/`.

| Opción | Pros | Contras |
|---|---|---|
| A. Filtrar en los dos idiomas: si un fichero tiene traducción, la pregunta solo recibe la copia en su idioma | Contexto en un solo idioma | Pierde respuestas en español: a veces la sección inglesa recuperada contiene la respuesta y la sección española recuperada es otra ("contiene la respuesta" ES @5: 0.94 → 0.83) |
| B. Filtrar solo las preguntas en inglés | Recuperación de "about" en inglés mejor (R@3 0.44 → 0.50, R@5 0.50 → 0.56; fuentes en el otro idioma 16 → 3 de 90); español idéntico. Generación con el 0.6B: EN contiene 0.44 → **0.61** | Con el 1.7B, Phi y el 4B bajan las citas correctas en EN (por ejemplo, Phi 0.33 → 0.17) y Phi y el 4B dicen "no encontrado" algo más (0.17 → 0.28, 0.22 → 0.28) |
| **C. Dejar B implementado y desactivado** ✅ | Cumple la regla de no empeorar | Tu queja (fuentes mezcladas) sigue ahí hasta que lo actives |

**Por qué C:** B mejora claramente el modelo base, que es el que se despliega (P12), pero empeora algunas métricas de los opcionales, y la regla de esta noche no lo permite. Para activarlo, descomenta `translations` y `translation_languages` en `[sources.about]` de `rag.toml`; no hace falta reindexar. **Mi recomendación:** activarlo si el servidor va a usar el 0.6B.

**Reversible:** sí, dos líneas de `rag.toml`.

## DEC-24 — Preguntas que nombran el proyecto o al autor

"Háblame sobre este rag" iba a vLLM (1.04 frente a −1.85 de "about"). Aunque hubiera ido a "about", su filtro (−1.0) la habría rechazado.

| Opción | Pros | Contras |
|---|---|---|
| **A. `route_names`: expresiones que nombran el dominio sin ambigüedad ("rag against the machine", "este/esta/tu rag, proyecto, sistema, chatbot, asistente, web, aplicación", "this/your rag, project, system, chatbot, assistant, website, app"). El dominio gana y su filtro no se aplica, porque la pregunta va explícitamente sobre él. "The project" y "el proyecto" siguen como pista débil (deben pasar el umbral)** ✅ | Las 8 preguntas de prueba que nombran el proyecto llegan a "about" y responden; **antes fallaban las 8** (4 a "no encontrado", 4 a vLLM, XQuAD o CV). Comprobado: ninguna pregunta de los demás benchmarks coincide | Una pregunta absurda que nombre el proyecto ("¿qué tiempo hace en este rag?") llega al LLM, que dirá que no lo encuentra |
| B. Bajar el umbral de "about" | Simple | Deja pasar más preguntas ajenas (medido en §7a.7) |
| C. Añadir "este rag" a las pistas débiles | Mínimo | No basta: −1.85 no pasa el umbral |

**Además, el nombre del autor para el CV** (pista débil `chrystian|donaire`). Al reindexar "about", "What is Chrystian's contact e-mail?" pasó a "about" (que la respondía con código) en vez de al CV. Con la pista, si la pregunta nombra al autor y el CV pasa su umbral, gana el CV. Solo coinciden preguntas del CV (27 de 30 por idioma).

**Resultado:** route-bench final (`85-night-final`) con el mismo enrutado que el commit en todos los conjuntos (42 0.99, XQuAD 0.981 / 0.975, CV 0.967 / 0.967, about 0.778 / 0.889). Única diferencia: XQuAD/ES R@1 0.9059 → 0.9050, una pregunta en una posición, por la búsqueda vectorial aproximada de Qdrant tras restaurar el bundle (DEC-25), que es lo mismo que cargará el servidor.

**Reversible:** sí, `rag.toml`.

## DEC-25 — Índice de "about": el de la línea base

Al reindexar "about" esta noche entraron ~35 fragmentos nuevos: la documentación escrita el día 24 (tablas de §7a.8 con preguntas del CV, `DETECTOR_BUCLES.md`, `loops.py`…). Con ese índice, **sin ningún cambio de código**, la generación de "about" baja frente a la línea base (por ejemplo, el 1.7B en ES contiene 0.67 → 0.56) y una pregunta de "about" en ES cambia de dominio.

| Opción | Pros | Contras |
|---|---|---|
| **A. Restaurar el índice de la línea base (desde `deploy/bundle`, SHA256 comprobado) y no reindexar "about" esta noche** ✅ | Mañana tienes exactamente lo de ayer más las mejoras de código | La documentación de hoy no entra en "about" hasta que se reindexe |
| B. Quedarse con el índice nuevo | "About" sabe lo último | Incumple la regla |
| C. Marcar con `about:skip` las partes nuevas que compiten | Arreglaría la causa | Es decidir qué documentación ve "about", y eso te toca a ti |

**Por qué A:** la regla de esta noche. Pero el problema de fondo queda abierto: **"about" empeora a medida que crece la documentación**, porque los changelogs repiten datos y citan preguntas. Habrá que decidir qué entra (opción C) antes del despliegue.

**Ya preparado, sin efecto hasta reindexar:** `deploy/space/README.md` sale de "about" (`exclude_paths`). Es la ficha antigua del Space y dice cosas falsas ("Agent (default)").

**Reversible:** sí, `make index SOURCE=about`.

## DEC-26 — Lo que no he tocado

- **Citas mal formadas de Phi** (`[langchain](1)`) y **el cierre contradictorio** ("no se encontró información…" después de responder). Salieron con tu pregunta abierta, no en los benchmarks (`bad_citation` = 0). El arreglo natural era la regla de `v5`, que hereda el problema de `v4`. Queda para medirlo con más preguntas abiertas.
- **"Paso a paso de vLLM"**, que va a "about" (3.13 frente a 2.09). Es una pregunta corta y ambigua; con una formulación completa va a vLLM.
- **Reintentar al detectar eco** (DEC-22 C).
- **Commits:** ninguno, como pediste.

## Cómo queda todo (verificación final, `85-*`)

| Comprobación | Resultado |
|---|---|
| `make bench` de 42 | **Idéntico:** docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88 |
| Route-bench | Igual que el commit (ver DEC-24) |
| `gen-bench` de vllm, xquad y cv | Generación idéntica a `80` (mismo prompt y mismos índices) más la limpieza del eco: el eco pasa a 0 y no se pierde ninguna respuesta |
| `gen-bench` de about, los cuatro modelos | Idéntico a `80`, con el eco a 0. Única diferencia: Phi en about/en, idioma 1.00 → 0.93, porque una respuesta limpia queda en un fragmento de código cuyo idioma no se puede detectar (el contenido es el mismo) |
| Las 8 preguntas que nombran el proyecto | 8 de 8 en "about", y responden (antes, 0) |
| Tests | 122; flake8 y mypy limpios |

# Sesión autónoma 2026-10-25/26

Encargo: Phi-4-mini seguía copiando fuentes con "Hablame sobre este rag" y "What is RAG against the Machine?" (la segunda, además, cortada), y el 0.6B no daba ninguna respuesta a la primera. Objetivo: respuestas correctas de forma y de fondo (sin verborrea y sin frases cortadas). La regla es la misma: **ningún caso puede empeorar**. Sin commits durante la sesión; al final, un checkpoint porque lo pediste. Detalle en `changelog/FASE_7.md` §7b.7.

**Resumen:**

| DEC | Qué | Estado |
|---|---|---|
| 27 | Medir la forma como en la web: métricas `cut` y `tokens` y banco de 34 preguntas abiertas | ✅ Aplicada |
| 28 | Detector de bucles: ventana 8 → 12 | ✅ Aplicada |
| 29 | Reintento cuando Phi copia las fuentes | ✅ Aplicada (variante prudente) |
| 30 | Bloques repetidos en el detector de bucles | ✅ Aplicada |
| 31 | Lo que no he tocado | — |

Antes de todo, un arreglo sin opciones: la limpieza de la instrucción repetida (DEC-22) se comía la respuesta entera del 0.6B en "Hablame sobre este rag" (el patrón cruzaba los dos puntos). Ahora no los cruza y, si deja la respuesta vacía, se devuelve la original. 0 cambios en las 4.662 respuestas guardadas.

## DEC-27 — Medir la forma como en la web

Los benchmarks no veían tus casos. `gen-bench` usa preguntas de un solo dominio y no contaba las respuestas cortadas, y la web pasa por otro camino (todos los dominios, 1.024 tokens, recorte con " …").

| Opción | Pros | Contras |
|---|---|---|
| **A. Métricas `cut`, `tokens` y `tokens_max` en `gen-bench` + un banco de 34 preguntas abiertas por `RagService.chat` (el camino de la web) para los cuatro modelos** ✅ | Tus casos y los ejemplos de la web pasan a ser números comparables; detecta cortadas, eco, bucles, frases repetidas, vacías e idioma | El banco abierto está en `data/output/night2/` (ignorado por git): es una herramienta de esta sesión, no del proyecto |
| B. Probar a mano en la web | Lo más fiel | No escala ni dice qué empeora |

**Línea base `90-*`:** matriz de `gen-bench` a 1.024 tokens + banco abierto. En el abierto, Phi tiene 2 respuestas cortadas, 1 con eco, 4 con frases repetidas y un máximo de 1.016 tokens. El 0.6B, el 1.7B y el 4B no tienen ninguna cortada ni bucles.

**Reversible:** sí; solo mide.

## DEC-28 — Detector de bucles: ventana 8 → 12

Un bucle de Phi de 4 frases que se repiten ("The Spanish BENCHMARK_REPORT.md file…") llegaba a los 1.024 tokens: con 8 unidades nunca hay 5 copias en la ventana.

| Opción | Falsos positivos (14.261 respuestas + 299 documentos) | Bucles detectados |
|---|---|---|
| Ventana 8, 5 repeticiones (antes) | 0 | 3 de 7 |
| **Ventana 12, 5 repeticiones** ✅ | 0 | 4 de 7, incluido el nuevo |
| Ventana 10, 5 repeticiones | 0 | 4 de 7 |
| Ventana 10, 4 repeticiones | Sí | — |

**Por qué 12:** detecta lo mismo que 10, admite ciclos de hasta 7 frases y no tiene falsos positivos.

**Reversible:** sí, una constante.

## DEC-29 — Reintento cuando Phi copia las fuentes

Phi empieza algunas respuestas copiando el prompt (`[1] --- file: …`) y sigue con todas las fuentes. O se para sin responder, o se queda sin tokens antes de responder. `strip_echo` (DEC-22) no puede sacar una respuesta de ahí.

| Opción | Resultado |
|---|---|
| A. Reintentar en cuanto la respuesta empieza con una cabecera (`91-*`) | Phi: arregla sus casos. 0.6B: mejora la forma de ~11 respuestas de XQuAD y del CV (de un párrafo copiado a una frase), pero **pierde una** (Toyota/ES: "2017" → "febrero de 2014"). Además, en XQuAD/EN "contiene" baja de 0.637 a 0.633 por otra, en la que la nueva respuesta dice "30%" y la referencia es "up to 30%". Incumple la regla |
| **B. Reintentar solo si, además, llega a copiar una segunda cabecera o etiqueta (`92-*`)** ✅ | 0.6B, 1.7B y 4B: **idénticos** a `90` en toda la matriz. Phi: 3 respuestas de `gen-bench` y 5 abiertas cambian, todas a mejor (`FASE_7.md` §7b.7) |
| C. No reintentar, solo limpiar | Tus casos siguen fallando |
| D. Prohibir las cabeceras desde el primer intento (`bad_words_ids` siempre) | No probado: cambia la generación de todas las respuestas de todos los modelos, y la regla pide no tocar lo que funciona |

**Cómo es el reintento:**
- Se genera otra vez sin dejar empezar por `[` y sin dejar escribir `--- file`, `SOURCES:` ni `QUESTION:`.
- Probado en CPU antes: solo prohibir las cabeceras da "[1] [2] [3]…", así que hace falta también lo del primer `[`.
- En la web se retiene el principio de la respuesta hasta saber que no es un eco, así que la copia no llega a la pantalla.

**Por qué B:** es la única que no empeora nada. A cambio, el eco de una sola cabecera del 0.6B se sigue limpiando como antes, con `strip_echo` (a veces queda un párrafo copiado de la fuente).

**Reversible:** sí; quitando el criterio `EchoStart` de `stopping_criteria`, todo vuelve a como estaba.

## DEC-30 — Bloques repetidos en el detector de bucles

En el banco abierto aparecieron dos formas de repetir que la ventana no ve:
- **Un ciclo de 14 frases** (Phi, "How does the hybrid search work?": 1.016 tokens, cortada).
- **La respuesta escrita dos veces:** "…dispositivo). La respuesta en español, citando las fuentes, es: <la misma respuesta>" (Phi, "¿Qué es RAG against the Machine?", 773 tokens).

| Opción | Pros | Contras |
|---|---|---|
| **A. Regla de bloque: las últimas N frases repiten, una a una, las de un poco antes (ciclo de hasta 40 frases). Si la frase justo anterior contiene a su pareja (el "La respuesta… es: <primera frase>"), el corte empieza ahí** ✅ con N = 6 | Detecta los dos casos y se corta donde empieza la copia. En 15.793 respuestas y 299 documentos solo cambian las de Phi que repetían | Una respuesta que de verdad repita 6 frases seguidas se cortaría (no hay ninguna en todo lo guardado) |
| A con N = 4 | Detecta lo mismo | Falsos positivos en 4 documentos de vLLM (pasos de instalación repetidos) |
| A con N = 5 | Sin falsos positivos | Menos margen que 6 |
| B. Ventana mayor (40) | Una sola regla | Más coste por token y más riesgo de comparar frases lejanas parecidas |
| C. Limpiar la frase "La respuesta en español… es:" con otro patrón | Arreglaría el segundo caso | Otro parche de texto como `strip_echo`, y no arregla el primero |

**Efecto lateral:** la respuesta de Phi escrita dos veces pierde sus citas, que solo estaban al final de la copia (about/ES de Phi: "cites" 0.93 → 0.86). Lo cuento como mejora (de 773 a 375 tokens sin repetir), pero es una métrica que baja.

**Reversible:** sí; `BLOCK` o la llamada a `repeated_block` en `find_loop`.

## DEC-31 — Lo que no he tocado

- **"Hablame sobre este rag" sigue sin una buena respuesta.**
  - El 0.6B responde algo pobre en inglés, y Phi dice que no lo encuentra (ya no vuelca 873 tokens).
  - La causa es la recuperación: con "este rag", las fuentes que llegan son secciones sueltas.
  - Probé a buscar con el nombre del proyecto en su lugar. Mejora las preguntas generales ("Háblame de…", "Tell me about…", "¿Quién lo ha hecho?") y empeora las concretas (reranker, agente, web).
  - No lo aplico. Opciones para hablarlo: hacerlo solo con las preguntas generales, o buscar con las dos formulaciones y fusionarlas.
- **Phi en "about" sigue siendo prolijo y repite datos falsos** ("Hugging Face Space", "Agent (default)").
  - Vienen de `deploy/space/README.md`, que sigue en el índice restaurado (DEC-25).
  - Se arregla reindexando "about", que es tu decisión pendiente.
- **"No encontrado en los proporcionados fuentes."** (una forma rara de Phi) no se reconoce como "no encontrado". Es menor y no lo he tocado.
- **El banco abierto del 4B en `92`** no se pudo pasar: el modelo no carga en ese proceso con 12 GB. Su `gen-bench` es idéntico a `90`.

## ¿Volver a una versión más estable? (para discutir, 2026-10-26)

Me pediste los pros y contras de volver atrás, distinguiendo las mejoras de verdad de las "trampas" que han hecho falta para los resultados. Lo que sigue es mi lectura, con los números de `90` (línea base de hoy) y `92` (estado final).

### Qué hay en cada punto

| Punto | Qué tiene | Problemas conocidos |
|---|---|---|
| `3378494` (Fase 6) | API, web React y despliegue preparados. Sin "about" y sin detector de bucles | Phi entra en bucles de hasta 1.500 tokens; no se puede preguntar por el proyecto |
| `8ff05d0` (Fase 7, "about" terminado) | "About" en la web, despliegue en Oracle, límite por modelo (512; 640 para Phi) | Los bucles de Phi se cortan por el límite, a media frase; el eco de Phi llega a la web; "Háblame sobre este rag" va a vLLM |
| `02ff464` (último commit antes de estas sesiones) | Detector de bucles y límite de 1.024 tokens | El eco de Phi y los bucles largos siguen; "Háblame sobre este rag" no llega a "about" |
| Checkpoint de hoy (DEC-20 a DEC-31) | Lo de la tabla siguiente | Lo de DEC-31 |

### Lo añadido desde `02ff464`: ¿mejora o parche?

| Cambio | Tipo | Por qué |
|---|---|---|
| Métricas de forma y banco de preguntas abiertas (DEC-20, DEC-27) | **Mejora** | Solo miden, no cambian ninguna respuesta |
| Detector de bucles: ventana 12 y bloques repetidos (DEC-28, DEC-30) | **Mejora** | Son reglas generales (texto que se repite), medidas sin falsos positivos sobre 15.793 respuestas y 299 documentos. No dependen de ninguna pregunta |
| Reintento cuando Phi copia dos fuentes (DEC-29) | **Parche razonable** | Es general (no depende de la pregunta), pero trata un síntoma de Phi, no la causa: el modelo copia el prompt. Con los Qwen no se activa en nada de lo medido |
| `strip_echo` (DEC-22) | **Parche** | Expresiones regulares sobre el texto ya generado. Cada modelo nuevo puede copiar el prompt a su manera y pedir patrones nuevos. Hoy mismo, uno de ellos se comía la respuesta del 0.6B |
| `route_names`: frases fijas ("este rag", "this project"…) que mandan a "about" sin pasar su filtro (DEC-24) | **Trampa ligera** | Es una lista escrita a mano: arregla los 8 casos medidos, pero formulaciones nuevas ("vuestro sistema", "la app") se quedan fuera |
| Pista del nombre del autor para el CV (DEC-24) | **Trampa ligera** | Regla léxica para un caso concreto |
| Índice de "about" restaurado de la línea base (DEC-25) | **Trampa** | No arregla nada: evita que la documentación nueva empeore "about" y deja dentro una ficha desfasada que Phi repite |
| Filtro de idioma de "about" (DEC-23) | Desactivado | No cuenta |

### Pros de volver atrás

- **Menos código especial.** Sin `strip_echo`, `route_names`, la pista del CV ni el reintento, el generador vuelve a ser "prompt → modelo → limpieza mínima", más fácil de explicar y de mantener.
- **Menos riesgo con preguntas reales.** Cada parche está medido con nuestras preguntas; con las de los usuarios pueden aparecer casos raros (por ejemplo, una pregunta absurda que nombre el proyecto llega al LLM sin filtro).
- **El modelo que se desplegaría casi no lo necesita.** El 0.6B (P12) responde igual de bien de forma en `90` y `92`: 0 cortadas y 0 bucles. Los parches son, sobre todo, para Phi.

### Contras de volver atrás

- **Se pierden mejoras que no son trampas:** las métricas y el detector de bucles mejorado. Los bucles largos de Phi vuelven a llegar a ~1.000 tokens y a cortarse a media frase.
- **Vuelven los fallos que viste en la web:**
  - Phi responde a "What is RAG against the Machine?" con 49 tokens cortados, y a "Hablame sobre este rag" con 873 tokens de fuentes copiadas.
  - "Háblame sobre este rag" vuelve a ir a vLLM con todos los modelos.
- **Lo que de verdad falla en "about" no se arregla volviendo atrás.** El problema de fondo es el índice: documentación que repite datos y una ficha del Space desfasada. Está igual en `8ff05d0` y en `02ff464`.

### Mi recomendación

No volver atrás entero, sino **quedarse con las mejoras y decidir los parches uno a uno:**
1. **Quedarse:** métricas, banco abierto y detector de bucles (ventana 12 y bloques).
2. **Solo si Phi sigue en la web:** el reintento (DEC-29) y `strip_echo` (DEC-22). Si la web ofrece solo los Qwen, se pueden quitar sin perder nada medido: el reintento no se activa con ellos, y `strip_echo` solo toca respuestas con eco (sobre todo de Phi; en el 0.6B, unas pocas de XQuAD y del CV).
3. **Decides tú:** `route_names` (útil pero frágil) y la pista del CV.
4. **Arreglar de verdad:** reindexar "about" sin `deploy/space/README.md` y sin lo que repite datos (DEC-25 C). Es lo que más mejora el fondo de las respuestas de "about", y no es un parche.

Si prefieres la versión más simple, el punto razonable es **`02ff464` + métricas + detector de bucles** (sin `strip_echo`, sin reintento, sin `route_names`), **quitando Phi de los modelos de la web**. Phi es el único modelo que necesita los parches para dar respuestas limpias.

## Cómo queda todo (sesión 2026-10-25/26, `92-*`)

| Comprobación | Resultado |
|---|---|
| `gen-bench`, 0.6B, 1.7B y 4B (todas las suites) | **Idénticos** a `90`, respuesta a respuesta |
| `gen-bench`, Phi-4-mini | 3 respuestas cambian, las tres a mejor. Baja una métrica de about/ES ("cites" 0.93 → 0.86) por la respuesta que se escribía dos veces (DEC-30) |
| Preguntas abiertas | 0.6B y 1.7B idénticos. Phi: cortadas 2 → 0, eco 1 → 0, máximo 1.016 → 606 tokens. 4B sin medir en `92` |
| `make bench` de 42 (`93-session-final`) | **Idéntico:** docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88 |
| Tests | 129; flake8 y mypy limpios |
