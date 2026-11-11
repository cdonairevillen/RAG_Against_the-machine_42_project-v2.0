# CHANGELOG — Fase 9: repaso, dominio de películas y web

Fase abierta el 2026-11-05. Objetivo: un dominio genérico `film` que ingiere películas (diálogo y escenas) y responde con el minuto exacto, más su reflejo en la web, para la demo. Aquí se apunta qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`. Las preguntas de prueba se citan por identificador (DEC-39).

## Estado

| Bloque | Estado |
|---|---|
| 9.0 — Repaso y línea base | 🟡 En curso: mediciones base lanzadas (`140`) |
| 9a — Ingesta de películas | 🟡 Módulo hecho; Shrek y Shrek 2 con diálogo y planos; descripciones de escena en curso |
| 9b — Evaluación y router | 🟡 14 preguntas de diálogo; faltan las de escenas, el umbral y el `route-bench` |
| 9c — Web | 🟡 Reproductor del fragmento y `API_SHOW=film`; faltan las preguntas de ejemplo |
| 9d — Pruebas y ensayo | Sin empezar |

## Decisiones tuyas (2026-11-05)

- **8f (plan B del agente) pasa a la Fase 10**, junto al trabajo de lenguaje natural.
- **Se ingiere todo**: vídeo y subtítulos. Las películas salen de tus discos originales; el ingester empieza en el fichero de vídeo.
- **Escenas: entran.** Se podrá preguntar por lo que se ve, no solo por lo que se dice.
- **Web pública:** el dominio `film` estará activo en la web pública solo el día de la grabación y el de la presentación. Los derechos no preocupan: las películas se retiran después. El código queda en el repo para que cualquiera pruebe con sus propios ficheros. **La web no reproduce el vídeo:** las tarjetas de fuente muestran la película y el minuto, sin servir el fichero.
- **Dependencias:** grupo opcional `film` en `pyproject.toml` (`faster-whisper`, `scenedetect`); la instalación base no cambia.
- **Whisper:** `large-v3-turbo`, pero se mide también `large-v3` con la prueba de 5 minutos y se decide con los tiempos. El tiempo de ingesta no importa (no se hace en directo).
- **Modelo de visión:** se comparan Qwen3-VL-2B y Florence-2 con Gulliver.
- **Formato:** un `.md` por película, con una sección por escena (`## 00:12:30`) que reúne el diálogo y la descripción visual.
- **Calendario:** se intenta acortar para empezar antes la Fase 10.

## 9.0 — Repaso y línea base

Mediciones antes de tocar nada, con la configuración de hoy:

| Medición | Etiqueta | Resultado |
|---|---|---|
| `make bench` (42) | `140-fase9-base` | **Idéntico a `97-final`**: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88. Latencia 265 / 438 ms (antes 6 / 15): **no comparable**, la API estaba abierta y compartía la GPU |
| `route-bench` oficial (pendiente desde 8b) | `140-route` | Frente a `102`: 42 al 100 % a vLLM en docs y code (antes, una de code iba a "about"); XQuAD igual; CV 29/30 en EN y ES (antes ES 27/30); "about" EN 15/18 (antes 14), ES 16/18 (antes 17) |
| `gen-bench` de "about" con el 0.6B (pendiente desde 8b) | `140-about` | Frente a `102`: contiene la respuesta EN 0.56 (antes 0.50), ES 0.50 (igual); falsos "no encontrado" EN 0.11 (antes 0.17), ES 0.11 (igual); citas correctas ES 0.27 (antes 0.40), EN 0.25 (antes 0.23). Son 18 preguntas por idioma: la bajada de ES equivale a 2–3 preguntas |
| Banco abierto con el 1.7B (modelo de la web) | `140-open` | Frente a `130`: 33/34 contestadas (antes 29/34); 0 cortes, eco o bucles; **2 respuestas con alguna frase repetida** (antes 0), a revisar |

**Nota:** todo se midió con la API pública abierta en la misma GPU. Los resultados son válidos (búsqueda y generación deterministas), pero las latencias no: el `route-bench` tardó 8,5 h (~9 s por pregunta). A partir de aquí, la API se cierra durante las mediciones largas y se vuelve a abrir al acabar (autorizado por ti).

## 9a — Ingesta de películas

**Banco de pruebas: Gulliver** (1939, dominio público en EE. UU.), ya descargado en `data/raw/gulliver/` y con el SHA256 del vídeo comprobado (2026-11-05). Se añade la transcripción automática que publica archive.org (`GulliversTravels.asr.srt`, 19 963 bytes) como referencia: es de muy mala calidad (frases sueltas e inventadas al principio), así que solo sirve para comparar a ojo.

### Dependencias (grupo opcional `film`)

- **`faster-whisper` 1.2.1**, instalado con `uv sync --extra film`. No cambia ninguna versión de lo que ya estaba instalado (comprobado en el diff de `uv.lock`). Trae PyAV con ffmpeg dentro, así que en Windows no hace falta instalar ffmpeg.
- **`av<17`**: PyAV 19 quitó el argumento `metadata_errors` que usa `faster-whisper` 1.2.1 al leer el audio (`TypeError`). Con 16.1.0 funciona.
- **CUDA en Windows:** CTranslate2 (el motor de `faster-whisper`) no encontraba `cublas64_12.dll`. torch ya la trae (`torch/lib`), así que se añade esa carpeta a las rutas de DLL antes de cargar Whisper. Sin instalar CUDA aparte.
- **`scenedetect`, sin instalar (pendiente de tu decisión):** depende de `opencv-python`, y el proyecto ya tiene `opencv-python-headless`. Los dos instalan el mismo módulo `cv2` y se pisan.

### Prueba de Whisper: 5 minutos de Gulliver (00:15:00–00:20:00, 3080 Ti, API cerrada)

Script: `data/output/fase9/whisper5.py` (ignorado por git). Mismo audio, filtro VAD y `beam_size=5`.

| Modelo | Carga | Transcripción | Velocidad | Segmentos | Película entera (76 min), estimado |
|---|---|---|---|---|---|
| `large-v3-turbo` | 2.0 s | 1.5 s | 197× tiempo real | 14 | ~25 s |
| `large-v3` | 44.3 s (primera descarga incluida) | 2.7 s | 110× tiempo real | 2 | ~45 s |

**Lectura:**
- **Texto:** muy parecido y bueno en los dos. `large-v3` acierta algún detalle más (*"Be off with you"* frente a *"Be off of you"*, *"wait"* frente a *"weight"*) y recoge un *"shoo, shoo…"* que turbo omite.
- **Marcas de tiempo:** turbo da frases sueltas con su minuto; `large-v3` junta 3 minutos en un solo segmento (00:15:01–00:18:17) y se deja la última frase (00:18:37). Para responder con el minuto exacto, eso importa. Se podría corregir pidiendo marcas por palabra (`word_timestamps`), sin medir aún.
- **Música:** los dos dejan sin texto un tramo de ~2 min (00:15:56–00:18:18 en turbo). Lo que se ve en ese tramo lo cubrirán las descripciones de escenas.
- **Tiempo:** irrelevante en los dos. Las tres películas de ESDLA (~9–11 h) llevarían unos minutos con cualquiera.

### Películas de la demo (2026-11-11)

Las elegiste tú: **Shrek (2001)** (90.1 min) y **Shrek 2 (2004)** (92.4 min), 720p con `.srt` en inglés (1 471 y 1 381 líneas, sin líneas de publicidad). El vídeo no lleva pistas de subtítulos, y el audio es solo en inglés. Están en `data/raw/film/` (DEC-43).

### El módulo (`src/rag/sources/film.py`)

Una carpeta por película → un `.md` con una sección por tramo (`## 00:12:30 - 00:13:05`), con la descripción de la escena y el diálogo que se dice en él. El chunker de Markdown y los offsets del evaluador funcionan sin cambios. Pasos, cada uno guardado en `data/film/.work/` para no repetirlo:
1. **Diálogo** (DEC-40): `.srt` → pista de texto del vídeo → Whisper.
2. **Planos** (DEC-41): cortes por histograma de color, un fotograma por plano (y uno cada 20 s en los planos largos).
3. **Escenas** (DEC-42): descripción de cada fotograma con Qwen3-VL-2B.
4. **Markdown:** planos agrupados en tramos de al menos 30 s.

**Detección de planos en Gulliver:** 425 planos y 493 fotogramas en 14 s de CPU. Revisados 16 seguidos: todos son planos distintos.

### Comparación de los modelos de visión (40 fotogramas de Gulliver, API cerrada)

| | Qwen3-VL-2B | Florence-2-large |
|---|---|---|
| Velocidad | 0.46 s/fotograma | 0.29 s/fotograma |
| Lo que se ve | Correcto (el rey con bigote, la chica con los pájaros, el chico con la antorcha) | Errores: un rey como "Simba", un teléfono que no está |
| Texto en pantalla | Bien leído (el contrato de boda de Liliput, con fecha) | Con errores ("Ring Little of Billiput") |
| Fallo común | Se inventa el título de la película y se alarga | Igual, peor |

**Elegido:** Qwen3-VL-2B (DEC-42). **Ajuste:** el prompt prohíbe nombrar la película y los personajes, y cada descripción se recorta en su última frase completa.

**Incidencia:** la primera descarga de Qwen3-VL-2B falló al cargar el tokenizador porque tenías una VPN activa. Sin ella, bajó bien.

**Prompt corregido, comprobado con los mismos fotogramas:** ninguna descripción nombra ya una película; todas en dos frases o menos, y el texto en pantalla se sigue leyendo (el contrato de boda de Liliput, con los nombres de los novios).

### Shrek y Shrek 2, sin descripciones (CPU)

`make film SCENES=0`: diálogo de los `.srt` y detección de planos.

| Película | Diálogo | Planos | Fotogramas | Secciones en el `.md` |
|---|---|---|---|---|
| Shrek (2001) | 1 471 líneas (`srt`) | 959 | 1 009 | 139 |
| Shrek 2 (2004) | 1 381 líneas (`srt`) | 926 | 992 | 133 |

**Limitación:** los subtítulos no dicen quién habla, así que las preguntas de "quién dijo…" dependen de que el nombre salga en la propia frase o en las vecinas.

### Integración en el proyecto

| Pieza | Qué hace |
|---|---|
| `make film` (`prepare_film` en la CLI) | Construye los `.md`. `FILM="Shrek (2001)"` rehace una sola; `SCENES=0` se salta las descripciones (sin GPU). Usa `--extra film` |
| `[sources.film]` en `rag.toml` | Raíz `data/film`, chunker de Markdown, `.work` excluido, `web = false`. Umbral propio: pendiente de calibrar |
| `web` en `SourceConfig` | Campo nuevo, `true` por defecto (ningún dominio existente cambia). Con `false`, la API no lo sirve aunque esté indexado |
| `API_SHOW` en el `Makefile` | `make api-public API_SHOW=film` enciende las películas en la web (los días de la demo). Sin él, la web es la de siempre |
| Fuentes de `film` en la API | Título con la película y el minuto (`Shrek (2001) · 00:27:03`) y un campo `clip` (película, inicio y fin) |
| `GET /film/{id}/video` (DEC-44) | Sirve el vídeo por identificador, solo con `film` activo, con peticiones por rangos (Starlette `FileResponse`) |
| Web | Botón "▶ play this scene" en las tarjetas de `film`: reproductor que empieza en el minuto de la fuente y para al final (`#t=inicio,fin`). Solo aparece en fuentes de `film` |
| `bench/datasets/film/` | 14 preguntas sobre el diálogo (`film-01` a `film-14`), en inglés y español; `build_film_bench` localiza cada evidencia en el `.md`. **Ignorado por git** (cita las películas) |
| Benchmarks | Suite `film` en `bench` y `gen-bench`; `route-bench` añade `film/en` y `film/es` solo si el dominio está indexado y sus datasets existen |
| `tests/test_film.py` | 6 tests de las partes sin vídeo ni GPU: subtítulos, tiempos, identificadores, recorte de descripciones y agrupación en secciones |

**Comprobado:** 141 tests pasan (135 + 6); flake8 y mypy sin errores; la web compila. En este Windows, `make test` y `make lint` no arrancan porque Control de aplicaciones bloquea los `.exe` de `pytest` y `flake8`; con `python -m pytest` y `python -m flake8` funcionan.

### Descripciones de escena de Shrek y Shrek 2 (API cerrada)

`make film`: 2 001 fotogramas descritos con Qwen3-VL-2B en 13 min 55 s. `make index SOURCE=film` (con todas las descripciones): 431 padres y 1 681 hijos. Las descripciones leen el texto en pantalla (los créditos, la página del libro del principio) y a veces inventan detalles; en los logos del principio, más.

## 9b — Evaluación del dominio `film`

**Primera medida** (`141`, 14 preguntas de diálogo): EN 0.21 / 0.43 / 0.50 / 0.64, ES 0.07 / 0.29 / 0.36 / 0.43. Al revisar los fallos, parte eran de mi ground truth:
- **film-01:** "ogres are like onions" se dice dos veces; el buscador encontraba la primera y la evidencia era la segunda. Corregida a la primera.
- **film-07 y film-11:** las dos películas empiezan con el cuento de la princesa y el beso, así que la pregunta era ambigua. Ahora nombran la película.

**Aclaración (pregunta tuya):** el recall no depende del LLM. Mide la búsqueda (BM25, `bge-m3` y el reranker); un LLM más grande mejora la respuesta, no estas cifras.

**Métrica añadida** (como en "about", `data/output/fase9/film_contains.py`): si el texto de la respuesta aparece en las 5 primeras fuentes. Es lo que ve quien usa la demo, y no castiga encontrar la misma frase en otro tramo.

### Cuánta descripción cabe en cada tramo (tras corregir el ground truth)

| Variante del `.md` | Fragmentos (padres / hijos) | EN R@1/3/5/10 | ES R@1/3/5/10 |
|---|---|---|---|
| Todas las descripciones, 2 frases (`142`) | 431 / 1 681 | 0.36 / 0.57 / 0.57 / 0.71 | 0.00 / 0.29 / 0.36 / 0.50 |
| Solo diálogo (`143`) | 75 / 288 | 0.50 / 0.71 / 0.71 / 0.93 | 0.00 / 0.14 / 0.14 / 0.36 |
| Hasta 3 por tramo, 1 frase (`144`) | 136 / 513 | 0.43 / 0.57 / 0.57 / 0.93 | 0.00 / 0.07 / 0.21 / 0.43 |

Con todas, el diálogo queda ahogado (un tramo de 30 s llevaba hasta 8 descripciones, ~1 500 caracteres). Se queda la tercera (`SCENES_PER_SECTION = 3`: los planos más largos, su primera frase), que mantiene las escenas y recupera el inglés. Con 14 preguntas, cada una vale 0.07.

### El reranker en la rama de documentos

En las preguntas de documentación el reranker no se usa (`rerank_doc_branch = false`, Fase 2: empeoraba los docs de vLLM), y `film` es todo documentos. Por eso el perfil `gpu-quality` daba exactamente lo mismo (`145`). Con el reranker encendido en esa rama:

| Variante (3 descripciones por tramo) | EN R@1/3/5/10 | ES R@1/3/5/10 | Respuesta en top 5 (EN / ES) |
|---|---|---|---|
| Sin reranker en documentos (`144`) | 0.43 / 0.57 / 0.57 / 0.93 | 0.00 / 0.07 / 0.21 / 0.43 | 11 / 4 |
| + `mmarco` (el actual, `146`) | 0.29 / 0.57 / 0.64 / 0.86 | 0.07 / 0.21 / 0.36 / 0.71 | 11 / **9** |
| + `bge-reranker-v2-m3` (`147`) | 0.43 / 0.79 / 0.79 / 0.93 | 0.29 / 0.43 / 0.57 / 0.79 | **12** / **9** |

**Comprobado:** 42 idéntico con el cambio (`148-vllm-check`: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88).

**Aplicado:** campo nuevo `rerank_doc_branch` por fuente (como `relevance_threshold`), encendido solo en `film` con el reranker actual (`148`: idéntico a `146`). Los demás dominios no cambian. El reranker grande queda propuesto (DEC-48): mejora más, pero es un segundo modelo en la GPU.

### Umbral de `film` (`149-film-gate`, 40 preguntas por grupo)

Primera prueba en la web: una pregunta de diálogo daba "not found" porque `film` usaba el umbral global (0.0), que rechaza el 71 % de sus preguntas. Proporción que pasa el filtro de `film` con cada umbral:

| Grupo | −4.0 | −3.5 | **−3.0** | −2.5 | −2.0 |
|---|---|---|---|---|---|
| film/en (deben pasar) | 0.79 | 0.79 | **0.79** | 0.71 | 0.43 |
| film/es (deben pasar) | 0.93 | 0.86 | **0.71** | 0.64 | 0.57 |
| xquad/es (no deben) | 0.62 | 0.57 | **0.45** | 0.15 | 0.03 |
| cv/es (no deben) | 0.53 | 0.47 | **0.23** | 0.13 | 0.03 |
| es/docs (vLLM, no deben) | 0.50 | 0.40 | **0.20** | 0.20 | 0.10 |
| Fuera de dominio cercanas (ES) | 0.70 | 0.60 | **0.60** | 0.40 | 0.30 |
| 42 docs y code, XQuAD/EN, CV/EN, about | ≤ 0.12 | ≤ 0.10 | **≤ 0.03** | 0 | 0 |

**Elegido: −3.0** (como el CV). Las preguntas en español puntúan alto en todos los dominios; pasar el filtro de `film` no basta para responder desde él, porque el router elige el dominio con mejor puntuación. El `route-bench` (`150`) dirá cuántas preguntas de otros dominios acaban en `film`, y el `gen-bench` cómo responde.

### Qdrant lento desde Python: `localhost` → `127.0.0.1` (DEC-49)

El `route-bench` de la noche (`150`) iba a 13 s por pregunta con la API cerrada y la GPU al 2 %. Perfilada una búsqueda: 12.4 de 13.1 s eran 6 consultas a Qdrant de 2.05 s cada una. En Windows, `httpx` prueba IPv6 primero con `localhost` y espera ~2 s. Medido: 2.21 s frente a 0.03 s con `127.0.0.1`. Ya pasaba el 2026-11-05 (el `140` tardó 8.5 h). **Arreglado en `rag.toml` y en el valor por defecto de `src/config.py`**; también acelera la web. El `150` se paró y se relanzó como `151`.

**Noche interrumpida:** al parar el `150`, su script siguió con los `gen-bench` mientras arrancaba el `151`; con dos procesos en la GPU, el 1.7B iba a ~380 s por pregunta. A las 03:59 Windows Update reinició el equipo (KB5132061, reinicio planeado, sin fallo). Se repitió todo por orden el 2026-11-11 por la mañana: 25 min en total.

### Route-bench con `film` (`151`, frente a `140`)

| Set | `140` (sin `film`) | `151` (con `film`, −3.0) |
|---|---|---|
| 42 docs / code | 100 % / 100 % a vLLM | **igual** (0.76 / 0.91 / 0.92 / 0.94 y 0.51 / 0.72 / 0.80 / 0.88) |
| es/docs, es/code, CV, about | — | **igual** |
| xquad/en | 1 167 a xquad | 1 167 (1 pregunta pasa de vLLM a `film`) |
| xquad/es | 1 160 a xquad (0.975) | **1 152 (0.968)**: 10 van a `film` (8 salen de xquad) |
| film/en | — | 12 / 14 a `film` (2 a xquad); R@5 0.57 |
| film/es | — | 12 / 14 a `film` (2 a vLLM); R@5 0.29 |

El coste del umbral: 8 de 1 190 preguntas de XQuAD en español (−0.7 puntos). Nada más cambia.

**Decisión tuya (2026-11-11):** se acepta −3.0. XQuAD **deja de ser prioridad**: se mantiene indexado y medido, pero sus pérdidas pequeñas no bloquean cambios en otros dominios. La comparación entre dos idiomas se hará con "about" y el CV (datos no estructurados, más cercanos a un caso real). Quitar XQuAD queda como opción, sin decidir.

### Generación de `film` (`151`, 14 preguntas por idioma)

| Modelo | Contiene la respuesta EN / ES | "Not found" en falso EN / ES | Idioma EN / ES | Latencia EN / ES |
|---|---|---|---|---|
| Qwen3-0.6B (`151-film-q06`) | 0.36 / 0.07 | 0.21 / 0.29 | 0.91 / 0.80 | 1.1 / 1.6 s |
| Qwen3-1.7B (`151-film-q17`, el de la web) | 0.43 / 0.29 | 0.21 / 0.29 | 1.00 / 1.00 | 1.0 / 1.3 s |

Los "not found" en falso son todos sin la respuesta en el contexto (columna "with answer in ctx" a 0.00): fallos de búsqueda o de enrutado, no del LLM. El `150-film-q06` (anoche) da las mismas cifras de calidad que el `151`.

### `film` sin BM25 en la rama de documentos (`152`)

El corpus de `film` es todo inglés. Posición de la respuesta por lista (`film_ranks.py`, `152-ranks`; respuesta entre las 5 primeras, de 14):

| Lista | EN | ES |
|---|---|---|
| BM25 solo | 10 | **0** |
| Embeddings (`bge-m3`) solos | 11 | **11** |
| BM25 + embeddings (RRF) | 11 | 5 |
| Final (con el reranker) | 11 | 9 |

BM25 no encuentra nada con palabras en español y su lista enterraba los aciertos de los embeddings en la fusión. Simulado (`film_variants.py`): embeddings + reranker (RRF, 15 candidatos) da **12 / 12**; el reranker grande (DEC-48) daba 12 / 9.

**Aplicado:** campo `bm25_in_doc_branch` por fuente (por defecto `true`), `false` solo en `film`. Medido:

| | Antes (`148`/`151`) | Sin BM25 (`152`) |
|---|---|---|
| `film` R@1/3/5/10 EN (route-bench) | 0.21 / 0.50 / 0.57 / 0.71 | **0.29 / 0.57 / 0.64 / 0.71** |
| `film` R@1/3/5/10 ES (route-bench) | 0.07 / 0.14 / 0.29 / 0.57 | **0.14 / 0.50 / 0.57 / 0.71** |
| Respuesta en las 5 primeras EN / ES | 11 / 9 | **12 / 12** |
| xquad/es a su dominio | 1 152 | **1 156** (5 a `film`, antes 10) |
| 42 | — | **idéntico** (`152-vllm-check`) |
| `gen-bench` 0.6B, contiene EN / ES | 0.36 / 0.07 | 0.43 / 0.00 |
| `gen-bench` 1.7B, contiene EN / ES | 0.43 / 0.29 | 0.36 / 0.21 |

La búsqueda mejora, la generación no. Diagnóstico (`film_gate_check.py`): con o sin BM25, la respuesta llega al modelo **y pasa el filtro** en 9–10 / 14 (EN) y 7 / 14 (ES). El cuello de botella es el filtro: el reranker puntúa bajo los tramos correctos con preguntas en español (−3.3 a −3.7, umbral −3.0). Con 14 preguntas, cada una vale 0.07: la bajada del `gen-bench` está en el ruido. **Propuesta:** mantenerlo y recalibrar el umbral tras el enriquecimiento (cambiará las puntuaciones). Pendiente de tu decisión.

### Contexto en orden de película (A, `153`)

Campo `chronological_context` por fuente (solo `film`): las fuentes que pasan el filtro se ordenan por película y posición (el tiempo) antes de numerarlas [1]…[n]; cada tramo lleva su minuto en la cabecera. Se aplica en el flujo directo y en el del agente.

| `gen-bench` (contiene EN / ES) | Sin orden (`152`) | Con orden (`153`) |
|---|---|---|
| 0.6B | 0.43 / 0.00 | 0.29 / 0.00 |
| 1.7B | 0.36 / 0.21 | **0.57** / 0.14 |

Mixto y dentro del ruido: el 1.7B gana 3 preguntas en inglés y pierde 1 en español; el 0.6B pierde 2 en inglés. Las 14 preguntas son de diálogo directo, donde el orden apenas importa; la A apunta a las preguntas de "primera vez" y de secuencia (film-15 a film-22, propuestas). Se decide con ellas.

### Preguntas nuevas: personajes, "primera vez" y visuales (`154`, `155`)

**Aprobado por ti:** se mantiene `bm25_in_doc_branch = false` en `film`. Set ampliado a 22 preguntas por idioma (film-15 a film-22, con menos peso en Asno y el Gato, a petición tuya): primera aparición de Asno y del dragón, DuLoc, quién es el Gato con Botas, el pantano de Shrek, el secreto de Fiona, el color del dragón y la madre del Príncipe Encantador. La prueba de film-15 es la primera frase de Asno (tramo 00:04:49, confirmado por ti); la respuesta "00:05" vale para esa escena.

Recuperación (22 preguntas): EN 0.23 / 0.41 / 0.55 / 0.77, ES 0.14 / 0.36 / 0.50 / 0.59; respuesta entre las 5 primeras en 15 / 22 en los dos idiomas. De las nuevas, solo encuentra DuLoc, el color del dragón y la madre de Encantador; fallan las de "primera vez", "quién es el Gato", el pantano y el secreto de Fiona, como se esperaba.

**La A con las 22 preguntas** (contiene la respuesta, EN / ES):

| Modelo | Sin orden | Con orden de película |
|---|---|---|
| 0.6B | 0.27 / 0.05 | 0.23 / 0.05 |
| 1.7B (el de la web) | 0.23 / 0.18 | **0.41** / 0.14 |

El 1.7B gana 4 preguntas en inglés y pierde 1 en español; las citas correctas suben en español (0.75 → 0.88). El 0.6B pierde 1. **Se mantiene encendida** (`chronological_context = true`); no resuelve las preguntas de "primera vez", que siguen esperando al enriquecimiento.

### Enriquecimiento: resúmenes de escena y fichas de personaje (`156`–`163`, DEC-50 a DEC-54)

Opción C de las causas de abajo, decidida contigo: ventanas de 3 minutos y dos capas (resúmenes de escena y fichas de personaje). Código en `src/rag/sources/film_enrich.py`, `make film-enrich` (`ENRICH_PROVIDER=nvidia` para la API). Se añade al final del `.md` de cada película, sin mover los tramos (las pruebas del benchmark siguen valiendo); las cabeceras de los resúmenes llevan su rango de tiempo, así que la web reproduce su clip.

**Ejecuciones:**
1. **Qwen3-4B, primera (`156`):** bucle en la lista de personajes ("Man in Medieval Clothing" decenas de veces) y fichas de "Princess" o "Knight". Parada.
2. **Qwen3-4B, segunda (`157`):** sin bucles, pero con errores que confirmaste: el Hada Madrina como madre de Fiona, Harold confuso, Pinocho "central character", fichas vacías de Lillian y Gingy, una ficha de "Dad", el Gato duplicado y la primera aparición de Asno en el minuto 13.
3. **Nemotron 3.5 Lightning por la API (`158`, `159`, DEC-50):** tus correcciones salen bien (Encantador hijo del Hada Madrina, Lillian madre de Fiona, Harold padre de Fiona, Gingy la galleta). Asno, primera mención en 00:03:07–00:06:26 (su primera frase es a las 4:49). 3 min 50 s, sin GPU.

**Reglas del código** (DEC-51): un nombre solo cuenta si está en el texto de su ventana; fuera los cargos y nombres comunes; los alias se unen ("Puss" → "Puss In Boots"); las menciones las busca el código, así que la ficha dice "First mentioned in the scene…"; la ficha se escribe también con las líneas de diálogo que nombran al personaje. **Nombre en español dado por el modelo** (DEC-52): falla en Asno (da "Burro").

**Medidas** (umbral −2.0, DEC-53):

| | Antes (`154`/`155`) | Con enriquecimiento (`160`–`163`) |
|---|---|---|
| R@1/3/5/10 oficial EN | 0.23 / 0.41 / 0.55 / 0.77 | 0.00 / 0.05 / 0.27 / 0.41 |
| R@1/3/5/10 oficial ES | 0.14 / 0.36 / 0.50 / 0.59 | 0.05 / 0.14 / 0.27 / 0.41 |
| **R@k con cualquier fuente válida EN** | (= oficial) | **0.45 / 0.68 / 0.82 / 0.91** |
| **R@k con cualquier fuente válida ES** | (= oficial) | **0.41 / 0.64 / 0.77 / 0.91** |
| Filtro: preguntas de `film` que pasan (EN / ES) | 0.79 / 0.71 (−3.0) | **0.91 / 0.91** (−2.0) |
| 0.6B contiene / "not found" en falso (EN) | 0.23 / 0.32 | **0.50 / 0.09** |
| 0.6B contiene / "not found" en falso (ES) | 0.05 / 0.27 | **0.27 / 0.09** |
| 1.7B contiene / "not found" en falso (EN) | 0.41 / 0.27 | **0.59 / 0.14** |
| 1.7B contiene / "not found" en falso (ES) | 0.14 / 0.27 | **0.27 / 0.23** |
| `film` a su dominio (route-bench) | 12 / 14 | **21 / 22** (EN y ES) |
| XQuAD a su dominio EN / ES | 1 167 / 1 156 (`152`) | 1 164 / 1 153 (`162`) |
| 42, CV, "about" | — | **idénticos** (`161-vllm-check`, `162`) |

**Error mío** (DEC-54): un `sed` cambió también el umbral del CV durante el `route-bench` `161`; se paró, se restauró y se repitió (`162`).

**Pruebas en la web (2026-11-11, 1.7B):**
- "Donkey, first appear" → "the scene 00:03:07 - 00:06:26" ✅
- "¿Quién es Farquaad?" → el antagonista, gobernante de DuLoc ✅ (antes lo describía como un ogro verde). Añade "El nombre español de Farquaad es…", sobrante.
- "Who is Prince Charming's mother?" → el Hada Madrina ✅
- "¿Quién es Lillian?" → la reina, madre de Fiona ✅
- "¿Quién es el Gato con Botas?" → "un gato de pelaje marrón" en *Shrek 2*: pobre, no dice que lo contrataron para matar a Shrek.
- "¿Cuándo aparece Asno por primera vez en Shrek?" → "no aparece en las fuentes" ❌: el corpus dice "Donkey" y la ficha "Burro" (DEC-52).

### Causas de los fallos de razonamiento (pregunta tuya)

Ejemplos tuyos: "¿cuándo es la primera aparición de Asno?" y "¿quién es el Gato con Botas?". La información está en el índice (Asno, tramo 00:05:20 de *Shrek*; el Gato, 00:34:31 de *Shrek 2*). Causas:
1. **"La primera vez" es una agregación:** el RAG ve 5 tramos, no puede saber que no hay uno anterior. Ningún modelo lo arregla solo.
2. **Los subtítulos no dicen quién habla.**
3. **Las descripciones no nombran a los personajes** ("a grey donkey", "a ginger cat with a black hat").
4. **"¿Quién es X?" pide unir varios tramos**, lo que peor hacen los modelos pequeños.
5. **Nombres en otro idioma** (Asno / Donkey, Gato con Botas / Puss in Boots): resuelto en parte por `152`.

Opciones valoradas: A (orden de película, hecha), C (resúmenes por personaje y escena generados offline, siguiente paso), traducir la pregunta o una herramienta de búsqueda por tiempo en el agente (Fase 10), diarización y reconocimiento de personajes (coste alto).

## Ficheros cambiados

| Fichero | Cambio |
|---|---|
| `docs/es/PLAN_FASES_9_10.md` | Nuevo: plan de las Fases 9 y 10. Fuera del índice de "about" |
| `rag.toml` | `PLAN_FASES_9_10.md` excluido de "about" (como `PLANING.md`) |
| `docs/es/ROADMAP.md`, `docs/es/changelog/FASE_8.md` | 8f pasa a la Fase 10 |
| `pyproject.toml`, `uv.lock` | Grupo opcional `film`: `faster-whisper`, `av<17`. La instalación base no cambia |
| `src/rag/sources/film.py` | Nuevo: el ingester de películas, el clip de cada fuente y el builder del benchmark |
| `src/cli.py` | `prepare_film` y `build_film_bench` |
| `src/config.py` | Campo `web` de cada fuente |
| `src/api/app.py` | `web_domains()` (`RAG_API_SHOW`), `film_clip()` en las fuentes y `GET /film/{id}/video` |
| `src/evaluation/bench.py`, `gen_bench.py`, `routing.py` | Suite `film` |
| `rag.toml` | `[sources.film]` |
| `Makefile` | `make film` (`FILM`, `SCENES`) y `API_SHOW` |
| `.gitignore` | `bench/datasets/film/` |
| `web/src/api.ts`, `App.tsx`, `index.css` | Reproductor del fragmento en las tarjetas de `film` |
| `tests/test_film.py` | Nuevo |
| `docs/es/decisions.md` | DEC-40 a DEC-44 |
| `src/config.py`, `src/rag/retriever.py`, `rag.toml` | `bm25_in_doc_branch` (global y por fuente), `false` en `film` |
| `src/config.py`, `src/rag/domain_rules.py`, `src/rag/pipeline.py`, `src/agent/agent.py`, `rag.toml` | `chronological_context` por fuente (`context_order`), `true` en `film` |
| `tests/test_config.py`, `tests/test_domain_rules.py` | Tests de los dos campos |
| `src/rag/sources/film_enrich.py` | Nuevo: enriquecimiento (resúmenes de escena y fichas de personaje), generador local y por API compatible con OpenAI |
| `src/rag/sources/film.py` | `enrich()`, `transcript_sections()`, `enrichment_text()` (la caché más reciente), cabecera de resumen en `SECTION_HEADER`, `valid_sources()` |
| `src/cli.py`, `Makefile` | `enrich_film` / `make film-enrich` (`FILM`, `ENRICH_MODEL`, `ENRICH_PROVIDER`) |
| `src/evaluation/bench.py` | `recall_any`: R@k con cualquier fuente válida (solo si existe `valid_sources.json`) |
| `rag.toml` | `film`: `relevance_threshold = -2.0`; `LLM_EXTERNO.md` fuera de "about" |
| `tests/test_film.py` | Tests del enriquecimiento y de las fuentes válidas |
| `docs/es/LLM_EXTERNO.md` | Nuevo: requisitos, modelos de NVIDIA probados y lo que tienes que hacer tú |
| `docs/es/decisions.md` | DEC-49 a DEC-54 |

