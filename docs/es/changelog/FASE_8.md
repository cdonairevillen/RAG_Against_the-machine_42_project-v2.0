# CHANGELOG — Fase 8: Granite, despliegue y pruebas extra

Fase abierta el 2026-10-27, tras el commit `477bff9` (cierre de la Fase 7). El plan está en `ROADMAP.md` (Fase 8). Aquí se irá apuntando qué se cambia, por qué y en qué afecta, según las normas de `PLANING.md`.

**Regla añadida en la Fase 7 (DEC-39):** en este documento no se copia el texto de una pregunta de prueba sobre el proyecto ni una respuesta incorrecta. Se usa su identificador (`A-NN`, `about-NN`, `L-N`) y una descripción; lo literal va a `RESPUESTAS_ARCHIVADAS.md`, que está fuera del índice de "about".

## Estado

| Bloque | Estado |
|---|---|
| 8w — Web: 1.7B por defecto, 4B solo sin agente | ✅ Implementado y comprobado con la API real (§8w); opción A para la memoria del 4B |
| 8a — Granite | Granite 4.0 Micro (densa, 3B): matriz `110` medida (§8a), pendiente de tu evaluación |
| 8b — Umbral de "about" | Propuesto |
| 8c — Pista de idioma (opción C) | Propuesto, prioridad baja |
| 8d — Despliegue | Desde tu ordenador con un túnel, como parche (decisión tuya); Oracle y Hugging Face PRO, opciones para el futuro |
| 8e — Pruebas extra | Las de siempre (la matriz de los Qwen), para evaluar Granite |
| 8f — Plan B del agente | Entra (decisión tuya, 2026-10-27); sin empezar |

## Decisiones tuyas (2026-10-27)

- **La base sigue siendo Qwen3-0.6B** (benchmarks, CLI, comparativas con 42).
- **Web: Qwen3-1.7B por defecto**, para lucir más el RAG.
- **Web: Qwen3-4B vuelve a la lista, solo con el agente desactivado.**
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
