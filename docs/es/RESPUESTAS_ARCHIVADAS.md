# Respuestas archivadas: preguntas de prueba y respuestas incorrectas, al pie de la letra

> **Fuera del índice de "about"** (`exclude_paths` en `[sources.about]` de `rag.toml`). No se traduce.
>
> **Por qué existe** (DEC-39, `changelog/FASE_7.md` §7b.9): los changelogs y `decisions.md` copiaban literalmente las preguntas de prueba y las respuestas malas de los modelos. Al hacer esa misma pregunta en la web, la búsqueda devolvía la nota que la citaba en lugar de la respuesta, y el modelo respondía con el historial. Desde el 2026-10-27, los documentos indexados nombran las preguntas por su identificador y describen los fallos sin copiarlos. El texto literal se conserva aquí, como historial.
>
> **Regla para lo que se escriba a partir de ahora:** en los documentos indexados, ni el texto de una pregunta de prueba sobre el proyecto ni una respuesta incorrecta copiada. Se usa el identificador y una descripción; lo literal va aquí.

---

## 1. Identificadores

### `A-NN`: banco de preguntas abiertas

Las 16 primeras preguntas de `data/output/night2/open_bench.py` (las del proyecto; el resto son del CV, vLLM, XQuAD y fuera de dominio). Se hacen como en la web: todos los dominios, modo directo y 1.024 tokens.

| Id | Pregunta |
|---|---|
| A-01 | Hablame sobre este rag |
| A-02 | Háblame sobre este rag |
| A-03 | Tell me about this RAG |
| A-04 | What is RAG against the Machine? |
| A-05 | ¿Qué es RAG against the Machine? |
| A-06 | What does this project do? |
| A-07 | ¿Qué hace el agente de este proyecto? |
| A-08 | ¿Qué modelos usa este sistema? |
| A-09 | How was this website built? |
| A-10 | ¿Quién ha hecho esta aplicación? |
| A-11 | Which reranker does your system use? |
| A-12 | How does the router choose a domain? |
| A-13 | ¿Qué modelo de lenguaje usa el proyecto? |
| A-14 | ¿Cómo se mide el recall? |
| A-15 | How does the hybrid search work? |
| A-16 | ¿Por qué se eligió Qwen3-0.6B como modelo base? |

A-04, A-12 y A-14 son además preguntas de ejemplo de la web (`web/src/examples.ts`), y A-13 sustituye allí a una que no pasaba el filtro (§3, `FASE_7.md` §7a.8).

### `about-NN`: benchmark de "about"

Las 18 preguntas de `bench/datasets/about/questions.json`, cada una en inglés y en español.

| Id | EN | ES |
|---|---|---|
| about-01 | What is RAG against the Machine? | ¿Qué es RAG against the Machine? |
| about-02 | Which language model does the project use by default? | ¿Qué modelo de lenguaje usa el proyecto por defecto? |
| about-03 | Which embedding model does the retrieval use? | ¿Qué modelo de embeddings usa la recuperación? |
| about-04 | Which reranker does the project use? | ¿Qué reranker usa el proyecto? |
| about-05 | Which database stores the chunks and their vectors? | ¿Qué base de datos guarda los chunks y sus vectores? |
| about-06 | How does the router choose which domain answers a question? | ¿Cómo elige el router qué dominio responde una pregunta? |
| about-07 | How much did recall improve on the official 42 benchmark? | ¿Cuánto mejoró el recall en el benchmark oficial de 42? |
| about-08 | Does the agent remember the conversation? | ¿Recuerda el agente la conversación? |
| about-09 | How is the Python code split into chunks? | ¿Cómo se divide el código Python en chunks? |
| about-10 | Which tools does the MCP server expose? | ¿Qué herramientas expone el servidor MCP? |
| about-11 | Where is the project deployed? | ¿Dónde se despliega el proyecto? |
| about-12 | Under which license is the project released? | ¿Bajo qué licencia se publica el proyecto? |
| about-13 | When does a retrieved source count as a hit in the 42 evaluation? | ¿Cuándo cuenta como acierto una fuente recuperada en la evaluación de 42? |
| about-14 | Which databases were compared before choosing Qdrant? | ¿Qué bases de datos se compararon antes de elegir Qdrant? |
| about-15 | Why does the docs branch skip the reranker? | ¿Por qué la rama de documentación no usa el reranker? |
| about-16 | Which function lists the files of a source before indexing them? | ¿Qué función lista los ficheros de una fuente antes de indexarlos? |
| about-17 | How does the web's Stop button stop the generation? | ¿Cómo detiene la generación el botón Stop de la web? |
| about-18 | What does the agent do if its rewritten query finds nothing? | ¿Qué hace el agente si su consulta reescrita no encuentra nada? |

### `L-N`: las tres preguntas que hacían entrar a Phi-4-mini en bucle

Reproducción de `FASE_7.md` §7b.2 y `DETECTOR_BUCLES.md` §1 (Phi-4-mini en GPU, 10 fuentes, 1.500 tokens).

| Id | Pregunta |
|---|---|
| L-1 | Give me a step-by-step guide to serve a model with vLLM |
| L-2 | List all the command-line options of vllm serve |
| L-3 | Paso a paso de vLLM |

---

## 2. Bucles de Phi-4-mini (`DETECTOR_BUCLES.md` §1 y §6, `FASE_7.md` §7b.2, `FASE_6.md`)

**a) L-1, la misma línea una y otra vez:**
```
26. For more information on how to use the vLLM features, refer to ... (Source: [1])
27. For more information on how to use the vLLM features, refer to ... (Source: [1])
28. For more information on how to use the vLLM features, refer to ... (Source: [1])
...
```

**b) L-2, dos líneas que se alternan:**
```
29. `--help=serve=ApiServerCount`: Shows the argument group for the number of API servers. [1]
30. `--help=serve=Headless`: Displays the argument group for running the server in headless mode. [1]
31. `--help=serve=ApiServerCount`: ...
32. `--help=serve=Headless`: ...
```

**c) L-3, la misma frase con una palabra cambiada, en prosa:**
> En la **séptima** etapa, la respuesta se compara con el umbral por dominio… En la **décima** etapa, la respuesta se compara con el umbral por dominio… En la **decimotercera** etapa, la respuesta se compara con el umbral por dominio…

Las tres terminaban con "step step step step…" hasta el límite. Tras el detector, la respuesta recortada de L-3 aún conserva "séptima… octava… novena… décima etapa".

**`FASE_6.md` (revisión de la web):** con L-3, Phi repetía una plantilla desde el paso ~20 y se inventaba opciones (`--response-func`…).

**`decisions.md` DEC-28 y `FASE_7.md` §7b.7:** el ciclo de 4 frases que la ventana 8 no detectaba empezaba por "The Spanish BENCHMARK_REPORT.md file…".

---

## 3. "about" y el router (`FASE_7.md` §7a.3, §7a.7, §7a.8 y §7b.5)

- **§7a.3:** el 1.7B, ante una pregunta personal del CV, añadió *"la respuesta se presenta con el agente por defecto (D7)"* (jerga interna de los changelogs).
- **§7a.7:** about-01 (EN/ES) se iba al CV; about-02 y about-11 (EN), a vLLM; about-03 y about-09 (EN y ES), a vLLM.
- **§7a.8:** el ejemplo de la web *"¿Qué modelos usa el proyecto?"* iba a vLLM (−0.83) y no pasaba el filtro. Se sustituyó por A-13.
- **§7b.5 y DEC-24:** "What is Chrystian's contact e-mail?" acababa en "about", que la respondía con código.
- **DEC-24 y DEC-33:** las frases fijas de `route_names` eran "rag against the machine", "este/esta/tu/vuestro + rag/proyecto/sistema/chatbot/asistente/web/aplicación" y "this/your + rag/project/system/chatbot/assistant/website/app". Pregunta absurda de ejemplo: "¿qué tiempo hace en este rag?". Formulaciones nuevas que quedaban fuera: "vuestro sistema", "la app".

---

## 4. Eco del prompt (`FASE_7.md` §7b.3 y §7b.7, DEC-21, DEC-22, DEC-27 a DEC-31)

- **Phi con A-04 (§7b.3):** la "respuesta" eran las 5 fuentes copiadas con sus cabeceras (`[1] --- file: README.md ---…`), y la respuesta de verdad (`ANSWER: …`) llegaba al final, cortada.
- **0.6B (§7b.3):** acababa con *"The answer is in English, citing the sources by number."*
- **0.6B con A-01 (§7b.7):** *"The answer in Spanish, citing the sources by number, is: [1] "Hablame sobre este rag" and [4] …"*. Antes del arreglo del patrón, la limpieza se comía la respuesta entera.
- **Phi con A-01 (§7b.7):** de 873 tokens de fuentes copiadas pasó a *"No se encuentra en las fuentes proporcionadas."*
- **Phi con A-05 (DEC-30):** la respuesta escrita dos veces: "…dispositivo). La respuesta en español, citando las fuentes, es: <la misma respuesta>" (773 tokens).
- **Phi con A-15 (DEC-30):** un ciclo de 14 frases, 1.016 tokens, cortada.
- **Ficha antigua del Space (§7b.7, DEC-25, DEC-31):** Phi repetía "Hugging Face Space" y "Agent (default)".
- **DEC-26:** citas mal formadas de Phi (`[langchain](1)`) y el cierre contradictorio ("no se encontró información…" después de responder).
- **DEC-29:** prohibir solo las cabeceras daba "[1] [2] [3]…".
- **DEC-29, versión `91-*`:** el 0.6B, en una pregunta de XQuAD/ES sobre Toyota, pasaba de "2017" (correcto) a "febrero de 2014". En otra de XQuAD/EN respondía "30%" con la referencia "up to 30%".
- **DEC-31:** una forma rara de "no encontrado" de Phi: "No encontrado en los proporcionados fuentes."

---

## 5. Recuperación sin las trampas (DEC-33)

Qué respondían las preguntas que nombran el proyecto al quitar `route_names`:

| Pregunta | Sin la regla |
|---|---|
| A-01 / A-02 | vLLM: habla de la técnica RAG en general, o "no encontrado" |
| A-03 | vLLM: la técnica RAG con vLLM + LangChain |
| A-06 | XQuAD: un contrato de obra ("design build") |
| A-10 | XQuAD: "el informe del IPCC" (0.6B) / la teoría de Aristóteles (1.7B) |
| A-07 | CV: describe el otro proyecto de agentes del autor (MBPP, SWE-bench) |
| A-08 / A-09 / A-11 | about, pero su filtro las rechaza: "no encontrado" |

---

## 6. Pista de idioma (DEC-36, `96`)

- about-01/ES con el 0.6B: respondía solo `[1]`.
- about-10/ES: la mitad de la respuesta en inglés.

---

## 7. La documentación se cita a sí misma (DEC-37, `97`–`100`)

**`97` frente a `95`:**

| Pregunta | Modelo | Respuesta |
|---|---|---|
| A-15 | 0.6B | `[1] "How does the hybrid search work?" 1,016 → 307 tokens, without the cycle.` |
| A-09 | 0.6B | `The answer in Spanish, citing the sources by number, is: [1] "Hablame sobre este rag" and [4] "…". Phi cannot find it.` |
| A-04 | 0.6B y 1.7B | Explica `strip_echo` |
| A-06 | 1.7B | Explica cómo se enruta esa misma pregunta a "about" |

**`99` (sin historial):** A-02 respondía solo `[3]`.

**`100`, banco abierto:**

| Pregunta | Modelo | Respuesta (inicio) |
|---|---|---|
| A-04 | 0.6B | "The only option measured without losses is option A, which improves the recall for the "about" recall in the open bank by 0.53 and 0.67. The sources are cited a…" |
| A-13 | 0.6B | "No se encuentra en las fuentes proporcionadas." |
| A-13 | 1.7B | "The question "¿Qué modelo de lenguaje usa el proyecto?" is answered by the `about` domain, which has a score of 1.09. The answer is cited as the `about` domain…" |
| A-09 | 0.6B y 1.7B | El texto de DEC-37 |

**En la web, tras `100` (lo que vio el autor el 2026-10-27):**
- A-04, 1.7B: *"The `clean_output` function in the `decisions.md` file provides the rationale for the decision to use option A, which is to use `strip_echo` in `clean_output` to keep what follows the last `ANSWER:` and drop the repeated instruction. …"*
- A-13, 0.6B: *"No se encuentra en las fuentes proporcionadas."*

---

## 9. Fase 8: Granite y la longitud de las respuestas (`FASE_8.md` §8a.2 y §8g)

**§8a.2, Granite, pregunta de contacto que acabó en "about":** *"[5], [2][3]"* (solo números de cita, sin contenido).

**§8g, Qwen3-1.7B con reglas de respuesta largas, preguntas del CV sin respuesta en español (`gen-bench`, `cv-ood/es-missing`):**

| Regla | Pregunta | Respuesta |
|---|---|---|
| S1 | ¿Tiene Chrystian carnet de conducir? | "No, Chrystian Donaire Villén no tiene carnet de conducir. Esta información no se encuentra en los documentos proporcionados." |
| S1, S3, S5 | ¿Tiene mascotas Chrystian? | "No, Chrystian Donaire Villén no tiene mascotas. Esta información no se encuentra en ningún de los fuentes proporcionadas." (S3: "…en los documentos proporcionados.") |
| S4 | ¿Qué salario pide Chrystian? | "Chrystian Donaire Villén no menciona específicamente un salario en sus fuentes. Su enfoque principal es desarrollar software…" (contesta en lugar de dar el mensaje del CV) |

Con la regla 6 de siempre (S0), las tres acaban en el mensaje del CV.

---

## 8. Lo que no se ha movido aquí

- **Las transcripciones del CV** ya estaban fuera del índice, marcadas con `about:skip` (`FASE_4.md` §4b, `FASE_5.md`, `FASE_6.md`; §7a.6). Se quedan donde estaban.
- **"What is the capital of France?" → "Paris"** (B15, `FASE_0.md`, `FASE_3.md`, `FASE_6.md`, ROADMAP): no es una respuesta incorrecta. La documentación de vLLM trae esa pregunta como ejemplo de la API (`FASE_3.md`).
- **Las preguntas de vLLM, XQuAD y CV citadas sin respuesta mala** (tablas de umbrales, router, ejemplos de la web): no son del proyecto y "about" no compite por ellas.
- **El código** (`src/rag/loops.py`, `src/rag/generator.py`): sus comentarios llevan fragmentos cortos de ejemplo ("step step step…"). Es documentación del código, no se ha tocado.
