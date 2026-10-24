# Despliegue (Fase 6)

Guía para publicar la web sin coste:
- **Backend:** la API, más la web compilada, en un **Hugging Face Space** (Docker, CPU gratuito).
- **Frontend (opcional):** en **GitHub Pages**.
- **El índice:** viaja aparte, en un **dataset privado de Hugging Face**.

Google Cloud no se toca.

Todo está preparado y probado en local hasta el último paso. **Lo que queda en tus manos** son las acciones con tus cuentas: crear el dataset privado y el Space, poner los secretos y lanzar el workflow de Pages.

```
                ┌──────────────── Hugging Face Space (Docker, CPU) ────────────────┐
navegador ───►  │ FastAPI (src/api) ── web/dist (React)                            │
                │    │                                                             │
                │    ├── RAG: router + bge-m3 + reranker + Qwen3-0.6B (en la imagen)│
                │    └── Qdrant (en el contenedor) ◄── bundle (al arrancar) ◄──────┼── dataset PRIVADO de HF
                └──────────────────────────────────────────────────────────────────┘
GitHub Pages (opcional) ── la misma web, apuntando a la API del Space (VITE_API_URL)
```

## 0. Requisitos locales

- El índice construido con la base estable: `make index` (en la 3080 Ti tarda ~6 min).
- Docker en marcha (para `make space-build` y `make space-run`).
- Una cuenta de Hugging Face y un token con permiso de escritura: `uv run hf auth login`.

## 1. Empaquetar el índice (bundle)

```bash
make bundle            # deploy/bundle/: snapshots de Qdrant + BM25 + bundle.json (SHA256)
```

⚠️ **El bundle contiene el material del CV sin enmascarar** (el enmascarado se aplica al responder). Por eso:
- `deploy/bundle/` está en `.gitignore`.
- Se sube solo a un dataset **privado**.

```bash
uv run hf repos create <tu-usuario>/rag-index --repo-type dataset --private
uv run hf upload <tu-usuario>/rag-index deploy/bundle . --repo-type dataset
```

## 2. Probar el Space en local

```bash
make space-build       # compila la web y construye la imagen (descarga los modelos: tarda)
make space-run         # http://localhost:7860, con deploy/bundle montado
```

Debe responder igual que `make api` + `make web-dev`.

## 3. Crear el Space

1. En huggingface.co, *New Space*: SDK **Docker**, hardware **CPU basic** (gratuito) y visibilidad **pública**. La web es pública; los datos van en el dataset privado.
2. En *Settings → Variables and secrets*:
   - **Secret** `HF_TOKEN`: un token de **solo lectura** con acceso al dataset privado.
   - **Variable** `RAG_BUNDLE_REPO`: `<tu-usuario>/rag-index`.
   - **Variable** `RAG_ALLOWED_ORIGINS`, opcional: `https://<tu-usuario>.github.io` si vas a usar GitHub Pages. Si no se pone, se permite cualquier origen.
3. Sube el contenido del Space:
   ```bash
   make space-stage                 # deploy/stage/: Dockerfile en la raíz y solo el código necesario
   cd deploy/stage
   git init && git add . && git commit -m "RAG against the Machine"
   git remote add space https://huggingface.co/spaces/<tu-usuario>/<space>
   git push --force space main
   ```
   El Space construye la imagen. El primer arranque descarga el bundle, lo restaura en el Qdrant del contenedor y carga los modelos (1–2 min).

## 4. Web en GitHub Pages (opcional)

El Space ya sirve la web en su propia URL. Si además la quieres en `https://<tu-usuario>.github.io/<repo>/`:
1. En el repo de GitHub, *Settings → Pages → Source*: **GitHub Actions**.
2. En *Settings → Secrets and variables → Actions → Variables*: `RAG_API_URL` = `https://<tu-usuario>-<space>.hf.space`.
3. En *Actions*, lanza **"web (GitHub Pages)"**. El workflow es manual a propósito, así que nada se publica sin que lo lances tú.

## 5. Actualizar

- **Código o web:** `make space-stage` y vuelve a hacer `push` al Space.
- **Índice** (reindexado, o la biografía cambiada): `make index`, `make bundle` y vuelve a subir el bundle al dataset. Basta con reiniciar el Space.

## Límites conocidos

- **CPU gratuito:** medido en local con `docker run --cpus=2 --memory=16g`, la respuesta tarda **~15–25 s en directo** y **~22–32 s con el agente**. El primer token llega a los ~10–28 s (`docs/changelog/FASE_6.md` §6). Hay *streaming*, así que el texto aparece mientras se genera.
- **Hilos:** `entrypoint.sh` ajusta los hilos de torch a la cuota de CPU del contenedor. Sin eso iba ~3.5× más lento (DEC-17). Para forzar un valor, define `OMP_NUM_THREADS` en el Space.
- **Una sola respuesta a la vez:** la generación se serializa (un solo LLM). Con varias visitas a la vez, esperan su turno.
- **El Space gratuito se duerme** tras un tiempo sin uso. La primera visita lo despierta, y el arranque restaura el bundle y carga los modelos.
- **Imagen grande:** ~13.5 GB. El `uv.lock` fija el torch con CUDA (el de desarrollo), que funciona en CPU pero ocupa ~4.5 GB más (DEC-11), y los modelos ocupan 6.2 GB.
- **Antes de subir nada,** revisa `docs/decisions.md` DEC-18 (datos privados en el historial de git).
