# Plan de trabajo — Fases 9 y 10

Documento de trabajo, **fuera del índice de "about"** (excluido en `rag.toml`, como `PLANING.md`). No se traduce. Lo que se haga en cada fase se documenta en `changelog/FASE_9.md` y `FASE_10.md`, que **sí** se indexan; allí las preguntas de prueba se citan por identificador (DEC-39).

Escrito el 2026-11-05. Fechas de referencia (noviembre de 2026):

| Fecha | Hito |
|---|---|
| Hasta el lun. **23** | **Fase 9**: repaso del proyecto, dominio de películas (`film`), web y pruebas. Todo listo para grabar |
| 23 → 27 | Grabas y envías el vídeo-demo (lo haces tú). Yo solo arreglo lo que salga al grabar |
| Tras el visto bueno | **Fase 10**: LLM externo por API key y lenguaje natural más libre |

---

## Fase 9 — Repaso, dominio `film` y web (hasta el 23)

### 9.0 — Repaso y cierre de la Fase 8 (días 1–2)

- Cerrar la Fase 8: falta el `route-bench` oficial tras el umbral −1.25 (8b), y 8c (prioridad baja). **8f (plan B del agente) pasa a la Fase 10** (decisión tuya, 2026-11-05).
- Estado limpio antes de empezar: `make bench` (42), `route-bench` y banco abierto como línea base de la Fase 9. Cualquier cambio posterior se compara con esto.
- Revisión rápida de la web en marcha: errores conocidos de `IMPORTANTE.md` que se vean en un vídeo (sobre todo el punto 8, respuesta cortada, y el 3, errores con rutas). Solo se arreglan con tu permiso.

### 9a — Ingesta de películas (días 3–9)

**Idea:** un dominio genérico `film`. El código queda en el repo para que cualquiera pruebe con sus propios ficheros; las películas y todo lo derivado viven en `data/` (ignorado por git) y se borran después de la demo.

**Banco de pruebas: Gulliver.** Ya está descargado (`data/raw/gulliver/`; SHA256 del vídeo comprobado el 2026-11-05), es de dominio público y archive.org tiene una transcripción automática para comparar. Se desarrolla y se mide con él; *El Señor de los Anillos* entra solo cuando el pipeline funciona. Así el repo tiene un ejemplo reproducible sin problemas de derechos.

**Pipeline** (offline en la 3080 Ti, con la API parada para liberar la GPU):

1. **Texto del diálogo** (decisión tuya: se ingiere todo, vídeo y subtítulos). El ingester empieza en el fichero de vídeo; sacarlo del disco lo haces tú.
   - **Subtítulos de texto** (`.srt` junto al vídeo, o pista de texto dentro del `.mkv`): se extraen con `ffmpeg`, en segundos y sin errores.
   - **Subtítulos de disco**: en DVD y Blu-ray suelen ser **imágenes** (VobSub, PGS), no texto. Opciones: OCR de esas imágenes o Whisper. Se decide al ver qué traen tus ficheros.
   - **Whisper** (`faster-whisper`, con filtro VAD contra el texto inventado en música y batallas) para lo que no tenga subtítulos. Se prueba primero con 5 minutos: calidad y velocidad.
   - Si hay subtítulos y audio, el texto de los subtítulos manda y Whisper sirve de respaldo.
2. **Fichero derivado en Markdown**, con una cabecera por ventana de tiempo (`## 00:12:30`). Es la propuesta pendiente de la 4c: el chunker actual (`markdown_headers_packed`) y el evaluador de 42 siguen funcionando con offsets de caracteres, y el timestamp sale de la cabecera. Sin mapa aparte de offsets a segundos.
3. **Metadatos de cada chunk:** película, timestamp de inicio y fin, modalidad (`transcript`, y `caption` si se hace el paso 4).
4. **Descripción de escenas (entra, decisión tuya).** Keyframes (PySceneDetect) + una descripción por fotograma con un modelo de visión pequeño, guardada como chunk `caption` con su timestamp. Así se puede preguntar por escenas, no solo por diálogos. El modelo y la frecuencia de fotogramas se eligen midiendo con Gulliver (calidad y tiempo en la 3080 Ti). Es lo que más tiempo puede llevar: si aprieta el calendario, se describen menos fotogramas, no se quita.

**En `rag.toml`:** `[sources.film]` con su raíz en `data/raw/film/`, su colección `rag_film`, su umbral propio (calibrado con `gate_scores`) y el cargador nuevo (`src/rag/sources/film.py`, como `cv.py` y `xquad.py`).

### 9b — Evaluación y router (días 10–12)

- **Set de 10–15 preguntas** por película (identificadores `F-NN`), con el timestamp correcto como ground truth. EN y ES, para medir el multilingüismo sobre audio en inglés.
- **Recall** con `bench --suite film` y **generación** con `gen-bench`.
- **`route-bench`:** 42 → vLLM al 100 %, XQuAD ~98 %, CV y "about" como hoy. Un dominio de fantasía podría robarle preguntas a XQuAD (Wikipedia); se comprueba.
- **42 no puede empeorar.**

### 9c — Web (días 12–15)

- Chip `film` y sus preguntas de ejemplo.
- **Tarjeta de fuente con el timestamp** (`película · 01:23:45`), y la miniatura del fotograma si se hace 9a.4.
- Tarjeta de recall del dominio, si hay set de evaluación.
- **Web pública (decisión tuya):** `film` se activa en la web pública solo el día de la grabación y el de la presentación. Se hace con un interruptor al arrancar (`API_DOMAINS`), sin tocar código: apagado por defecto.

### 9d — Pruebas y ensayo (días 16–18, hasta el 23)

- Probar la demo de punta a punta, en el orden en que la vas a grabar.
- Preguntas que lucen y preguntas que fallan, para que sepas qué evitar o qué explicar.
- `changelog/FASE_9.md` y traducción al inglés; reindexar "about".

### Riesgos

| Riesgo | Plan |
|---|---|
| Whisper inventa texto en música y batallas | Filtro VAD y prueba de 5 min; subtítulos si existen |
| Transcribir las tres películas lleva más de lo previsto | Se mide con Gulliver y la prueba de 5 min antes de lanzar todo; se puede empezar por una sola película |
| El dominio nuevo roba preguntas a otros | Umbral propio + `route-bench` |
| Memoria de la GPU (Whisper + modelos de la API) | La ingesta va con la API parada |
| Hay que retirar las películas después | Todo en `data/` (ignorado). Se borra con `make` + se reindexa; el código y Gulliver se quedan |

---

## Fase 10 — LLM externo y lenguaje natural (tras el visto bueno)

### 10a — LLM externo por API key

- **Por qué toca el código de generación:** `Generator` (`src/rag/generator.py`) da por hecho que el modelo está en memoria: usa su tokenizador para contar tokens y aplicar la plantilla de chat, sus tokens de parada, `generate` de transformers (con el detector de bucles y el botón Stop dentro) y el agente renderiza y lee las llamadas a herramientas como texto. Una API externa recibe directamente la lista de mensajes (que `build_messages()` ya construye), aplica su propia plantilla y devuelve el texto o las llamadas a herramientas ya estructuradas. **No se reescribe nada:** se separa una interfaz con dos implementaciones, la local (el código de hoy, movido sin cambios) y la remota. Recuperación, router, filtros, reglas de dominio, limpieza y benchmarks no se tocan. **Garantía:** la ruta local debe dar respuestas idénticas antes y después (decodificación greedy, así que es comprobable con `gen-bench`), y 42 igual.
- **Backend compatible con OpenAI** en `src/llm/`. Ya existe uno para el juez (`src/evaluation/judge.py`, Groq), así que se reutiliza. NVIDIA (build.nvidia.com), Groq y otros sirven con el mismo backend cambiando la URL, el modelo y la variable de la clave.
- **Perfil `llm-<proveedor>-<modelo>`**, igual que los locales. La base sigue siendo Qwen3-0.6B: benchmarks y 42 no cambian.
- **La clave solo en `.env`** del servidor; nunca llega al navegador.
- **Streaming** y **llamadas a herramientas nativas** para el agente.
- **A verificar antes de empezar** (no lo doy por hecho): condiciones del nivel gratuito de NVIDIA (créditos, límites por minuto, si caduca) y qué modelos ofrece.
- **Ojo con la privacidad:** con un LLM externo, los fragmentos del CV salen del ordenador hacia el proveedor (ya enmascarados). Propuesta: el CV solo con modelos locales, o aceptarlo sabiendo esto. Decisión tuya.
- **Medida:** la misma matriz de siempre (`gen-bench`, banco abierto, `agent-bench`, idioma, latencia), comparada con el 1.7B y Granite.

### 10b — Lenguaje natural más libre

El problema: la gente pregunta como a un chatbot y choca con las reglas pensadas para el benchmark. Propuestas, cada una medida por separado:

1. **Charla y preguntas sobre el asistente** (saludos, gracias, "qué puedes hacer") con una respuesta propia, sin pasar por la búsqueda ni el filtro.
2. **"No encontrado" más útil:** decir qué dominios hay y sugerir preguntas, en lugar de un rechazo seco.
3. **Reglas del prompt por modelo:** más libertad con los modelos grandes y el externo (S5 de 8g ya está lista); el 0.6B se queda como está.
4. **Plan B del agente (8f):** buscar con la mezcla y responder solo a la pregunta original.

**Tipo de pregunta (tú, 2026-11-05):** preguntas vagas sobre el propio asistente ("qué eres", "para qué sirves"). **Norma: nada de pistas nuevas en el prompt ni de frases fijas** (las trampas que se quitaron en DEC-33). Caminos generales, a medir:

- **Que el modelo interprete la pregunta antes de buscar** (solo modelos medianos y el externo): reescribirla en una consulta concreta, o pedir una aclaración si es ambigua. Es lo que ya hace el paso de reescritura del agente, sacado también al modo directo.
- **Enrutar por significado y no por palabras:** comparar la pregunta con la `description` de cada dominio usando los embeddings que ya se calculan. Una pregunta sobre el asistente se parece a la descripción de "about" sin necesidad de listar frases. Encaja con el clasificador semántico pendiente de `PLANING.md`.
- **Con el 0.6B, sin cambios:** es la base de las comparativas con 42 y ahí no se espera que lo resuelva.

---

## Reglas de siempre

- 42 no empeora (`make bench` al cerrar cada bloque). Prioridad R@5 > R@10 > R@3 > R@1.
- Cada cambio se mide por separado; si empeora algo, no se adopta sin tu decisión.
- Sin commits ni push salvo que lo pidas. `llm_sdk/` no se toca.

## Preguntas abiertas

1. **Ficheros de ESDLA:** lo estás buscando (probablemente de los discos originales). Cuando los tengas: formato, pistas de subtítulos (texto o imagen) e idiomas del audio. Mientras tanto se avanza con Gulliver.
2. ~~Descripción de escenas~~ → entra.
3. ~~`film` en la web pública~~ → sí, solo los días de grabación y presentación.
4. ~~¿8f pasa a la Fase 10?~~ → sí.
5. ~~Dónde se graba~~ → web pública.
