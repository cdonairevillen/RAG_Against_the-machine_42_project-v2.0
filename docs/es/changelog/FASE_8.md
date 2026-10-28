# CHANGELOG — Fase 8: Granite, despliegue y pruebas extra

Fase abierta el 2026-10-27, tras el commit `477bff9` (cierre de la Fase 7). El plan está en `ROADMAP.md` (Fase 8). Aquí se irá apuntando qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`.

**Regla añadida en la Fase 7 (DEC-39):** en este documento no se copia el texto de una pregunta de prueba sobre el proyecto ni una respuesta incorrecta. Se usa su identificador (`A-NN`, `about-NN`, `L-N`) y una descripción; lo literal va a `RESPUESTAS_ARCHIVADAS.md`, que está fuera del índice de "about".

## Estado

| Bloque | Estado |
|---|---|
| 8w — Web: 1.7B por defecto, 4B solo sin agente | ✅ Implementado y comprobado con la API real (§8w); opción A para la memoria del 4B |
| 8a — Granite | ✅ Granite 4.0 Micro: matriz `110` (§8a). **Sustituye al 4B en la web** (decisión tuya, 2026-10-27), con una regla propia para los datos privados del CV (§8a.2) |
| 8b — Umbral de "about" | ✅ −1.0 → **−1.25** (§8b): recupera dos preguntas del proyecto; una de XQuAD en español pasa de "no encontrado" a una respuesta incorrecta. Falta el `route-bench` oficial |
| 8c — Pista de idioma (opción C) | Propuesto, prioridad baja |
| 8d — Despliegue | 🟡 Preparado para desplegar desde tu ordenador (§8d): `make api-public`, guía en `deploy/local/README.md` y ensayo completo. Túneles comprobados y medidas de seguridad en §8d.2: Tailscale Funnel es la única opción gratuita que sirve (el túnel rápido de Cloudflare no admite el streaming del chat). Falta que crees la cuenta de Tailscale |
| 8e — Pruebas extra | Las de siempre (la matriz de los Qwen), para evaluar Granite |
| 8f — Plan B del agente | Entra (decisión tuya, 2026-10-27); sin empezar |
| 8h — Documentación para "about" | ✅ README, ROADMAP, BENCHMARK_REPORT y la traducción de la Fase 8 al día; "about" reindexado (§8h). Una pregunta del banco abierto empeora por el umbral de "about" (8b) |
| 8g — Respuestas más elaboradas | ✅ Medido (§8g): 6 reglas en el 1.7B y S2 en Granite y el 0.6B. **No se adopta ninguna** (todas empeoran algo; la mejor, S5 en el 1.7B, pierde en code). S5 queda comentada en `rag.toml`, lista para activarla; el CV mantiene siempre la regla corta |

## Decisiones tuyas (2026-10-27)

- **La base sigue siendo Qwen3-0.6B** (benchmarks, CLI, comparativas con 42).
- **Web: Qwen3-1.7B por defecto**, para lucir más el RAG.
- **Web: Qwen3-4B vuelve a la lista, solo con el agente desactivado.** Después lo sustituyó Granite (§8a.2): hoy el 4B no está en la web.
- **Granite:** sus limitaciones se ven a medida que se prueba.
- **Las decisiones las tomas tú.**
- **El plan B del agente entra en esta fase.** El 4B no usa agente (memoria de la GPU), así que no le afecta.
- **Memoria del 4B en la web: opción A** (abajo), vigilando que los tiempos no se disparen.
- **Granite: Granite 4.0 Micro** (`ibm-granite/granite-4.0-micro`, la densa de 3B). Si tras tu evaluación funciona como debe, se sigue con él; si no, se descarta.
- **Pruebas:** la misma matriz que con los Qwen (`gen-bench`, banco abierto, `agent-bench`, eco, bucles, idioma, latencia).
- **Despliegue: desde tu ordenador con un túnel, como parche.** Oracle y Hugging Face PRO quedan como opciones probables para el futuro.

## Lo que hay ahora en el código (punto de partida de 8w)

- **`Makefile`:** `API_MODELS ?= default,llm-qwen3-1.7b`. El 4B está fuera porque, con la recuperación en la GPU, no cabe en 12 GB (medido en la Fase 6).
- **`src/api/app.py`, `ModelPool`:**
  - El modelo `default` es el de la configuración base (0.6B), y es el que se carga al arrancar (`RagService.load`).
  - Se mantiene un solo modelo cargado (`RAG_API_MAX_LOADED=1`). Al cambiar de modelo se descarga el anterior y, si el nuevo no carga, se vuelve al anterior con un error claro.
  - La API solo toma la parte de **generación** de cada perfil `llm-*`. Por eso el `[profiles.llm-qwen3-4b.models] device = "cpu"` del 4B (la recuperación en la CPU) no se aplica en la web.
- **Medido:** el 4B no carga en el proceso de la web ni sin agente (banco abierto de `92`, `100` y `101`, modo directo). El error de `llm_sdk` es *"You can't move a model that has some modules offloaded to cpu or disk"*. En `gen-bench` sí carga, porque allí su perfil completo pone la recuperación en la CPU.

**Consecuencia:** desactivar el agente no basta para que el 4B funcione en la web. Hay que hacerle sitio en memoria. Opciones a valorar contigo, todas sin medir:

| Opción | Idea | A comprobar |
|---|---|---|
| **A** ✅ (decisión tuya) | Al elegir el 4B, la recuperación (bge-m3 y el reranker) pasa a la CPU, como en su perfil. **Es lo que ya pasa fuera de la web:** allí el 4B genera en la GPU (`llm_sdk` elige el dispositivo) y solo la búsqueda va a la CPU | Latencia de la búsqueda en CPU; volver a la GPU al cambiar de modelo. Tu preferencia, si los tiempos no se disparan |
| B | El 4B en la CPU y la recuperación en la GPU | Generación muy lenta (varios minutos por respuesta) |
| C | Dejar la recuperación siempre en la CPU en la web | Afecta a todos los modelos |

En Oracle (CPU, 12 GB) el 4B está sin medir. En float32 serían unos 16 GB; solo podría caber en bf16, y está sin comprobar.

**Primer dato para la opción A** (de los `gen-bench` de `101`, sin medir nada nuevo; un solo dominio, "about"):

| | Búsqueda (mediana · máx.) | Generación (mediana · máx.) |
|---|---|---|
| 4B, búsqueda en CPU | 0.47 s · 1.83 s | 4.3 s · 9.3 s |
| 1.7B, búsqueda en GPU | 0.07 s · 0.32 s | 2.8 s · 14.7 s |

En la web se busca en los cuatro dominios, así que la búsqueda en CPU tardará más. Es una estimación, no una medida, y se mide al implementar 8w.

## 8w — Web: 1.7B por defecto y 4B solo sin agente (implementado, 2026-10-27)

### Qué ha cambiado

| Fichero | Cambio |
|---|---|
| `src/api/app.py` | `ModelPool`: `RAG_API_DEFAULT_MODEL` (el modelo con el que arranca la web y que se carga al iniciar; sin él, el de siempre, `default`), `RAG_API_DIRECT_ONLY` (modelos que solo se ofrecen sin agente) y, por modelo, el dispositivo de la búsqueda que dice su perfil de `rag.toml`. `/config` añade `model_default` y `agent` en cada modelo. `RagService.generator_for`: si el modelo elegido busca en otro dispositivo, descarga los LLM cargados, mueve el embedder y el reranker (compartidos por todos los dominios) y después carga el modelo. `chat` rechaza el agente con un modelo de solo directo, con un mensaje claro |
| `Makefile` | `API_MODELS ?= default,llm-qwen3-1.7b,llm-qwen3-4b`, `API_DEFAULT_MODEL ?= llm-qwen3-1.7b` y `API_DIRECT_ONLY ?= llm-qwen3-4b` |
| `web/src/App.tsx`, `web/src/api.ts`, `web/src/index.css` | La web arranca con `model_default`. Con el agente encendido, el 4B sale en el selector pero deshabilitado ("Turn the agent off to use it"); si se enciende el agente con el 4B elegido, pasa al modelo por defecto. Nota del 4B: "Best answers · slowest · direct RAG only". Web recompilada |
| `tests/test_api.py` | 3 tests nuevos: modelo por defecto y modelos de solo directo, el 4B rechaza el agente, y la búsqueda se mueve antes de cargar el modelo (y vuelve al cambiar) |

**Sin cambios:** la base (0.6B) en benchmarks, CLI y `rag.toml`; el despliegue (`deploy/`), que no define las variables nuevas y se queda como antes; `llm_sdk`.

**No hay código especial para el 4B:** la búsqueda en la CPU sale de su perfil (`[profiles.llm-qwen3-4b.models] device = "cpu"`), igual que fuera de la web.

### Comprobado con la API real (`make api`, 3080 Ti, todos los dominios, modo directo; `data/output/night2/web8w.py`)

| Paso | Primer token | Total | GPU usada |
|---|---|---|---|
| Arranque | — | — | 1.7B cargado por defecto |
| 1.7B, 3 preguntas (vLLM, XQuAD/ES, vLLM) | 0.7–1.2 s | 1.7–9.7 s | 9.0 GB |
| 4B con agente | Rechazado con el mensaje | — | — |
| 4B sin agente, 1.ª pregunta (incluye la carga y mover la búsqueda) | 9.7 s | 15.7 s | — |
| 4B sin agente, siguientes | 3.8 s | 4.7–8.9 s | 10.5 GB |
| Vuelta al 1.7B, 1.ª (incluye la carga y devolver la búsqueda a la GPU) | 4.6 s | 13.1 s | — |
| 1.7B, siguientes | 0.8 s | 1.7–5.5 s | 9.0 GB |
| 0.6B con agente | 4.8 s (con la carga) | 7.9 s | 6.5 GB |

La cifra de GPU es la de toda la máquina, no solo la de la API.

**Lectura:** con el 4B, el primer token tarda unos 3 s más (la búsqueda en CPU en los cuatro dominios, más el prompt del modelo grande), pero el total sigue por debajo de 10 s en estas preguntas. Los cambios de modelo cuestan unos 4–10 s la primera vez. Las respuestas del 1.7B empiezan igual antes y después de pasar por el 4B (comparados los primeros 70 caracteres de cada una).

**Pruebas:** 126 tests; flake8 y mypy limpios.

## 8a — Granite 4.0 Micro (en curso)

**Perfil:** `llm-granite-micro` en `rag.toml` (`ibm-granite/granite-4.0-micro`). Solo cambia el modelo de generación, como los perfiles de Qwen. `llm_sdk` no se toca.

### Comprobaciones antes de medir (las mismas que se hicieron con Phi, `FASE_7.md` §7b.1)

| Comprobación | Resultado |
|---|---|
| Arquitectura | `GraniteMoeHybridForCausalLM` con **solo capas de atención** (la variante densa; la híbrida con Mamba2 es `granite-4.0-h-micro`). Soportada por la versión de transformers del proyecto (5.12.1) |
| Plantilla de chat | La suya (`<\|start_of_role\|>…<\|end_of_role\|>…<\|end_of_text\|>`). Nuestro mensaje de sistema **sustituye** a su mensaje por defecto: no aparece en el prompt |
| Final de generación | `<\|end_of_text\|>` (100257), declarado en su `generation_config`; nuestro `stop_token_ids` lo recoge. `<\|im_end\|>` (el de Qwen) no existe en su vocabulario y se ignora |
| Precisión | `llm_sdk` carga en float16 en la GPU (Granite se publica en bf16). Sin desbordes en la primera prueba: respuestas normales |
| Memoria (3080 Ti) | 9.55 GB con la búsqueda en la GPU: **cabe sin mover la búsqueda a la CPU**, a diferencia del 4B |
| Formato de herramientas | `<tool_call>{json}</tool_call>`, el mismo que ya lee el agente (`src/agent/toolcalls.py`) |
| Primera prueba (todos los dominios, modo directo) | Responde bien y cita en una pregunta de vLLM (3.4 s), una de XQuAD en español (1.4 s, en español) y la de fuera de dominio conocida de B15 (1.0 s, el caso de la documentación de vLLM) |

### Matriz (`110`, terminada el 2026-10-27)

Banco abierto, `gen-bench` a 1.024 tokens (vllm 25 por set, cv, about, xquad) y `agent-bench`. Con el 1.7B se repiten about, xquad y `agent-bench` con el índice actual, para comparar con el modelo por defecto de la web. Los Qwen de vllm y cv salen de `97` (mismo índice de esos dominios); el 0.6B de "about", de `102`, y el 4B de "about", de `101`. Script: `data/output/night2/run8.sh 110` (ignorado por git).

**`gen-bench`, contiene la respuesta (EN / ES)** y, entre paréntesis, la cita correcta:

| Suite | 0.6B | 1.7B | 4B | **Granite Micro** |
|---|---|---|---|---|
| CV | 0.73 / 0.80 (0.73 / 0.89) | 0.90 / 0.90 (0.79 / 0.78) | 0.90 / 0.93 (0.82 / 0.82) | **0.87 / 0.93 (0.86 / 0.93)** |
| about | 0.50 / 0.50 | 0.56 / 0.61 | 0.67 / 0.72 | **0.67 / 0.83** |
| XQuAD (300 por idioma) | 0.64 / 0.59 | 0.79 / 0.68 | — | **0.81 / 0.74** (cita 0.96 / 0.97) |

**`gen-bench` de vLLM, F1** (en vLLM "contiene" no sirve: las respuestas de referencia son largas) y la cita correcta:

| Set | 0.6B | 1.7B | 4B | **Granite Micro** |
|---|---|---|---|---|
| public/docs | 0.51 (0.87) | 0.50 (0.73) | 0.59 (0.80) | **0.55 (0.83)** |
| public/code | 0.43 (0.86) | 0.46 (0.86) | 0.47 (0.91) | **0.54 (0.92)** |
| es/docs | 0.19 (0.90) | 0.25 (0.80) | 0.20 (1.00) | **0.28 (1.00)** |
| es/code | 0.27 (1.00) | 0.22 (0.89) | 0.27 (0.90) | **0.29 (0.90)** |
| Fuera de dominio, cercanas EN / ES | 0.8 / 0.8 | 0.8 / 0.7 | 0.9 / 0.9 | 0.8 / 0.7 |

**Preguntas del CV que no debe contestar** (datos de contacto privados y lo que no está en el CV; las fugas se miden aparte):

| | 0.6B | 1.7B | 4B | Granite Micro |
|---|---|---|---|---|
| Fugas | 0 | 0 | 0 | 0 |
| Privadas bien redirigidas (EN / ES, 2 por idioma) | 2 / 2 | 2 / 2 | 1 / 2 | **1 / 0** |
| Sin información en el CV (EN / ES, 7 por idioma) | 7 / 6 | 7 / 7 | 7 / 7 | 7 / 7 |

En las privadas, Granite falla de dos formas. Dos veces responde con el correo público en lugar del mensaje del CV, y una de ellas lo presenta como si fuera la dirección privada que se pide (es falso). Una vez dice en español que el dato es privado, pero sin el mensaje fijo que el benchmark espera. No sale ningún dato privado.

**`agent-bench`** (contiene la respuesta, agente / directo; última columna, el agente hace una llamada válida a una herramienta):

| Set | 1.7B (`110`) | Granite Micro (`110`) |
|---|---|---|
| Conversaciones, primera pregunta | 0.92 / 0.83 · 1.00 | 0.92 / 0.83 · 1.00 |
| Conversaciones, seguimiento | 0.78 / 0.33 · 0.61 | **0.89** / 0.33 · **0.94** |
| CV EN | 0.90 / 0.90 · 0.83 | 0.87 / 0.87 · 0.93 |
| CV ES | 0.80 / 0.83 · 0.87 | **0.90** / 0.87 · 0.97 |
| XQuAD EN | 0.78 / 0.78 · 0.74 | 0.76 / 0.76 · 0.94 |
| XQuAD ES | 0.66 / 0.70 · 0.90 | **0.78** / 0.76 · 0.94 |
| Segundos por respuesta, agente (rango por set) | 3.5–6.4 | 4.8–11.5 |

Referencia de la Fase 5 en los seguimientos: 0.6B 0.78 y 4B 1.00. En vLLM (public), "contiene" queda en ~0 con todos los modelos y no se usa.

**Banco abierto** (34 preguntas, como en la web): 29/34 respondidas, ninguna cortada, ningún bucle, idioma bien en todas. Media de 179 tokens; máximo 606.
- **Eco: 1.** Granite añade a veces al final una lista "Sources:" y `strip_echo` la deja como `[n] (ruta)`. El registro de eco (`110-echo.jsonl`) tiene 5 casos limpiados en toda la matriz.
- **Repetidas: 3**, comandos de Docker o Podman legítimos, no bucles.
- **Preguntas del proyecto (`A-01`..`A-16`):**
  - Bien: A-04, A-05, A-12 y A-13.
  - Genéricas sobre RAG (~500 tokens): A-01 y A-03.
  - Desviadas: A-06 (habla del contrato de obra) y A-10 (incorrecta).
  - No encontradas: A-02, A-08, A-09 y A-11.
  - Larga: A-16 (606 tokens).
  - Es parecido a lo que pasa con los Qwen en "about" tras DEC-39 (el umbral de 8b), no algo propio de Granite.

**Latencia y memoria (3080 Ti):**
- Directo: 1.3–5.4 s por respuesta, entre el 1.7B y el 4B.
- Agente: más lento que el 1.7B, entre 1.4 y 2 veces según el set.
- Memoria: 9.55 GB con la búsqueda en la GPU. Cabe sin moverla, así que en la web no necesitaría ser "solo directo" como el 4B.

### Lectura (para tu evaluación; la decisión es tuya)

- **A favor:**
  - En calidad queda al nivel del 4B o por encima en CV, about, XQuAD y vLLM.
  - Es el mejor agente medido después del 4B: seguimientos 0.89 y llamadas válidas a herramientas por encima del 0.93 en todos los sets.
  - Cabe en la GPU con el agente encendido, que es justo lo que el 4B no puede.
- **En contra:**
  - Es el que peor redirige las preguntas privadas del CV (1 de 4), y en una afirma algo falso sobre el correo. No hay fugas, pero en el dominio del CV es lo más delicado.
  - Va más lento que el 1.7B, sobre todo con el agente.
  - Tiene un pequeño eco de la lista "Sources:", que se limpia.
- **Sin medir:** CPU (Oracle) y el juez de Groq.
- **Si se sigue con él, propuestas** (no hechas):
  - Revisar con Granite el mensaje del CV para preguntas privadas, sin cambiar el prompt de los Qwen.
  - Decidir si entra en la web y con qué etiqueta.

### 8a.2 — Granite en la web y sus datos privados (2026-10-27)

**Decisión tuya:** Granite sustituye al Qwen3-4B en la web, pueda o no usar el agente. Puede: cabe en la GPU con la búsqueda y el agente (ensayo de §8d). Pediste que oculte el teléfono y el correo como los demás modelos, aunque no es crítico.

**Lo que ya estaba protegido:** el teléfono y el correo antiguo se enmascaran en el código (`rag.toml`, `private_data`) antes de que el modelo los vea y otra vez en la respuesta y en las fuentes. Ningún modelo puede mostrarlos. Medido en `112-privacy` y `111-privacy`: 0 fugas en 84 respuestas (0.6B, 1.7B y Granite, con y sin agente).

**El fallo real de Granite:** ante "¿cuál es su Hotmail?" daba el Gmail público como si fuera el Hotmail. Es falso, aunque no revela nada.

**Arreglo, solo para Granite:**

| Fichero | Cambio |
|---|---|
| `src/config.py` | `SourceConfig.model_rules`: reglas de un dominio para un modelo concreto (por su id de Hugging Face), añadidas después de `prompt_rules` |
| `src/rag/domain_rules.py` | `prompt_rules(domain, model)` añade la regla del modelo cuando existe |
| `src/rag/pipeline.py`, `src/agent/agent.py` | Pasan el modelo cargado (`generator.model_name`) |
| `rag.toml` | `[sources.cv.model_rules]` con la regla 12 para `ibm-granite/granite-4.0-micro`: el Gmail es un Gmail; si piden el Hotmail, el teléfono, WhatsApp o la dirección, se dice que es privado y se da el Gmail como contacto público |

**Los Qwen no cambian:** su prompt es idéntico byte a byte (comprobado).

**Medido:**

| | Antes (`110`) | Con la regla (`112`) |
|---|---|---|
| Privadas bien tratadas, `gen-bench` (EN / ES) | 1/2 · 0/2 | **2/2** · 0/2 (*) |
| Hotmail presentado como Gmail (banco de 14 preguntas de contacto, directo + agente) | 2 de 2 | **0** |
| CV contiene (EN / ES) | 0.87 / 0.93 | 0.87 / 0.93 |
| CV cita correcta (EN / ES) | 0.86 / 0.93 | 0.86 / 0.93 |
| Fugas | 0 | 0 |

(*) Las dos en español son correctas aunque el benchmark no las cuente: una dice que el teléfono es privado y la otra que no hay un correo de Hotmail. El benchmark solo da por buenas las que acaban en el mensaje fijo del CV.

**Queda (no es de Granite):**
- Algunas preguntas de contacto acaban en "about" en lugar de en el CV, con cualquier modelo.
- Granite dio una respuesta vacía de contenido (solo números de cita) a una de ellas en "about" (texto en `RESPUESTAS_ARCHIVADAS.md` §9).
- Es el umbral de "about" (8b).

**Web:**
- `Makefile`: `API_MODELS ?= default,llm-qwen3-1.7b,llm-granite-micro`, con `API_DIRECT_ONLY` vacío.
- `web/src/App.tsx`: nota "IBM Granite · best answers · slowest".
- El soporte de "solo directo" sigue en el código por si vuelve el 4B.

## 8d — Despliegue desde tu ordenador (preparado, 2026-10-27)

Guía completa en `deploy/local/README.md`.

**Opciones de túnel** comparadas en la guía: Tailscale Funnel (gratis, URL fija `*.ts.net`), ngrok gratis (página de aviso antes de la web; 1 GB/mes), Cloudflare Tunnel (ver §8d.2) y DuckDNS + router + Caddy (expone tu IP; no funciona con CGNAT). Crear la cuenta e instalar el cliente lo haces tú.

**Qué ha cambiado:**

| Fichero | Cambio |
|---|---|
| `src/api/app.py` | `RAG_API_MAX_QUEUE`: preguntas como mucho a la vez (contestando o esperando); a partir de ahí, error "The server is busy… try again in a minute". 0 (por defecto) = sin límite, como antes |
| `Makefile` | `make api-public` = `make api` con `API_MAX_QUEUE=4` y `RAG_ALLOWED_ORIGINS=$(PUBLIC_ORIGIN)`. `make api` pasa ahora `RAG_ALLOWED_ORIGINS='*'`, que ya era su valor por defecto |
| `web/src/App.tsx` | Los errores de la API se muestran una vez ("Error: …"), no "Error: Error: …" |
| `tests/test_api.py` | Test de la cola llena |
| `deploy/local/README.md` | Guía nueva |

**Ensayo con `make api-public`** (`data/output/night2/web8d.py`, 3080 Ti, todos los dominios):

| Paso | Primer token | Total | GPU |
|---|---|---|---|
| 1.7B directo (vLLM) | 1.3 s | 4.7 s | 7.9 GB |
| 1.7B con agente (CV) | 2.2 s | 6.4 s | 7.9 GB |
| Granite directo, 1.ª (incluye la carga) | 4.7 s | 6.9 s | 10.5 GB |
| Granite directo (XQuAD/ES) | 0.7 s | 1.4 s | 10.6 GB |
| Granite con agente (CV) | 10.8–13.9 s | 14.2–17.6 s | 10.7 GB |
| Granite con agente, seguimiento con memoria | 6.8–10.7 s | 8.2–11.5 s | — |
| 0.6B con agente, 1.ª (incluye la carga) | 9.2 s | 11.4 s | 5.4 GB |
| Vuelta al 1.7B, 1.ª | 3.5 s | 7.6 s | — |

- **Privacidad:** 0 fugas en las respuestas. Las 5 fuentes de una respuesta de contacto, pedidas enteras por `/sources`, no muestran ningún dato privado.
- **Cola (límite 4):** 7 preguntas a la vez → 4 respondidas y 3 con el aviso de servidor ocupado, en 16.9 s.
- **Granite con agente es lento:** 11–14 s hasta el primer token (reescritura, llamada a la herramienta y respuesta). Es lo que hay que valorar para la web.

### 8d.2 — Túneles comprobados y medidas de seguridad (2026-10-28)

**Petición tuya:** probar Cloudflare y Tailscale Funnel, y saber qué medidas de seguridad tomar antes de abrir tu ordenador.

**Lo comprobado en la documentación oficial** (guía actualizada en `deploy/local/README.md`):
- **Cloudflare, túnel rápido** (sin cuenta, URL aleatoria): no admite Server-Sent Events, y el chat de la web los usa para el streaming. No sirve para la web.
- **Cloudflare, túnel con nombre** (URL fija): exige cuenta y un dominio propio en Cloudflare, que es de pago.
- **Tailscale Funnel:** gratis, URL fija, el TLS se termina en tu PC (el relay no ve el contenido) y solo expone el puerto elegido. Sin `--bg`, el túnel se cierra con la terminal; con `--bg`, sobrevive a los reinicios. Se recomienda sin `--bg`.

**Qué ha cambiado:**

| Fichero | Cambio |
|---|---|
| `src/api/app.py` | `RAG_API_DOCS=0` oculta `/docs`, `/redoc` y `/openapi.json`. `/search` pasa por la misma cola que `/chat` (con la cola llena, error 503). `ServerBusy`, la excepción de la cola llena, para no confundirla con otros errores |
| `Makefile` | `API_DOCS ?= 1`; `make api-public` pone `API_DOCS = 0` |
| `tests/test_api.py` | 2 tests: `/search` con la cola llena y la documentación oculta |
| `deploy/local/README.md` | Tabla de túneles con lo comprobado, pasos sin `--bg`, prueba opcional del túnel rápido de Cloudflare y una sección de seguridad (qué queda expuesto, qué está protegido y qué riesgos quedan) |

`make api` sigue igual: documentación visible y sin límite de cola.

**Hallazgo pendiente de tu permiso:** Docker publica Qdrant (puertos 6333 y 6334) en todas las interfaces y sin contraseña. Desde tu red local se podría leer el índice, incluido el CV sin enmascarar, o borrarlo. El túnel no lo expone a internet. Propuesta: `"127.0.0.1:6333:6333"` y `"127.0.0.1:6334:6334"` en `docker-compose.yml`, y `docker compose up -d` (los datos están en un volumen con nombre).

**Comprobado:** 131 tests, flake8 y mypy limpios.

## 8g — Respuestas más elaboradas (sesión de noche del 27 al 28)

**Petición tuya:** las respuestas son muy cortas. Probar reglas por modelo; mismos parámetros, y si algo empeora, no se adopta.

**Causa:** la regla 6 del prompt, "Be direct and concise: a few sentences, no preamble.", que está desde la Fase 3. El límite de tokens no ha cambiado: la web sigue con 1024 (`API_MAX_TOKENS`). Las respuestas largas que recuerdas eran de Phi-4-mini (239 tokens de media), retirado en la Fase 7 (DEC-32).

### Mecanismo (sin cambiar nada por defecto)

| Fichero | Cambio |
|---|---|
| `src/config.py` | `GenerationConfig.style_rule`: regla 6 de un modelo (vacía = la de siempre). `SourceConfig.style_rule`: regla 6 de un dominio, por encima de la del modelo (`None` = la del modelo) |
| `src/rag/generator.py` | `STYLE_RULE` (la regla 6 actual); `build_messages(..., style_rule)` la sustituye cuando se da otra. `answer_with_text`, `stream_answer`, `build_prompt` y `fit_sources` aceptan la regla del dominio |
| `src/rag/domain_rules.py` | `style_rule(domain)` |
| `src/rag/pipeline.py`, `src/agent/agent.py` | Pasan la regla del dominio al generador solo cuando el dominio la define |
| `tests/test_generator.py` | La regla sustituye solo a la 6; la del dominio se lee de su fuente |

Sin `style_rule` en `rag.toml`, el prompt es idéntico byte a byte al anterior. Se prueba con la variable de entorno `RAG_GENERATION_STYLE_RULE`.

### Reglas probadas

| | Regla 6 |
|---|---|
| S0 | (la actual) Be direct and concise: a few sentences, no preamble. |
| S1 | Give a complete answer: start with the direct answer, then explain the relevant details from the SOURCES (how it works, steps, options or examples). Use a short list when there are several items. No preamble. |
| S2 | Answer in one or two short paragraphs: the direct answer first, then the most relevant details from the SOURCES. No preamble. |
| S3 | S1 + "Add only details stated in the SOURCES; if they do not answer the question, follow rule 4." |
| S4 | S2 sin "from the SOURCES" |
| S5 | Be direct, no preamble: give the answer, then explain it briefly in two or three more sentences. |

**Matriz** (la de 8a, `data/output/night2/run9.sh`): banco abierto (34 preguntas, como en la web); `gen-bench` a 1024 tokens de vLLM (25 por conjunto; 50 en el 0.6B, como en `97`), CV, "about" y XQuAD (300 por idioma); juez de Groq sobre vLLM (25 por conjunto). El 1.7B con S0 se volvió a medir (`120`) y salió idéntico a `97`: la generación es determinista, así que cada diferencia es de la regla.

### Qwen3-1.7B (`120`–`125`)

| | S0 | S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|---|---|
| Tokens, banco abierto (media / máx.) | 130 / 383 | 228 / 548 | 185 / 403 | 222 / 592 | 193 / 384 | 187 / 532 |
| Tokens vLLM docs (media) | 104 | 186 | 158 | 173 | 161 | 154 |
| Juez docs / code | 1.48 / 1.32 | 1.68 / 1.16 | 1.52 / 1.32 | 1.68 / 1.16 | 1.64 / 1.28 | 1.64 / 1.28 |
| Juez ES docs / code | 1.70 / 1.50 | 1.80 / 1.60 | 1.80 / 1.30 | 1.80 / 1.10 | 1.80 / 1.40 | 1.70 / 1.60 |
| Correctas según el juez (de 70) | 47 | 49 | 45 | 47 | 47 | **50** |
| Falso "no encontrado" code / ES code | 0.12 / 0.10 | 0.20 / 0.10 | 0.12 / 0.20 | 0.20 / 0.10 | 0.08 / 0.10 | 0.08 / 0.10 |
| Cita (docs / code / ES code) | 0.88 / 0.95 / 1.00 | 0.76 / 0.90 / 0.78 | 0.88 / 0.95 / 1.00 | 0.88 / 1.00 / 1.00 | 0.84 / 0.87 / 1.00 | 0.96 / 0.96 / 0.89 |
| Fuera de dominio cercano EN / ES | 0.8 / 0.7 | 0.9 / 0.7 | 0.9 / 0.8 | 0.9 / 0.8 | 0.9 / 0.8 | 0.9 / 0.7 |
| CV contiene EN / ES | 0.90 / 0.90 | 0.90 / 0.87 | 0.90 / 0.87 | 0.87 / 0.90 | 0.90 / 0.87 | 0.90 / 0.90 |
| CV sin respuesta (ES) bien tratadas | 7/7 | 5/7 | 7/7 | 6/7 | 6/7 | 6/7 |
| "about" contiene EN / ES | 0.56 / 0.61 | 0.61 / 0.67 | 0.61 / 0.61 | 0.67 / 0.61 | 0.67 / 0.67 | 0.61 / 0.67 |
| XQuAD contiene EN / ES | 0.79 / 0.68 | 0.81 / 0.71 | 0.82 / 0.71 | 0.76 / 0.68 | 0.82 / 0.72 | 0.81 / 0.72 |

El F1 baja con todas las reglas largas porque compara con referencias cortas; no es una señal de calidad.

**Lo que se ve:**
- **S1 y S3** (las "completas", con listas): inventan datos del CV (afirman que el autor no tiene algo que el CV no menciona) y suben los "no encontrados" falsos de code. Descartadas.
- **El CV es el punto débil de todas las reglas largas.** Con S1, S3, S4 y S5, alguna pregunta del CV sin respuesta acaba en una negación inventada seguida de "esta información no se encuentra" (texto en `RESPUESTAS_ARCHIVADAS.md` §9): al alargar, el modelo afirma un dato en lugar de dar el mensaje del CV. Por eso **el CV mantiene la regla corta** con cualquier modelo (`[sources.cv] style_rule`), y sus respuestas quedan como con S0.
- **S5 es la mejor:** la que más correctas tiene según el juez (50 de 70 frente a 47), menos "no encontrados" falsos en code, más citas en docs, y mejor en "about" y XQuAD. Lo que baja: en code, una correcta menos (15 frente a 16 de 25: contesta bien una que S0 no encontraba, deja sin encontrar una que S0 contestaba y en otra añade un tipo de más), y en code en español una respuesta sin cita (0.89 frente a 1.00). Son intercambios de preguntas sueltas, no un empeoramiento general, pero **no es un "no empeora nada" estricto**: lo marco para tu decisión.

### Granite 4.0 Micro y Qwen3-0.6B con S2

| | Granite S0 (`110`/`112`) | Granite S2 (`126`) | 0.6B S0 (`97`/`102`) | 0.6B S2 (`127`) |
|---|---|---|---|---|
| Tokens, banco abierto (media) | 179 | 175 | 78 | 183 |
| Banco abierto: cortadas / eco | 0 / 1 | **1 / 3** | 0 / 3 | 0 / 0 |
| Juez docs / code | 1.64 / 1.36 | 1.60 / 1.56 | 1.16 / 1.04 | 1.24 / **0.84** |
| Correctas según el juez (de 70) | 52 | 54 | 33 | 29 |
| Juez ES docs / code | 1.90 / 1.50 | 2.00 / 1.40 | 1.60 / 1.20 | 1.70 / **1.00** |
| Eco en vLLM docs | 0.04 | **0.32** | 0.00 | 0.00 |
| Falso "no encontrado" ES code | 0.00 | **0.20** | 0.10 | 0.00 |
| CV privadas ES bien tratadas | 2/2 (`112`) | **1/2** | 2/2 | 2/2 |

- **Granite no cambia:** ya escribía largo (179 tokens en el banco abierto, más que el 1.7B con cualquier regla). Con S2 no alarga; el juez sube algo (54 frente a 52 correctas), pero aparece eco (copia las fuentes) en un tercio de las respuestas de docs, una respuesta cortada, más "no encontrados" falsos en code en español y una pregunta privada del CV peor tratada. Se queda con la regla 6.
- **El 0.6B no cambia:** alarga mucho (78 → 183 tokens), pero baja en code (juez 1.04 → 0.84; correctas 11 → 5 de 25). Es la base de las comparativas con 42; se queda con la regla 6.

### Qwen3-1.7B con S5 desde `rag.toml`: agente y comprobación (`128`, `129`)

S5 se puso en el perfil del 1.7B y `style_rule` corta en `[sources.cv]`, y se midió la configuración real.

- **CV:** idéntico a S0 (`120`) en todas las cifras, incluidas las 7/7 preguntas sin respuesta en español. El CV queda protegido.
- **vLLM:** idéntico a S5 (`125`).
- **Banco abierto:** 176 tokens de media (frente a 130), 28/34 contestadas, sin cortes, eco, bucles ni frases repetidas.

**`agent-bench`**, los dos a 1024 tokens como en la web (contiene / no encontrado; agente):

| | S0 (`128`) | S5 (`129`) |
|---|---|---|
| Conversaciones, primera pregunta | 0.92 / 0.00 | **1.00** / 0.00 |
| Conversaciones, seguimiento | 0.78 / 0.11 | 0.78 / 0.11 |
| CV EN / ES | 0.90 · 0.80 | 0.90 · 0.80 (no encontrado ES 0.17 → 0.13) |
| XQuAD EN | 0.78 / 0.10 | 0.78 / **0.14** |
| XQuAD ES | 0.66 / 0.06 | **0.76** / 0.06 |
| vLLM code | 0.04 / 0.08 | **0.00 / 0.16** |
| Segundos por respuesta (code) | 5.0 | 6.7 |

Con el agente, S5 dobla los "no encontrados" falsos de code (de 2 a 4 de 25) y sube los de XQuAD en inglés. A cambio mejora la primera pregunta de las conversaciones y XQuAD en español.

### Decisión (según tu norma: si empeora, no se adopta)

- **Ningún modelo cambia su regla 6.** S5 era la mejor para el 1.7B (50 correctas de 70 frente a 47 en directo), pero empeora code: una correcta menos en directo y el doble de "no encontrados" falsos con el agente. Granite y el 0.6B empeoran con S2 (arriba).
- **Queda preparado:** en `rag.toml`, la línea `style_rule` del perfil `llm-qwen3-1.7b` está comentada. Si prefieres respuestas más largas en la web aunque se pierda algo en code, basta con descomentarla y reiniciar `make api` (el CV seguirá corto).
- **Se queda activo:** `style_rule` en `[sources.cv]`, que hoy no cambia nada (es la regla 6 de siempre) y protege el CV si algún modelo usa una regla larga. Los prompts de todos los modelos son los de antes.
- **Ojo si se activa S5:** la CLI y los benchmarks usan 150 tokens (`rag.toml`), y las respuestas de S5 pasan de esa cifra en docs (154 de media). En la web no afecta (1024).

**Ficheros de la sesión:** `data/output/night2/run9.sh`, `run9-stage2.sh`, `run9-stage3.sh` y `styles/` (ignorados por git); resultados en `bench/results/gen/` (`120`–`129`), `bench/results/judge/` y `data/output/gen_bench/<etiqueta>/answers.json`.

**Comprobado:** 129 tests, flake8 y mypy limpios. 42 no se ve afectado: el benchmark de recall no genera, y `answer_dataset` usa la regla de siempre.

## 8b — Umbral de "about" (2026-10-28)

**Objetivo:** recuperar preguntas del proyecto que no pasaban el filtro de "about" (−1.0) desde que la documentación dejó de citar las preguntas de prueba (DEC-39), sin dejar pasar preguntas de otros dominios ni de fuera de dominio. Decisión tuya: adelante.

**Cómo se ha medido:**
1. **`gate_scores`** de "about" sobre el índice actual (`131-about-gate`): con −1.0 pasan el 78 % (EN) y el 89 % (ES) de las preguntas del proyecto.
2. **Simulación del camino de la web** (`data/output/night2/gate8b.py`, `132-gate8b`): cada pregunta pasa una vez por el router (todos los dominios, las fuentes de `answer_k`) y la decisión del router se repite con cada umbral (la regla léxica del proyecto incluida). 2 790 preguntas: 42 (docs y code), complemento en español, XQuAD EN/ES, CV, "about", fuera de dominio, CV sin respuesta y el banco abierto.
3. **Respuestas reales** de las preguntas que cambian, con el 1.7B y el 0.6B (`gate8b_gen.py`).

**Preguntas que cambian respecto a −1.0** (en el resto de los 2 790, el resultado es el mismo con todos los umbrales; 42, XQuAD y CV llegan igual a su dominio):

| Pregunta | −1.25 | −1.5 | −2.0 |
|---|---|---|---|
| about-EN, el modelo por defecto | ✅ responde bien (los dos modelos) | ✅ | ✅ |
| Banco abierto, el reranker (EN) | ✅ responde bien (los dos) | ✅ | ✅ |
| about-EN, la función que lista los ficheros | El 1.7B: no encontrado; el 0.6B: respuesta incorrecta | igual | igual |
| about-ES, el reranker | no encontrado | ✅ responde bien (los dos) | ✅ |
| about-EN, el reranker | no encontrado | no encontrado | pasa |
| XQuAD-ES, una pregunta sobre el título de un artículo | ❌ pasa a "about" y responde mal (antes: no encontrado) | ❌ | ❌ |
| CV sin respuesta (carnet de conducir, EN) | pasa a "about": no encontrado | igual | igual |
| Fuera de dominio: una pregunta de deportes | no encontrado | ❌ **el 1.7B lo contesta** con la documentación | ❌ |
| Fuera de dominio cercanas (ES), 2 | no encontrado | no encontrado | ❌ pasan a "about" |
| Banco abierto: los modelos del sistema y cómo se hizo la web | no encontrado | no encontrado | pasan (−1.75 y −2.0) |

**Decisión: −1.25** (`rag.toml`, `[sources.about] relevance_threshold`). Recupera dos preguntas del proyecto con los dos modelos y no deja pasar nada de fuera de dominio. Coste: una pregunta de XQuAD en español, que ya no llegaba a su dominio, pasa de "no encontrado" a una respuesta incorrecta. −1.5 recuperaría una pregunta más en español, pero el 1.7B contestaría una pregunta de fuera de dominio con la documentación.

**Nota:** "¿Qué hace el agente de este proyecto?" (peor en §8h) vuelve a "about" con el índice final, incluso con −1.0: al reindexar después de §8h cambiaron otra vez los cortes de los fragmentos. Las preguntas al límite del umbral se mueven con cada cambio de la documentación.

**Sin medir aún:** el `route-bench` oficial (k = 10) y el `gen-bench` de "about" con el umbral nuevo. La simulación cubre las mismas preguntas por el camino de la web. Quedan para cuando la GPU esté libre (con la web en marcha, compiten por ella).

**Ficheros:** `rag.toml` (umbral y comentario). Scripts ignorados por git: `data/output/night2/gate8b.py` y `gate8b_gen.py`; resultados en `bench/results/gate/` y `data/output/night2/132-gate8b.json`.

## 8h — Documentación al día para "about" (2026-10-28)

**Petición tuya:** actualizar los documentos para que "about" no se líe. Con el filtro de idioma de "about" (DEC-34), las preguntas en inglés solo ven `docs/`, y allí no había nada de la Fase 8.

**Qué ha cambiado:**

| Fichero | Cambio |
|---|---|
| `README.md`, `docs/es/README.md` | Modelos: Qwen3-0.6B (base), Qwen3-1.7B (por defecto en la web), Qwen3-4B (CLI y benchmarks) e IBM Granite 4.0 Micro. Selector de modelos de la web. Despliegue actual: desde el ordenador del autor con un túnel. `deploy/local` en la estructura. "about" pasa a ~3 000 fragmentos |
| `docs/changelog/FASE_8.md` | Nuevo: traducción al inglés de este changelog |
| `docs/ROADMAP.md` | Fase 8 traducida, diagrama, P12 y registro |
| `docs/es/ROADMAP.md`, `docs/ROADMAP.md` | Notas de "hoy vigente" junto al texto histórico: el plan de despliegue de la Fase 6 (Space, después Oracle), el 4B fuera de la web, y el problema del 4B marcado como resuelto |
| `docs/es/BENCHMARK_REPORT.md`, `docs/BENCHMARK_REPORT.md` | §10 nuevo (Granite y la longitud de las respuestas) y, en §8, qué modelos están hoy en la web |
| `docs/es/changelog/FASE_8.md` | Las citas literales de respuestas inventadas del CV (§8g) y una respuesta vacía de Granite (§8a.2) pasan a `RESPUESTAS_ARCHIVADAS.md` §9 (DEC-39) |

"about" reindexado (`make index SOURCE=about`): 1 005 padres y 3 015 hijos (con este apartado incluido).

**Comprobado con el 1.7B, como en la web** (`data/output/night2/about8.py`, 12 preguntas sobre lo nuevo):
- **Bien:** los modelos de la web (inglés), Granite, el 4B fuera de la web, dónde está desplegada (español), por qué no Cloudflare (los dos idiomas) y por qué las respuestas son cortas. Antes de las notas de "hoy vigente", la web aparecía desplegada en Oracle o en el Space, y la lista de modelos incluía Phi.
- **No llegan a "about":** "¿Qué modelos puedo elegir en la web?" (no encontrado) y "Where is the web hosted?" (va a vLLM). No pasan el filtro de "about": es el umbral de 8b.
- **"Does this project use IBM Granite?"** va a vLLM, cuya documentación lista modelos Granite. Es una pregunta ambigua.
- **Preguntas del CV sin respuesta** (mascotas, carnet): acaban en "about" con "no encontrado", no en el mensaje del CV. Ya pasaba (8b).

**Banco abierto, 1.7B** (`130` frente a `120`): 29/34 contestadas, sin cortes, eco, bucles ni frases repetidas, 125 tokens de media. Cambian 6 respuestas: 5 de "about" iguales o mejores, y **una peor**: "¿Qué hace el agente de este proyecto?" pasa de "about" al CV y responde mal. Antes pasaba el filtro de "about" con 0.03 de margen (−0.97 frente al umbral de −1.0); al crecer el README cambian los cortes de sus fragmentos y el mejor queda en −1.46. Es el problema del umbral de "about" (8b): con el umbral actual, cualquier cambio en la documentación mueve las preguntas que están en el límite.

42 no cambia: vLLM no se ha reindexado.
