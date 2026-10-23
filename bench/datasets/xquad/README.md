# XQuAD (en, es) — benchmark de cultura general

Derivado de **XQuAD** (Artetxe, Ruder y Yogatama, 2020, *On the Cross-lingual Transferability of Monolingual Representations*), publicado por Google bajo **CC-BY-SA 4.0**. Estos ficheros se distribuyen con la misma licencia.

- Preguntas, párrafos y respuestas: [`google/xquad`](https://huggingface.co/datasets/google/xquad) en Hugging Face (revisión `51adfef`).
- Títulos de los artículos: [`google-deepmind/xquad`](https://github.com/google-deepmind/xquad) en GitHub (commit `7d30520`).
- Los párrafos proceden de artículos de Wikipedia (CC-BY-SA), vía SQuAD v1.1.

**Cambios respecto al original:** los párrafos se agrupan en un fichero Markdown por artículo (`data/raw/xquad/<lang>/<Title>.md`), y cada fuente del ground truth es el fragmento exacto de la respuesta dentro de ese fichero. Se regeneran con `make data-xquad` (ver `src/sources/xquad.py`).
