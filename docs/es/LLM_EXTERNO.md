# LLM externo: requisitos, modelos y lo que tienes que hacer tú

Documento de trabajo, **fuera del índice de "about"** (excluido en `rag.toml`, como `PLAN_FASES_9_10.md`). No se traduce. Escrito el 2026-11-11 para el paso 2 del orden acordado (`PLAN_FASES_9_10.md`, Fase 10).

**Objetivo:** un segundo modo de la web ("externo", azul con una nube) donde el RAG responde con un modelo potente alojado fuera, gratis y sin un límite de uso que se agote, mientras el modo local (rojo con el rayo) sigue enseñando los Qwen y Granite en tu 3080 Ti. La recuperación (BM25, `bge-m3`, reranker, router y filtros) es la misma en los dos modos; solo cambia quién redacta la respuesta.

---

## 1. Requisitos del proveedor y del modelo

### Imprescindibles

| Requisito | Por qué |
|---|---|
| **API compatible con OpenAI** (`/v1/chat/completions`, clave por `Authorization: Bearer`) | Un solo backend nuevo en `src/llm/` vale para NVIDIA, Groq y otros cambiando URL, modelo y clave. El juez (`src/evaluation/judge.py`) ya usa este formato. `llm_sdk/` no se toca |
| **Gratis, sin tarjeta y sin caducidad** | `PLANING.md`: no gastar dinero. Un plan de créditos que se acaban no sirve para una web que dura meses |
| **Límite por minuto razonable** (≥ 30 peticiones/min) | La web limita la cola a 4 preguntas. Con el agente, cada pregunta son ~4 llamadas (hasta 3 pasos + respuesta): con 40/min caben ~10 preguntas por minuto |
| **Condiciones que permitan una demo pública** | Algunos planes gratuitos son "solo para desarrollo o evaluación". Hay que leerlo antes de enseñarlo a empresas |
| **Streaming (SSE)** | `/chat` de la API va por streaming; sin él, el usuario espera la respuesta entera |
| **Llamadas a herramientas nativas** (*tool calling*) | El agente (Fase 5) decide las búsquedas con llamadas a herramientas. Sin esto, el modo externo no puede tener agente |
| **Español e inglés** | Preguntas en los dos idiomas y respuesta en el de la pregunta (regla del prompt) |
| **Contexto ≥ 8 000 tokens** | Hoy el prompt llega a ~3 000 tokens (`max_input_tokens = 3072`). Con un modelo grande conviene dar más fuentes; para el enriquecimiento (resúmenes por personaje) hace falta más |

### Deseables

| Requisito | Por qué |
|---|---|
| **Pesos abiertos** (Apache 2.0, MIT o licencia abierta de NVIDIA) | Coherente con el proyecto: todo lo local es abierto. Además, si el proveedor cierra, el modelo se puede alojar en otro sitio |
| **Que no sea demasiado grande ni lento** | Primer token en ~1–2 s. Tú lo dijiste: no hace falta un modelo enorme |
| **Razonamiento ("thinking") desactivable** | Los modelos con razonamiento escriben un bloque largo antes de responder: más latencia y más llamadas consumidas. Si no se puede apagar, se filtra (ya lo hacemos con Qwen) |
| **El proveedor no entrena con nuestras peticiones** | Por los datos del CV (ver §4) |
| **Que no sea el mismo modelo que el juez** | El juez es `gpt-oss-120b` en Groq. Si el generador es el mismo modelo, se juzgaría a sí mismo (sesgo). Si se elige, se cambia el juez |

---

## 2. Proveedores

| Proveedor | Lo comprobado (2026-11-11) | Lo que falta confirmar |
|---|---|---|
| **NVIDIA build.nvidia.com** (tu propuesta) | Catálogo de 100+ modelos abiertos, API compatible con OpenAI en `integrate.api.nvidia.com/v1`, sin tarjeta. Fuentes de terceros y el foro de NVIDIA hablan de **40 peticiones/min por clave** (una guía dice 30). Hay un aviso de error 403 con Nemotron 3 Super en algunas cuentas personales | La cifra oficial; si hay límite diario o de tokens; si caduca; si permite una demo pública; si guarda o usa las peticiones |
| **Groq** (ya lo usamos de juez) | Funciona con nuestra clave y el mismo formato | Sus límites diarios de tokens del plan gratuito; con el juez se agotaron alguna vez. Sirve como **plan B** si NVIDIA falla |

Ninguna cifra de esta tabla sale de una página oficial: compruébalas en tu cuenta cuando la crees.

---

## 3. Modelos aconsejados (a verificar en el catálogo)

No he podido ver el catálogo por dentro, así que **la disponibilidad de cada uno está por confirmar**. Te propongo buscar por familias, en este orden:

| # | Familia / modelo | Por qué | A comprobar |
|---|---|---|---|
| 1 | **Qwen3 grande** (por ejemplo, un Qwen3 MoE de decenas o cientos de miles de millones de parámetros) | **Misma familia que la base.** Es la mejor historia para la demo: "el mismo RAG, la misma familia de modelos, de 0.6B en un PC a un modelo grande en la nube". Comparaciones limpias con nuestros benchmarks | Que esté en el catálogo, que tenga *tool calling* y que se pueda apagar el razonamiento |
| 2 | **Nemotron Nano** (la versión de ~9B) | Pequeño y rápido, de NVIDIA (encaja con su catálogo), pensado para agentes | Que admita español y *tool calling* en el endpoint |
| 3 | **Nemotron Super** (la versión de ~49B, o Nemotron 3 Super) | Más capacidad para el agente y la síntesis entre varios tramos | El 403 de algunas cuentas; latencia |
| 4 | **`gpt-oss-20b` o `gpt-oss-120b`** (Apache 2.0) | Buenos con herramientas; el 120b ya lo conocemos como juez | Si se usa de generador, el juez debe ser otro (§1) |
| 5 | Llama 3.x de 70B, Mistral u otros | Alternativas si los anteriores fallan | Español y *tool calling* |

**Propuesta para la web:** un selector con **2–3 modelos** (por ejemplo, uno de la familia Qwen y uno Nemotron). Si un modelo da error de límite, el usuario cambia a otro y el sistema puede caer a uno local. Si prefieres uno fijo, el 1. Lo decides con las medidas.

**Cómo los mediría yo** (cuando tengas la clave): la misma matriz que los locales, `gen-bench` (vLLM, XQuAD, CV, "about" y `film`), banco abierto, `agent-bench`, idioma, eco, latencia y errores de límite. Comparado con el 1.7B y Granite.

---

## 4. Lo que tienes que hacer tú

### Para empezar (paso 2)

1. **Crear la cuenta** en build.nvidia.com y **generar la clave** (empieza por `nvapi-` según las guías; se muestra una sola vez).
2. **Ponerla en `.env`** con la línea `NVIDIA_API_KEY=nvapi-...`. `.env` ya está en `.gitignore`; yo no la leo, solo la usa el programa.
3. **Leer en tu cuenta y anotarme:**
   - El límite real (peticiones/min, y si hay límite diario o de tokens).
   - Si caduca o va por créditos.
   - Si las condiciones permiten una demo pública.
   - Qué hace el proveedor con las peticiones (si las guarda o entrena con ellas).
4. ~~Elegir 2–4 modelos candidatos~~ → **lo hago yo** (2026-11-11, al verte perdido con el catálogo): con la clave en `.env`, listo los modelos que tu clave puede usar (`/v1/models`), hago una prueba corta a los candidatos (respuesta en español, llamada a herramientas, latencia, errores de límite) y te traigo una tabla para que elijas.

**Prueba con tu clave (2026-11-11):** `/v1/models` lista 84 modelos, **sin ningún Qwen de texto**. Prueba corta a 14 candidatos: una pregunta en español con un tramo de *Shrek* como fuente ("¿Cuál es el secreto de Fiona?") y una llamada a herramientas (`search`).

| Modelo | Respuesta RAG | Herramientas | Latencia (total / primer token) |
|---|---|---|---|
| **`nvidia/nemotron-3.5-lightning-30b-a3b`** (razonamiento apagado con `chat_template_kwargs: {enable_thinking: false}`) | Correcta, en español, fiel a la fuente; **no citó [1]** | ✅ | 0.8–5.1 s / 0.3–0.5 s |
| **`nvidia/nemotron-3.5-bolt-e4b`** | Correcta, en español, fiel, con [1] | ✅ | 0.8–1.1 s / 0.3–0.5 s |
| `nvidia/nemotron-3.5-lightning-30b-a3b` con razonamiento | Gasta los 400 tokens pensando, sin respuesta | ✅ | 97 s |
| `nvidia/nemotron-3-ultra-550b-a55b` | Texto basura sin razonamiento; vacío con él | ❌ | — |
| `openai/gpt-oss-20b`, `deepseek-ai/deepseek-v4.1-flash`, `z-ai/glm-5.3-flash`, `minimaxai/minimax-m3.1-flash`, `mistralai/mistral-large-4-1t-a52b` | Sin respuesta en 60–90 s (colgados o saturados) | — | — |
| `nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-nano-3-30b-a3b`, `nvidia/llama-3.1-nemotron-70b-instruct`, `nv-mistralai/mistral-nemo-12b-instruct`, `moonshotai/kimi-k2.6`, `google/gemma-4-31b-it` | Error 404 "Not found for account": salen en la lista, pero tu cuenta no puede usarlos | — | — |

**Propuesta:** Lightning 30B-A3B como modelo principal del modo externo (MoE con ~3B activos: rápido, más capacidad que Bolt) y Bolt E4B como segundo del selector o reserva. Los dos de NVIDIA. Una sola pregunta no decide nada: se miden con la matriz completa (§3) antes de elegir.

**Visto en el catálogo de build.nvidia.com (2026-11-11, solo la primera página):** Nemotron 3.5 Lightning 30B-A3B (MoE rápido para agentes), Nemotron 3.5 Bolt E4B (compacto, con herramientas), Nemotron 3 Ultra 550B-A55B (enorme, con herramientas), `gpt-oss-20b`. No vi un Qwen de texto en esa página; puede estar en la segunda o solo en la API.

### Decisiones tuyas

| Decisión | Opciones | Cuándo |
|---|---|---|
| ~~El CV con el modelo externo~~ | **Decidido (tú, 2026-11-11): (b)**, también con el externo. Los fragmentos salen hacia el proveedor con los datos privados ya enmascarados; no hay información delicada en los documentos | Hecho |
| **Selector o modelo fijo** en el modo externo | Selector de 2–3 modelos / uno fijo | Paso 4, con las medidas |
| **Qué pasa si se agota el límite** | Mensaje de error / caer a un Qwen local (1.7B) / caer a Groq | Paso 3 |
| **Juez** | Mantener `gpt-oss-120b` en Groq (si el generador es otro) o cambiarlo | Si se elige un `gpt-oss` como generador |

### Lo que ya cubro yo (no tienes que hacer nada)

- El backend en `src/llm/`, el perfil `llm-<proveedor>-<modelo>`, el streaming, las herramientas del agente y la caída a un modelo local.
- Que la ruta local dé **las mismas respuestas** antes y después (garantía de `PLAN_FASES_9_10.md`, 10a) y que 42 no cambie.
- Las medidas, la documentación en `changelog/` y la web de dos modos (paso 4), contigo revisándola.
