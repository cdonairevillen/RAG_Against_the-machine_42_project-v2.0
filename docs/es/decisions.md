# Decisiones tomadas por necesidad (sesiones autónomas)

Cuatro sesiones: la del 2026-10-23/24 (DEC-01 a DEC-18), la noche del 2026-10-24/25 (DEC-20 a DEC-26), la del 2026-10-25/26 (DEC-27 a DEC-31) la del 2026-10-26/27 (DEC-32 a DEC-38) y la mañana del 2026-10-27 (DEC-39, al final). DEC-19 (Oracle) se decidió contigo.

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

Encargo: arreglar los fallos que viste en la web con Phi-4-mini (respuestas que copian las fuentes, A-02 mandado a vLLM, fuentes de "about" mezcladas de idioma), con vía libre y una sola regla: **ningún caso puede empeorar respecto a lo que había**. Sin commits. Todo está medido contra una línea base tomada al empezar, con el código del commit `02ff464` (`80-*`, `gen-bench` de los cuatro modelos). El detalle está en `changelog/FASE_7.md` §7b.3–7b.5.

**Resumen:**

| DEC | Qué | Estado |
|---|---|---|
| 20 | Medir antes de tocar: suite `about` y métricas `echo` y `bad_citation` en `gen-bench` | ✅ Aplicada |
| 21 | Prompt: se mantiene `v3`; los prompts nuevos (`v4`, `v6`) se descartan y `v5` no se prueba | ✅ Aplicada (no cambia nada) |
| 22 | Eco: limpieza de la respuesta (`strip_echo`) en lugar de cambiar el prompt | ✅ Aplicada |
| 23 | Filtro de idioma en "about" | ⏸️ Implementado y **desactivado**: decides tú (activado en DEC-34) |
| 24 | Preguntas que nombran el proyecto (`route_names`) y el nombre del autor para el CV | ✅ Aplicada (retirada en DEC-33) |
| 25 | Índice de "about": se restaura el de la línea base y no se reindexa con la documentación nueva | ✅ Aplicada, provisional (sustituida en DEC-37) |
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

**Por qué A:** es lo único medido sin pérdidas. Tu ejemplo de A-04 con Phi queda en *"RAG against the Machine is a multi-domain Retrieval-Augmented Generation system with an agent, an MCP server, and a web interface. …"*.

**Reversible:** sí, una línea en `clean_output`.

## DEC-23 — Filtro de idioma en "about": implementado y desactivado

Para una pregunta en inglés, 2 de las 5 fuentes salían en español: el mismo contenido en `docs/` y en `docs/es/`.

| Opción | Pros | Contras |
|---|---|---|
| A. Filtrar en los dos idiomas: si un fichero tiene traducción, la pregunta solo recibe la copia en su idioma | Contexto en un solo idioma | Pierde respuestas en español: a veces la sección inglesa recuperada contiene la respuesta y la sección española recuperada es otra ("contiene la respuesta" ES @5: 0.94 → 0.83) |
| B. Filtrar solo las preguntas en inglés | Recuperación de "about" en inglés mejor (R@3 0.44 → 0.50, R@5 0.50 → 0.56; fuentes en el otro idioma 16 → 3 de 90); español idéntico. Generación con el 0.6B: EN contiene 0.44 → **0.61** | Con el 1.7B, Phi y el 4B bajan las citas correctas en EN (por ejemplo, Phi 0.33 → 0.17) y Phi y el 4B dicen "no encontrado" algo más (0.17 → 0.28, 0.22 → 0.28) |
| **C. Dejar B implementado y desactivado** ✅ | Cumple la regla de no empeorar | Tu queja (fuentes mezcladas) sigue ahí hasta que lo actives |

**Por qué C:** B mejora claramente el modelo base, que es el que se despliega (P12), pero empeora algunas métricas de los opcionales, y la regla de esta noche no lo permite. Para activarlo, descomenta `translations` y `translation_languages` en `[sources.about]` de `rag.toml`; no hace falta reindexar. **Mi recomendación:** activarlo si el servidor va a usar el 0.6B. *(Activado en DEC-34.)*

**Reversible:** sí, dos líneas de `rag.toml`.

## DEC-24 — Preguntas que nombran el proyecto o al autor

A-02 iba a vLLM (1.04 frente a −1.85 de "about"). Aunque hubiera ido a "about", su filtro (−1.0) la habría rechazado.

| Opción | Pros | Contras |
|---|---|---|
| **A. `route_names`: expresiones que nombran el dominio sin ambigüedad ("rag against the machine", "este/esta/tu rag, proyecto, sistema, chatbot, asistente, web, aplicación", "this/your rag, project, system, chatbot, assistant, website, app"). El dominio gana y su filtro no se aplica, porque la pregunta va explícitamente sobre él. "The project" y "el proyecto" siguen como pista débil (deben pasar el umbral)** ✅ | Las 8 preguntas de prueba que nombran el proyecto llegan a "about" y responden; **antes fallaban las 8** (4 a "no encontrado", 4 a vLLM, XQuAD o CV). Comprobado: ninguna pregunta de los demás benchmarks coincide | Una pregunta absurda que nombre el proyecto llega al LLM, que dirá que no lo encuentra |
| B. Bajar el umbral de "about" | Simple | Deja pasar más preguntas ajenas (medido en §7a.7) |
| C. Añadir esa forma de nombrar el RAG a las pistas débiles | Mínimo | No basta: −1.85 no pasa el umbral |

**Además, el nombre del autor para el CV** (pista débil `chrystian|donaire`). Al reindexar "about", una pregunta del CV por el correo de contacto pasó a "about" (que la respondía con código) en vez de al CV. Con la pista, si la pregunta nombra al autor y el CV pasa su umbral, gana el CV. Solo coinciden preguntas del CV (27 de 30 por idioma).

**Resultado:** route-bench final (`85-night-final`) con el mismo enrutado que el commit en todos los conjuntos (42 0.99, XQuAD 0.981 / 0.975, CV 0.967 / 0.967, about 0.778 / 0.889). Única diferencia: XQuAD/ES R@1 0.9059 → 0.9050, una pregunta en una posición, por la búsqueda vectorial aproximada de Qdrant tras restaurar el bundle (DEC-25), que es lo mismo que cargará el servidor.

**Reversible:** sí, `rag.toml`. *(Retirada en DEC-33.)*

## DEC-25 — Índice de "about": el de la línea base

Al reindexar "about" esta noche entraron ~35 fragmentos nuevos: la documentación escrita el día 24 (tablas de §7a.8 con preguntas del CV, `DETECTOR_BUCLES.md`, `loops.py`…). Con ese índice, **sin ningún cambio de código**, la generación de "about" baja frente a la línea base (por ejemplo, el 1.7B en ES contiene 0.67 → 0.56) y una pregunta de "about" en ES cambia de dominio.

| Opción | Pros | Contras |
|---|---|---|
| **A. Restaurar el índice de la línea base (desde `deploy/bundle`, SHA256 comprobado) y no reindexar "about" esta noche** ✅ | Mañana tienes exactamente lo de ayer más las mejoras de código | La documentación de hoy no entra en "about" hasta que se reindexe |
| B. Quedarse con el índice nuevo | "About" sabe lo último | Incumple la regla |
| C. Marcar con `about:skip` las partes nuevas que compiten | Arreglaría la causa | Es decidir qué documentación ve "about", y eso te toca a ti |

**Por qué A:** la regla de esta noche. Pero el problema de fondo queda abierto: **"about" empeora a medida que crece la documentación**, porque los changelogs repiten datos y citan preguntas. Habrá que decidir qué entra (opción C) antes del despliegue. *(Resuelto en DEC-37.)*

**Ya preparado, sin efecto hasta reindexar:** `deploy/space/README.md` sale de "about" (`exclude_paths`). Es la ficha antigua del Space y dice cosas falsas (que el agente está activado por defecto).

**Reversible:** sí, `make index SOURCE=about`.

## DEC-26 — Lo que no he tocado

- **Citas mal formadas de Phi** (un enlace de Markdown en lugar de `[n]`) y **el cierre contradictorio** (decir que no hay información después de responder; literales en `RESPUESTAS_ARCHIVADAS.md`). Salieron con tu pregunta abierta, no en los benchmarks (`bad_citation` = 0). El arreglo natural era la regla de `v5`, que hereda el problema de `v4`. Queda para medirlo con más preguntas abiertas.
- **L-3** (una guía de vLLM pedida en tres palabras; `RESPUESTAS_ARCHIVADAS.md`), que va a "about" (3.13 frente a 2.09). Es una pregunta corta y ambigua; con una formulación completa va a vLLM.
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

Encargo: Phi-4-mini seguía copiando fuentes con A-01 y A-04 (la segunda, además, cortada), y el 0.6B no daba ninguna respuesta a la primera. Objetivo: respuestas correctas de forma y de fondo (sin verborrea y sin frases cortadas). La regla es la misma: **ningún caso puede empeorar**. Sin commits durante la sesión; al final, un checkpoint porque lo pediste. Detalle en `changelog/FASE_7.md` §7b.7.

**Resumen:**

| DEC | Qué | Estado |
|---|---|---|
| 27 | Medir la forma como en la web: métricas `cut` y `tokens` y banco de 34 preguntas abiertas | ✅ Aplicada |
| 28 | Detector de bucles: ventana 8 → 12 | ✅ Aplicada |
| 29 | Reintento cuando Phi copia las fuentes | ✅ Aplicada (variante prudente; retirada en DEC-32) |
| 30 | Bloques repetidos en el detector de bucles | ✅ Aplicada |
| 31 | Lo que no he tocado | — |

Antes de todo, un arreglo sin opciones: la limpieza de la instrucción repetida (DEC-22) se comía la respuesta entera del 0.6B en A-01 (el patrón cruzaba los dos puntos). Ahora no los cruza y, si deja la respuesta vacía, se devuelve la original. 0 cambios en las 4.662 respuestas guardadas.

## DEC-27 — Medir la forma como en la web

Los benchmarks no veían tus casos. `gen-bench` usa preguntas de un solo dominio y no contaba las respuestas cortadas, y la web pasa por otro camino (todos los dominios, 1.024 tokens, recorte con " …").

| Opción | Pros | Contras |
|---|---|---|
| **A. Métricas `cut`, `tokens` y `tokens_max` en `gen-bench` + un banco de 34 preguntas abiertas por `RagService.chat` (el camino de la web) para los cuatro modelos** ✅ | Tus casos y los ejemplos de la web pasan a ser números comparables; detecta cortadas, eco, bucles, frases repetidas, vacías e idioma | El banco abierto está en `data/output/night2/` (ignorado por git): es una herramienta de esta sesión, no del proyecto |
| B. Probar a mano en la web | Lo más fiel | No escala ni dice qué empeora |

**Línea base `90-*`:** matriz de `gen-bench` a 1.024 tokens + banco abierto. En el abierto, Phi tiene 2 respuestas cortadas, 1 con eco, 4 con frases repetidas y un máximo de 1.016 tokens. El 0.6B, el 1.7B y el 4B no tienen ninguna cortada ni bucles.

**Reversible:** sí; solo mide.

## DEC-28 — Detector de bucles: ventana 8 → 12

Un bucle de Phi de 4 frases que se repiten llegaba a los 1.024 tokens: con 8 unidades nunca hay 5 copias en la ventana.

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
| A. Reintentar en cuanto la respuesta empieza con una cabecera (`91-*`) | Phi: arregla sus casos. 0.6B: mejora la forma de ~11 respuestas de XQuAD y del CV (de un párrafo copiado a una frase), pero **pierde una** (XQuAD/ES: pasa a una fecha equivocada). Además, en XQuAD/EN "contiene" baja de 0.637 a 0.633 por otra, en la que la nueva respuesta se queda corta frente a la referencia (literales en `RESPUESTAS_ARCHIVADAS.md`). Incumple la regla |
| **B. Reintentar solo si, además, llega a copiar una segunda cabecera o etiqueta (`92-*`)** ✅ | 0.6B, 1.7B y 4B: **idénticos** a `90` en toda la matriz. Phi: 3 respuestas de `gen-bench` y 5 abiertas cambian, todas a mejor (`FASE_7.md` §7b.7) |
| C. No reintentar, solo limpiar | Tus casos siguen fallando |
| D. Prohibir las cabeceras desde el primer intento (`bad_words_ids` siempre) | No probado: cambia la generación de todas las respuestas de todos los modelos, y la regla pide no tocar lo que funciona |

**Cómo es el reintento:**
- Se genera otra vez sin dejar empezar por `[` y sin dejar escribir `--- file`, `SOURCES:` ni `QUESTION:`.
- Probado en CPU antes: solo prohibir las cabeceras da una respuesta hecha solo de citas seguidas, así que hace falta también lo del primer `[`.
- En la web se retiene el principio de la respuesta hasta saber que no es un eco, así que la copia no llega a la pantalla.

**Por qué B:** es la única que no empeora nada. A cambio, el eco de una sola cabecera del 0.6B se sigue limpiando como antes, con `strip_echo` (a veces queda un párrafo copiado de la fuente).

**Reversible:** sí; quitando el criterio `EchoStart` de `stopping_criteria`, todo vuelve a como estaba. *(Retirado con Phi en DEC-32.)*

## DEC-30 — Bloques repetidos en el detector de bucles

En el banco abierto aparecieron dos formas de repetir que la ventana no ve:
- **Un ciclo de 14 frases** (Phi, A-15: 1.016 tokens, cortada).
- **La respuesta escrita dos veces**, con la instrucción repetida en medio (Phi, A-05, 773 tokens; literal en `RESPUESTAS_ARCHIVADAS.md`).

| Opción | Pros | Contras |
|---|---|---|
| **A. Regla de bloque: las últimas N frases repiten, una a una, las de un poco antes (ciclo de hasta 40 frases). Si la frase justo anterior contiene a su pareja (la instrucción repetida que acaba con la primera frase de la respuesta), el corte empieza ahí** ✅ con N = 6 | Detecta los dos casos y se corta donde empieza la copia. En 15.793 respuestas y 299 documentos solo cambian las de Phi que repetían | Una respuesta que de verdad repita 6 frases seguidas se cortaría (no hay ninguna en todo lo guardado) |
| A con N = 4 | Detecta lo mismo | Falsos positivos en 4 documentos de vLLM (pasos de instalación repetidos) |
| A con N = 5 | Sin falsos positivos | Menos margen que 6 |
| B. Ventana mayor (40) | Una sola regla | Más coste por token y más riesgo de comparar frases lejanas parecidas |
| C. Limpiar esa instrucción repetida con otro patrón | Arreglaría el segundo caso | Otro parche de texto como `strip_echo`, y no arregla el primero |

**Efecto lateral:** la respuesta de Phi escrita dos veces pierde sus citas, que solo estaban al final de la copia (about/ES de Phi: "cites" 0.93 → 0.86). Lo cuento como mejora (de 773 a 375 tokens sin repetir), pero es una métrica que baja.

**Reversible:** sí; `BLOCK` o la llamada a `repeated_block` en `find_loop`.

## DEC-31 — Lo que no he tocado

- **A-01 sigue sin una buena respuesta.**
  - El 0.6B responde algo pobre en inglés, y Phi dice que no lo encuentra (ya no vuelca 873 tokens).
  - La causa es la recuperación: sin el nombre del proyecto, las fuentes que llegan son secciones sueltas.
  - Probé a buscar con el nombre del proyecto en su lugar. Mejora las preguntas generales (A-02, A-03, A-10) y empeora las concretas (reranker, agente, web).
  - No lo aplico. Opciones para hablarlo: hacerlo solo con las preguntas generales, o buscar con las dos formulaciones y fusionarlas.
- **Phi en "about" sigue siendo prolijo y repite datos falsos** de la ficha antigua del Space (el despliegue y el agente por defecto).
  - Vienen de `deploy/space/README.md`, que sigue en el índice restaurado (DEC-25).
  - Se arregla reindexando "about", que es tu decisión pendiente.
- **Una forma rara de "no encontrado" de Phi** (mal traducida; literal en `RESPUESTAS_ARCHIVADAS.md`) no se reconoce como "no encontrado". Es menor y no lo he tocado.
- **El banco abierto del 4B en `92`** no se pudo pasar: el modelo no carga en ese proceso con 12 GB. Su `gen-bench` es idéntico a `90`.

## ¿Volver a una versión más estable? (para discutir, 2026-10-26)

Me pediste los pros y contras de volver atrás, distinguiendo las mejoras de verdad de las "trampas" que han hecho falta para los resultados. Lo que sigue es mi lectura, con los números de `90` (línea base de hoy) y `92` (estado final). *(Resultado: DEC-32 a DEC-37.)*

### Qué hay en cada punto

| Punto | Qué tiene | Problemas conocidos |
|---|---|---|
| `3378494` (Fase 6) | API, web React y despliegue preparados. Sin "about" y sin detector de bucles | Phi entra en bucles de hasta 1.500 tokens; no se puede preguntar por el proyecto |
| `8ff05d0` (Fase 7, "about" terminado) | "About" en la web, despliegue en Oracle, límite por modelo (512; 640 para Phi) | Los bucles de Phi se cortan por el límite, a media frase; el eco de Phi llega a la web; A-02 va a vLLM |
| `02ff464` (último commit antes de estas sesiones) | Detector de bucles y límite de 1.024 tokens | El eco de Phi y los bucles largos siguen; A-02 no llega a "about" |
| Checkpoint de hoy (DEC-20 a DEC-31) | Lo de la tabla siguiente | Lo de DEC-31 |

### Lo añadido desde `02ff464`: ¿mejora o parche?

| Cambio | Tipo | Por qué |
|---|---|---|
| Métricas de forma y banco de preguntas abiertas (DEC-20, DEC-27) | **Mejora** | Solo miden, no cambian ninguna respuesta |
| Detector de bucles: ventana 12 y bloques repetidos (DEC-28, DEC-30) | **Mejora** | Son reglas generales (texto que se repite), medidas sin falsos positivos sobre 15.793 respuestas y 299 documentos. No dependen de ninguna pregunta |
| Reintento cuando Phi copia dos fuentes (DEC-29) | **Parche razonable** | Es general (no depende de la pregunta), pero trata un síntoma de Phi, no la causa: el modelo copia el prompt. Con los Qwen no se activa en nada de lo medido |
| `strip_echo` (DEC-22) | **Parche** | Expresiones regulares sobre el texto ya generado. Cada modelo nuevo puede copiar el prompt a su manera y pedir patrones nuevos. Hoy mismo, uno de ellos se comía la respuesta del 0.6B |
| `route_names`: frases fijas que nombran el proyecto y mandan a "about" sin pasar su filtro (DEC-24) | **Trampa ligera** | Es una lista escrita a mano: arregla los 8 casos medidos, pero las formulaciones nuevas se quedan fuera |
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
  - Phi responde a A-04 con 49 tokens cortados, y a A-01 con 873 tokens de fuentes copiadas.
  - A-02 vuelve a ir a vLLM con todos los modelos.
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

# Sesión autónoma 2026-10-26/27

Encargo (tus palabras): *"Limpieza encima del commit actual. Vamos a quitar las trampas, aunque empeoren preguntas poco focalizadas. El filtro de idioma se queda. Si podemos darle pistas con él a los LLM de qué idioma estamos usando, mejor que mejor."* Antes, en la conversación, decidiste quitar Phi-4-mini ("insalvable": el detector de bucles funciona, pero las salidas no) y quedarte con los Qwen. Sin commits. Detalle en `changelog/FASE_7.md` §7b.8.

**Cómo lo he medido:** cada paso por separado, sobre el mismo índice y con la misma matriz que la sesión anterior (`gen-bench` a 1.024 tokens del 0.6B, 1.7B y 4B, banco abierto de 34 preguntas y `route-bench`):

| Ejecución | Qué cambia frente a la anterior |
|---|---|
| `92` | Estado del commit `644c455` (la sesión anterior), con Phi |
| `94` | Limpieza de código: sin Phi, sin reintento, sin `route_names` y sin la pista del CV. Filtro de idioma **apagado**, para medir solo la limpieza |
| `95` | `94` + filtro de idioma **encendido** (DEC-34). Con registro de cada respuesta que toca `strip_echo` (DEC-35) |
| `96` | `95` + pista de idioma en el prompt (DEC-36) |
| `97` | `95` + "about" reindexado con la documentación sincronizada (DEC-37) |
| `98` | `97` con el ground truth de "about" regenerado (DEC-37) |
| `99` | Experimento: "about" sin el historial (changelogs, `decisions.md`, `DETECTOR_BUCLES.md`). Medido y **revertido** (DEC-37) |
| `100` | Estado final, tras escribir esta documentación (DEC-37) |

**Resumen:**

| DEC | Qué | Estado |
|---|---|---|
| 32 | Phi-4-mini fuera, y con él el reintento por eco (DEC-29) | ✅ Aplicada (decisión tuya) |
| 33 | Quitar las trampas: `route_names` y la pista del nombre del autor (DEC-24) | ✅ Aplicada (decisión tuya) |
| 34 | Filtro de idioma de "about" encendido (DEC-23) | ✅ Aplicada (decisión tuya) |
| 35 | `strip_echo` (DEC-22) se queda sin Phi: también limpia 17 respuestas de los Qwen | ✅ Aplicada |
| 36 | Pista de idioma en el prompt: medida y **no adoptada** (empeora el idioma del 0.6B) | ❌ No adoptada; opción C abierta |
| 37 | Documentación sincronizada, "about" reindexado (sustituye a DEC-25) y ground truth de "about" regenerado | ✅ Aplicada. El historial dentro de "about": resuelto en DEC-39 (se queda, sin las citas) |
| 38 | Lo que no he tocado | — |

## DEC-32 — Phi-4-mini fuera

**Decisión tuya.** Lo que quedaba de Phi tras las dos sesiones anteriores: respuestas prolijas que resumen fuente por fuente, eco del prompt y bucles, contenidos por parches (`strip_echo`, el reintento de DEC-29 y el detector de bucles). Tu lectura: "el controlador de loops funciona, pero las salidas son infumables".

**Qué se quita** (vuelta a la versión de `02ff464` de cada fichero, más lo que se mantiene de después):

| Fichero | Cambio |
|---|---|
| `rag.toml` | Perfil `[profiles.llm-phi4-mini.generation]` eliminado; comentario de los LLM opcionales actualizado |
| `Makefile` | `API_MODELS ?= default,llm-qwen3-1.7b` (antes, también Phi) |
| `src/rag/generator.py` | Sin el reintento (`EchoStart`, `echo_started`, constantes `ECHO_*`, `bad_words_ids`, `begin_suppress_tokens`, el streaming retenido y `echo_guard`). Se queda `strip_echo` (DEC-35) con el arreglo del 0.6B de la sesión anterior |
| `tests/test_generator.py` | Fuera los tests del reintento; se quedan los de `strip_echo` |
| `web/src/App.tsx` | Fuera la nota de Phi del selector de modelos (web recompilada) |
| `src/agent/toolcalls.py`, `src/api/app.py` | Solo comentarios y ejemplos de la documentación del código |

**Qué se queda, aunque naciera por Phi:** el detector de bucles con ventana 12 y bloques repetidos (DEC-28, DEC-30). Son reglas generales, medidas sin falsos positivos, y nunca comparan código, tablas ni logs (§7b.7). Queda como red de seguridad para cualquier modelo. También se queda el formato de herramientas de Phi en `toolcalls.py` (`system_tools`): es genérico (lo usa cualquier plantilla que declare las herramientas en el mensaje de sistema) y tiene sus tests.

**Comprobado (`94` frente a `92`):** el 0.6B, el 1.7B y el 4B son **idénticos en `gen-bench`**, respuesta a respuesta en las diez ejecuciones de la matriz. El reintento nunca se activaba con ellos (ya lo decía DEC-29), así que quitarlo no les cambia nada.

**¿Otro modelo de otra familia?** Me preguntaste si podíamos encontrar uno que sustituya a Phi. No he probado ninguno esta noche; son candidatos para hablarlo:

| Candidato | A favor | Dudas |
|---|---|---|
| IBM Granite (4.x, ~3B, o la variante "micro") | Apache 2.0, multilingüe con español, pensado para RAG y herramientas | Sin medir con nuestro prompt ni con llm_sdk/transformers |
| Gemma 3 (1B / 4B) | Buena calidad en tamaños pequeños | Licencia propia de Google (con condiciones de uso); el 4B probablemente no cabe en la GPU junto a la búsqueda, como el Qwen3-4B en la web |
| Llama 3.2 (1B / 3B) | Muy usado, formato de herramientas conocido | Licencia comunitaria de Meta; el español no es de sus idiomas fuertes en tamaños pequeños |

Mi recomendación: si se prueba uno, que sea con la misma matriz (`gen-bench` a 1.024 tokens + banco abierto) y **sin parches nuevos**: si necesita parches para dar respuestas limpias, no entra.

**Reversible:** sí, el perfil y el reintento están en `644c455`.

## DEC-33 — Quitar las trampas

**Decisión tuya**, sabiendo que empeoran las preguntas poco concretas. Lo que se quita (las "trampas ligeras" de la tabla de "¿Volver a una versión más estable?"):
- **`route_names`** (DEC-24): frases fijas que nombraban el proyecto y mandaban a "about" **sin pasar su filtro**. Fuera el campo de `SourceConfig` (`src/config.py`), su compilación en `src/rag/retriever.py` y `DomainRouter.named` (`src/rag/router.py`, vuelve a la versión de `02ff464`), y sus dos tests.
- **La pista del nombre del autor** (`route_hints = ['\b(chrystian|donaire)\b']` en `[sources.cv]`).
- **Las pistas débiles de "about"** vuelven a las de `8ff05d0`: `\b(this|the|your) project\b`, `\b(este|el|tu) proyecto\b` y `rag against the machine`. Siguen siendo pistas débiles: solo deciden si "about" pasa su umbral (−1.0).

**Qué empeora** (banco abierto, `94` frente a `92`; 9 respuestas cambian con el 0.6B y las mismas 9 con el 1.7B, todas de las que nombraban el proyecto):

| Pregunta | Antes (`92`) | Ahora (`94`) |
|---|---|---|
| A-01 / A-02 | about | vLLM: habla de la técnica RAG en general, o "no encontrado" |
| A-03 | about | vLLM: la técnica RAG con vLLM + LangChain |
| A-06 | about | XQuAD: un contrato de obra |
| A-10 | about | XQuAD: un informe sobre el clima (0.6B) / un filósofo griego (1.7B) |
| A-07 | about | CV: describe tu otro proyecto de agentes |
| A-08 / A-09 / A-11 | about, respondía | about, pero su filtro las rechaza: "no encontrado" |

Lo que falla es la recuperación: sin la regla, estas preguntas puntúan más en otro dominio, o no llegan al umbral de "about". Las preguntas que nombran el proyecto con "el proyecto" o "RAG against the Machine" siguen yendo a "about".

**Lo que no cambia:** el `route-bench` (`94-route`) es **idéntico** a `76-about-hints` y a `85-night-final` en todos los conjuntos (42, XQuAD, CV y about). Ninguna pregunta de los benchmarks dependía de `route_names` ni de la pista del CV con el índice actual. `gen-bench` es idéntico (cada suite va a un solo dominio).

**Reversible:** sí, todo está en `644c455`.

## DEC-34 — Filtro de idioma de "about" encendido

**Decisión tuya** ("el filtro de idioma se queda"). En `[sources.about]` de `rag.toml`: `translations` ([`README.md`, `docs/es/README.md`] y [`docs/`, `docs/es/`]) y `translation_languages = ["en"]`. Para una pregunta en inglés, quita de las fuentes la copia en español de los ficheros traducidos; las preguntas en español ven los dos idiomas (filtrarlas también perdía respuestas, DEC-23).

**Medido (`95` frente a `94`, mismo índice):** solo cambia about/EN. vLLM, XQuAD, CV y about/ES son idénticos respuesta a respuesta.

| | `94` (sin filtro) | `95` (con filtro) |
|---|---|---|
| Route-bench about/EN, R@1/@3/@5/@10 | 0.22 / 0.39 / 0.39 / 0.61 | 0.22 / 0.39 / **0.44** / 0.56 |
| 0.6B about/EN: contiene · cita · cita bien | 0.50 · 0.87 · 0.23 | **0.56** · 0.80 · 0.17 |
| 1.7B about/EN: contiene · "no encontrado" falso · cita bien | 0.61 · 0.17 · 0.43 | 0.61 · **0.11** · 0.27 |
| 4B about/EN: contiene · "no encontrado" falso · cita bien | 0.67 · 0.22 · 0.64 | **0.72** · **0.17** · 0.47 |
| Banco abierto (0.6B y 1.7B) | — | 2 respuestas cambian por modelo, las dos a mejor o igual: A-04 pasa a describir el proyecto completo (el 0.6B antes daba una frase incompleta) |
| Respuestas que cambian de idioma a mitad (`lang_mix.py`) | 10 de 1.103 | 10 de 1.105 (las mismas) |

**Lectura:** sube lo que más pesa (R@5 y "contiene la respuesta") y bajan las citas correctas, como ya se vio en DEC-23. Una parte de esa bajada es de la métrica: "cita bien" compara con el fichero de la respuesta de referencia, y con el filtro llegan otras secciones en inglés que también la contienen. Pero hay una pérdida real: about-04 en inglés deja de dar el modelo (`mmarco-mMiniLMv2`) con el 1.7B y el 4B, y el 0.6B pasa a "no encontrado". El R@10 de about/EN baja una pregunta (0.61 → 0.56).

Este es el estado con el **índice antiguo**; la medida que cuenta es la final con el índice reindexado (DEC-37). Además, en estas ejecuciones 3 de los 18 pasajes de referencia ya estaban desplazados (DEC-37): afecta al recall y a "cita bien" de "about", no a "contiene".

**Reversible:** sí, dos líneas de `rag.toml`, sin reindexar.

## DEC-35 — `strip_echo` sin Phi

`strip_echo` (DEC-22) era, en la tabla de "¿Volver atrás?", un **parche**: expresiones regulares sobre el texto ya generado. Lo dejé decidido por los datos: en `95` se registraron todas las respuestas que cambiaba (`data/output/night2/95-echo.jsonl`).

| Opción | Pros | Contras |
|---|---|---|
| **A. Quedarse** ✅ | Con los Qwen también actúa: **17 respuestas** en `95`, todas a mejor | Sigue siendo un parche de patrones |
| B. Quitarlo | Generador más simple | Esas 17 respuestas vuelven a empezar con `[1] --- file: data/raw/...` en la web |

**Qué hace en esas 17** (XQuAD 12, CV 3, about 1 y vLLM 1; el registro no guarda el modelo, pero XQuAD solo se mide con el 0.6B):
- 16 empiezan copiando la cabecera de una fuente (`[2] --- file: data/raw/xquad/es/Victoria_(Australia).md ---`) y luego dan la respuesta: queda la respuesta citada como `[2]`.
- 1 (vLLM) termina listando las cabeceras de sus fuentes: quedan como `[1] (ruta)`.
- En ninguna se pierde texto de la respuesta. El arreglo del 0.6B de la sesión anterior (no dejar nunca una respuesta vacía) se mantiene.

**Reversible:** sí, una línea en `clean_output`.

## DEC-36 — Pista de idioma para el LLM

Pediste darle al LLM pistas del idioma "si podemos". El prompt ya le dice el idioma (*"Answer in Spanish, citing the sources by number."*, en inglés aunque la pregunta sea en español). Y el filtro de DEC-34 ya es una pista: a una pregunta en inglés solo le llegan fuentes de "about" en inglés.

| Opción | Pros | Contras |
|---|---|---|
| A. Escribir la instrucción final en el idioma de la pregunta: *"Responde en español, citando las fuentes por su número."* (y enseñarle a `strip_echo` su eco en español) | La pista más directa: la última frase que lee el modelo está en español | Medida en `96`: empeora (abajo) |
| **B. Dejar el prompt como está** ✅ | Nada empeora; el idioma ya va al 99–100 % | No hay pista nueva |
| C. Otras formas (el idioma en el mensaje de sistema, una línea "La pregunta está en español") | Podrían no tener los fallos de A | Sin medir. Con el 0.6B, cualquier cambio de prompt mueve muchas respuestas (DEC-21) |

**Medido (`96` = `95` + opción A, solo cambia el prompt de las preguntas en español):** 22 métricas bajan frente a `95`, con 158 respuestas cambiadas solo en XQuAD/ES del 0.6B.
- **Idioma, justo lo que se quería mejorar:** about/ES del 0.6B, 1.00 → **0.86**. A about-01 responde solo con una cita, sin texto, y a about-10, la mitad en inglés. Respuestas que cambian de idioma a mitad: 10 → 11.
- **Privacidad del CV:** sin fugas en ningún caso, pero el 4B deja de dar el mensaje del CV en 1 de las 2 preguntas privadas en español (1.00 → 0.50), y el 0.6B en 1 de las 7 sin respuesta (0.86 → 0.71).
- **XQuAD/ES (0.6B):** contiene 0.59 → 0.56. Citas correctas de vLLM/ES (0.6B): 0.90 → 0.80 (docs) y 1.00 → 0.89 (code).
- **A favor:** 1.7B vLLM/ES, idioma 0.90 → 1.00 y citas correctas 0.80 → 0.90; cv/ES del 0.6B, contiene 0.80 → 0.83.

**Por qué B:** la regla es que nada empeore, y A empeora justo el idioma con el modelo base. **Queda abierto C**, para medirlo con la misma matriz si quieres seguir por aquí. La implementación de A está en `data/output/night2/logged.py` (`RAG_EXP_LANG_HINT=1`, ignorado por git); no he tocado `generator.py`.

**Reversible:** no hay nada que revertir.

## DEC-37 — Documentación sincronizada y "about" reindexado

**Encargo tuyo:** "actualiza los documentos (todos) para evitar discrepancias". Con eso, el índice restaurado de DEC-25 dejaba de tener sentido: guardaba justo las contradicciones que se querían quitar.

**Qué se ha sincronizado** (lista completa en `FASE_7.md` §7b.8):
- README (EN y ES): cuatro dominios, solo Qwen, despliegue en Oracle, agente apagado en la web y chip "about" fijo.
- `deploy/README.md` y la ficha del Space, `DETECTOR_BUCLES.md` (ventana 12), ROADMAP, `BENCHMARK_REPORT.md` y los changelogs, con notas en lo que DEC-32 a DEC-36 dejan desfasado.
- La traducción al inglés, que estaba parada en `8ff05d0`: ROADMAP, `decisions.md` (DEC-19 a DEC-38) y `FASE_7.md` (§7a.6 a §7b.8).

**Reindexado** (`make index SOURCE=about`):

| | Índice de DEC-25 (bundle del 24) | Reindexado |
|---|---|---|
| Trozos (hijos) | 2.008 | 2.407 (1.623 de documentación, 784 de código) |
| Padres | 718 | 828 |
| `docs/nextstep.md` (fichero fantasma, ya no existe) | 19 trozos | Fuera |
| `deploy/space/README.md` (ficha antigua del Space) | Dentro | Fuera (`exclude_paths`) |

### El ground truth de "about" estaba desfasado

Al comparar `97` con `95`, el recall de "about" en el `route-bench` se hundía (EN R@5 0.44 → 0.28). No era la recuperación: el ground truth de "about" guarda **offsets de caracteres** de cada fichero, y al editar el README se habían movido **16 de los 18 pasajes** de referencia en cada idioma.
- Ya en el commit `644c455` había **3 desplazados** (about-14, 16 y 17), porque la documentación se había editado sin regenerarlo. Afecta al recall y a "cita bien" de "about" en las ejecuciones anteriores; no a "contiene la respuesta", que mira el texto.
- **Arreglo:** `python -m src build_about_bench`, que vuelve a buscar cada evidencia en su fichero y falla si no la encuentra exactamente una vez. Hubo que tocar dos preguntas:
  - **about-11** (el lugar del despliegue): la respuesta de referencia era "Hugging Face", que es falso desde DEC-19. Ahora es "Oracle", con la evidencia de la sección de despliegue del README.
  - **about-17** (el botón Stop): la firma de `stopping_criteria` cambió con el detector de bucles (`02ff464`); la evidencia apunta a la firma actual.
- `98` repite la medida de "about" con el ground truth regenerado. Es la que vale, no `97`.

### Resultados del reindexado (`98` frente a `95`)

`gen-bench` de vLLM, XQuAD y CV: **idéntico** respuesta a respuesta. 42 (`97-final`): **idéntico**, docs 0.76 / 0.91 / 0.92 / 0.94 y code 0.51 / 0.72 / 0.80 / 0.88.

| | `95` (índice de DEC-25) | `98` (reindexado) |
|---|---|---|
| Route-bench about/EN, enrutado · R@1/@3/@5/@10 | 0.778 · 0.22 / 0.39 / 0.44 / 0.56 | **0.833** · 0.11 / 0.33 / 0.33 / **0.61** |
| Route-bench about/ES, enrutado · R@1/@3/@5/@10 | 0.889 · 0.33 / 0.39 / 0.50 / 0.56 | **0.944** · **0.39 / 0.50 / 0.67 / 0.67** |
| Route-bench CV EN / ES, enrutado | 0.967 / 0.967 | 0.933 / 0.900 (1 y 2 preguntas más se van a "about") |
| Route-bench 42 y XQuAD | — | Igual en enrutado y recall; en XQuAD, una pregunta por idioma pasa de "about" a vLLM |
| 0.6B about/EN · ES, contiene | 0.56 · 0.56 | 0.44 · **0.61** |
| 1.7B about/EN · ES, contiene | 0.61 · 0.67 | 0.56 · **0.78** |
| 4B about/EN · ES, contiene | 0.72 · 0.67 | 0.67 · **0.78** |
| "No encontrado" falso en about/ES (los tres modelos) | 0.22 | **0.06** |
| 0.6B about/ES: idioma · eco · cortadas | 1.00 · 0 · 0 | 0.88 · 0.06 · 0.06 |
| Respuestas que cambian de idioma a mitad (`lang_mix.py`, toda la matriz + banco abierto) | 10 de 1.105 | **20 de 1.117**: +5 en about/ES (0.6B y 1.7B) y +5 en el banco abierto; el resto, las mismas |

(La columna `95` usa el ground truth antiguo, con 3 pasajes desplazados; las filas de "contiene" no dependen de eso.)

**Lectura:** el español mejora claramente (R@5 0.50 → 0.67, "contiene" +0.05 a +0.11, y casi desaparecen los "no encontrado" falsos). El inglés baja en R@5 y en "contiene" (una pregunta con cada modelo), aunque sube en R@10. El CV pierde enrutado: con más documentación, "about" gana alguna pregunta personal (el `route-bench` no guarda qué preguntas son; no lo he investigado más). Y el 0.6B, en español, copia una vez las fuentes tal cual (1.011 tokens: una tabla del README, código de `language.py` y un trozo de este changelog; no es un bucle, así que el detector no actúa) y responde una vez en inglés. **El idioma es lo que más empeora:** las preguntas en español reciben fuentes de los dos idiomas (el filtro solo actúa con las preguntas en inglés, DEC-34), y la traducción al inglés ha crecido mucho esta noche (DEC-19 a DEC-38, §7a.6 a §7b.8). Que sea esa la causa es una deducción mía; no lo he medido.

### El problema nuevo: la documentación se cita a sí misma

En el banco abierto (`97` frente a `95`) cambian 12 de 34 respuestas con el 0.6B y 12 con el 1.7B. Unas mejoran (A-05 y A-07 pasan a describir el proyecto de verdad) y otras empeoran de una forma nueva (respuestas literales en `RESPUESTAS_ARCHIVADAS.md`):

| Pregunta | Modelo | Respuesta con el índice nuevo |
|---|---|---|
| A-15 | 0.6B | Copia la línea del changelog que cita esa misma pregunta |
| A-09 | 0.6B | Copia la nota del changelog sobre otra pregunta de prueba |
| A-04 | 0.6B y 1.7B | Explica `strip_echo` (antes describían el proyecto) |
| A-06 | 1.7B | Explica cómo se enruta esa misma pregunta a "about" |

**La causa:** los changelogs y `decisions.md` citan **al pie de la letra** las preguntas de prueba y sus respuestas malas (para documentar los fallos). Cuando se hace esa misma pregunta, el trozo que mejor coincide es el que la cita. Cuanto más se documenta un fallo, más se repite. Es el riesgo que ya apuntaba DEC-25, y esta sesión lo agrava: §7b.8 y este fichero vuelven a citar esas preguntas.

### Experimento: "about" sin el historial (`99`, revertido)

He medido la opción que tenías reservada (sacar el historial de "about"), **sin dejarla puesta**. `exclude_paths` con `docs/changelog`, `docs/es/changelog`, `docs/decisions.md`, `docs/es/decisions.md` y `docs/es/DETECTOR_BUCLES.md`. Se quedan el README, el ROADMAP, `BENCHMARK_REPORT.md` y el código.

El índice se queda en 1.286 trozos (502 de documentación y 784 de código): **el historial son 1.121 de los 1.623 trozos de documentación**.

| | `98` (con historial) | `99` (sin historial) |
|---|---|---|
| Route-bench about/EN, R@1/@3/@5/@10 | 0.11 / 0.33 / 0.33 / 0.61 | **0.22 / 0.39 / 0.50** / 0.56 |
| Route-bench about/ES, R@1/@3/@5/@10 | 0.39 / 0.50 / 0.67 / 0.67 | **0.56 / 0.78 / 0.78 / 0.83** |
| Route-bench es/docs (complementario de 42), enrutado · R@1/@3/@5/@10 | 0.900 · 0.50 / 0.70 / 0.70 / 0.80 | **1.000 · 0.60 / 0.80 / 0.80 / 0.90** |
| Route-bench XQuAD/ES, enrutado · R@1 | 0.975 · 0.91 | 0.973 · 0.90 (2 preguntas más a "about") |
| Route-bench 42, XQuAD/EN, CV | — | Igual |
| Contiene EN: 0.6B · 1.7B · 4B | 0.44 · 0.56 · 0.67 | **0.61 · 0.67 · 0.72** |
| Contiene ES: 0.6B · 1.7B · 4B | 0.61 · 0.78 · 0.78 | 0.50 · 0.61 · 0.67 |
| "No encontrado" falso EN · ES (1.7B) | 0.11 · 0.06 | 0.22 · 0.17 |
| Cita la correcta ES: 0.6B · 1.7B · 4B | 0.38 · 0.38 · 0.47 | 0.33 · **0.53 · 0.67** |
| 0.6B: eco · cortadas (EN / ES) | 0 · 0 / 0.06 · 0.06 | 0.06 · 0.07 / 0 · 0.06 |
| Banco abierto 0.6B: eco · idioma mal | 3 · 2 | **0 · 0** |
| Banco abierto 1.7B: idioma mal | 1 | 3 |
| Cambio de idioma a mitad (about + banco abierto) | 10 | 6 |

En el banco abierto (`99` frente a `97`), el 0.6B mejora en unas 7 de sus 12 respuestas cambiadas: A-04, A-05 (ahora en español), el agente, el modelo de lenguaje, el recall y la búsqueda híbrida (A-07, A-13, A-14, A-15) vuelven a responder al tema, y A-09 dice "no encontrado" en lugar de inventar. Empeoran A-02 (responde solo con una cita), A-06 (vuelve al contrato de obra de XQuAD) y A-16 (copia código). El 1.7B mejora en inglés y empeora en español: responde en inglés a 3 preguntas en español (el agente, el recall y por qué Qwen3-0.6B).

**Lectura:** sin el historial, el recall de "about" sube mucho y la documentación deja de citarse a sí misma casi del todo. No del todo: el ROADMAP también nombraba A-01, y el 1.7B lo cita. Pero el español pierde: buena parte del material en español era el historial (los changelogs y `decisions.md` se escriben en español primero), así que las preguntas en español reciben menos texto en su idioma, y bajan "contiene" y el idioma. **No hay un ganador claro**: depende de si pesa más el inglés (los recruiters) o el español.

### Opciones

| Opción | Pros | Contras |
|---|---|---|
| **A. Índice reindexado con todo** ✅ (aplicada) | Sin contradicciones; el español mejora mucho | La documentación se cita a sí misma; el inglés baja un poco; el CV pierde 1–2 preguntas de enrutado |
| B. A + historial fuera de "about" (`99`) | Recall de "about" mucho mayor; el inglés mejora con los tres modelos; casi desaparece la autocita; el 0.6B, sin eco ni idioma mal en el banco abierto | El español baja ("contiene" −0.11 a −0.17, más "no encontrado" falsos, el 1.7B responde en inglés); "about" no puede contar la historia del proyecto (por qué se decidió cada cosa) |
| C. Volver al índice de DEC-25 | Los números de `95` | Las contradicciones (Hugging Face, el fichero fantasma, la ficha del Space) vuelven |
| D. Reescribir el historial para no citar las preguntas | Arregla la causa | Mucho trabajo, y el historial perdería precisión (las citas son la prueba de cada fallo) |

**Por qué A, y no B:** sacar el historial lo dejaste como decisión tuya. A es lo que pediste (documentación al día e indexada); B queda medida para que decidas. Para aplicarla: añadir esas cinco rutas a `exclude_paths` en `[sources.about]` de `rag.toml` y `make index SOURCE=about` (~1 min).

**Orden final:** después de escribir toda esta documentación se reindexa "about" una última vez (`100`), para que el índice coincida con los ficheros. Esos números están en "Cómo queda todo", al final.

**Lo que dice `100`, y mi recomendación:** con esta documentación dentro, la autocita empeora: 7 de las 12 preguntas abiertas sobre el proyecto se responden con notas del historial, también las de esta sesión. El `gen-bench` en español, en cambio, sube con el 1.7B y el 4B. Para la web, donde los recruiters hacen preguntas abiertas, **recomiendo B**. A cambio, el español pierde algo, y "about" deja de poder contar por qué se decidió cada cosa. No lo he aplicado porque es tu decisión. Una variante intermedia, sin medir: sacar solo `decisions.md` y los changelogs de la Fase 7, que son los que citan las preguntas de prueba. *(Al final se eligió otra vía: DEC-39.)*

**Reversible:** A y B, sí (una línea y un reindexado). C, restaurando "about" desde el bundle del 24 (`deploy/bundle/`), como en DEC-25. Ojo: `make bundle` sobrescribe ese bundle, y con él la opción C.

## DEC-38 — Lo que no he tocado

No es una decisión, sino la lista de lo que he visto y he dejado como estaba, para que lo revises:

| Tema | Estado | Por qué no lo he tocado |
|---|---|---|
| El filtro de "about" rechaza preguntas concretas | Umbral −1.0 sin cambios. Por ejemplo, about-02 en inglés puntúa −2.07 y se queda en "no encontrado" si solo se busca en "about" | Bajar el umbral deja pasar preguntas de otros dominios. Habría que recalibrarlo con `gate_scores` y volver a pasar el `route-bench` |
| Las preguntas poco concretas (A-01, A-06) | Peor que con las trampas (DEC-33) | Lo aceptaste al quitarlas. La causa de fondo es la recuperación, no el generador |
| El historial dentro de "about" (changelogs, `decisions.md`) | Sigue indexado | Lo reservaste como opción tuya. En DEC-37 tienes la medida con y sin él. *(Resuelto en DEC-39: se queda, sin las citas.)* |
| El formato de herramientas de Phi en `toolcalls.py` (`system_tools`) | Se queda | Es genérico (cualquier plantilla que declare las herramientas en el mensaje de sistema) y tiene tests |
| Qwen3-4B en el banco abierto | No carga en ese proceso: `llm_sdk` manda parte del modelo a la CPU ("You can't move a model that has some modules offloaded") | Pasa igual desde `92`. Su `gen-bench` sí se mide. No lo he investigado |
| La pista de idioma, opción C | Abierta | DEC-36 |
| `deploy/stage/` (ignorado por git) y `deploy/bundle/` | `stage` todavía nombra a Phi y el bundle lleva el índice de "about" anterior | Se regeneran con `make bundle`. **Antes de desplegar**, rehazlo para llevar el índice nuevo (sobrescribe el bundle antiguo, y con él la opción C de DEC-37) |
| La API | Parada (la paré para liberar la GPU) | Se levanta con `make api` |
| El ground truth de "about" depende de los offsets de los documentos | Cualquier edición del README o del ROADMAP lo desfasa (DEC-37) | Lo he regenerado con `python -m src build_about_bench`. Habría que hacerlo cada vez que se editen los documentos, o automatizarlo; no lo he automatizado sin preguntarte |
| Commits | Ninguno | Norma de `PLANING.md` |

## Cómo queda todo (sesión 2026-10-26/27, `100-*`)

| Comprobación | Resultado |
|---|---|
| `gen-bench` de vLLM, XQuAD y CV, 0.6B, 1.7B y 4B | **Idénticos** a `94` (y a `92`), respuesta a respuesta |
| `gen-bench` de "about" (`100`), contiene EN / ES | 0.6B 0.44 / 0.50 · 1.7B 0.56 / 0.72 · 4B 0.72 / 0.83; "no encontrado" falso en ES: 0 con los tres |
| Route-bench (`100-route`) | 42 y CV como `98`; XQuAD/EN 0.980 (una pregunta más a "about"); about enrutado EN 0.889 · ES 0.944, R@1/@3/@5/@10 EN 0.11 / 0.28 / 0.33 / 0.67 · ES 0.39 / 0.50 / 0.61 / 0.67 |
| Banco abierto (`100`) | 12 de 34 respuestas cambian frente a `97` con cada modelo. **7 de las 12 preguntas sobre el proyecto se responden citando notas de los changelogs y de `decisions.md`**, también las de esta misma sesión (A-09 responde con el texto de DEC-37). Cambio de idioma a mitad: 4 (eran 10 en `97`) |
| `make bench` de 42 (`97-final`) | **Idéntico:** docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88 |
| Tests | 123 (129 menos los 6 del reintento y de `route_names`); flake8 y mypy limpios |
| Índice de "about" | Reindexado una última vez después de escribir estos números, para que coincida con los ficheros (solo cambia el texto de los documentos). No se ha vuelto a medir |
| Commits | Ninguno |

---

# Mañana del 2026-10-27

## DEC-39 — Fuera las citas de preguntas de prueba y respuestas incorrectas

**Lo que viste:** en la web, con el estado de `100`, el 1.7B respondió a A-04 con la justificación de `strip_echo` sacada de `decisions.md`, y el 0.6B dio "no encontrado" a A-13. Te confirmé que era la autocita de DEC-37 y que ya se veía en el banco abierto de `100`. Mi informe lo contaba como "7 de 12 preguntas citan el historial", pero no decía claramente que eso es lo que iba a verse en la web.

**Tu decisión** (tus palabras): *"Quita esas citas a respuestas incorrectas. Todas. Si quieres mantenerlas, por motivos de historial, mételo en algún archivo fuera de la indexación."* Es la opción D de DEC-37 (reescribir el historial para que no cite las preguntas), con las citas guardadas aparte.

**Lo que tuve que decidir yo:**

| Duda | Opción elegida | Por qué | Alternativa |
|---|---|---|---|
| ¿Solo las respuestas o también las preguntas? | **Las dos**: todas las respuestas incorrectas copiadas y el texto de todas las preguntas de prueba sobre el proyecto, aunque se respondieran bien | Lo que atrae a la búsqueda es la pregunta: una nota que copia la pregunta y describe el fallo sin la respuesta sigue ganando, y el modelo responde "no encontrado" o con la nota | Quitar solo las respuestas: más fiel a tus palabras, pero no arregla la causa |
| ¿Cómo se nombran las preguntas? | **Identificadores** (`A-NN` del banco abierto, `about-NN` del benchmark, `L-N` de los bucles), con la lista en el archivo | Un identificador no coincide con ninguna pregunta real. Una paráfrasis ("la pregunta sobre el modelo de lenguaje") seguiría pareciéndose | Paráfrasis: se lee mejor, pero se parece a la pregunta |
| ¿Dónde va lo literal? | **`docs/es/RESPUESTAS_ARCHIVADAS.md`**, un solo fichero, en español y sin traducir (como `DETECTOR_BUCLES.md`), ordenado por la sección de origen | Un sitio único es fácil de excluir (`exclude_paths`) y de consultar. Las citas son casi todas en inglés, así que traducirlo no aporta | Un `.md` por changelog, o dentro de `data/` (no versionado: se perdería el historial) |
| ¿Qué se queda? | Las preguntas de vLLM, XQuAD y CV sin respuesta mala, las respuestas correctas, los textos del prompt y de la interfaz, "capital of France" → "Paris" (B15: está en la documentación de vLLM, no es incorrecta), las transcripciones del CV (ya fuera con `about:skip`) y los comentarios del código | No son respuestas incorrectas ni preguntas sobre el proyecto, así que "about" no compite por ellas | Quitarlo todo: mucho más trabajo y el historial perdería legibilidad sin medir un beneficio |

**Comprobado:** un script recorre lo que indexa "about" (con las mismas exclusiones) y no queda ninguna de las 36 preguntas del benchmark de "about", ni de las 16 del banco abierto sobre el proyecto, ni de las de los bucles.

**Medido (`101` frente a `100`, tabla completa en `FASE_7.md` §7b.9):**
- **Banco abierto:** ninguna respuesta cita ya el historial (antes, 7 de 12 con el 0.6B). Con el 0.6B y el 1.7B, eco 0 e idioma equivocado 0 (antes, 2 y 1 con el 0.6B, y 1 y 2 con el 1.7B). Cambio de idioma a mitad: de 4 de 165 respuestas a 1 de 150.
- **`gen-bench` de "about":** el 0.6B igual (0.44 / 0.50). El 1.7B baja en ES (0.72 → 0.61) y el 4B en los dos idiomas (0.72 / 0.83 → 0.67 / 0.72). Los "no encontrado" falsos pasan de 0 a 0.11 en ES.
- **`route-bench`:** about/EN pierde dos preguntas frente a vLLM (0.889 → 0.778; R@5 0.33 → 0.28). about/ES sube (R@5 0.61 → 0.67). El CV/EN recupera una (0.933 → 0.967). 42, es/docs, es/code y XQuAD, igual.

**Con el índice final** (`102`, 0.6B y `route-bench`): lo mismo que `101`, sin autocita; about/ES R@5 0.61.

**Lectura honesta:** la bajada del `gen-bench` y del `route-bench` viene de las mismas tres preguntas (about-02, about-04 y about-11). Llegaban a "about", y pasaban su filtro, gracias a la nota del historial que las citaba, y parte de los "aciertos" eran esa cita. Sin ella, su mejor fuente puntúa por debajo del umbral (−1.0), que es lo que ya señalaba DEC-38. Las cifras de `100` estaban infladas por la autocita, y las de `101` son las reales. Lo que se ve en la web (el banco abierto) mejora claramente.

**Opciones para lo que queda:**

| Opción | Pros | Contras |
|---|---|---|
| **A. Dejarlo así** ✅ (aplicada) | Sin autocita; el banco abierto, limpio | about-02, 04 y 11 en "no encontrado" si gana "about" o si es el único dominio |
| B. Recalibrar el umbral de "about" con `gate_scores` | Recuperaría esas preguntas si el reranker las puntúa por encima de lo ajeno | Sin medir. Cambia el enrutado de todos los dominios: hay que repetir el `route-bench` y comprobar que no entra nada de fuera |
| C. Volver a `100` | Las cifras de `100` | La autocita vuelve, que es lo que viste en la web |

**Por qué A y no B:** B cambia el comportamiento general (el filtro decide qué preguntas se responden en todos los dominios), y eso requiere tu permiso (`PLANING.md`). Lo dejo propuesto para la Fase 8.

**Regla a partir de ahora** (escrita en la cabecera del archivo): en los documentos indexados no se copia el texto de una pregunta de prueba sobre el proyecto ni una respuesta incorrecta; se usa el identificador y una descripción, y lo literal va al archivo.

**Reversible:** sí. Lo literal está en el archivo, y la versión anterior de los documentos, en git hasta el commit `644c455` (lo escrito en la sesión del 26 al 27 no llegó a hacerse commit con las citas).
