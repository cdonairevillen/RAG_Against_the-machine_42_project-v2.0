# Web (Phase 6)

React 19 + Vite 6 + TypeScript frontend for the RAG API (`src/api`), with the same look as the Streamlit web (`src/web.py`).

```bash
make api        # API on http://127.0.0.1:8000
make web-dev    # this web on http://localhost:5173 (talks to the API above)
make web-build  # web/dist, served by the API at "/"
```

- `VITE_API_URL`: API base URL for a separate deployment (GitHub Pages). Empty means the same origin.
- `VITE_BASE`: public path, e.g. `/<repo>/` on GitHub Pages.

Code: `src/api.ts` (API client, SSE over `fetch`), `src/App.tsx` (UI) and `src/index.css` (styles).
