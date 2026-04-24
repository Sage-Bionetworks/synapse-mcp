"""Tool-selection eval: rank Synapse MCP tools against natural-language queries.

Drives the FastMCP BM25 index directly (no LLM in the loop) so we can
measure whether tool names, descriptions, synonyms, and siblings set up
the ranking the LLM will ultimately see.

Run with:
    uv run pytest tests/evals/test_tool_selection.py -v

The module-level summary fixture prints top-1 / top-3 / top-5 accuracy
at the end of the run.

Queries in this file only reference tools that exist in the current
stack (all 50 are read-only). When write tools ship — create_wiki,
submit_to_evaluation, register_json_schema, etc. — add their queries
here.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest
from fastmcp.server.transforms.search.bm25 import (
    _BM25Index,
    _extract_searchable_text,
)

# Importing synapse_mcp triggers @service_tool registration; by the time
# the list below is evaluated every tool is live on the server singleton.
import synapse_mcp  # noqa: F401
from synapse_mcp import mcp

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


# Query → expected tool. Mix of Synapse jargon and user-language
# synonyms, ≥2 per service. Only read tools in the current catalog.
QUERY_FIXTURES: List[Tuple[str, str]] = [
    # entity
    ("what's the metadata for syn456", "get_entity"),
    ("give me the entity record for syn123456", "get_entity"),
    ("what files are in this project syn100", "get_entity_children"),
    ("list everything inside folder syn200", "get_entity_children"),
    ("who owns syn789 and what permissions do I have", "get_entity_permissions"),
    ("show me the sharing settings on syn333", "get_entity_acl"),
    ("audit all ACLs under this project syn500 recursively", "list_entity_acl"),
    ("resolve the Link entity syn900 to its target", "get_link"),
    # annotations
    ("tags on this file syn789", "get_entity_annotations"),
    ("what metadata key-value pairs are on syn555", "get_entity_annotations"),
    # activity / provenance
    ("what produced this file syn456", "get_entity_provenance"),
    ("show me the lineage of syn123", "get_entity_provenance"),
    ("data history for syn999", "get_entity_provenance"),
    ("look up activity 9660001", "get_activity"),
    # entity schema
    ("what JSON schema is bound to syn777", "get_entity_schema"),
    ("validation compliance summary for project syn444", "get_entity_schema_validation_statistics"),
    ("which files failing schema validation under syn444", "get_entity_schema_invalid_validations"),
    ("what annotation keys does the bound schema require on syn888", "get_entity_schema_derived_keys"),
    # search
    ("find all files with cancer_type=glioma", "search_synapse"),
    ("search for tables about brain tissue", "search_synapse"),
    # wiki
    ("show me the readme for this project syn100", "get_wiki_page"),
    ("what documentation pages are in syn200's wiki", "get_wiki_headers"),
    ("who edited wiki page 12345 on syn200", "get_wiki_history"),
    ("how are wiki sub-pages ordered on syn300", "get_wiki_order_hint"),
    # team
    ("who is on team 3379097", "get_team_members"),
    ("pending invites to the NF-OSI team", "get_team_open_invitations"),
    ("is user 1234567 a member of team 3379097", "get_team_membership_status"),
    ("look up team by name NF-OSI Curators", "get_team"),
    # user
    ("is user 1234567 certified", "check_user_certified"),
    ("profile for user jane.doe", "get_user_profile"),
    # evaluation (challenge queue)
    ("show me the DREAM challenge queue", "get_evaluation"),
    ("what evaluations are open in project syn100", "list_evaluations"),
    ("who can submit to challenge 9600001", "get_evaluation_acl"),
    ("can I submit to queue 9600001", "get_evaluation_permissions"),
    # submission
    ("my entries to evaluation 9600001", "list_my_submissions"),
    ("my challenge submission bundles for queue 9600001", "list_my_submission_bundles"),
    ("how many submissions to queue 9600001", "get_submission_count"),
    ("scoring status of submission 9722233", "get_submission_status"),
    ("all entries to challenge 9600001", "list_evaluation_submissions"),
    ("statuses for every submission in 9600001", "list_submission_statuses"),
    ("submission and status together for 9600001", "list_evaluation_submission_bundles"),
    ("look up submission 9722233", "get_submission"),
    # curation
    ("list curation tasks in project syn123", "list_curation_tasks"),
    ("details of curation task 42", "get_curation_task"),
    ("resources linked to curation task 42", "get_curation_task_resources"),
    # schema / organization
    ("find the ELITE JSON schema organization", "get_schema_organization"),
    ("list JSON schemas owned by org.sagebionetworks", "list_json_schemas"),
    ("raw schema document for myDataset-1.0.0", "get_json_schema_body"),
    ("versions of the myDataset JSON schema", "list_json_schema_versions"),
    ("schema metadata for myDataset-1.0.0", "get_json_schema"),
    ("who can publish under org.sagebionetworks namespace", "get_schema_organization_acl"),
    # form
    ("list my submissions to form group 42", "list_form_data"),
    # utility
    ("does syn999 exist", "check_synapse_id"),
    ("find the file with md5 9e107d9d372bb6826bd81d3542a419d6", "search_entities_by_md5"),
    ("what's the synapse id of the file named sample.csv in folder syn100", "search_entity_by_name"),
    # docker
    ("what's the Synapse Docker repo for syn789", "get_docker_repository"),
    ("docker image entity by synapse id syn789", "get_docker_repository"),
]


async def _build_index() -> Tuple[_BM25Index, list]:
    # ``_list_tools`` returns the raw tool catalog before visibility /
    # BM25 transforms run — which is exactly what the BM25 index itself
    # consumes at runtime (it sees the pre-filter list). Calling
    # ``list_tools`` here would return only the always-visible +
    # synthetic search tools.
    tools = await mcp._list_tools()
    index = _BM25Index()
    docs = [_extract_searchable_text(t) for t in tools]
    index.build(docs)
    return index, tools


@pytest.fixture
async def bm25_index():
    return await _build_index()


def _rank_pos(index: _BM25Index, tools, query: str, target: str) -> int:
    """Return 1-based rank of target tool, or 0 if not found in top 50."""
    indices = index.query(query, top_k=50)
    for rank, i in enumerate(indices, start=1):
        if tools[i].name == target:
            return rank
    return 0


@pytest.mark.parametrize("query,expected", QUERY_FIXTURES, ids=[f"{e}::{q[:40]}" for q, e in QUERY_FIXTURES])
async def test_expected_tool_in_top_3(bm25_index, query, expected):
    index, tools = bm25_index
    rank = _rank_pos(index, tools, query, expected)
    assert 0 < rank <= 3, (
        f"{expected!r} ranked {rank or 'missing'} for query {query!r}; "
        f"top-3 was {[tools[i].name for i in index.query(query, 3)]}"
    )


async def test_selection_accuracy_summary(bm25_index, capsys):
    """Print aggregate top-1 / top-3 / top-5 accuracy. Does not gate the build."""
    index, tools = bm25_index
    top1 = top3 = top5 = 0
    failures = []
    for query, expected in QUERY_FIXTURES:
        rank = _rank_pos(index, tools, query, expected)
        if rank == 1:
            top1 += 1
        if 0 < rank <= 3:
            top3 += 1
        if 0 < rank <= 5:
            top5 += 1
        if not (0 < rank <= 3):
            failures.append((query, expected, rank, [tools[i].name for i in index.query(query, 5)]))

    n = len(QUERY_FIXTURES)
    print(f"\n=== Tool-selection eval ({n} queries) ===")
    print(f"top-1: {top1}/{n} ({100 * top1 / n:.1f}%)")
    print(f"top-3: {top3}/{n} ({100 * top3 / n:.1f}%)")
    print(f"top-5: {top5}/{n} ({100 * top5 / n:.1f}%)")
    if failures:
        print("\nQueries missing the expected tool from top-3:")
        for q, exp, rank, top5_names in failures:
            rank_str = f"rank {rank}" if rank else "missing"
            print(f"  - {q!r} -> {exp!r} ({rank_str}); top-5: {top5_names}")
