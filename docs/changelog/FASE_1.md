# CHANGELOG — Fase 1: Modificación de la ingesta

**Fecha:** 2026-10-18
**Estado:** completada. Pendiente de tu revisión y commit (no se ha hecho ningún commit).

---

## 1. Resultado en una tabla

Datasets públicos de 42, `k = 10`, evaluador original. Todas las ejecuciones están en `bench/results/`.

**Prioridad de métricas acordada: R@5 > R@10 > R@3 > R@1.**

### Ruta smart (`search_dataset`, benchmark oficial)

| Ejecución | Qué se prueba | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 | Decisión |
|---|---|---|---|---|
| `04-fase0-final` | Línea base Fase 0 | 0.64 / 0.83 / 0.85 / 0.85 | 0.45 / 0.62 / 0.64 / 0.72 | — |
| `10-fase1-qdrant` | Nueva arquitectura (Qdrant + config) | = Fase 0, **idéntico pregunta a pregunta** | = Fase 0 | ✅ |
| `11-fix-b7` | Arreglo de offsets (B7) | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.63 / 0.64 / 0.72 | ✅ (ver §2) |
| `12-langchain-md` | Chunker de docs LangChain | 0.72 / 0.84 / 0.87 / 0.87 | 0.44 / 0.63 / 0.64 / 0.72 | ❌ Descartado (tu decisión) |
| `14-packed` | Tu chunker empaquetado, solape por secciones | 0.68 / 0.84 / 0.86 / 0.88 | 0.43 / 0.63 / 0.64 / 0.72 | ✅ Por defecto |
| `16-packed-lines` | Ídem, solape por líneas | 0.68 / 0.82 / 0.85 / 0.87 | 0.44 / 0.63 / 0.64 / 0.72 | ❌ Empeora R@5/@10/@3 |
| **`17-fase1-final`** | **Estado final** (= `14-packed`, salida idéntica) | **0.68 / 0.84 / 0.86 / 0.88** | **0.43 / 0.63 / 0.64 / 0.72** | **Línea base oficial** |

> `13-fase1-final` es la ejecución con LangChain (cuando aún era el candidato). Se conserva como histórico; la buena es `17-fase1-final`.

### Ruta generation (web y `answer`)

| Ejecución | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| `04-fase0-final` | 0.70 / 0.82 / 0.89 / 0.89 | 0.23 / 0.55 / 0.62 / 0.70 |
| `13-fase1-final` (LangChain) | 0.69 / 0.81 / 0.85 / 0.90 | 0.24 / 0.55 / 0.62 / 0.70 |
| **`14-packed` (= estado final)** | **0.68 / 0.83 / 0.88 / 0.92** | **0.25 / 0.55 / 0.62 / 0.69** |
| `16-packed-lines` | 0.70 / 0.80 / 0.85 / 0.90 | 0.24 / 0.56 / 0.64 / 0.70 |

### Neto respecto a la Fase 0

- **Ruta oficial:**
  - Docs mejora en todos los cortes: **+0.01 en R@5, +0.03 en R@10, +0.01 en R@3** y +0.04 en R@1.
  - Code: R@5 y R@10 iguales, R@3 +0.01, R@1 −0.02.
- **⚠️ Ruta generation:**
  - Docs: R@10 +0.03 y R@3 +0.01, pero **R@5 −0.01** (una pregunta) y R@1 −0.02.
  - Code: R@10 −0.01.
  - No es la ruta del benchmark, pero es la de la web. Su unificación con smart ya está prevista en la Fase 2.

---

## 2. Qué se ha cambiado y por qué

### Base de datos: Qdrant en servidor (decisión tuya tras la comparativa)

- **Comparativa medida en tu equipo** con ~59 000 chunks:

  | Opción | Escritura | Con vectores 384d | Consulta filtrada |
  |---|---|---|---|
  | Qdrant modo local | ~9 min | — | — |
  | **Qdrant servidor** | **1,9 s** | **8,8 s** | **18 ms** |
  | Postgres + pgvector | 0,4 s | 1,1 s + 24 s de índice | 13 ms |
  | SQLite | 0,4 s | sin vectores | — |
  | LanceDB | bloqueada por el Control de aplicaciones de Windows (DLL de `pyarrow`) | | |

- **`docker-compose.yml`:** Qdrant **v1.19.1**, igual que el cliente `qdrant-client==1.19.1`, con un volumen Docker con nombre (`rag_2_qdrant_storage`). Usa un volumen con nombre porque Qdrant necesita un sistema de ficheros POSIX y los bind mounts de Windows no lo son.
- **Una colección por dominio** (`rag_vllm`), sin vectores en esta fase. Qdrant es la fuente de verdad de los chunks y sus metadatos; los vectores *dense* y *sparse* se añaden a los mismos puntos en la Fase 2.
- **BM25 sigue en disco** (`data/processed/<dominio>/`) con un `manifest.json`. Al cargar, el retriever comprueba que Qdrant y BM25 vienen de la misma ingesta: si no cuadran los recuentos, falla con "Run 'make index' again" en vez de devolver resultados incoherentes.

### Modelo de datos del chunk

- **IDs estables:** UUID5 de (dominio, nivel, fichero, rango, ocurrencia). El mismo chunk tiene el mismo ID en cada reindexado.
- **Campos nuevos:** `domain`, `level` (`parent` o `child`), `modality` (`text`; preparado para la Fase 4b) y `ordinal` (la fila en el índice BM25).
- **`parent_id`** pasa de índice entero a ID del padre.

### Configuración (`rag.toml` + `src/config.py`)

- Qdrant, rutas, tamaños de chunk y **fuentes**. Cada fuente declara su raíz, sus extensiones, los directorios excluidos y **qué chunker usa cada extensión**.
- **Override por variables de entorno** `RAG_<SECCIÓN>_<CLAVE>` (por ejemplo `RAG_QDRANT_URL`), validado con pydantic.
- Es la base de la modularización: el chunker se cambia en la config, no en el código.
- La CLI acepta `--config otro.toml` y `--domain`. Así se han hecho todas las comparativas sin tocar `rag.toml`.

### Ingesta multi-dominio

- `index --source <nombre>`; por defecto `vllm`.
- **Bug encontrado por los tests:** una fuente **sin código o sin documentación** (el caso del futuro modo CV) hacía fallar `bm25s` al crear un índice vacío. Ahora los índices por tipo solo se crean si hay chunks de ese tipo.

### B7: offsets de chunks enriquecidos

- **Problema:** al subdividir un método enriquecido (firma de clase + método) o una tabla con título, se dividía el texto *con* el prefijo, así que los offsets quedaban desplazados la longitud del prefijo. Además, **solo el primer trozo llevaba el contexto**.
- **Arreglo:** `split_with_header()` divide el texto original (offsets reales) y añade la cabecera a **cada** trozo.
- **Efecto en code:** −0.01 en R@1 y +0.01 en R@3, una pregunta en cada sentido. En la que baja, el 1.º resultado antiguo era un trozo **desplazado** que acertaba de rebote; ahora aparece el trozo **correcto**, que contiene la respuesta entera, pero el reranker lo pone 2.º.
- **Decisión:** se adopta por corrección, justificado según la regla.
- El test que en la Fase 0 era `xfail` ahora pasa. Se ha añadido otro para tablas, y he verificado que **los dos fallan con el código anterior**.

### Chunker de documentación

- **Por qué cambiaba tanto el recall:**
  - Las respuestas del ground truth miden de mediana **1 154 caracteres**.
  - El chunker original corta en cada cabecera y separa las tablas del texto, así que genera chunks de mediana **633 caracteres**, y solo el 63 % de las respuestas cae entera en un chunk.
- **`markdown_headers_packed` (nuevo, por defecto):** tu lógica de cabeceras con tres cambios:
  1. **Empaqueta** secciones consecutivas hasta el tamaño máximo.
  2. **Solapa por secciones enteras** (hasta un 20 % del tamaño), de modo que todos los chunks empiezan en una cabecera.
  3. **No separa las tablas del texto** de su sección.
  - **Además ignora los `#` dentro de bloques de código.** El original los tomaba por cabeceras: un `# comentario` de bash partía la sección.
  - Las secciones que superan el máximo se subdividen y cada trozo conserva el título.
- **LangChain** (`RecursiveCharacterTextSplitter` para Markdown): mejor R@1 en la ruta oficial, pero peor en R@10 y en la ruta de la web. **Descartado para esta versión** por tu decisión, con su código y su dependencia retirados. Queda anotado en *Posibilidades* (`docs/PLANING.md`) para volver a medirlo tras la Fase 2.
- **Solape por líneas** (afinado para intentar subir R@1): no mejora R@1 en la ruta oficial y empeora R@5, R@10 y R@3 en las dos rutas. **Descartado**, y su código retirado.
- `markdown_headers` (el original) sigue disponible en `rag.toml` como referencia.

| Chunker de docs | Chunks padre | Tamaño mediano | Respuesta GT entera en un chunk |
|---|---|---|---|
| `markdown_headers` (original) | 1 275 | 633 | 63 % |
| LangChain (descartado) | 797 | 1 419 | 81 % |
| **`markdown_headers_packed`** | 768 | 1 583 | 72 % |

---

## 3. Lista de ficheros

| Fichero | Cambio |
|---|---|
| `docker-compose.yml` | **Nuevo**: Qdrant v1.19.1 |
| `rag.toml` | **Nuevo**: configuración del pipeline |
| `src/config.py` | **Nuevo**: carga y validación de la config, overrides por entorno |
| `src/ingestion/chunk.py` | **Nuevo**: `Chunk` con ID estable, dominio, nivel, modalidad y ordinal |
| `src/ingestion/chunkers.py` | **Nuevo**: chunkers movidos desde `ingester.py` + registro + `split_with_header` (B7) + `markdown_headers_packed` |
| `src/ingestion/pipeline.py` | **Nuevo**: recorrido de fuentes, padres e hijos, BM25 y manifest |
| `src/storage/base.py` | **Nuevo**: interfaz `ChunkStore` |
| `src/storage/qdrant_store.py` | **Nuevo**: implementación con Qdrant |
| `src/ingester.py` | **Eliminado** (repartido en `ingestion/` y `storage/`) |
| `src/retriever.py` | `from_store()` en vez de `from_disk()`; padres por ID |
| `src/cli.py` | `--domain`, `--config`; `index` escribe en Qdrant; misma interfaz para los comandos de 42 |
| `src/bench.py` | Carga desde el almacén; registra el dominio, el chunking y los chunkers de cada ejecución |
| `src/web.py` | Carga desde el almacén |
| `Makefile` | `db-up`, `db-down`, `db-reset`; `index`, `search-*`, `bench*` y `web` levantan Qdrant si hace falta |
| `pyproject.toml`, `uv.lock` | `qdrant-client==1.19.1`, `tomli` (solo Python 3.10) y filtro de un aviso de Qdrant en memoria |
| `tests/test_config.py`, `tests/test_storage.py` | **Nuevos** |
| `tests/test_ingester.py`, `tests/test_retriever.py` | Adaptados, más tests de B7 y del chunker empaquetado |
| `docs/PLANING.md` | LangChain añadido a *Posibilidades* |
| `bench/results/*.json` | Mediciones 10–17 |
| `llm_sdk/**` | **Sin tocar** |

**Tests:** 31 (antes 13 + 1 xfail). Los de almacén e integración usan **Qdrant en memoria**, así que `make test` no necesita Docker.

---

## 4. Qué debes saber de la arquitectura

```
rag.toml ──► config ──► Ingester(domain) ──► chunkers (por extensión)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   Qdrant: colección rag_<domain>     data/processed/<domain>/
   (padres + hijos, payload)          bm25_*  + manifest.json
              └───────────────┬───────────────┘
                              ▼
                 Retriever.from_store(domain)
          (valida el manifest; hijo.ordinal = fila BM25)
```

- **Flujo de trabajo:** `make db-up` (o cualquier target que lo necesite) → `make index` → `make bench`. Qdrant se queda corriendo (`restart: unless-stopped`). `make db-down` lo para y `make db-reset` **borra también los datos**.
- **Arranque del retriever:** 2,5 s (lee los 58 731 chunks de Qdrant y carga BM25). Qdrant usa ~390 MB de RAM, y el volumen ocupa ~650 MB.
- **El retriever sigue cargando todos los chunks en memoria**, igual que antes. Era la forma de garantizar resultados idénticos en el refactor. En la Fase 2, la búsqueda por vectores irá contra Qdrant directamente.
- **Reindexar recrea la colección del dominio**: los demás dominios no se tocan.
- **Docker en 42:** las imágenes y volúmenes de Docker van al almacenamiento de Docker, no a `/goinfre`. Si en los ordenadores de 42 el home tiene poca cuota, habrá que mover el `data-root` de Docker. Está **por comprobar** allí.
- **Para el despliegue (Fase 6):** el Space de HF es un solo contenedor. Habrá que decidir entre Qdrant dentro del contenedor y un plan gratuito en la nube (límites **a verificar**).

---

## 5. Cómo verificarlo

```bash
make db-up                 # Qdrant v1.19.1 en Docker
make index                 # ~25 s
make bench LABEL=check     # debe reproducir 17-fase1-final / smart
make test                  # 31 passed (sin Docker)
make lint                  # flake8 + mypy limpios
make search-docs && make eval-docs   # comandos de 42: 0.68 / 0.84 / 0.86 / 0.88
```
