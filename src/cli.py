import os
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel
from tqdm import tqdm

from src.config import CONFIG_FILE, RagConfig, load_config
from src.rag.pipeline import RagPipeline
from src.rag.retriever import Retriever
from src.rag.router import DomainRouter
from src.rag.generator import Generator
from src.rag.embeddings import vector_name
from src.rag.ingestion.chunk import Chunk
from src.models import (
    MinimalAnswer,
    MinimalSearchResults,
    RagDataset,
    StudentSearchResults,
    StudentSearchResultsAndAnswer,
    MinimalSource,
)

if TYPE_CHECKING:
    from src.agent.agent import Agent
    from src.rag.ingestion.pipeline import Ingester

DEFAULT_DOMAIN = "vllm"


class CLI:
    """RAG against the Machine — single orchestrator and CLI entry
    point.

    Loads Retriever and Generator lazily on first use and reuses
    them for all subsequent calls within the same process. Pipeline
    settings (Qdrant, chunking, sources) come from rag.toml.

    Commands:
        index           Chunk a source and store it (Qdrant + BM25).
        search          Search for a single query (fast, no reranker).
        search_dataset  Batch retrieval over a full dataset JSON.
        answer          Answer a single question (with reranker).
        answer_dataset  Full pipeline: retrieve + rerank + generate.
        evaluate        Compute Recall@k against ground truth.
        bench           Run and record both public 42 datasets.

    Examples:
        uv run python -m src index
        uv run python -m src search "How to configure OpenAI server?"
        uv run python -m src answer "How to configure OpenAI server?"
        uv run python -m src search_dataset \\
            --dataset_path \\
            bench/datasets/public/UnansweredQuestions/dataset_docs_public.json
        uv run python -m src answer_dataset \\
            --dataset_path \\
            bench/datasets/public/UnansweredQuestions/dataset_docs_public.json
        uv run python -m src evaluate \\
            --student_answer_path \\
            data/output/search_results/dataset_docs_public.json \\
            --dataset_path \\
            bench/datasets/public/AnsweredQuestions/dataset_docs_public.json
    """

    def __init__(self, domain: str = DEFAULT_DOMAIN,
                 config: str = CONFIG_FILE,
                 profile: Optional[str] = None) -> None:
        """Initialise the CLI orchestrator.

        Args:
            domain: Knowledge source to work on (a source in rag.toml).
            config: Path to the TOML configuration file.
            profile: Optional profile from rag.toml (extra models on top
                of the stable base); defaults to RAG_PROFILE or none.
        """
        self.domain = domain
        self.config: RagConfig = load_config(config, profile=profile)
        self.retriever: Retriever | None = None
        self.router: DomainRouter | None = None
        self.agent: "Agent | None" = None
        self.index_embedder: Any = None
        self.generator: Generator | None = None

    def get_retriever(self, with_reranker: bool = True) -> Retriever:
        """Load and cache the Retriever.

        Args:
            with_reranker: When True, also loads the cross-encoder
                reranker.

        Returns:
            The loaded Retriever instance.

        Raises:
            Exception: Propagates any load error after printing a
                message.
        """
        if self.retriever is None:
            try:
                self.retriever = Retriever.from_store(
                    self.domain, config=self.config
                )
            except Exception as exc:
                print(f"Error loading index: {exc}")
                print("Is Qdrant up ('make db-up') and the source "
                      "indexed ('make index')?")
                raise

        if with_reranker and self.retriever.reranker is None:
            self.retriever.load_reranker()

        return self.retriever

    def get_generator(self) -> Generator:
        """Load and cache the Generator.

        Returns:
            The loaded Generator instance.

        Raises:
            Exception: Propagates any model load error.
        """
        if self.generator is None:
            try:
                self.generator = Generator(self.config.generation)
            except Exception as exc:
                print(f"Error loading model: {exc}")
                raise
        return self.generator

    def index(self, source: Optional[str] = None,
              max_chunk_size: Optional[int] = None,
              code_chunk_size: Optional[int] = None,
              doc_chunk_size: Optional[int] = None,
              repo_root: Optional[str] = None) -> None:
        """Chunk knowledge sources and persist them.

        Without `source`, every source in rag.toml is indexed in turn,
        each into its own collection (rag_<source>). Chunk records go to
        Qdrant and the BM25 indices to <processed_dir>/<source>/. Sizes
        default to rag.toml.

        Args:
            source: Single source to index (default: all of them).
            max_chunk_size: Overrides both code and doc parent sizes.
            code_chunk_size: Maximum characters per code parent chunk.
            doc_chunk_size: Maximum characters per doc parent chunk.
            repo_root: Overrides the source root directory (only with
                `source`).
        """
        if source is None and repo_root:
            print("Error: --repo_root needs --source.")
            return
        for domain in [source] if source else list(self.config.sources):
            self.index_source(domain, max_chunk_size, code_chunk_size,
                              doc_chunk_size, repo_root)

    def index_source(self, domain: str,
                     max_chunk_size: Optional[int] = None,
                     code_chunk_size: Optional[int] = None,
                     doc_chunk_size: Optional[int] = None,
                     repo_root: Optional[str] = None) -> None:
        """Index one source (see index())."""
        from src.rag.ingestion.pipeline import Ingester
        from src.rag.ingestion.tokens import corpus_part_types
        from src.rag.storage.qdrant_store import QdrantChunkStore

        try:
            source_cfg = self.config.source(domain)
        except KeyError as exc:
            print(f"Error: {exc.args[0]}")
            return
        if repo_root:
            source_cfg = source_cfg.model_copy(update={"root": repo_root})
        # A source's own sizes (rag.toml chunk_size/child_size) win over
        # --max_chunk_size, which `make index` passes for every source.
        parent = source_cfg.chunk_size or max_chunk_size
        chunking = self.config.chunking.model_copy(update={
            k: v for k, v in {
                "code_chunk_size": code_chunk_size or parent,
                "doc_chunk_size": doc_chunk_size or parent,
                "code_child_size": source_cfg.child_size,
                "doc_child_size": source_cfg.child_size,
            }.items() if v
        })

        if not os.path.isdir(source_cfg.root):
            print(f"Error: source root of '{domain}' not found at "
                  f"'{source_cfg.root}' (download it first: 'make data' "
                  f"for vllm, 'make data-xquad' for xquad).")
            return
        try:
            store = QdrantChunkStore.from_config(self.config.qdrant)
            ingester = Ingester(
                domain, source_cfg, chunking,
                part_types=corpus_part_types(
                    self.config.retrieval.code_aware_tokens
                ),
            )
            ingester.build()
            emb = self.config.embeddings
            vectors = self.embed_children(ingester) if emb.enabled else {}
            ingester.save_bm25(
                self.config.paths.processed_dir,
                embedding_model=emb.model if emb.enabled else None,
            )
            store.replace(
                domain, ingester.all_chunks(),
                vector_name=vector_name(emb.model) if emb.enabled else None,
                vectors=vectors,
            )
            docs = sum(1 for c in ingester.chunks if c.chunk_type == "doc")
            print(
                f"Indexed '{domain}': {len(ingester.parent_chunks)} "
                f"parents, {len(ingester.chunks)} children "
                f"({docs} doc, {len(ingester.chunks) - docs} code)"
            )
        except Exception as exc:
            print(f"Error during indexing: {exc}")

    def fetch_xquad(self) -> None:
        """Download XQuAD (en, es) and build its corpus and datasets.

        Writes the article files to data/raw/xquad/ and the benchmark
        datasets to bench/datasets/xquad/ (see src/rag/sources/xquad.py).
        """
        from src.rag.sources.xquad import prepare

        try:
            prepare()
        except (OSError, ValueError) as exc:
            print(f"Error preparing XQuAD: {exc}")

    def build_cv_bench(self) -> None:
        """Build the CV-mode datasets from bench/datasets/cv/questions.json.

        Locates every answer's evidence in the biography (re-run after
        editing it; fails if an evidence is missing or ambiguous).
        """
        from src.rag.sources.cv import build

        try:
            print(f"CV benchmark: {build()} questions per language "
                  f"(en, es), evidence verified.")
        except (OSError, ValueError) as exc:
            print(f"Error building the CV benchmark: {exc}")

    def embed_children(self, ingester: "Ingester") -> dict:
        """Embed every child chunk with the configured model.

        Args:
            ingester: A built Ingester.

        Returns:
            Child chunk id -> embedding vector.
        """
        import time

        from src.rag.embeddings import Embedder, document_text

        emb = self.config.embeddings
        device = self.config.models.resolved_device()
        print(f"Embedding {len(ingester.chunks)} children with "
              f"{emb.model} on {device}...")
        # Loaded once when several sources are indexed in a row.
        if self.index_embedder is None:
            self.index_embedder = Embedder(emb.model, device=device,
                                           batch_size=emb.batch_size)
        embedder = self.index_embedder
        start = time.perf_counter()
        matrix = embedder.encode_documents([
            document_text(c.file_path, c.text) for c in ingester.chunks
        ])
        print(f"Embedded in {time.perf_counter() - start:.1f}s "
              f"(dim {matrix.shape[1]})")
        return {c.id: matrix[i] for i, c in enumerate(ingester.chunks)}

    def search(self, query: str, k: int = 10) -> None:
        """Search the knowledge base for a single query.

        Uses fast BM25-only retrieval — no reranker.

        Args:
            query: Search string. Empty query exits cleanly.
            k: Number of results to retrieve.
        """
        if not query or not query.strip():
            print("Empty query — no results.")
            return
        try:
            retriever = self.get_retriever(with_reranker=False)
            results = retriever.search(query, k=k)
        except Exception as exc:
            print(f"Error during search: {exc}")
            return

        if not results:
            print("No results found.")
            return

        print(f"\nPrompt: \"{query}\"\n")
        for i, source in enumerate(results, 1):
            chunk = self.find_chunk(retriever, source)
            print(f"[{i}] filepath: {source.file_path}")
            print(f"    chunk:    {i - 1}")
            print(
                f"    range:    {source.first_character_index}:"
                f"{source.last_character_index}"
            )
            if chunk:
                preview = chunk.text[:200].replace("\n", " ")
                print(f"    text:     {preview}...")
            print()

    def search_dataset(self, dataset_path: str, k: int = 10,
                       save_directory: str = "data/output/search_results"
                       ) -> None:
        """Run classifier-guided retrieval over a dataset JSON.

        Routes each question to the doc or code index via
        search_smart(), using the reranker only for ambiguous code
        queries.

        Args:
            dataset_path: Path to a RagDataset JSON.
            k: Chunks to retrieve per question.
            save_directory: Where the StudentSearchResults JSON is
                written.
        """
        if not os.path.isfile(dataset_path):
            print(f"Error: dataset file not found: {dataset_path}")
            return
        try:
            with open(dataset_path, "r", encoding="utf-8") as fh:
                dataset = RagDataset.model_validate_json(fh.read())
        except Exception as exc:
            print(f"Error reading dataset: {exc}")
            return
        try:
            retriever = self.get_retriever(with_reranker=True)
        except Exception:
            return

        results: list[MinimalSearchResults] = []
        for question in tqdm(dataset.rag_questions, desc="Searching"):
            sources = retriever.search_smart(question.question, k=k)
            results.append(MinimalSearchResults(
                question_id=question.question_id,
                question_str=question.question,
                retrieved_sources=sources,
            ))

        self.save_json(
            StudentSearchResults(search_results=results, k=k),
            save_directory,
            os.path.basename(dataset_path),
            label="student_search_results",
        )

    def get_router(self) -> DomainRouter:
        """Load and cache a DomainRouter over every indexed domain."""
        if self.router is None:
            self.router = DomainRouter.from_store(config=self.config)
        return self.router

    def get_pipeline(self) -> RagPipeline:
        """The shared answer flow (router with reranker + generator)."""
        return RagPipeline(self.get_router(), self.get_generator())

    def get_agent(self, k: int = 5) -> "Agent":
        """Load and cache the agent (router + generator + session)."""
        from src.agent.agent import Agent
        from src.server.tools import RagTools

        if self.agent is None:
            tools = RagTools(self.get_router(), self.config,
                             self.get_generator())
            self.agent = Agent(tools, k=k)
        return self.agent

    def answer(self, query: str, k: int = 5, stream: bool = True,
               domains: Optional[str] = None, agent: bool = True) -> None:
        """Answer a single question.

        By default through the agent (D7): it rewrites the question,
        decides the searches and answers from the best domain. With
        --agent False, the direct flow (search every domain, answer
        from the best one). `domains` restricts the search either way.

        Args:
            query: Natural-language question.
            k: Number of chunks to retrieve as context.
            stream: Print the answer as it is generated.
            domains: Optional filter, e.g. "xquad" or "vllm,xquad"
                (default: all indexed domains).
            agent: Use the agent (True) or the direct flow (False).
        """
        if not query or not query.strip():
            print("Empty query — nothing to answer.")
            return
        print(f"\nPrompt: \"{query}\"\n")
        try:
            self.reply(query, k, stream, domains, agent)
        except Exception as exc:
            print(f"Error while answering: {exc}")

    def chat(self, agent: bool = True, k: int = 5,
             domains: Optional[str] = None) -> None:
        """Interactive conversation (session memory with the agent).

        Commands: /agent (toggle agent / direct), /reset (forget the
        conversation), /exit (or an empty line) to quit.

        Args:
            agent: Start with the agent (True) or in direct mode.
            k: Number of chunks to retrieve as context.
            domains: Optional domain filter for the whole session.
        """
        print("Chat with the RAG. /agent toggles agent/direct, /reset "
              "forgets the conversation, /exit quits.")
        use_agent = agent
        while True:
            try:
                question = input(
                    f"\n[{'agent' if use_agent else 'direct'}] > "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question or question == "/exit":
                break
            if question == "/agent":
                use_agent = not use_agent
                print(f"Mode: {'agent' if use_agent else 'direct'}")
                continue
            if question == "/reset":
                if self.agent is not None:
                    self.agent.session.clear()
                print("Conversation forgotten.")
                continue
            try:
                self.reply(question, k, True, domains, use_agent)
            except Exception as exc:
                print(f"Error while answering: {exc}")

    def reply(self, question: str, k: int, stream: bool,
              domains: Optional[str], use_agent: bool) -> None:
        """Answer one question (agent or direct) and print it."""
        def show(piece: str) -> None:
            print(piece, end="", flush=True)

        print("=== Answer ===")
        if use_agent:
            agent = self.get_agent(k)
            result = agent.ask(question, domains,
                               on_piece=show if stream else None)
            text, sources, not_found = (result.text, result.sources,
                                        result.not_found)
            trace = f"agent {agent.trace(result)}"
        else:
            pipeline = self.get_pipeline()
            answer = pipeline.answer(question, k=k, domains=domains,
                                     on_piece=show if stream else None)
            text, sources, not_found = (answer.text, answer.sources,
                                        answer.not_found)
            trace = "direct, route " + ", ".join(
                f"{d} ({s:.2f})" for d, s in self.get_router().last_route
            )
        if not stream:
            print(text)
        elif not_found and sources:
            # The LLM's own "not found" was streamed; show the domain's
            # message instead.
            print("\n" + text)
        else:
            print()
        print(f"\n=== Trace ===\n{trace}")
        if not not_found:
            self.print_sources(sources)

    def print_sources(self, sources: list[MinimalSource]) -> None:
        """Print sources with their (masked) text preview."""
        from src.rag.domain_rules import DomainRules

        rules = DomainRules(self.config)
        parents = self.get_router().get_parent_chunk_map()
        print("\n=== Sources ===")
        for i, src in enumerate(sources):
            chunk = parents.get((src.file_path, src.first_character_index))
            print(f"[{i + 1}] filepath: {src.file_path}")
            print(f"    range:    {src.first_character_index}:"
                  f"{src.last_character_index}")
            if chunk:
                text = rules.redact(chunk.text, chunk.domain)
                print(f"    text:     {text[:200].replace(chr(10), ' ')}...")
            print()

    def answer_dataset(self, dataset_path: str, k: int = 10,
                       save_directory: str = "data/output/answers",
                       skip_generation: bool = True) -> None:
        """Full RAG pipeline over an entire dataset:
        retrieve + rerank + generate.

        Args:
            dataset_path: Path to a RagDataset JSON.
            k: Chunks to retrieve per question.
            save_directory: Where the output JSON is written.
            skip_generation: If True, saves retrieval results only.
                Useful for measuring recall@k without the LLM.
        """
        if not os.path.isfile(dataset_path):
            print(f"Error: dataset file not found: {dataset_path}")
            return
        try:
            with open(dataset_path, "r", encoding="utf-8") as fh:
                dataset = RagDataset.model_validate_json(fh.read())
        except Exception as exc:
            print(f"Error reading dataset: {exc}")
            return

        try:
            retriever = self.get_retriever(with_reranker=True)
        except Exception:
            return

        if not skip_generation:
            try:
                self.generator = self.get_generator()
            except Exception:
                return

        answers: list[MinimalAnswer] = []
        search_only: list[MinimalSearchResults] = []
        desc = "Retrieving" if skip_generation else "RAG pipeline"

        if skip_generation:
            for question in tqdm(dataset.rag_questions, desc=desc):
                sources = retriever.search_for_generation(
                    question.question, k=k
                )
                search_only.append(MinimalSearchResults(
                    question_id=question.question_id,
                    question_str=question.question,
                    retrieved_sources=sources,
                ))
        else:
            # One domain (the 42 corpus), like the retrieval-only path.
            pipeline = RagPipeline(retriever, self.get_generator())
            for question in tqdm(dataset.rag_questions, desc=desc):
                try:
                    result = pipeline.answer(question.question, k=k)
                    response, sources = result.text, result.sources
                except Exception:
                    response, sources = "Error generating answer.", []
                answers.append(MinimalAnswer(
                    question_id=question.question_id,
                    question_str=question.question,
                    retrieved_sources=sources,
                    answer=response,
                ))

        filename = os.path.basename(dataset_path)
        if skip_generation:
            self.save_json(
                StudentSearchResults(search_results=search_only, k=k),
                save_directory,
                filename,
                label="search_results",
            )
        else:
            self.save_json(
                StudentSearchResultsAndAnswer(search_results=answers, k=k),
                save_directory,
                filename,
                label="search_results_and_answer",
            )

    def evaluate(self, student_answer_path: str, dataset_path: str,
                 k: int = 10, max_context_length: int = 2000) -> None:
        """Evaluate retrieval quality using Recall@k vs. ground truth.

        Args:
            student_answer_path: Path to a StudentSearchResults JSON.
            dataset_path: Path to the AnsweredQuestions RagDataset
                JSON.
            k: Evaluate Recall@1, @3, @5 and @k.
            max_context_length: Kept for moulinette CLI
                compatibility; unused.
        """
        from src.evaluation.evaluator import Evaluator

        if not os.path.isfile(student_answer_path):
            print(f"Error: file not found: {student_answer_path}")
            return
        if not os.path.isfile(dataset_path):
            print(f"Error: ground truth not found: {dataset_path}")
            return
        try:
            evaluator = Evaluator()
            metrics = evaluator.compute_recall(
                student_path=student_answer_path,
                ground_truth_path=dataset_path,
                k=k,
            )
            evaluator.print_report(metrics)
        except Exception as exc:
            print(f"Error during evaluation: {exc}")

    def judge(self, label: str, limit: Optional[int] = 10) -> None:
        """Grade a gen_bench run's answers with an LLM judge (Groq).

        Uses JUDGE_BASE_URL, JUDGE_MODEL and GROQ_API_KEY from .env.
        Verdicts are cached, so re-running costs no extra quota.

        Args:
            label: gen_bench run to judge.
            limit: Answers judged per set (default 10).
        """
        from src.evaluation.judge import JudgeError, run_judge

        try:
            run_judge(label, limit=limit)
        except (JudgeError, OSError) as exc:
            print(f"Judge unavailable: {exc}")

    def gen_bench(self, label: str = "run", k: int = 5,
                  limit: Optional[int] = None,
                  suite: str = "vllm", full: bool = False) -> None:
        """Generate answers for the benchmark sets and score them.

        Measures token F1 against the 42 reference answers, citations,
        answer language (Spanish set) and "not found" on out-of-domain
        questions. Results go to bench/results/gen/.

        Args:
            label: Short name for this run.
            k: Sources passed to the generator.
            limit: Questions per public dataset (default: all 100).
            suite: "vllm" (42 sets + out-of-domain) or "xquad" (XQuAD
                en/es over the xquad domain; 300 fixed questions per
                language unless --full).
            full: Ask every question of the suite (complete runs only).
        """
        from src.evaluation.gen_bench import run_gen_bench

        try:
            run_gen_bench(label=label, k=k, limit=limit,
                          domain=self.domain, config=self.config,
                          suite=suite, full=full)
        except Exception as exc:
            print(f"Error during gen_bench: {exc}")

    def bench(self, label: str = "run", k: int = 10,
              suite: str = "public") -> None:
        """Run both public datasets, evaluate and record the result.

        Results are appended to bench/results/ and compared against
        every previous run.

        Args:
            label: Short name for this run (e.g. 'baseline').
            k: Number of sources retrieved per question.
            suite: "public" (official 42 datasets), "en" or "es" (the
                20-question complement, same ground truth). The answer
                flow is measured by gen_bench.
        """
        from src.evaluation.bench import run_bench

        try:
            run_bench(
                label=label, k=k, suite=suite,
                domain=self.domain, config=self.config,
            )
        except Exception as exc:
            print(f"Error during bench: {exc}")

    def route_bench(self, label: str = "run", k: int = 10,
                    limit: Optional[int] = None) -> None:
        """Measure the router: unfiltered questions vs. their domain.

        Every benchmark set (42 public, Spanish complement, XQuAD en/es)
        is searched across all indexed domains. Records routing accuracy
        and routed Recall@k in bench/results/route/.

        Args:
            label: Short name for this run.
            k: Sources retrieved per question.
            limit: Questions per dataset (default: all).
        """
        from src.evaluation.routing import run_route_bench

        try:
            run_route_bench(label=label, k=k, limit=limit,
                            config=self.config)
        except Exception as exc:
            print(f"Error during route_bench: {exc}")

    def gate_scores(self, domain: Optional[str] = None, k: int = 5,
                    label: str = "run",
                    limit: Optional[int] = None) -> None:
        """Calibrate a domain's out-of-domain gate.

        Scores (as the gate does) the questions the domain should answer
        and those it should reject, and prints the pass rate of candidate
        thresholds. Results go to bench/results/gate/.

        Args:
            domain: Domain to calibrate (default: the CLI domain).
            k: Sources retrieved per question (gen-bench and web use 5).
            label: Short name for this run.
            limit: Questions per group (default: all).
        """
        from src.evaluation.gate import run_gate_scores

        try:
            run_gate_scores(domain or self.domain, k=k, label=label,
                            limit=limit, config=self.config)
        except Exception as exc:
            print(f"Error during gate_scores: {exc}")

    def agent_bench(self, label: str = "run", k: int = 5,
                    sets: str = "all") -> None:
        """Agent vs direct access on conversations and single questions.

        Results go to bench/results/agent/. The LLM (and so the agent)
        is the one of the active profile (--profile / PROFILE=).

        Args:
            label: Short name for this run.
            k: Sources per search / answer.
            sets: "conversations", "single" or "all".
        """
        from src.evaluation.agent_bench import run_agent_bench

        try:
            run_agent_bench(label=label, k=k, sets=sets,
                            config=self.config)
        except Exception as exc:
            print(f"Error during agent_bench: {exc}")

    def bundle_export(self, out_dir: str = "deploy/bundle") -> None:
        """Snapshot every indexed domain (Qdrant + BM25) into a bundle.

        The bundle holds raw CV text: keep it private (see
        docs/decisions.md). deploy/ is git-ignored.
        """
        from src.deploy.bundle import export_bundle

        try:
            export_bundle(out_dir, self.config)
        except Exception as exc:
            print(f"Error exporting the bundle: {exc}")

    def bundle_restore(self, bundle_dir: str = "deploy/bundle") -> None:
        """Load a bundle into Qdrant and data/processed (SHA256 checked)."""
        from src.deploy.bundle import restore_bundle

        try:
            restore_bundle(bundle_dir, self.config)
        except Exception as exc:
            print(f"Error restoring the bundle: {exc}")

    def mcp(self, transport: str = "stdio", port: int = 8765) -> None:
        """Serve the RAG over MCP (tools: list_domains, search, answer).

        Args:
            transport: "stdio" (launched by an MCP client) or
                "streamable-http" (http://127.0.0.1:<port>/mcp).
            port: HTTP port for streamable-http.
        """
        from src.server.mcp_server import run

        if transport not in ("stdio", "streamable-http"):
            print("Error: transport must be 'stdio' or 'streamable-http'")
            return
        run("stdio" if transport == "stdio" else "streamable-http", port)

    @staticmethod
    def find_chunk(retriever: Retriever,
                   source: MinimalSource) -> Chunk | None:
        """Find the Chunk object matching a MinimalSource.

        Args:
            retriever: The loaded Retriever instance.
            source: MinimalSource to look up.

        Returns:
            Matching Chunk or None if not found.
        """
        chunk_map = retriever.get_chunk_map()
        return chunk_map.get(
            (source.file_path, source.first_character_index)
        )

    @staticmethod
    def save_json(model: BaseModel, directory: str,
                  filename: str, label: str) -> None:
        """Serialize a Pydantic model to JSON and write it to disk.

        Args:
            model: Any Pydantic BaseModel with model_dump_json().
            directory: Target directory (created if missing).
            filename: Output filename.
            label: Human-readable label for the success message.
        """
        os.makedirs(directory, exist_ok=True)
        out_path = os.path.join(directory, filename)
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(model.model_dump_json(indent=2))
            print(f"Saved {label} to {out_path}")
        except Exception as exc:
            print(f"Error saving {label}: {exc}")
