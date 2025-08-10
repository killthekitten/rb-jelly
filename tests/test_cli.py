import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from cli import cli, load_config, validate_required_config


class TestConfigFunctions:
    """Test configuration loading and validation functions."""

    def test_load_config_with_env_vars(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "REKORDBOX_DB_PATH": "/path/to/db.db",
                "CRATES_ROOT": "/path/to/crates",
                "OUTPUT_DIR": "./test_output",
                "JELLYFIN_ROOT": "/data/music",
                "LOG_LEVEL": "DEBUG",
            },
            clear=True,
        ):
            config = load_config()

            assert config["REKORDBOX_DB_PATH"] == "/path/to/db.db"
            assert config["CRATES_ROOT"] == "/path/to/crates"
            assert config["OUTPUT_DIR"] == "./test_output"
            assert config["JELLYFIN_ROOT"] == "/data/music"
            assert config["LOG_LEVEL"] == "DEBUG"

    def test_load_config_defaults(self):
        """Test loading configuration uses defaults when not set."""
        # Clear environment variables that might interfere

        # Mock load_dotenv to prevent loading from .env files in development
        with patch("cli.load_dotenv"), patch.dict(os.environ, {}, clear=True):
            config = load_config()

            # Check defaults
            assert config["OUTPUT_DIR"] == "./output"
            assert config["JELLYFIN_ROOT"] == "/data/music"
            assert config["LOG_LEVEL"] == "INFO"

            # Check None values
            assert config["REKORDBOX_DB_PATH"] is None
            assert config["CRATES_ROOT"] is None

    def test_validate_required_config_valid(self):
        """Test validation passes with valid configuration."""
        config = {
            "CRATES_ROOT": "/valid/path",
            "REKORDBOX_DB_PATH": "/valid/db.db",
            "REKORDBOX_XML_PATH": None,
        }

        assert validate_required_config(config) is True

    def test_validate_required_config_missing_crates_root(self):
        """Test validation fails without CRATES_ROOT."""
        config = {
            "CRATES_ROOT": None,
            "REKORDBOX_DB_PATH": "/valid/db.db",
            "REKORDBOX_XML_PATH": None,
        }

        assert validate_required_config(config) is False

    def test_validate_required_config_missing_rekordbox_source(self):
        """Test validation fails without Rekordbox source."""
        config = {
            "CRATES_ROOT": "/valid/path",
            "REKORDBOX_DB_PATH": None,
            "REKORDBOX_XML_PATH": None,
        }

        assert validate_required_config(config) is False


class TestCLICommands:
    """Test CLI commands using Click's test runner."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    def teardown_method(self):
        """Clean up after each test."""
        # Clean up environment variables that might interfere with other tests
        env_vars_to_clean = [
            "REKORDBOX_DB_PATH",
            "CRATES_ROOT",
            "OUTPUT_DIR",
            "JELLYFIN_ROOT",
            "LOG_LEVEL",
        ]
        for var in env_vars_to_clean:
            if var in os.environ:
                del os.environ[var]

    def test_cli_help(self):
        """Test main CLI help command."""
        result = self.runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Rekordbox to Jellyfin migration tool" in result.output
        assert "create-playlists" in result.output

    @patch("cli.RekordboxExtractor")
    @patch("cli.PathConverter")
    @patch("cli.PlaylistGenerator")
    def test_create_playlists_dry_run(
        self, mock_playlist_gen, mock_path_conv, mock_extractor
    ):
        """Test create-playlists command with dry-run."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Setup mocks
                mock_extractor_instance = Mock()
                mock_extractor_instance.connect.return_value = True
                mock_extractor_instance.extract_playlists.return_value = (
                    self._create_mock_playlists()
                )
                mock_extractor.return_value = mock_extractor_instance

                mock_path_conv_instance = Mock()
                mock_path_conv_instance.validate_and_convert_path.return_value = (
                    "/data/music/test.mp3"
                )
                mock_path_conv_instance.get_invalid_paths.return_value = set()
                mock_path_conv.return_value = mock_path_conv_instance

                # Create valid .env
                self._create_valid_env()

                result = self.runner.invoke(cli, ["create-playlists", "--dry-run"])

                assert result.exit_code == 0
                assert "🔍 DRY RUN MODE" in result.output
                assert "📁 Playlists that would be created:" in result.output
                assert "🎉 Playlist creation completed!" in result.output
                # Ensure PlaylistGenerator methods weren't called in dry-run
                mock_playlist_gen.assert_not_called()
            finally:
                os.chdir(original_cwd)

    @patch("cli.RekordboxExtractor")
    @patch("cli.PathConverter")
    @patch("cli.PlaylistGenerator")
    def test_create_playlists_normal_mode(
        self, mock_playlist_gen, mock_path_conv, mock_extractor
    ):
        """Test create-playlists command in normal mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Setup mocks
                mock_extractor_instance = Mock()
                mock_extractor_instance.connect.return_value = True
                mock_extractor_instance.extract_playlists.return_value = (
                    self._create_mock_playlists()
                )
                mock_extractor.return_value = mock_extractor_instance

                mock_path_conv_instance = Mock()
                mock_path_conv_instance.validate_and_convert_path.return_value = (
                    "/data/music/test.mp3"
                )
                mock_path_conv_instance.get_invalid_paths.return_value = set()
                mock_path_conv.return_value = mock_path_conv_instance

                mock_playlist_gen_instance = Mock()
                mock_playlist_gen_instance.create_playlist_structure.return_value = {
                    "Test": "test.m3u"
                }
                mock_playlist_gen.return_value = mock_playlist_gen_instance

                # Create valid .env
                self._create_valid_env()

                result = self.runner.invoke(cli, ["create-playlists"])

                assert result.exit_code == 0
                assert "📝 Creating playlist files..." in result.output
                assert "✅ Created 1 playlist files" in result.output
                assert "🎉 Playlist creation completed!" in result.output

                # Verify methods were called
                mock_playlist_gen_instance.clean_output_directory.assert_called_once()
                mock_playlist_gen_instance.create_playlist_structure.assert_called_once()
            finally:
                os.chdir(original_cwd)

    def test_create_playlists_missing_config(self):
        """Test create-playlists fails with missing configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Mock load_dotenv and clear environment to simulate missing config
                with patch("cli.load_dotenv"), patch.dict(os.environ, {}, clear=True):
                    result = self.runner.invoke(cli, ["create-playlists"])

                    assert result.exit_code == 1
                    assert (
                        "CRATES_ROOT environment variable is required" in result.output
                    )
            finally:
                os.chdir(original_cwd)

    @patch("cli.RekordboxExtractor")
    @patch("cli.PathConverter")
    @patch("cli.PlaylistGenerator")
    def test_create_playlists_flat_mode(
        self, mock_playlist_gen, mock_path_conv, mock_extractor
    ):
        """Test create-playlists command with --flat option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Setup mocks
                mock_extractor_instance = Mock()
                mock_extractor_instance.connect.return_value = True
                mock_extractor_instance.extract_playlists.return_value = (
                    self._create_mock_playlists()
                )
                mock_extractor.return_value = mock_extractor_instance

                mock_path_conv_instance = Mock()
                mock_path_conv_instance.validate_and_convert_path.return_value = (
                    "/data/music/test.mp3"
                )
                mock_path_conv_instance.get_invalid_paths.return_value = set()
                mock_path_conv.return_value = mock_path_conv_instance

                mock_playlist_gen_instance = Mock()
                mock_playlist_gen_instance.create_playlist_structure.return_value = {
                    "Test - Flat": "test-flat.m3u"
                }
                mock_playlist_gen.return_value = mock_playlist_gen_instance

                # Create valid .env
                self._create_valid_env()

                result = self.runner.invoke(cli, ["create-playlists", "--flat"])

                assert result.exit_code == 0
                assert (
                    "📁 FLAT MODE - Playlists will be flattened for Jellyfin compatibility"
                    in result.output
                )
                assert "📝 Creating playlist files..." in result.output
                assert "🎉 Playlist creation completed!" in result.output

                # Verify PlaylistGenerator was called with flat_mode=True
                mock_playlist_gen.assert_called_once_with("./output", flat_mode=True)
                mock_playlist_gen_instance.create_playlist_structure.assert_called_once()
            finally:
                os.chdir(original_cwd)

    def _create_valid_env(self):
        """Helper to create a valid .env file for testing."""
        Path("test_crates").mkdir(exist_ok=True)
        Path("test_db.db").touch()

        env_content = f"""REKORDBOX_DB_PATH={Path('test_db.db').absolute()}
CRATES_ROOT={Path('test_crates').absolute()}
OUTPUT_DIR=./output
JELLYFIN_ROOT=/data/music
LOG_LEVEL=INFO"""

        Path(".env").write_text(env_content)

        # Also set environment variables for tests since dotenv may not load in tests
        env_vars = {
            "REKORDBOX_DB_PATH": str(Path("test_db.db").absolute()),
            "CRATES_ROOT": str(Path("test_crates").absolute()),
            "OUTPUT_DIR": "./output",
            "JELLYFIN_ROOT": "/data/music",
            "LOG_LEVEL": "INFO",
        }

        for key, value in env_vars.items():
            os.environ[key] = value

    def _create_mock_playlists(self):
        """Helper to create mock playlists for testing."""
        from rekordbox_to_jellyfin import Playlist, Track

        track = Track(
            title="Test Track",
            artist="Test Artist",
            file_path=Path("/test/path.mp3"),
            playlist_path="Test Playlist",
        )

        playlist = Playlist(
            name="Test Playlist", path="Test Playlist", tracks=[track], children=[]
        )

        return [playlist]


class TestErrorHandling:
    """Test error handling and edge cases."""

    def setup_method(self):
        """Set up test runner for each test."""
        self.runner = CliRunner()

    @patch("cli.RekordboxExtractor")
    def test_create_playlists_rekordbox_connection_failure(self, mock_extractor):
        """Test create-playlists handles Rekordbox connection failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                mock_extractor_instance = Mock()
                mock_extractor_instance.connect.return_value = False
                mock_extractor.return_value = mock_extractor_instance

                # Create valid .env and set environment
                Path("test_crates").mkdir()
                Path("test_db.db").touch()
                env_content = f"""REKORDBOX_DB_PATH={Path('test_db.db').absolute()}
CRATES_ROOT={Path('test_crates').absolute()}"""
                Path(".env").write_text(env_content)

                # Set environment variables
                os.environ["REKORDBOX_DB_PATH"] = str(Path("test_db.db").absolute())
                os.environ["CRATES_ROOT"] = str(Path("test_crates").absolute())

                result = self.runner.invoke(cli, ["create-playlists"])

                assert result.exit_code == 1
                assert "❌ Failed to connect to Rekordbox" in result.output
            finally:
                # Clean up environment
                for key in ["REKORDBOX_DB_PATH", "CRATES_ROOT"]:
                    if key in os.environ:
                        del os.environ[key]
                os.chdir(original_cwd)

    @patch("cli.RekordboxExtractor")
    @patch("cli.PathConverter")
    def test_create_playlists_no_playlists_found(self, mock_path_conv, mock_extractor):
        """Test create-playlists handles no playlists found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                mock_extractor_instance = Mock()
                mock_extractor_instance.connect.return_value = True
                mock_extractor_instance.extract_playlists.return_value = (
                    []
                )  # No playlists
                mock_extractor.return_value = mock_extractor_instance

                mock_path_conv_instance = Mock()
                mock_path_conv.return_value = mock_path_conv_instance

                # Create valid .env and set environment
                Path("test_crates").mkdir()
                Path("test_db.db").touch()
                env_content = f"""REKORDBOX_DB_PATH={Path('test_db.db').absolute()}
CRATES_ROOT={Path('test_crates').absolute()}"""
                Path(".env").write_text(env_content)

                # Set environment variables
                os.environ["REKORDBOX_DB_PATH"] = str(Path("test_db.db").absolute())
                os.environ["CRATES_ROOT"] = str(Path("test_crates").absolute())

                result = self.runner.invoke(cli, ["create-playlists"])

                assert result.exit_code == 1
                assert "❌ No playlists found" in result.output
            finally:
                # Clean up environment
                for key in ["REKORDBOX_DB_PATH", "CRATES_ROOT"]:
                    if key in os.environ:
                        del os.environ[key]
                os.chdir(original_cwd)
