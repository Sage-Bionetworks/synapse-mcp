"""Shared parameter types for write/mutation tools.

Keeps the tool signatures self-documenting: ``Literal`` enums render as
JSON-schema ``enum`` lists (so the LLM sees the exact allowed values) and
``TypedDict`` shapes render as named ``$ref`` objects instead of an opaque
``dict``. ``typing_extensions.TypedDict`` is required — pydantic rejects
``typing.TypedDict`` on Python < 3.12.
"""

from typing import List, Literal, Optional

from typing_extensions import TypedDict

# Entity types ``create_entity`` can build without uploading file content.
EntityType = Literal[
    "project",
    "folder",
    "file",
    "link",
    "dataset",
    "datasetcollection",
    "entityview",
    "table",
    "materializedview",
    "virtualtable",
    "submissionview",
    "dockerrepository",
    "recordset",
]

# Access types accepted by an entity ACL grant (set_permissions).
# See ACCESS_TYPE in the Synapse REST docs.
EntityAccessType = Literal[
    "READ",
    "UPDATE",
    "CREATE",
    "DELETE",
    "DOWNLOAD",
    "MODERATE",
    "CHANGE_PERMISSIONS",
    "CHANGE_SETTINGS",
]

# Access types accepted by an Evaluation queue ACL grant.
EvaluationAccessType = Literal[
    "READ",
    "UPDATE",
    "DELETE",
    "CREATE",
    "SUBMIT",
    "READ_PRIVATE_SUBMISSION",
    "DELETE_SUBMISSION",
    "UPDATE_SUBMISSION",
    "CHANGE_PERMISSIONS",
]

# Access types accepted by a JSON Schema Organization ACL grant.
OrganizationAccessType = Literal[
    "READ",
    "CREATE",
    "UPDATE",
    "DELETE",
    "CHANGE_PERMISSIONS",
]

# Scoring states a submission status can be set to.
SubmissionStatusValue = Literal[
    "OPEN",
    "CLOSED",
    "RECEIVED",
    "VALIDATED",
    "EVALUATION_IN_PROGRESS",
    "SCORED",
    "INVALID",
    "ACCEPTED",
    "REJECTED",
]


# Column data types supported when defining table/view columns.
ColumnDataType = Literal[
    "STRING",
    "DOUBLE",
    "INTEGER",
    "BOOLEAN",
    "DATE",
    "FILEHANDLEID",
    "ENTITYID",
    "SUBMISSIONID",
    "USERID",
    "LARGETEXT",
    "LINK",
    "MEDIUMTEXT",
    "STRING_LIST",
    "INTEGER_LIST",
    "BOOLEAN_LIST",
    "DATE_LIST",
    "ENTITYID_LIST",
    "USERID_LIST",
    "JSON",
]

# Scope types for view/dataset entities (ViewTypeMask flags).
ViewScopeType = Literal[
    "file",
    "project",
    "table",
    "folder",
    "view",
    "docker",
    "submission_view",
    "dataset",
]


class ColumnSpec(TypedDict, total=False):
    """A single table/view column definition."""

    name: str
    column_type: ColumnDataType
    maximum_size: int
    default_value: str
    enum_values: List[str]


class UsedItem(TypedDict, total=False):
    """One provenance input/output: a Synapse entity ref or an external URL.

    Provide ``target_id`` (and optionally ``target_version_number``) for a
    Synapse entity, or ``url`` (and optionally ``name``) for an external URL.
    """

    target_id: str
    target_version_number: int
    name: str
    url: str


class ProvenanceSpec(TypedDict, total=False):
    """Provenance/Activity attached to an entity on store."""

    name: str
    description: str
    used: List[UsedItem]
    executed: List[UsedItem]


class TaskProperties(TypedDict, total=False):
    """Curation-task shape selector.

    Provide ``record_set_id`` for a record-based task, or
    ``upload_folder_id`` (and optionally ``file_view_id``) for a file-based
    task.
    """

    record_set_id: str
    upload_folder_id: str
    file_view_id: str


class _Unset:
    """Sentinel distinguishing "argument omitted" from an explicit ``None``.

    Update tools default their optional fields to ``UNSET``. A field left at
    ``UNSET`` is not touched; passing ``None`` explicitly clears it. This lets
    a caller both leave a field alone and blank it out.
    """

    _instance: Optional["_Unset"] = None

    def __new__(cls) -> "_Unset":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()
