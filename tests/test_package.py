import unittest


class TestPackageInstallation(unittest.TestCase):
    """Test the synapse-mcp package installation."""

    def test_package_imports(self):
        """Test that all package modules can be imported."""
        import synapse_mcp
        self.assertIsNotNone(synapse_mcp)

        from synapse_mcp import auth
        self.assertTrue(auth is None or hasattr(auth, "authorize"))
        from synapse_mcp import utils
        self.assertIsNotNone(utils)

        from synapse_mcp import search_synapse
        self.assertTrue(callable(search_synapse))

        from synapse_mcp.services import EntityService
        self.assertIsNotNone(EntityService)

        from synapse_mcp.services import ActivityService
        self.assertIsNotNone(ActivityService)

        from synapse_mcp.services import SearchService
        self.assertIsNotNone(SearchService)

        from synapse_mcp.services import CurationTaskService
        self.assertIsNotNone(CurationTaskService)

        from synapse_mcp.services import WikiService
        self.assertIsNotNone(WikiService)

        from synapse_mcp.services import TeamService
        self.assertIsNotNone(TeamService)

        from synapse_mcp.services import UserService
        self.assertIsNotNone(UserService)

        from synapse_mcp.services import EvaluationService
        self.assertIsNotNone(EvaluationService)

        from synapse_mcp.services import SubmissionService
        self.assertIsNotNone(SubmissionService)

        from synapse_mcp.services import SchemaOrganizationService
        self.assertIsNotNone(SchemaOrganizationService)

    def test_entry_point(self):
        """Test that the entry point is available."""
        from synapse_mcp.__main__ import main
        self.assertTrue(callable(main))


if __name__ == "__main__":
    unittest.main()
