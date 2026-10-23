"""The RAG as an MCP server (Phase 5).

Exposes src/server/tools.py to any MCP client (the project's own agent, Claude
Desktop, an IDE...): list_domains, search and answer. Built with the MCP
Python SDK's MCPServer (the FastMCP API, renamed in mcp 2.x).

Run:
    make mcp                          # stdio (a client launches it)
    make mcp MCP_TRANSPORT=streamable-http   # HTTP on MCP_PORT
"""
import sys
from contextlib import redirect_stdout
from typing import Any, Callable, Literal, Optional, TypeVar

from src.server.tools import RagTools

T = TypeVar("T")

INSTRUCTIONS = (
    "Retrieval-Augmented Generation over several knowledge domains. Call "
    "list_domains to see what each one contains, search to get sources "
    "for a complete question (optionally restricted to some domains) "
    "and answer to get a grounded answer with citations."
)


def build_server(tools: Optional[RagTools] = None) -> Any:
    """Create the MCP server; the RAG loads on the first tool call.

    Args:
        tools: Already loaded tools (tests); loaded lazily otherwise, so
            the server starts at once and answers the handshake.
    """
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(name="rag-against-the-machine",
                       instructions=INSTRUCTIONS)
    state: dict[str, RagTools] = {}
    if tools is not None:
        state["tools"] = tools

    def call(fn: Callable[[RagTools], T]) -> T:
        # On stdio, stdout is the protocol channel: the RAG's progress
        # messages ("Loaded ... chunks") go to stderr instead.
        with redirect_stdout(sys.stderr):
            if "tools" not in state:
                state["tools"] = RagTools.load()
            return fn(state["tools"])

    @server.tool()
    def list_domains() -> list[dict[str, Any]]:
        """List the knowledge domains and what each one contains."""
        return call(lambda t: t.list_domains())

    @server.tool()
    def search(query: str, domains: Optional[str] = None,
               k: int = 5) -> dict[str, Any]:
        """Search the knowledge base.

        Args:
            query: A complete, self-contained question.
            domains: Optional comma-separated domains ("cv",
                "vllm,xquad"); all of them when omitted.
            k: Number of sources to return.
        """
        return call(lambda t: t.search(query, domains, k))

    @server.tool()
    def answer(question: str, domains: Optional[str] = None,
               k: int = 5) -> dict[str, Any]:
        """Answer a question with citations from the knowledge base.

        Args:
            question: A complete, self-contained question.
            domains: Optional comma-separated domains; all when omitted.
            k: Number of sources given to the model.
        """
        return call(lambda t: t.answer(question, domains, k))

    return server


def run(transport: Literal["stdio", "streamable-http"] = "stdio",
        port: int = 8765) -> None:
    """Start the MCP server on stdio or streamable HTTP."""
    server = build_server()
    if transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host="127.0.0.1", port=port)
