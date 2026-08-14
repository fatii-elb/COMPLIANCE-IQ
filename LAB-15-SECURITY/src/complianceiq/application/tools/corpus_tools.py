"""Built-in tools over the knowledge base.

``search_corpus`` lets an agent look up relevant controls on demand. Its typed
arguments (validated Pydantic) prevent malformed calls, and it returns the
assembled context text — which the bounded-agent layer scans for injection before
trusting.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from complianceiq.application.graphs._common import retrieve_and_assemble
from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.application.tools.registry import Tool
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.value_objects.enums import Framework


class SearchCorpusArgs(BaseModel):
    """Arguments for the ``search_corpus`` tool."""

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    framework: Framework | None = None


def build_corpus_tools(
    retriever: HybridRetriever, assembler: ContextAssembler, config: RetrievalConfig
) -> list[Tool]:
    """Build the knowledge-base tools bound to the retrieval stack."""

    async def _search(args: BaseModel, auth: AuthContext) -> str:
        assert isinstance(args, SearchCorpusArgs)
        metadata_filter = (
            MetadataFilter(framework=args.framework) if args.framework else MetadataFilter()
        )
        _, context = await retrieve_and_assemble(
            retriever,
            assembler,
            query_text=args.query,
            top_k=args.top_k,
            token_budget=config.context_token_budget,
            metadata_filter=metadata_filter,
        )
        return context.text or "No relevant sources found."

    return [
        Tool(
            name="search_corpus",
            description="Search the compliance knowledge base for the most relevant controls.",
            args_model=SearchCorpusArgs,
            handler=_search,
        )
    ]
