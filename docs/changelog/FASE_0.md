# CHANGELOG — Fase 0: Saneamiento y profesionalización

**Fecha:** 2026-10-18
**Estado:** completada. Pendiente de tu revisión y commit (no se ha hecho ningún commit).

---

## 1. Resultado en una tabla

Datasets públicos de 42 (100 preguntas docs + 100 code), `k = 10`, evaluador original. Todas las ejecuciones están en `bench/results/`.

| Ejecución | Ruta | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 | Decisión |
|---|---|---|---|---|
| `00-baseline` | smart | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.61 / 0.63 / 0.68 | Línea base "antes" |
| `00-baseline` | generation | 0.70 / 0.82 / 0.89 / 0.89 | 0.23 / 0.55 / 0.62 / 0.70 | Ruta de `make search-*` (B3) |
| `01-fix-b2` | smart | = baseline (salida idéntica byte a byte) | = baseline | ✅ Adoptado |
| `02-fix-b1` | smart | 0.66 / 0.82 / 0.84 / 0.84 | 0.46 / 0.63 / 0.65 / 0.71 | ❌ Rompe 1 pregunta de docs |
| `02b-fix-b1-refined` | smart | 0.64 / 0.83 / 0.85 / 0.85 | 0.45 / 0.62 / 0.64 / **0.72** | ✅ Adoptado |
| `03-fix-b14` | smart | 0.65 / 0.82 / 0.84 / 0.85 | 0.43 / 0.58 / 0.63 / 0.75 | ❌ Empeora R@3; a Fase 2 |
| **`04-fase0-final`** | **smart** | **0.64 / 0.83 / 0.85 / 0.85** | **0.45 / 0.62 / 0.64 / 0.72** | **Línea base oficial v2.0** |
| `04-fase0-final` | generation | 0.70 / 0.82 / 0.89 / 0.89 | 0.23 / 0.55 / 0.62 / 0.70 | Sin cambios (no le afecta B1) |

**Neto:**
- Docs se queda igual, con cero preguntas cambiadas.
- Code mejora en todos los cortes, sin regresiones por pregunta: +0.01 en R@1, R@3 y R@5, y +0.04 en R@10.
  - 4 preguntas que antes fallaban ahora aciertan.
  - 1 pregunta sube de puesto.

> **Ojo con el README:** sus cifras (docs 0.89, code 0.75 en R@10) son de los datasets **privados**. Ahora usamos los públicos (D1), así que no son comparables. La línea base oficial es la fila `04-fase0-final / smart`.

---

## 2. Qué se ha cambiado y por qué

### Bugs

- **B1 — Clasificador doc/code** (`src/retriever.py`, `classify_query`):
  - **Problema:** la señal CamelCase estaba muerta, porque se buscaban mayúsculas después de hacer `.lower()`.
  - **Arreglo:** la detección de identificadores pasa a usar los tokens originales, con un patrón (`IDENTIFIER_PATTERN`) que reconoce snake_case, CamelCase interno (`PagedAttention`) y siglas pegadas (`RMSNorm`).
  - **Lo que hubo que afinar:** la primera versión contaba **`vLLM` como identificador** (`v→L`), y vLLM aparece en casi todas las preguntas, así que rompía una pregunta de docs. Ahora se excluye el nombre del producto (`NON_IDENTIFIER_TERMS`), se quita el posesivo `'s` y las siglas en plural (`LLMs`) no cuentan.
- **B2 — Expansión por símbolos** (`expand_query`):
  - **Problema:** nunca añadía nada (lo que añadía, el filtro final lo eliminaba) y recorría los 41 608 chunks en cada query.
  - **Arreglo:** eliminada, y `expand_query` deja de recibir `chunks`. Salida idéntica y algo más rápida.
- **B3 — Una sola ruta de evaluación** (`Makefile`): `search-docs` y `search-code` usan ahora `search_dataset` (→ `search_smart`), que es el modo evaluado en 42, en vez de `answer_dataset --skip_generation` (→ `search_for_generation`). La ruta *generation* sigue disponible en `make bench-gen`.
- **B10 — "Not found" centralizado** (`src/generator.py`): una única función `is_not_found()` con `NOT_FOUND_PATTERNS`, usada por el `Generator`, la CLI y la web. Antes había tres listas distintas.
- **B13 — Limpieza:**
  - Eliminado `RRF_K` sin uso.
  - Import estándar `from llm_sdk import Small_LLM_Model` (ver §4).
  - Los ficheros de `src/` terminan en salto de línea (flake8 W292).

### Bugs nuevos encontrados durante la fase

- **B14 — La descomposición de identificadores en `expand_query` era código muerto.**
  - **Problema:** el filtro final descartaba toda variante que fuera *subcadena* de la query, y las partes de un identificador siempre lo son. Solo sobrevivía la variante snake_case de los nombres CamelCase (`PagedAttention` → `paged_attention`).
  - **Medición:** con la descomposición activada (`03-fix-b14`), code R@10 sube a 0.75, pero R@1 y R@3 bajan. El motivo es que inflar la query infla el score BM25 y supera más a menudo el umbral manual `SKIP_RERANK_SCORE = 9.0`, así que el reranker se salta más veces (el tiempo de code pasa de 40 s a 19 s).
  - **Decisión:** no adoptarlo en la Fase 0 (regla de no empeorar). `expand_query` conserva su comportamiento efectivo, ahora escrito de forma explícita y documentada. **Pasa a la Fase 2**, junto con el tokenizador code-aware (B8) y la revisión de umbrales.
- **B15 — Qwen responde fuera de dominio.**
  - **Síntoma:** `answer "What is the capital of France?"` devuelve *"The capital of France is Paris"*. Lo curioso es que es literalmente el ejemplo de rechazo del propio prompt.
  - **Verificación:** comprobado con el `generator.py` original: es **comportamiento previo**, no introducido en esta fase.
  - **Causa:** el umbral BM25 de 5.5 no filtra esta pregunta, y el modelo de 0.6B ignora la instrucción.
  - **Pasa a la Fase 3** (prompt, chat template oficial y guardarraíles).

### Repositorio y herramientas

- **`.gitignore`** nuevo. Se ignoran `data/*` **excepto `data/datasets/`**, y `data/output/`.
- **`__pycache__` fuera de git** (`git rm --cached`; los ficheros siguen en disco).
- **Datasets públicos versionados** en `data/datasets/` (172 KB). Recuperados del historial (commit `d4e13a6`).
  - **Motivo:** el CDN de 42 devuelve **403** sin sesión, así que el benchmark no era reproducible.
- **vLLM 0.10.1 desde GitHub** (etiqueta oficial `v0.10.1`). Verificado: las 200 fuentes de ground truth existen y el texto en sus offsets coincide con las respuestas. Es equivalente al adjunto de 42.
- **`Makefile` reescrito:**
  - `install` → `data` + venv + `uv sync`. **Ya no hace `rm -rf data/`**.
  - `data`: descarga vLLM desde GitHub si falta.
  - `data-42`: la descarga original de la intra, para cuando haya acceso.
  - Cachés en `/goinfre` **solo si existe**. Fuera de 42 se usan las cachés normales y no se vuelven a descargar los modelos.
    - La detección la hace el shell (`sh -c 'test -d /goinfre'`), no `$(wildcard)`, y se puede forzar con `ON_42=yes|no`.
    - **Motivo:** en tu Windows existe un `C:\goinfre\` vacío, resto de un `make install` antiguo. El `make` nativo lo veía, pero el shell traducía `/goinfre` a la carpeta de Git, y `uv` fallaba con "Acceso denegado". El Makefile original tenía el mismo fallo. No he borrado esa carpeta; puedes eliminarla si quieres.
  - `PY := python`. En Windows, `python3` apunta al stub de la Microsoft Store.
  - Nuevos: `bench`, `bench-gen`, `test`. Eliminados: `test-*` (D1) e `index-embed` (no hacía nada; vuelve en la Fase 2).
  - `clean` ya no borra `data/datasets/`.
  - El Makefile queda con finales LF a propósito (`make` en Linux).
- **`make bench`** (`src/bench.py` + comando `bench` de la CLI):
  - Carga el retriever una vez, ejecuta docs y code y evalúa con el evaluador de 42.
  - Guarda la config, el commit y las métricas en `bench/results/<fecha>_<label>_<modo>.json`.
  - Imprime la tabla comparativa con todo el historial.
  - Uso: `make bench LABEL=mi-cambio`.
- **Tests** (`tests/`, `make test`): 13 tests más 1 `xfail` estricto.
  - Cubren el evaluador (solape y crédito parcial), `expand_query`, el clasificador, el mapeo hijo→padre y los offsets de chunks.
  - **El `xfail` documenta B7** (offsets desplazados en chunks enriquecidos). Cuando se arregle en la Fase 1, el test empezará a pasar y obligará a quitar la marca.
- **`pytest`** añadido como dependencia de desarrollo (`[dependency-groups] dev`).

---

## 3. Lista de ficheros

| Fichero | Cambio |
|---|---|
| `src/retriever.py` | B1, B2, B13, `expand_query` documentada (B14) |
| `src/generator.py` | B10 (`is_not_found`), import estándar de `llm_sdk`, tipado de `generate()` |
| `src/cli.py` | Comando `bench`; `is_not_found` delega en el generator |
| `src/web.py` | `is_not_found` delega en el generator |
| `src/ingester.py` | Solo el salto de línea final |
| `src/bench.py` | **Nuevo**: harness de benchmark |
| `tests/test_evaluator.py`, `tests/test_retriever.py`, `tests/test_ingester.py` | **Nuevos** |
| `Makefile` | Reescrito (ver arriba) |
| `pyproject.toml` | `pytest` (dev), `[tool.pytest.ini_options]`, `mypy_path = "llm_sdk"` |
| `uv.lock` | `pytest` y sus dependencias |
| `.gitignore` | **Nuevo** |
| `data/datasets/**` | **Nuevos** (datasets públicos versionados) |
| `bench/results/*.json` | **Nuevos**: historial de mediciones de esta fase |
| `src/__pycache__/*`, `llm_sdk/llm_sdk/__pycache__/*` | Fuera del control de versiones |
| `llm_sdk/**` | **Sin tocar** |

---

## 4. Qué debes saber de la arquitectura

- **`llm_sdk` y mypy:**
  - El paquete se instala vía `pyproject.toml` (`[tool.uv.sources]`, editable) y se importa de forma estándar.
  - El antiguo `from llm_sdk.__init__ import ...` era un parche para mypy: con `mypy_path = "."`, mypy confundía la carpeta exterior `./llm_sdk/` (sin `__init__.py`) con el paquete. Además ese import ejecutaba el `__init__.py` dos veces.
  - Ahora `mypy_path = "llm_sdk"` apunta al paquete real.
  - **Efecto secundario:** mypy ya comprueba los tipos de la interacción con el SDK. Por eso `generate()` lleva un `Any` explícito y comentado: las anotaciones de transformers no lo exponen en `PreTrainedModel`.
- **`search_smart` es la ruta oficial de benchmark**, porque es la que usa `search_dataset` (moulinette). `search_for_generation` es la que usan la web y `answer`: da más recall en docs pero mucho menos en code R@1, y tarda 5 veces más (reranker sobre 50 candidatos). **Unificar o elegir ruta es una decisión para la Fase 2.**
- **La regla de "no empeorar" se aplica por pregunta, no solo a la media.** `src/bench.py` guarda las salidas en `data/output/bench/<label>_<modo>/`, que permiten diferenciar pregunta a pregunta (así se detectó el falso positivo de `vLLM` en B1).
- **Finales de línea:** el repo guarda los `.py` en **CRLF** (se mantienen así, y `src/` y `tests/` están normalizados), pero `uv` reescribe `uv.lock` y `pyproject.toml` en LF. **Propuesta para cuando quieras:** un `.gitattributes` (`* text=auto`, `Makefile eol=lf`) que normalice el repo una vez. Genera un diff grande en un solo commit, así que no lo he hecho sin tu permiso.
- **Torch en CPU:** `uv sync` instala `torch 2.12.1+cpu` (en Windows, PyPI no trae CUDA). Basta para el retrieval y para Qwen3-0.6B. Para usar la 3080 Ti en las fases 2 y 3 habrá que configurar el índice de PyTorch con CUDA en `pyproject.toml`; se decidirá entonces.

---

## 5. Cómo verificarlo

```bash
make data              # vLLM desde GitHub (si falta)
make index             # ~15 s
make bench LABEL=check # debe reproducir 04-fase0-final / smart
make test              # 13 passed, 1 xfailed
make lint              # flake8 + mypy limpios
```
