# Detector de bucles: qué he hecho y cómo funciona

> Explicación detallada del detector de bucles de la Fase 7b. El resumen está en `changelog/FASE_7.md` §7b.2 y el código en `src/rag/loops.py`.

---

## 1. El problema, visto de cerca

Antes de tocar nada reproduje el fallo: Phi-4-mini en la GPU, 10 fuentes, un límite de 1.500 tokens y 6 preguntas largas de "paso a paso" y de listas. Tres de las seis se quedaron en bucle hasta agotar el límite. Hay **tres formas distintas** de bucle (las preguntas L-1 a L-3 y las salidas literales están en `RESPUESTAS_ARCHIVADAS.md`, fuera del índice de "about"):

**a) La misma línea una y otra vez** (L-1): a partir del paso 26 de una lista, el mismo paso con otro número delante.

**b) Dos líneas que se alternan** (L-2): desde la opción 29 de una lista, dos opciones que se repiten una detrás de otra.

**c) La misma frase con una palabra cambiada, en prosa y sin saltos de línea** (L-3): una frase larga que se repite cambiando solo el ordinal de la etapa.

Las tres terminaban además con la misma palabra repetida hasta el límite.

**Por qué no servían las soluciones anteriores:**
- **`repetition_penalty`** (tu observación era correcta): en el caso (c) Phi cambia una palabra en cada vuelta (el ordinal). La penalización castiga tokens repetidos, pero la frase nunca es idéntica. Además castiga repeticiones legítimas, como nombres de clases en código.
- **El detector de n-gramas exactos** de la Fase 6 ("parar si se repite la misma secuencia de N palabras") saltaba en 32 de 3.933 respuestas buenas, porque las listas y el código repiten secuencias de forma natural. Y no cazaba el caso (c).
- **La plantilla y los tokens de parada** estaban bien (lo comprobamos): Phi no deja de escribir porque nunca "quiere" cerrar el turno, no porque no sepa cómo.

## 2. La idea

En vez de buscar **palabras** repetidas, el detector busca **frases o líneas casi iguales**. Si al leer la respuesta ves que las últimas frases son prácticamente la misma con un detalle cambiado, sabes que el modelo ha entrado en bucle. El detector hace exactamente eso:

1. Parte la respuesta en **unidades**: líneas y frases.
2. **Normaliza** cada unidad para que lo que cambia en cada vuelta (el número de la lista, la cita) no esconda la repetición.
3. Mira las **últimas 12 unidades** (eran 8 hasta el 2026-10-26, §8). Si **5 o más** son casi copias de alguna anterior de esa ventana, es un bucle.
5. **Bloques repetidos** (añadido el 2026-10-26, §8): si las últimas 6 unidades o más repiten, una a una, las de un poco antes (un ciclo de hasta 40 unidades), también es un bucle.
4. "Casi copia" significa **parecidas al 95 % o más**, carácter a carácter.

Con eso, los tres casos caen:
- **(a)** Las líneas son idénticas al quitar el número: similitud 1.0.
- **(b)** Cada línea es idéntica a la de dos posiciones antes: similitud 1.0.
- **(c)** Dos vueltas de la misma frase con distinto ordinal: similitud **0.97**, porque solo cambia una palabra en una frase larga.

## 3. El código, pieza a pieza (`src/rag/loops.py`)

### 3.1 Los parámetros

```python
WINDOW = 12         # cuántas unidades recientes se miran (antes 8)
REPEATS = 5         # cuántas casi copias hacen falta para declarar bucle
SIMILARITY = 0.95   # cuánto se tienen que parecer dos unidades
MIN_WORDS = 3       # las unidades más cortas no cuentan ("[1]", "Paso 3:")
WORD_RUN = 12       # la misma palabra 12 veces seguidas ("step step step…")
BLOCK = 6           # unidades seguidas que repiten un bloque anterior (§8)
MAX_PERIOD = 40     # el ciclo más largo que se busca, en unidades
```

No los elegí a ojo: probé varias combinaciones (§5). Los de arriba son los que detectan todos los bucles sin ningún falso positivo. La variante más agresiva (`REPEATS = 4`) ya se equivocaba en 1 documento y 4 respuestas buenas.

### 3.2 Partir en unidades

```python
UNITS = re.compile(r"(?<=[^\d\s][.!?])[ \t]+|\n")
```

Corta en cada salto de línea y después de cada `.`, `!` o `?` seguido de espacio. Así sirve para las listas (una línea por elemento) y para la prosa (caso c, todo en un párrafo).

**El detalle `[^\d\s]`:** el punto tiene que ir después de algo que **no sea un número**. Si no, en un elemento de lista como "5. Texto…", el "5." contaría como una frase propia, y al recortar quedaba un "5." colgando al final de la respuesta. Lo encontró uno de los tests nuevos.

### 3.3 Normalizar

```python
def normalise(unit):
    unit = CITATION.sub("", LIST_MARK.sub("", unit.lower()))
    return " ".join(unit.split())
```

Quita lo que cambia en cada vuelta sin cambiar el contenido:
- **Numeración de lista** (`27.`, `-`, `*`, `##`): si no, el mismo elemento con los números 27 y 28 parecería distinto.
- **Citas** (`[1]`, `(Source: [3])`): el modelo a veces cambia el número de la fuente en cada vuelta.
- **Mayúsculas y espacios de más.**

### 3.4 Lo que no se compara

```python
def structured(unit, in_code):
    return in_code or unit.startswith("    ") \
        or stripped.startswith(("|", "<", "```", "===")) \
        or bool(LOG_LINE.search(stripped))
```

Hay contenido que **repite su forma por naturaleza** y que se confundiría con un bucle:
- **Tablas** (`| Llama-3.1-8B | 8B |`, `| Llama-3.1-70B | 70B |`…).
- **HTML.**
- **Logs** con fecha y hora (`INFO 08-01 22:26:48 …`).
- **Bloques de código** y líneas sangradas.

Sin esta regla, el detector saltaba en 4 de los 202 documentos de prueba (10 con una configuración más agresiva), todos por tablas, logs o HTML. Con ella, en ninguno.

### 3.5 La búsqueda del bucle

```python
for unit in UNITS.split(text):
    ...
    units.append(words); offsets.append(start)
    recent = units[-WINDOW:]                       # las últimas 12
    copies = [i for i in range(1, len(recent))
              if any(similar(recent[i], recent[j]) for j in range(i))]
    if len(copies) >= REPEATS:                     # 5 o más casi copias
        return offsets[first + copies[0]]          # dónde empieza el bucle
```

Recorre las unidades en orden. Para cada una mira si, en la ventana de las 12 últimas, hay 5 o más que repiten a otra anterior. Si las hay, devuelve **la posición (en caracteres) de la primera repetición**: ahí empieza el bucle.

`similar()` usa `difflib.SequenceMatcher` de la biblioteca estándar de Python, que da un número de 0 a 1 según cuánto texto comparten dos cadenas. No hace falta ningún modelo ni dependencia nueva.

La regla de la palabra repetida (`WORD_RUN`) va aparte, con una expresión regular. Si se cumplen las dos, gana la que empieza antes.

### 3.6 Recortar

```python
def cut_loop(text):
    at = find_loop(text)
    return text if at is None else text[:at].rstrip()
```

Si hay bucle, se queda con todo lo anterior. **Lo bueno se conserva**: los primeros 20–25 pasos de la lista, que eran correctos, siguen ahí.

## 4. Dónde se engancha (`src/rag/generator.py`)

El detector actúa en **dos momentos**:

**a) Durante la generación: para el modelo.** Al criterio de parada que ya existía (`Cancelled`, el del botón Stop) se añade otro, `Looping`:

```python
class Looping(StoppingCriteria):
    def __call__(self, input_ids, scores, **kwargs):
        last = tokenizer.decode(input_ids[0, -1:])        # el último token
        if BOUNDARY.search(last):                         # ¿cierra línea o frase?
            text = tokenizer.decode(input_ids[0, prompt_length:])
            stop = find_loop(text) is not None
```

`transformers` lo llama **en cada token**. Para no gastar tiempo, solo hace el trabajo cuando el último token trae un salto de línea, un punto, una exclamación o una interrogación, que es cuando ha terminado una unidad nueva y puede haber cambiado algo. El resto de tokens solo cuestan decodificar uno.

Este es el paso que **ahorra el tiempo**: sin él, el modelo seguiría escribiendo basura hasta el límite. Con él, para unas 5 repeticiones después de empezar el bucle.

**b) Al terminar: recorta.** En `clean_output()`, la limpieza final por la que pasan todas las respuestas:

```python
text = cut_loop(text.strip())
```

Hace falta porque el modelo para **cuando ya ha escrito** esas ~5 repeticiones (necesita verlas para estar seguro). El recorte las quita.

**En la web:** mientras se escribe, ves las repeticiones durante un instante. Al terminar llega el evento `done` con la respuesta final ya recortada, y la web sustituye el texto por esa versión. Por eso no llegas a ver el bucle.

**Dónde actúa:** en todo lo que genera texto (web, CLI, benchmarks y agente), porque todo pasa por el mismo `Generator`.

## 5. Cómo sé que no rompe nada

Un detector así tiene dos formas de fallar: **no ver un bucle** o, peor, **cortar una respuesta buena**. Medí las dos.

**Bucles reales** (las 3 respuestas de Phi del §1): los **3 detectados**.

**Falsos positivos**, con dos tipos de texto bueno:

| Texto bueno | Por qué es una buena prueba | Marcados como bucle |
|---|---|---|
| 202 documentos `.md` (vLLM, nuestros `docs/`, README y XQuAD) | Son largos, con listas, tablas, código y logs: el peor caso | **0** |
| 11.550 respuestas guardadas de todos los benchmarks (`gen-bench` y `agent-bench`, los cuatro modelos) | Son respuestas reales del sistema | **0** |

**Variantes que descarté:**

| Variante | Bucles | Falsos positivos |
|---|---|---|
| Solo líneas, sin frases | 3/3, pero el de prosa lo cortaba tarde (4.399 caracteres en vez de 1.828) | 0 |
| Sin excluir tablas, logs y código | 3/3 | **4 documentos** |
| `REPEATS = 4` (más agresivo) | 3/3 | 1 documento y **4 respuestas** |
| `SIMILARITY = 0.9` (más permisivo) | 3/3 | 1 documento y **2 respuestas** |
| **Elegida:** líneas + frases, `REPEATS = 5`, `SIMILARITY = 0.95` | **3/3** | **0 y 0** |

**Prueba real de extremo a extremo** (Phi generando de verdad con el detector puesto):

| Pregunta | Antes | Ahora |
|---|---|---|
| L-3 | 1.500 tokens, 67 s | **419 tokens, 34 s** |
| L-1 | 1.500 tokens, 69 s | **661 tokens, 47 s** |
| L-2 | 1.500 tokens, 73 s | **499 tokens, 35 s** |
| Las otras 3 (sin bucle) | 133, 248 y 493 tokens | **idénticas, carácter a carácter** |

**Tests** (`tests/test_loops.py`, 6 tests nuevos): línea repetida, dos líneas alternas, frases con una palabra cambiada, palabra repetida, y que tablas, código y una respuesta buena **no** se marcan. Además, `clean_output` recorta. En total, 117 tests en verde, con flake8 y mypy limpios.

## 6. Límites (lo que no hace)

- **Necesita ver ~5 repeticiones.** Un bucle de 2 o 3 vueltas que el modelo cierra solo no se toca. Es a propósito: con menos, aparecían falsos positivos.
- **Conserva algo de repetición.** En el caso de la prosa, la respuesta recortada aún tiene unas cuantas vueltas de la frase, que son las frases que el detector usa como referencia antes de confirmar el bucle.
- **Solo ve repeticiones, no errores.** Si el modelo se inventa una opción sin repetirse, el detector no lo ve. Eso es alucinación, otro problema.
- **No mira dentro de tablas ni de código.** Un bucle dentro de un bloque de código no se detecta.
- **Medido con Phi-4-mini en GPU.** Con los demás modelos no he reproducido bucles. Las 11.550 respuestas sin falsos positivos incluyen los cuatro modelos, pero con respuestas de 150 tokens.

## 7. Qué ha cambiado en ficheros

| Fichero | Cambio |
|---|---|
| `src/rag/loops.py` | **Nuevo.** `find_loop`, `cut_loop` y los parámetros |
| `src/rag/generator.py` | `clean_output` recorta bucles; `stopping_criteria` recibe la longitud del prompt y añade `Looping` |
| `tests/test_loops.py` | **Nuevo.** 6 tests |
| `Makefile`, `deploy/space/Dockerfile` | Límite de la web a 1.024 tokens para todos (antes 512, y 640 para Phi) |
| `docs/es/changelog/FASE_7.md` §7b.2, `docs/es/ROADMAP.md` | Documentado |
| `data/output/loop_detector/` (fuera de git) | Prototipo, preguntas de reproducción y respuestas antes y después |

**Los benchmarks no cambian:** con su límite de 150 tokens no hay bucles. Las cifras publicadas siguen siendo válidas.

## 8. Actualización (2026-10-26/27): ventana 12 y bloques repetidos

Con el banco de preguntas abiertas (`FASE_7.md` §7b.7) aparecieron dos formas de repetir que la ventana de 8 no veía:
- **Un ciclo de 4 frases** que se repetía entero: con 8 unidades no caben 5 copias. Con **12** sí (admite ciclos de hasta 7 frases) y no aparece ningún falso positivo nuevo (DEC-28 en `decisions.md`).
- **Un bloque largo** (14 frases) repetido, o la respuesta escrita dos veces con la instrucción del prompt repetida en medio. Para eso está la regla de bloque (DEC-30):

```python
def repeated_block(units):
    # Para cada periodo de 6 a 40 unidades: cuántas de las últimas
    # unidades repiten, una a una, la que está `periodo` posiciones antes.
    # Con 6 o más seguidas, el bucle empieza en la primera de ellas
    # (o una antes, si esa frase ya contiene a su pareja: el caso
    # "La respuesta… es: <primera frase>").
```

**Medido:** sin falsos positivos en 15.793 respuestas guardadas y 299 documentos. Con `BLOCK = 4` cortaba pasos de instalación repetidos en 4 documentos de vLLM; con 5 ya no, y se eligió 6 para tener margen.

**Sobre el código:** las tablas, los logs y los bloques de código **no se comparan nunca** (§3.4), así que el detector no corta código repetido. El riesgo que queda es el contrario: un bucle dentro de un bloque de código no se detecta (§6).

**Phi-4-mini, el modelo con el que se diseñó, se retiró el 2026-10-27** (DEC-32). El detector se queda porque es una regla general, que no depende de ningún modelo: es la red de seguridad para cualquier modelo que entre en bucle con el límite de 1.024 tokens de la web.
