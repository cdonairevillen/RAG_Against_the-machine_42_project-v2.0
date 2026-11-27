# CHANGELOG — Fase 10: LLM externo, agentes y cierre

Fase abierta el 2026-11-25, tras el visto bueno del vídeo-demo. Objetivo: un LLM externo por API (gratis) junto a los modelos locales, mejorar los agentes, una tercera película (*El método*), los retoques de cada dominio y la documentación final. Aquí se apunta qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`. Las preguntas de prueba se citan por identificador (DEC-39).

## Estado

| Bloque | Estado |
|---|---|
| 10a — Backend externo | ✅ Hecho y comprobado: la ruta local da las mismas respuestas. Matriz de Lightning y Bolt (`180`, `181`) hecha salvo el `agent-bench`; Gemini 3.5 Flash-Lite añadido y medido (`182`) |
| 10b — *El método* (2005) | ✅ Ingerida, enriquecida en español e indexada; 9 preguntas nuevas (`174`) |
| 10c — "About": código + README + benchmark | ✅ Adoptada (opción B, `172`, `173`) y sección "Key decisions" en los dos README |
| 10d — Web con dos modos (local / externo) | 🟡 Implementada y probada de punta a punta; pendiente de tu revisión (modo, modelo y agente por defecto) |
| 10e — Preguntas sobre el sistema y las películas | ✅ Sección en los README, títulos de película en el router y sinopsis (`183`, `185`) |
| 10e bis — Agentes con el modelo externo y plan B (8f) | ✅ Medidos todos (`186`–`191`). Plan B descartado (DEC-64); el agente responde a la pregunta del usuario y no a su reescritura en Lightning, Gemini y Granite (DEC-63) |
| 10h — Noche del 26 al 27: batería con todos los modelos | ✅ Ver §10h |
| 10f — Retoques por dominio | Sin empezar (pendiente de tu lista) |
| 10g — Documentación final y traducción | Sin empezar |

## Decisiones tuyas (2026-11-25)

- **Backend externo:** adelante, con **caída al Qwen3-1.7B** si el modelo externo falla.
- **"About" (opción B):** solo el código, el README y el informe de benchmarks. Fuera el ROADMAP, `decisions.md` y los changelogs. Con una sección "Key decisions" en el README.
- **Resúmenes de *El método* en español**, el idioma de la película.

## 10a — Backend externo

**Diseño** (`PLAN_FASES_9_10.md`, 10a): dos implementaciones detrás de la misma interfaz. La local (`Generator`, `src/rag/generator.py`) **no cambia**. La remota (`RemoteGenerator`, `src/llm/remote.py`) habla con cualquier API compatible con OpenAI:
- **Mismo prompt y misma limpieza** que los modelos locales (`build_messages`, `clean_output`). La API aplica la plantilla de chat del modelo.
- **Streaming** (SSE), con el botón Stop y el detector de bucles.
- **Agente:** el paso de planificación usa las llamadas a herramientas nativas de la API (`tool_step`). Devuelve cada llamada con el mismo formato que un modelo local (`<tool_call>{json}</tool_call>`), así que el agente las lee, las registra y las repite igual que antes.
- **Presupuesto de contexto estimado** (3,5 caracteres por token), porque el tokenizador del modelo remoto no está en local.
- **Reintentos** con espera creciente ante límites (429), errores del servidor y tiempos agotados. Si sigue fallando, lanza `RemoteUnavailable`.
- **Caída al 1.7B en la web** (DEC-58): si el modelo externo falla antes de escribir nada, la misma pregunta la responde `API_FALLBACK_MODEL` (por defecto `llm-qwen3-1.7b`), y la traza lo marca con `fallback_from`.
- **La clave**, solo en `.env` del servidor (`NVIDIA_API_KEY`, `GEMINI_API_KEY`). Nunca llega al navegador.

**Perfiles nuevos en `rag.toml`:** `llm-nvidia-lightning` (`nvidia/nemotron-3.5-lightning-30b-a3b`) y `llm-nvidia-bolt` (`nvidia/nemotron-3.5-bolt-e4b`), con el razonamiento apagado. Mismos límites de tokens que la base, para comparar con los modelos locales. En la web entran con los dos modos (10d).

**Comprobado:**
- **Ruta local idéntica:** el `gen-bench` de `film` con el 0.6B (`170-local-check`) da las 44 respuestas iguales, carácter por carácter y con las mismas fuentes, que `165`.
- 148 tests, flake8 y mypy sin errores.
- **Prueba real con Lightning** (5 preguntas): vLLM, CV y Shrek, correctas en 3.7–5.1 s en modo directo. Con el agente, "¿Quién es el Gato con Botas?" y el seguimiento "¿Y quién le contrató?" se reescriben solos; el agente llega a buscar *"Puss in Boots"* en inglés y responde "El Rey" ✅. Es la traducción de la pregunta que DEC-56 dejaba pendiente.

**Matriz completa** (`run10.sh`, la de la Fase 8 más `film` y `agent-bench`), sin modelo de reserva para que un fallo de la API se vea en los números. Comparada con el 1.7B (`120`, `172`, `174`) y Granite (`110`):

| | 1.7B local | Granite local | Lightning | Bolt |
|---|---|---|---|---|
| CV, contiene EN / ES | 0.90 / 0.90 | 0.87 / 0.93 | 0.83 / 0.90 | 0.90 / 0.90 |
| CV, cita correcta EN / ES | 0.79 / 0.78 | 0.86 / 0.93 | 0.95 / 0.92 | 0.96 / 0.96 |
| About, contiene EN / ES | 0.72 / 0.56* | 0.67 / 0.83 | 0.72 / 0.67 | 0.78 / 0.67 |
| XQuAD, contiene EN / ES | 0.79 / 0.68 | 0.81 / 0.74 | 0.82 / 0.73 | 0.84 / 0.79 |
| Film, contiene EN / ES | 0.55 / 0.35* | — | 0.65 / 0.42 | 0.58 / 0.39 |
| vLLM, fuera de dominio cercano ES | 0.7 | 0.7 | 0.7 | 0.9 |
| Segundos por respuesta | 1.4–4.7 | 1.3–5.8 | 1.1–1.5 | 1.3–2.4 |

\* Medidos con 150 tokens de límite (los demás, con 1 024).

- **Banco abierto** (34 preguntas): los dos responden 32 de 34, sin respuestas cortadas, eco, bucles ni idioma equivocado.
- **Lightning contesta en telegrama** ("Denver", "Lord Farquaad"), muchas veces sin cita (58 % de citas en XQuAD EN). Sus métricas de "cortada" e idioma salen mal por eso, no porque fallen. **Inventa un dato del CV:** "¿Está casado Chrystian?" → "No está casado. [1][2]".
- **Bolt** cita siempre, es el que mejor rechaza lo que no está en las fuentes y no tiene fugas ni invenciones en el CV.
- **`agent-bench`:** falló en los dos con HTTP 429. No es nuestra cuota: la cabecera `nvcf-error-source: upstream_status` indica que el servidor del modelo de NVIDIA está saturado, y es intermitente (un minuto después respondía). Se añade `min_interval` (pausa mínima entre peticiones, 0 por defecto) y se respeta `Retry-After`; se relanza con 25 reintentos.
- **Consecuencia para la web:** con el plan gratuito habrá ratos en que el modelo externo no responda; entonces contesta el 1.7B (DEC-58).

### Gemini (Google AI Studio)

Probado por tu propuesta, con su endpoint compatible con OpenAI. En el plan gratuito de tu cuenta:

| Modelo | Resultado |
|---|---|
| Gemini 3.5 Flash-Lite | ✅ ~2 s por respuesta directa; agente correcto. Perfil `llm-gemini-lite` |
| Gemini 3.5 Flash | Solo 20 peticiones al día por modelo (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`); ~25 s por respuesta. Perfil `llm-gemini-flash`, sin uso |
| Gemini 4 | Cuota gratuita 0 |
| Gemini 2.5 | Ya no disponible para cuentas nuevas |
| Gemma 4, Gemini 3.8 Flash, 3.1 Flash-Lite | Saturados (503) o más de 40 s en la prueba |

**Cambio necesario:** Gemini exige que se le devuelva la `thought_signature` de cada llamada a herramienta. `RemoteGenerator` guarda ahora los campos propios del proveedor de cada llamada y los reenvía (`call_extras`); NVIDIA no manda ninguno, así que con él no cambia nada.

**Cuota gratuita de Flash-Lite** (la que ves en AI Studio): 15 peticiones por minuto y 500 al día, por modelo. Se reinicia a medianoche del Pacífico (las 9:00 en España).

**Matriz reducida** (`run10_lite.sh`, `182`): banco abierto, CV, about, film y el `agent-bench` solo con las conversaciones (el completo pasaba de 1 000 peticiones), una petición cada 4.5 s. Unas 360 peticiones.

| Gemini 3.5 Flash-Lite (`182`) | EN | ES |
|---|---|---|
| CV, contiene / cita correcta | 0.90 / 1.00 | 0.93 / 1.00 |
| CV sin respuesta en las fuentes | 7 de 7 rechazadas, 0 fugas | 7 de 7, 0 fugas |
| About, contiene | 0.72 | 0.61 |
| Film, contiene | 0.58 | 0.42 |

- **Banco abierto:** 32 de 34, sin cortes, eco, bucles ni idioma equivocado.
- **Agente, conversaciones** (contiene la respuesta):

| | Primera pregunta, agente / directo | Seguimiento, agente / directo |
|---|---|---|
| Qwen3-1.7B (`128`) | 0.92 / 0.83 | 0.78 / 0.33 |
| Granite 4.0 Micro (`110`) | 0.92 / 0.83 | 0.89 / 0.33 |
| **Gemini 3.5 Flash-Lite** (`182`) | **1.00 / 1.00** | **0.94** / 0.33 |

  El mejor agente medido hasta ahora en los seguimientos. Los ~19 s por respuesta del agente son de la pausa de 4.5 s entre peticiones del benchmark (hasta 4 por pregunta); en la web no hay pausa.
- **Segundos por respuesta directa:** 4–5 s en el benchmark, por la misma pausa (~2 s sin ella).

### Retirado: el mensaje de broma de "no encontrado"

`src/api/app.py` (commit `9c4f021`) sustituía **todas** las respuestas "no encontrado" de la web por una frase de broma, con un comentario que pedía revertirla. Quitada, y la web pública reiniciada.

## 10b — *El método* (2005)

Película española de 111 min, 360p y **sin subtítulos**. La carpeta pasa a llamarse `El método (2005)`, con el formato `Título (año)` de las demás.

| Paso | Resultado |
|---|---|
| Diálogo | Whisper (`large-v3-turbo`) detecta el español solo: 1 683 líneas. Sin las alucinaciones típicas (créditos inventados, frases en bucle) |
| Escenas | 834 fotogramas descritos con Qwen3-VL-2B (en inglés, como Shrek) |
| Identificador web | `el-metodo-2005`: `film_id` quita ahora las tildes (antes habría salido `el-m-todo-2005`). Los de Shrek no cambian |
| Resúmenes y fichas | Nemotron Lightning, **en español** (DEC-59): resúmenes de escena y 8 fichas (Carlos, Nieves, Fernando, Julio, Ricardo, Enrique, Ana y Monse) |
| Índice de `film` | 268 padres y 961 hijos (antes 172 y 618) |

**Errores heredados de Whisper:** el mismo apellido sale como "Aristegui" y "Vistegui", la empresa como "Deke", y la secretaria como "Montse" en un resumen y "Monse" en su ficha.

**Preguntas nuevas** (`film-23` a `film-31`, en inglés y español): respuestas que son nombres propios o números siempre que se puede, para que "contiene la respuesta" funcione en los dos idiomas. Cada evidencia aparece una sola vez en el `.md`.

| `film`, 31 preguntas (`174`) | EN | ES |
|---|---|---|
| R@1/3/5/10 | 0.19 / 0.29 / 0.45 / 0.58 | 0.23 / 0.35 / 0.39 / 0.58 |
| 0.6B: contiene la respuesta, todas / solo *El método* | 0.42 / 6 de 9 | 0.32 / 4 de 9 |
| 1.7B: contiene la respuesta, todas / solo *El método* | 0.55 / 5 de 9 | 0.35 / 5 de 9 (7 de 9 a mano) |

- **Shrek no cambia:** el recall de sus 22 preguntas es idéntico con y sin *El método* (`route-bench` `165` frente a `173`).
- **Fallos del 1.7B en *El método*:**
  - "Madrid" (la noticia del principio): no llega a las fuentes.
  - El nombre del método: "Bronhol" en inglés, "El método" en español.
  - En inglés, confunde Sony Vision con Sonco.
  - En español, la métrica da por fallo "Nieves" (la respuesta esperada es "Nieves Martín"), aunque es correcta.
- **XQuAD:** algo más de preguntas van a `film` (EN 4 → 8, ES 11 → 13 de 1 190), por el corpus nuevo en español.

## 10c — "About": código, README e informe de benchmarks

**Problema** (pregunta tuya): la documentación de trabajo (ROADMAP, decisiones, changelogs) repite tu nombre y el CV y crece en cada fase. Con ella, la búsqueda de "about" empeoraba: R@5 de 0.56 en la Fase 7 (`79`) a 0.33 hoy (`171`).

**Aplicado (DEC-60):** "about" indexa el código de `src/`, el README (EN y ES) y `BENCHMARK_REPORT.md` (EN y ES). Pasa de 1 008 a 554 padres. Quedan fuera:
- El ROADMAP, `decisions.md`, los changelogs y `DETECTOR_BUCLES.md`.
- Las guías de `deploy/`.
- `video/`, el guion del vídeo, ignorado por git pero que no estaba excluido.

| "About" | Antes (`171` / `165`) | Opción B (`172` / `173`) |
|---|---|---|
| R@1/3/5/10 EN | 0.17 / 0.33 / 0.33 / 0.56 | 0.22 / 0.28 / 0.50 / 0.56 |
| R@1/3/5/10 ES | 0.28 / 0.33 / 0.44 / 0.56 | **0.50 / 0.67 / 0.72 / 0.72** |
| 0.6B: contiene EN / ES | 0.56 / 0.50 | 0.61 / 0.50 |
| 1.7B: contiene EN / ES | 0.56 / 0.67 | 0.72 / 0.56 |
| 1.7B: cita la fuente correcta EN / ES | 0.20 / 0.44 | 0.47 / 0.71 |
| "About" que llega a su dominio EN / ES | 15 / 16 | 14 / 17 |
| CV que llega a su dominio EN / ES | 29 / 29 | 29 / 29 |
| 42 (route-bench) | docs 100 %, code 100 % | docs 100 %, code 99 % (1 pregunta a "about"; mismo recall) |

La búsqueda mejora mucho; la generación queda dentro del ruido (cada pregunta vale 0.055). El CV sigue perdiendo 1 pregunta por idioma hacia "about", así que eso no venía del registro de trabajo. `make bench` (42) va fijado a vLLM y no cambia.

**Sección "Key decisions" / "Decisiones clave"** en los dos README (aprobada por ti): base Qwen3-0.6B, Qdrant (con la comparativa de la Fase 1), `bge-m3`, búsqueda híbrida con RRF, el reranker, un umbral por dominio y el agente opcional en la web. Cubre la única pregunta de "about" que dependía del ROADMAP (`about-14`), cuyo ground truth pasa a la tabla del README. "About" reindexado: 558 padres.

## 10e — Preguntas sobre el propio sistema y las películas

Probando la web (2026-11-25) salieron tres problemas, con decisiones tuyas:

- **"¿Qué eres?" / "¿qué sabes de xquad?" (opción A):** sección "What it can answer, and its limits" / "Qué puede responder y hasta dónde llega" en los dos README: qué contiene cada dominio y dónde acaba (vLLM solo 0.10.1, XQuAD no es toda la Wikipedia sino 48 artículos, las tres películas), con la frase "¿No sabes qué preguntar? Usa las preguntas de ejemplo… o pregúntame por alguno de los dominios". La misma frase va en el texto de bienvenida del chat. Tabla de dominios con `film`. Con el ground truth de "about" regenerado (la sección desplaza las posiciones del README), **"about" sube a su mejor marca** (`185`): R@1/3/5/10 EN 0.33 / 0.61 / 0.72 / 0.72, ES 0.67 / 0.78 / 0.83 / 0.89 (antes, `172`: 0.22 / 0.28 / 0.50 / 0.56 y 0.50 / 0.67 / 0.72 / 0.72).
- **"¿Qué puedes decirme de El método?" iba a "about"** porque dos comentarios del código nombraban la película: reescritos sin el título. Después iba a vLLM ("método" ≈ *method*). **Títulos como nombre del dominio** (`route_names_from_titles` en `rag.toml`, `title_patterns` en `film.py`): una pregunta que nombra una película ingerida va a `film` y se salta su umbral. Los títulos salen de los ficheros de `data/film/`. Un título que empieza por artículo ("El método") solo cuenta al final de la pregunta o tras "película"/"film"/"movie", para no robar "¿qué devuelve el método generate?". `route-bench` `183`: 42 idéntico, `film` 31/31 EN y 30/31 ES, "about" 15/17, CV igual, XQuAD → `film` +1 de 1 190. La descripción de `film` nombra ahora las tres películas (la lee el agente).
- **"¿De qué va la película?" no tenía respuesta:** todas las fuentes de `film` cubrían un tramo de tiempo. **Sinopsis por película** (`<Título>.synopsis.md`, un fragmento), generada con Nemotron Lightning a partir de los resúmenes de escena ya existentes, en el idioma del diálogo, cubriendo principio, mitad y final (máximo ~250 palabras; Shrek 471). Los demás ficheros de las películas quedan idénticos. `film` reindexado: 272 padres. Con el agente, "¿Qué me puedes decir sobre el método?" y "What is Shrek 2 about?" responden con el argumento completo; en directo, la primera sigue recuperando líneas de diálogo.
- **"¿Qué pasa en el minuto 30?" (decisión tuya):** la búsqueda por parecido no lo encuentra ("minuto 30" no se parece a `## 00:30:00 - 00:30:30`). Ahora el router lo resuelve por tiempo (`DomainRouter.moment`, `time_of` y `chunks_at` en `film.py`): detecta la hora ("minuto 30", "1:05:00" y, si la pregunta nombra una película, también "30 min", "1h20", "media hora", "12:30") y da como fuentes el resumen de escena y el tramo de transcripción que cubren ese momento, de las películas nombradas o de las tres si no nombra ninguna. "Shrek 2" ya no cuenta también como "Shrek". Solo actúa en el dominio con títulos y con una hora en la pregunta; "a timeout of 30 minutes" no lo activa. Probado en la web: "¿qué pasa en el minuto 45 de Shrek 2?" responde la escena de la poción, en directo y con el agente. Límite: los fragmentos agrupan varios tramos, así que el clip de la web puede empezar unos minutos antes del momento preguntado.
- **Batería de preguntas básicas** (`make demo-check`, `scripts/demo_check.py`, `bench/datasets/demo/questions.json`): 32 preguntas cotidianas de todos los dominios, lanzadas contra la web como un visitante. No es un guion: un fallo señala una causa general que arreglar, nunca un parche por pregunta. Primera pasada, 28 de 31; los fallos y sus causas:
  - **"¿Qué umbral tiene film?" inventaba −1.0:** los umbrales solo estaban en `rag.toml`, que "about" no indexa. Ahora están en la viñeta "Un umbral de relevancia por dominio" de los dos README.
  - **"¿Qué ocurre en Shrek 1?" no encontraba la sinopsis:** su cabecera no nombraba la película. Ahora "## Synopsis of the whole film: Shrek (2001)".
  - **"Where was Nikola Tesla born?" respondía con el mensaje del CV** ("¡pregúntaselo tú!"): las preguntas de nacimiento se parecen a los datos del autor y caen en el CV. El mensaje propio del CV sale ahora solo si la pregunta es sobre el autor (`not_found_when`: su nombre, "el autor", "él/he"); si no, el "no se encuentra" genérico, que es lo correcto (XQuAD no dice dónde nació Tesla). Las preguntas sin respuesta del benchmark del CV nombran a Chrystian, así que no cambian.
  - **"¿Y quién le contrató?" (Gato con Botas):** la pista está ("Fiona's father paid you"), pero hay que deducirla; Gemini 3.1 no la encuentra y Lightning y Gemini 3.5 sí. Variabilidad del modelo, sin cambio.
  - **"¿Capital de Francia?" → "París":** la documentación de vLLM trae ese ejemplo con su respuesta (Fase 3, B15). Correcto; la batería lo espera así.
  - Tras los arreglos, las preguntas afectadas pasan (7 de 7).
- **Cuota de Gemini 3.5 agotada** al final del día (500 peticiones: matriz, pruebas y batería). La cadena de reserva respondió todo con Gemini 3.1 y el 1.7B, sin dejar de responder; la cuota se reinicia a las 9:00.
- **El `list index out of range` de los `agent-bench` de Bolt y Lightning:** causado por reindexar "about" y `film` mientras corrían. Cada proceso carga la lista de fragmentos al arrancar; Qdrant pasó a tener más y devolvía posiciones fuera de la lista vieja (`retriever.py`, `dense_parents`). La web no lo sufre porque se reinicia tras cada reindexado. Pendiente: que un proceso largo lo tolere. Los resultados del agente con NVIDIA se perdieron; no hacen falta para decidir (Cloud va con Gemini). El `agent-bench` imprime ahora la traza completa si falla.

## 10d — Web con dos modos

Según el orden acordado (`PLAN_FASES_9_10.md`):
- **⚡ Local:** el aspecto de siempre, en rojo y sin interruptor de agente. Modelos: 0.6B, 1.7B (por defecto), Granite y Qwen3-4B de vuelta (solo directo, con la búsqueda en la CPU, opción A de 8w).
- **☁ Cloud:** tema claro con acento azul (fondo, paneles, grises, bordes y sombras cambian con la misma transición; el modo va en `data-mode` de `<html>`, así que cambia toda la ventana). Modelos remotos (`remote` en `/config`): **Gemini 3.5 Flash-Lite por defecto** (decisión tuya, por la matriz `182`), Lightning y Bolt. **Agente encendido por defecto** (`API_AGENT_CLOUD=1`), con el interruptor para apagarlo; sin el aviso de "work in progress" (decisión tuya). En Local no hay interruptor: siempre directo.
- **Transición:** el acento y un halo superior pasan de rojo a azul en 0.9 s (colores registrados con `@property`). La conversación se conserva al cambiar de modo; se reinician el modelo y el agente.
- **Cadena de reserva** (petición tuya): si el modelo externo falla, contesta el siguiente de `API_FALLBACK_MODEL`, por orden y saltando los ya probados: Gemini 3.5 Flash-Lite → Gemini 3.1 Flash-Lite (cuota diaria propia; solo de reserva, no sale en el selector) → Qwen3-1.7B local, así que la web siempre responde. La traza dice "… unavailable". Una cuota diaria agotada (`PerDay` en el error de Gemini) no se reintenta: se pasa al siguiente al momento. Los modelos Live de Gemini no entran: solo funcionan por WebSocket (`bidiGenerateContent`), para voz en tiempo real.
- **API:** `/config` añade `remote` por modelo, `model_default_cloud`, `mode_default` y `agent_default_cloud` (variables `API_DEFAULT_MODE`, `API_DEFAULT_CLOUD_MODEL` y `API_AGENT_CLOUD` del `Makefile`).
- **Al pasar de Cloud a Local**, el primer mensaje tarda unos 6 s más: el modelo local vuelve a la GPU (`API_MAX_LOADED=1`).

**Probado por `/chat`:** Lightning directo 3.8 s (primer token 1.9 s); agente con seguimiento ("¿Y quién le contrató?" → "El Rey") en unos 5 s; 1.7B local 12.4 s con la recarga.

## 10h — Noche del 26 al 27: batería con todos los modelos, plan B y respuesta del agente

Sesión autónoma autorizada por ti. Decisiones en `decisions.md` (DEC-62 a DEC-66).

**Al empezar** (22:40) estaba todo parado: el ordenador se había reiniciado. Arranqué Docker y la API, y abrí el túnel de Tailscale (en segundo plano, sin `--bg`). **Error mío:** la primera vez arranqué la API sin `API_SHOW=film API_DEFAULT_MODE=local` (las opciones de ayer), y las preguntas de películas fueron a "about". Lo vi en la batería, la reinicié con esas opciones y repetí la batería desde cero. La web estuvo parada de 0:30 a 1:20 para medir los modelos locales con la GPU libre.

### Batería de preguntas básicas con los 7 modelos

Primera pasada (las 32 preguntas de ayer, con el agente en la nube y en directo en los locales, como en la web):

| Gemini | Lightning | Bolt | 0.6B | 1.7B | Granite | 4B |
|---|---|---|---|---|---|---|
| 25 | 25 | 27 | 24 | 25 | 24 | 27 |

**Causas de los fallos:**
- **Preguntas mal planteadas** (DEC-62): "¿Quién ganó la Super Bowl 50?" no tiene respuesta en el corpus; "Retrieval-Augmented Generation" no contenía "rag"; la lista de películas desde `film` es correcta; un seguimiento no puede pasar sin memoria. Corregidas las preguntas, no el RAG.
- **El agente responde a su reescritura** (DEC-63): la causa de que Lightning dijera "no lo sé" en todo el CV. Arreglado por modelo con `agent_answer_with`.
- **Modo directo, enrutado por puntuación** (DEC-66): "¿Qué películas tienes?" va al CV y "¿Qué base de datos vectorial usa el proyecto?" no pasa ningún umbral. Con el agente salen bien. Queda como límite.
- **Calidad del modelo:** los pequeños fallan "¿Para qué sirves?" o el minuto 45 de Shrek 2 con las fuentes correctas delante.

**Tras los cambios**, con el agente: Gemini **29**, Lightning **29**, Bolt 25 con `context` (vuelve a `rewrite`, con el que dio 27). Las 29 mezclan los dos arreglos: las preguntas corregidas y el agente respondiendo a la pregunta del usuario.

**Locales en directo, con las preguntas corregidas** (31: sin el seguimiento, que solo vale con agente): 0.6B 24, 1.7B 25, Granite 24, 4B 27. Fallan en casi todos: "¿Qué películas tienes?" y "¿Qué base de datos vectorial usa el proyecto?" (enrutado, DEC-66), "Que me puedes decir sobre el metodo?" (en directo llegan líneas de diálogo y no la sinopsis, como ya se vio en 10e) y el minuto 45 de Shrek 2 (las fuentes son las correctas, pero los modelos pequeños describen el fotograma y no la escena).

### Plan B (8f) y qué responde el agente

Opciones nuevas en el agente (`src/agent/agent.py`), medibles con `make agent-bench FALLBACK_ANSWER=… ANSWER_WITH=… MODES=agent`:
- `fallback_answer`: `mixed` (hasta hoy) u `original` (el plan B).
- `answer_with`: `rewrite` (hasta hoy), `original`, `context` o `both`. Por defecto, el del perfil del modelo (`agent_answer_with` en `rag.toml`).

**Plan B, descartado** (DEC-64): seguimientos 0.6B 0.72 → 0.72, 1.7B 0.78 → 0.72, Granite 0.94 → 0.89 (`187`).

**`context`, adoptado por modelo** (DEC-63), en las conversaciones (primera / seguimiento):

| Modelo | `rewrite` | `context` |
|---|---|---|
| Lightning | 0.75 / 0.83 | 0.92 / 0.89 |
| Bolt | 1.00 / 0.94 | 1.00 / 1.00 |
| Gemini 3.5 Flash-Lite | 0.92 / 0.94 | 1.00 / 0.94 |
| Qwen3-0.6B | 1.00 / 0.72 | 1.00 / 0.72 |
| Qwen3-1.7B | 0.92 / 0.78 | 0.92 / 0.72 |
| Granite 4.0 Micro | 0.92 / 0.94 | 0.92 / 1.00 |

Preguntas sueltas (`189`): Granite igual; Lightning con mucho más F1 en el CV y XQuAD y algo menos en el código de vLLM (respuestas correctas pero más cortas). **Activado en:** Lightning, Gemini (los tres perfiles) y Granite. **Sin cambios:** 0.6B, 1.7B y Bolt.

### Comprobaciones

- **42 idéntico** (`190-night-check`): docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88. La recuperación y el router no se han tocado, así que no repito el `route-bench`.
- 155 tests, flake8 y mypy sin errores.
- **Cuota de Gemini 3.5 agotada** a las 2:20 (batería ×2 y `agent-bench`): hasta las 9:00 responde Gemini 3.1 de reserva.

## Ficheros cambiados

| Fichero | Cambio |
|---|---|
| `src/llm/__init__.py`, `src/llm/remote.py` | Nuevos: la fábrica `create_generator` y el backend compatible con OpenAI (con `min_interval`, `Retry-After` y los campos propios del proveedor en las llamadas a herramientas) |
| `src/config.py` | `GenerationConfig`: `provider`, `base_url`, `api_key_env`, `extra_body`, `timeout`, `retries` y `min_interval` (los valores por defecto dejan todo como estaba) |
| `src/agent/agent.py` | Planificación con `tool_step` si el generador lo tiene (remoto); el camino local no cambia |
| `src/api/app.py` | Cadena de modelos de reserva (`RAG_API_FALLBACK_MODEL`, los que no están en el selector quedan ocultos), "respuesta cortada" con el `finish_reason` de la API, fuera el mensaje de broma |
| `src/cli.py`, `src/server/tools.py`, `src/evaluation/gen_bench.py`, `src/evaluation/agent_bench.py` | El generador se crea con `create_generator` |
| `rag.toml` | Perfiles `llm-nvidia-lightning`, `llm-nvidia-bolt`, `llm-gemini-lite`, `llm-gemini-lite-31` y `llm-gemini-flash`; "about" con la opción B |
| `Makefile` | `API_FALLBACK_MODEL` (por defecto `llm-qwen3-1.7b`); modelos de la web con los remotos y el 4B; `API_DEFAULT_MODE`, `API_DEFAULT_CLOUD_MODEL` y `API_AGENT_CLOUD` |
| `web/src/App.tsx`, `web/src/api.ts`, `web/src/index.css` | Modos local y Cloud, con la transición de color |
| `src/rag/sources/film.py` | `film_id` sin tildes |
| `src/rag/sources/film_enrich.py` | Resúmenes y fichas en el idioma del diálogo (`film_language`); roles, tratamientos y fichas vacías en español |
| `README.md`, `docs/es/README.md` | Sección "Key decisions" / "Decisiones clave" |
| `bench/datasets/about/` | `about-14` apunta al README |
| `bench/datasets/film/` (ignorado por git) | `film-23` a `film-31` |
| `docs/es/decisions.md` | DEC-57 a DEC-66 |
| `src/agent/agent.py` | (10h) `fallback_answer` y `answer_with`: qué pregunta responde el generador tras el fallback y tras las búsquedas del modelo |
| `src/config.py`, `src/llm/__init__.py` | (10h) `agent_answer_with` por perfil; la fábrica se lo pasa al generador sin tocar sus clases |
| `src/evaluation/agent_bench.py`, `src/cli.py`, `Makefile` | (10h) `agent-bench` con `FALLBACK_ANSWER`, `ANSWER_WITH` y `MODES` (solo agente, sin repetir el directo) |
| `rag.toml` | (10h) `agent_answer_with = "context"` en Lightning, Gemini y Granite |
| `scripts/demo_check.py`, `bench/datasets/demo/questions.json` | (10h) Dominio esperado como lista, `agent_only` y cuatro preguntas corregidas (DEC-62) |
| `tests/test_agent.py` | (10h) Tests del plan B, de `answer_with` y del ajuste por modelo |
