---
title: RAG against the Machine
emoji: ⚡
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Multi-domain RAG with an agent (vLLM, Wikipedia, CV)
---

# RAG against the Machine

A multi-domain Retrieval-Augmented Generation system built by Chrystian Donaire Villén as an improvement of a 42 Madrid project.

- **Domains:** the vLLM 0.10.1 documentation and source code, general knowledge from XQuAD (Wikipedia, English and Spanish) and the author's CV.
- **Retrieval:** hybrid BM25 + `bge-m3` embeddings in Qdrant, cross-encoder reranking and a router between domains.
- **Generation:** Qwen3-0.6B, with citations and answers in the language of the question.
- **Agent (default):** session memory, rewriting of follow-up questions and tool calls. The "Direct RAG" switch turns it off.

Source code: https://github.com/cdonairevillen/RAG_Against_the-machine_42_project-v2.0

General-knowledge answers use XQuAD (Google, CC-BY-SA 4.0), based on Wikipedia.

> Running on a free CPU: expect a few seconds per answer, more with the agent.
