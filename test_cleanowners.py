"""Test the functions in the cleanowners module."""

import unittest
import uuid
from io import StringIO
from unittest.mock import MagicMock, patch

import github3
from cleanowners import (
    commit_changes,
    get_codeowners_file,
    get_org,
    get_repos_iterator,
    get_usernames_from_codeowners,
    print_stats,
)


class TestCommitChanges(unittest.TestCase):
    """Test the commit_changes function in cleanowners.py"""

    @patch("uuid.uuid4")
    def test_commit_changes(self, mock_uuid):
        """Test the commit_changes function."""
        mock_uuid.return_value = uuid.UUID(
            "12345678123456781234567812345678"
        )  # Mock UUID generation
        mock_repo = MagicMock()  # Mock repo object
        mock_repo.default_branch = "main"
        mock_repo.ref.return_value.object.sha = "abc123"  # Mock SHA for latest commit
        mock_repo.create_ref.return_value = True
        mock_repo.file_contents.return_value = MagicMock()
        mock_repo.file_contents.update.return_value = True
        mock_repo.create_pull.return_value = "MockPullRequest"

        title = "Test Title"
        body = "Test Body"
        dependabot_file = "testing!"
        branch_name = "codeowners-12345678-1234-5678-1234-567812345678"
        commit_message = "Test commit message"
        result = commit_changes(
            title,
            body,
            mock_repo,
            dependabot_file,
            commit_message,
            "CODEOWNERS",
        )

        # Assert that the methods were called with the correct arguments
        mock_repo.create_ref.assert_called_once_with(
            f"refs/heads/{branch_name}", "abc123"
        )
        mock_repo.file_contents.assert_called_once_with("CODEOWNERS")
        mock_repo.create_pull.assert_called_once_with(
            title=title,
            body=body,
            head=branch_name,
            base="main",
        )

        # Assert that the function returned the expected result
        self.assertEqual(result, "MockPullRequest")


class TestGetUsernamesFromCodeowners(unittest.TestCase):
    """Test the get_usernames_from_codeowners function in cleanowners.py"""

    def test_get_usernames_from_codeowners_ignore_teams(self):
        """Test usernames are correctly parsed ignoring teams"""
        codeowners_file_contents = MagicMock()
        codeowners_file_contents.decoded = b"""
        # Comment
        *.js    @user1
        *.ts    @user2
        /src/   @org/team
        *.py    @user3 @user4
        """

        expected_usernames = ["user1", "user2", "user3", "user4"]
        result = get_usernames_from_codeowners(codeowners_file_contents)
        self.assertEqual(result, expected_usernames)

    def test_get_usernames_from_codeowners_with_teams(self):
        """Test usernames are correctly parsed including teams"""
        codeowners_file_contents = MagicMock()
        codeowners_file_contents.decoded = b"""
        # Comment
        *.js    @user1
        *.ts    @user2
        /src/   @org/team
        *.py    @user3 @user4
        """

        expected_usernames = ["user1", "user2", "org/team", "user3", "user4"]
        result = get_usernames_from_codeowners(codeowners_file_contents, ignore_teams=False)
        self.assertEqual(result, expected_usernames)

    def test_get_usernames_from_codeowners_decode_fallback(self):
        """Test fallback when .decoded attribute is missing"""
        codeowners_file_contents = MagicMock()
        # Simulate .decode() call on the object directly
        codeowners_file_contents.decode.return_value = """
        *.js    @fallbackuser
        """.strip()

        result = get_usernames_from_codeowners(codeowners_file_contents)
        self.assertEqual(result, ["fallbackuser"])

    def test_get_usernames_from_codeowners_invalid_encoding(self):
        """Test when decoding fails and issue is opened"""
        codeowners_file_contents = MagicMock()
        codeowners_file_contents.decode.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "reason")
        repo = MagicMock()
        repo.full_name = "org/repo"

        issue_opened = {}

        def fake_issue_opener(repo_obj, title, body):
            issue_opened["title"] = title
            issue_opened["body"] = body

        result = get_usernames_from_codeowners(codeowners_file_contents, repo=repo, open_issue_func=fake_issue_opener)
        self.assertEqual(result, [])
        self.assertIn("⚠️ Unable to parse CODEOWNERS file", issue_opened["title"])


class TestGetOrganization(unittest.TestCase):
    """Test the get_org function in cleanowners.py"""

    @patch("github3.login")
    def test_get_organization_succeeds(self, mock_github):
        """Test the organization is valid."""
        organization = "my_organization"
        github_connection = mock_github.return_value

        mock_organization = MagicMock()
        github_connection.organization.return_value = mock_organization

        result = get_org(github_connection, organization)

        github_connection.organization.assert_called_once_with(organization)
        self.assertEqual(result, mock_organization)

    @patch("github3.login")
    def test_get_organization_fails(self, mock_github):
        """Test the organization is not valid."""
        organization = "my_organization"
        github_connection = mock_github.return_value

        github_connection.organization.side_effect = github3.exceptions.NotFoundError(
            resp=MagicMock(status_code=404)
        )
        result = get_org(github_connection, organization)

        github_connection.organization.assert_called_once_with(organization)
        self.assertIsNone(result)


class TestGetReposIterator(unittest.TestCase):
    """Test the get_repos_iterator function in evergreen.py"""

    @patch("github3.login")
    def test_get_repos_iterator_with_organization(self, mock_github):
        """Test the get_repos_iterator function with an organization"""
        organization = "my_organization"
        repository_list = []
        github_connection = mock_github.return_value

        mock_organization = MagicMock()
        mock_repositories = MagicMock()
        mock_organization.repositories.return_value = mock_repositories
        github_connection.organization.return_value = mock_organization

        result = get_repos_iterator(organization, repository_list, github_connection)

        # Assert that the organization method was called with the correct argument
        github_connection.organization.assert_called_once_with(organization)

        # Assert that the repositories method was called on the organization object
        mock_organization.repositories.assert_called_once()

        # Assert that the function returned the expected result
        self.assertEqual(result, mock_repositories)

    @patch("github3.login")
    def test_get_repos_iterator_with_repository_list(self, mock_github):
        """Test the get_repos_iterator function with a repository list"""
        organization = None
        repository_list = ["org/repo1", "org2/repo2"]
        github_connection = mock_github.return_value

        mock_repository = MagicMock()
        mock_repository_list = [mock_repository, mock_repository]
        github_connection.repository.side_effect = mock_repository_list

        result = get_repos_iterator(organization, repository_list, github_connection)

        # Assert that the repository method was called with the correct arguments for each repository in the list
        expected_calls = [
            unittest.mock.call("org", "repo1"),
            unittest.mock.call("org2", "repo2"),
        ]
        github_connection.repository.assert_has_calls(expected_calls)

        # Assert that the function returned the expected result
        self.assertEqual(result, mock_repository_list)


class TestPrintStats(unittest.TestCase):
    """Test the print_stats function in cleanowners.py"""

    @patch("sys.stdout", new_callable=StringIO)
    def test_print_stats_all_counts(self, mock_stdout):
        """Test the print_stats function with all counts."""
        print_stats(5, 10, 2, 3, 4)
        expected_output = (
            "Found 4 users to remove\n"
            "Created 5 pull requests successfully\n"
            "Skipped 2 repositories without a CODEOWNERS file\n"
            "Processed 3 repositories with a CODEOWNERS file\n"
            "50.0% of eligible repositories had pull requests created\n"
            "60.0% of repositories had CODEOWNERS files\n"
        )
        self.assertEqual(mock_stdout.getvalue(), expected_output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_print_stats_no_pull_requests_needed(self, mock_stdout):
        """Test the print_stats function with no pull requests needed."""
        print_stats(0, 0, 2, 3, 4)
        expected_output = (
            "Found 4 users to remove\n"
            "Created 0 pull requests successfully\n"
            "Skipped 2 repositories without a CODEOWNERS file\n"
            "Processed 3 repositories with a CODEOWNERS file\n"
            "No pull requests were needed\n"
            "60.0% of repositories had CODEOWNERS files\n"
        )
        self.assertEqual(mock_stdout.getvalue(), expected_output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_print_stats_no_repositories_processed(self, mock_stdout):
        """Test the print_stats function with no repositories processed."""
        print_stats(0, 0, 0, 0, 0)
        expected_output = (
            "Found 0 users to remove\n"
            "Created 0 pull requests successfully\n"
            "Skipped 0 repositories without a CODEOWNERS file\n"
            "Processed 0 repositories with a CODEOWNERS file\n"
            "No pull requests were needed\n"
            "No repositories were processed\n"
        )
        self.assertEqual(mock_stdout.getvalue(), expected_output)


class TestGetCodeownersFile(unittest.TestCase):
    """Test the get_codeowners_file function in cleanowners.py"""

    def setUp(self):
        self.repo = MagicMock()

    def test_codeowners_in_github_folder(self):
        """Test that a CODEOWNERS file in the .github folder is considered valid."""
        self.repo.file_contents.side_effect = lambda path: (
            MagicMock(size=1) if path == ".github/CODEOWNERS" else None
        )
        contents, path = get_codeowners_file(self.repo)
        self.assertIsNotNone(contents)
        self.assertEqual(path, ".github/CODEOWNERS")

    def test_codeowners_in_root(self):
        """Test that a CODEOWNERS file in the root is considered valid."""
        self.repo.file_contents.side_effect = lambda path: (
            MagicMock(size=1) if path == "CODEOWNERS" else None
        )
        contents, path = get_codeowners_file(self.repo)
        self.assertIsNotNone(contents)
        self.assertEqual(path, "CODEOWNERS")

    def test_codeowners_in_docs_folder(self):
        """Test that a CODEOWNERS file in a docs folder is considered valid."""
        self.repo.file_contents.side_effect = lambda path: (
            MagicMock(size=1) if path == "docs/CODEOWNERS" else None
        )
        contents, path = get_codeowners_file(self.repo)
        self.assertIsNotNone(contents)
        self.assertEqual(path, "docs/CODEOWNERS")

    def test_codeowners_not_found(self):
        """Test that a missing CODEOWNERS file is not considered valid because it doesn't exist."""
        self.repo.file_contents.side_effect = lambda path: None
        contents, path = get_codeowners_file(self.repo)
        self.assertIsNone(contents)
        self.assertIsNone(path)

    def test_codeowners_empty_file(self):
        """Test that an empty CODEOWNERS file is not considered valid because it is empty."""
        self.repo.file_contents.side_effect = lambda path: MagicMock(size=0)
        contents, path = get_codeowners_file(self.repo)
        self.assertIsNone(contents)
        self.assertIsNone(path)
