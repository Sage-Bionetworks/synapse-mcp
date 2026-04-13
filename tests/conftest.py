"""Test configuration for synapse-mcp."""

import os
import sys
from pathlib import Path

from synapseclient.models import (
    CurationTask,
    FileBasedMetadataTaskProperties,
    RecordBasedMetadataTaskProperties,
)

# Ensure package can be imported without real credentials.
# The app module raises ValueError at import time when no auth env var is set,
# which blocks test collection even though all tests use mocked clients.
os.environ.setdefault("SYNAPSE_PAT", "fake-for-tests")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# -------------------------------------------------------------------
# Shared test helpers for curation task objects
# -------------------------------------------------------------------


def make_task(
    *,
    task_id=1,
    data_type="DataType",
    project_id="syn999",
    instructions="Do curation",
    etag="abc123",
    created_on="2024-01-01",
    modified_on="2024-01-02",
    created_by="user1",
    modified_by="user2",
    task_properties=None,
):
    """Build a CurationTask model instance for testing."""
    return CurationTask(
        task_id=task_id,
        data_type=data_type,
        project_id=project_id,
        instructions=instructions,
        etag=etag,
        created_on=created_on,
        modified_on=modified_on,
        created_by=created_by,
        modified_by=modified_by,
        task_properties=task_properties,
    )


def file_based_properties(upload_folder_id="syn100", file_view_id="syn200"):
    """Create a FileBasedMetadataTaskProperties instance."""
    return FileBasedMetadataTaskProperties(
        upload_folder_id=upload_folder_id,
        file_view_id=file_view_id,
    )


def record_based_properties(record_set_id="syn300"):
    """Create a RecordBasedMetadataTaskProperties instance."""
    return RecordBasedMetadataTaskProperties(record_set_id=record_set_id)
