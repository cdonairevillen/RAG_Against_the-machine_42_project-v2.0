---
title: RAG against the Machine
emoji: ⚡
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
license: mit
pinned: false
short_description: Multi-domain RAG with an agent (vLLM, Wikipedia, CV, about)
---

# RAG against the Machine

> This card is kept because the server image is still built from this folder (`deploy/space/`). The project is deployed on Oracle Cloud, not on a Hugging Face Space: see the main README and `deploy/README.md`.

A multi-domain Retrieval-Augmented Generation system built by Chrystian Donaire Villén as an improvement of a 42 Madrid project.

- **Domains:** the vLLM 0.10.1 documentation and source code, general knowledge from XQuAD (Wikipedia, English and Spanish), the author's CV and the project itself (about).
- **Retrieval:** hybrid BM25 + `bge-m3` embeddings in Qdrant, cross-encoder reranking and a router between domains.
- **Generation:** Qwen3-0.6B (Qwen3-1.7B as an option), with citations and answers in the language of the question.
- **Agent (off by default in the web, a work in progress):** session memory, rewriting of follow-up questions and tool calls.

Source code: https://github.com/cdonairevillen/RAG_Against_the-machine_42_project-v2.0

General-knowledge answers use XQuAD (Google, CC-BY-SA 4.0), based on Wikipedia.

> Running on a free CPU: expect 20–40 seconds per answer, streamed as it is written.
