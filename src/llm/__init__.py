"""LLM backends (Phase 10, 10a).

Two implementations behind the same interface:
    local   src/rag/generator.py `Generator`: the model loaded through
            llm_sdk (Qwen3, Granite...). Unchanged since Phase 8.
    openai  src/llm/remote.py `RemoteGenerator`: an OpenAI-compatible API
            (NVIDIA build.nvidia.com, Groq...), chosen per profile in
            rag.toml (`provider = "openai"`).

Retrieval, routing, domain rules, the answer clean-up and the
benchmarks do not depend on which one writes the answer.
"""
from typing import Any

from src.config import GenerationConfig


def create_generator(config: GenerationConfig | None = None) -> Any:
    """The generator a configuration asks for (local by default)."""
    config = config or GenerationConfig()
    generator: Any
    if config.provider == "openai":
        from src.llm.remote import RemoteGenerator

        generator = RemoteGenerator(config)
    else:
        from src.rag.generator import Generator

        generator = Generator(config)
    # Read by the agent (src/agent/agent.py): which question it answers
    # with this model. Set here so neither generator class changes.
    generator.agent_answer_with = config.agent_answer_with
    return generator
