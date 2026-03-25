"""Tests for curation task tools, service, and manager layers.

Test coverage is organized by layer:
  - CurationTaskManager  — raw Synapse API interactions
  - CurationTaskService  — orchestration and response shaping
  - MCP tool functions   — thin controller (auth + delegation)
"""

import synapse_mcp
import synapse_mcp.tools as tools
from synapse_mcp.context_helpers import ConnectionAuthError
from synapse_mcp.managers.curation_task_manager import CurationTaskManager
from synapse_mcp.services.curation_task_service import CurationTaskService, _format_task, _format_task_properties


# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

class DummyContext:
    pass


class _FileBasedProperties:
    """Simulates file-based CurationTask task_properties."""
    def __init__(self, upload_folder_id="syn100", file_view_id="syn200"):
        self.upload_folder_id = upload_folder_id
        self.file_view_id = file_view_id


class _RecordBasedProperties:
    """Simulates record-based CurationTask task_properties."""
    def __init__(self, record_set_id="syn300"):
        self.record_set_id = record_set_id


class _DummyTask:
    def __init__(
        self,
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
        self.task_id = task_id
        self.data_type = data_type
        self.project_id = project_id
        self.instructions = instructions
        self.etag = etag
        self.created_on = created_on
        self.modified_on = modified_on
        self.created_by = created_by
        self.modified_by = modified_by
        self.task_properties = task_properties

    def get(self, synapse_client=None):
        return self


class _DummySynapseClient:
    """Minimal stand-in for synapseclient.Synapse."""
    pass


# ---------------------------------------------------------------------------
# _format_task_properties (unit)
# ---------------------------------------------------------------------------

def test_format_task_properties_file_based():
    props = _FileBasedProperties("syn100", "syn200")
    result = _format_task_properties(props)
    assert result == {
        "type": "file-based",
        "upload_folder_id": "syn100",
        "file_view_id": "syn200",
    }


def test_format_task_properties_record_based():
    props = _RecordBasedProperties("syn300")
    result = _format_task_properties(props)
    assert result == {
        "type": "record-based",
        "record_set_id": "syn300",
    }


def test_format_task_properties_none():
    result = _format_task_properties(None)
    assert result == {}


# ---------------------------------------------------------------------------
# _format_task (unit)
# ---------------------------------------------------------------------------

def test_format_task_includes_all_fields():
    task = _DummyTask(task_id=42, task_properties=_FileBasedProperties())
    result = _format_task(task)
    assert result["task_id"] == 42
    assert result["data_type"] == "DataType"
    assert result["project_id"] == "syn999"
    assert result["instructions"] == "Do curation"
    assert result["etag"] == "abc123"
    assert result["task_properties"]["type"] == "file-based"


def test_format_task_omits_task_properties_when_none():
    task = _DummyTask(task_properties=None)
    result = _format_task(task)
    assert "task_properties" not in result


# ---------------------------------------------------------------------------
# CurationTaskManager (unit)
# ---------------------------------------------------------------------------

def test_manager_list_tasks(monkeypatch):
    task = _DummyTask(task_id=1)
    monkeypatch.setattr(
        "synapse_mcp.managers.curation_task_manager.CurationTask",
        type("CurationTask", (), {"list": staticmethod(lambda project_id, synapse_client: iter([task]))}),
    )
    manager = CurationTaskManager(_DummySynapseClient())
    results = list(manager.list_tasks("syn999"))
    assert len(results) == 1
    assert results[0].task_id == 1


def test_manager_get_task(monkeypatch):
    task = _DummyTask(task_id=7)
    monkeypatch.setattr(
        "synapse_mcp.managers.curation_task_manager.CurationTask",
        lambda task_id: task,
    )
    manager = CurationTaskManager(_DummySynapseClient())
    result = manager.get_task(7)
    assert result.task_id == 7


def test_manager_get_folder(monkeypatch):
    class _FakeFolder:
        def __init__(self, id):
            self.id = id
        def get(self, synapse_client=None):
            return {"id": self.id}

    monkeypatch.setattr("synapse_mcp.managers.curation_task_manager.Folder", _FakeFolder)
    manager = CurationTaskManager(_DummySynapseClient())
    result = manager.get_folder("syn100")
    assert result["id"] == "syn100"


def test_manager_get_entity_view(monkeypatch):
    class _FakeView:
        def __init__(self, id):
            self.id = id
        def get(self, synapse_client=None):
            return {"id": self.id}

    monkeypatch.setattr("synapse_mcp.managers.curation_task_manager.EntityView", _FakeView)
    manager = CurationTaskManager(_DummySynapseClient())
    result = manager.get_entity_view("syn200")
    assert result["id"] == "syn200"


def test_manager_get_record_set(monkeypatch):
    class _FakeRecordSet:
        def __init__(self, id, download_file=False):
            self.id = id
        def get(self, synapse_client=None):
            return {"id": self.id}

    monkeypatch.setattr("synapse_mcp.managers.curation_task_manager.RecordSet", _FakeRecordSet)
    manager = CurationTaskManager(_DummySynapseClient())
    result = manager.get_record_set("syn300")
    assert result["id"] == "syn300"


# ---------------------------------------------------------------------------
# CurationTaskService (unit)
# ---------------------------------------------------------------------------

class _StubManager:
    """Stub for CurationTaskManager used to test the service layer in isolation."""

    def __init__(self, tasks=None, task=None, folder=None, view=None, record_set=None):
        self._tasks = tasks or []
        self._task = task
        self._folder = folder or {"id": "syn100"}
        self._view = view or {"id": "syn200"}
        self._record_set = record_set or {"id": "syn300"}

    def list_tasks(self, project_id):
        return iter(self._tasks)

    def get_task(self, task_id):
        return self._task

    def get_folder(self, folder_id):
        return self._folder

    def get_entity_view(self, view_id):
        return self._view

    def get_record_set(self, record_set_id):
        return self._record_set


def _service_with_stub(stub: _StubManager) -> CurationTaskService:
    """Create a CurationTaskService with an injected stub manager."""
    svc = CurationTaskService.__new__(CurationTaskService)
    svc._manager = stub
    return svc


def test_service_list_tasks_returns_formatted_list():
    tasks = [
        _DummyTask(task_id=1, task_properties=_FileBasedProperties()),
        _DummyTask(task_id=2, task_properties=_RecordBasedProperties()),
    ]
    svc = _service_with_stub(_StubManager(tasks=tasks))
    result = svc.list_tasks("syn999")

    assert len(result) == 2
    assert result[0]["task_id"] == 1
    assert result[0]["task_properties"]["type"] == "file-based"
    assert result[1]["task_id"] == 2
    assert result[1]["task_properties"]["type"] == "record-based"


def test_service_list_tasks_empty():
    svc = _service_with_stub(_StubManager(tasks=[]))
    result = svc.list_tasks("syn999")
    assert result == []


def test_service_get_task():
    task = _DummyTask(task_id=42, task_properties=_FileBasedProperties())
    svc = _service_with_stub(_StubManager(task=task))
    result = svc.get_task(42)
    assert result["task_id"] == 42
    assert result["task_properties"]["type"] == "file-based"


def test_service_get_task_resources_file_based():
    task = _DummyTask(task_id=1, task_properties=_FileBasedProperties("syn100", "syn200"))
    svc = _service_with_stub(_StubManager(task=task))
    result = svc.get_task_resources(1)

    assert result["task_id"] == 1
    assert result["resources"]["type"] == "file-based"
    assert result["resources"]["upload_folder"]["id"] == "syn100"
    assert result["resources"]["file_view"]["id"] == "syn200"


def test_service_get_task_resources_record_based():
    task = _DummyTask(task_id=2, task_properties=_RecordBasedProperties("syn300"))
    svc = _service_with_stub(_StubManager(task=task))
    result = svc.get_task_resources(2)

    assert result["task_id"] == 2
    assert result["resources"]["type"] == "record-based"
    assert result["resources"]["record_set"]["id"] == "syn300"


def test_service_get_task_resources_folder_fetch_error():
    """A folder fetch failure should be captured gracefully, not bubble up."""
    task = _DummyTask(task_id=3, task_properties=_FileBasedProperties("syn100", "syn200"))

    class _BrokenManager(_StubManager):
        def get_folder(self, folder_id):
            raise RuntimeError("folder unavailable")

    svc = _service_with_stub(_BrokenManager(task=task))
    result = svc.get_task_resources(3)

    assert "error" in result["resources"]["upload_folder"]
    assert result["resources"]["upload_folder"]["id"] == "syn100"
    # file_view should still succeed
    assert result["resources"]["file_view"]["id"] == "syn200"


def test_service_get_task_resources_view_fetch_error():
    """An entity view fetch failure should be captured gracefully."""
    task = _DummyTask(task_id=4, task_properties=_FileBasedProperties("syn100", "syn200"))

    class _BrokenManager(_StubManager):
        def get_entity_view(self, view_id):
            raise RuntimeError("view unavailable")

    svc = _service_with_stub(_BrokenManager(task=task))
    result = svc.get_task_resources(4)

    assert result["resources"]["upload_folder"]["id"] == "syn100"
    assert "error" in result["resources"]["file_view"]
    assert result["resources"]["file_view"]["id"] == "syn200"


def test_service_get_task_resources_record_set_fetch_error():
    """A record set fetch failure should be captured gracefully."""
    task = _DummyTask(task_id=5, task_properties=_RecordBasedProperties("syn300"))

    class _BrokenManager(_StubManager):
        def get_record_set(self, record_set_id):
            raise RuntimeError("record set unavailable")

    svc = _service_with_stub(_BrokenManager(task=task))
    result = svc.get_task_resources(5)

    assert result["resources"]["type"] == "record-based"
    assert "error" in result["resources"]["record_set"]
    assert result["resources"]["record_set"]["id"] == "syn300"


def test_service_get_task_resources_no_properties():
    """Tasks with no task_properties should return empty resources."""
    task = _DummyTask(task_id=6, task_properties=None)
    svc = _service_with_stub(_StubManager(task=task))
    result = svc.get_task_resources(6)

    assert result["resources"] == {}


# ---------------------------------------------------------------------------
# MCP tool controller layer (integration with service via monkeypatch)
# ---------------------------------------------------------------------------

def test_tool_list_curation_tasks_delegates_to_service(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: _DummySynapseClient())
    monkeypatch.setattr(
        tools.CurationTaskService, "list_tasks",
        lambda self, project_id: [{"task_id": 1}],
    )
    result = synapse_mcp.list_curation_tasks.fn("syn999", ctx)
    assert result == [{"task_id": 1}]


def test_tool_list_curation_tasks_invalid_id():
    ctx = DummyContext()
    result = synapse_mcp.list_curation_tasks.fn("not-a-syn-id", ctx)
    assert len(result) == 1
    assert "Invalid Synapse ID" in result[0]["error"]


def test_tool_list_curation_tasks_auth_error(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: (_ for _ in ()).throw(ConnectionAuthError("no auth")))
    result = synapse_mcp.list_curation_tasks.fn("syn999", ctx)
    assert "Authentication required" in result[0]["error"]


def test_tool_list_curation_tasks_service_exception(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: _DummySynapseClient())
    monkeypatch.setattr(
        tools.CurationTaskService, "list_tasks",
        lambda self, project_id: (_ for _ in ()).throw(RuntimeError("service down")),
    )
    result = synapse_mcp.list_curation_tasks.fn("syn999", ctx)
    assert result[0]["error_type"] == "RuntimeError"


def test_tool_get_curation_task_delegates_to_service(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: _DummySynapseClient())
    monkeypatch.setattr(
        tools.CurationTaskService, "get_task",
        lambda self, task_id: {"task_id": task_id},
    )
    result = synapse_mcp.get_curation_task.fn(42, ctx)
    assert result == {"task_id": 42}


def test_tool_get_curation_task_auth_error(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: (_ for _ in ()).throw(ConnectionAuthError("no auth")))
    result = synapse_mcp.get_curation_task.fn(1, ctx)
    assert "Authentication required" in result["error"]
    assert result["task_id"] == 1


def test_tool_get_curation_task_service_exception(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: _DummySynapseClient())
    monkeypatch.setattr(
        tools.CurationTaskService, "get_task",
        lambda self, task_id: (_ for _ in ()).throw(ValueError("not found")),
    )
    result = synapse_mcp.get_curation_task.fn(99, ctx)
    assert result["error_type"] == "ValueError"
    assert result["task_id"] == 99


def test_tool_get_curation_task_resources_delegates_to_service(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: _DummySynapseClient())
    monkeypatch.setattr(
        tools.CurationTaskService, "get_task_resources",
        lambda self, task_id: {"task_id": task_id, "resources": {}},
    )
    result = synapse_mcp.get_curation_task_resources.fn(3, ctx)
    assert result == {"task_id": 3, "resources": {}}


def test_tool_get_curation_task_resources_auth_error(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: (_ for _ in ()).throw(ConnectionAuthError("no auth")))
    result = synapse_mcp.get_curation_task_resources.fn(1, ctx)
    assert "Authentication required" in result["error"]
    assert result["task_id"] == 1


def test_tool_get_curation_task_resources_service_exception(monkeypatch):
    ctx = DummyContext()
    monkeypatch.setattr(tools, "get_synapse_client", lambda _: _DummySynapseClient())
    monkeypatch.setattr(
        tools.CurationTaskService, "get_task_resources",
        lambda self, task_id: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    result = synapse_mcp.get_curation_task_resources.fn(5, ctx)
    assert result["error_type"] == "RuntimeError"
    assert result["task_id"] == 5
