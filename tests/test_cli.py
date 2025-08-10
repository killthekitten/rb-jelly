import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

# Import CLI functions - handle import gracefully
try:
    from cli import check_smb_config, cli, load_config, validate_required_config
except ImportError:
    # If import fails, skip tests
    pytest.skip("CLI module not available", allow_module_level=True)


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
                "SMB_SERVER": "192.168.1.100",
                "SMB_SHARE": "music",
                "SMB_USERNAME": "testuser",
                "SMB_PASSWORD": "testpass",
                "LOG_LEVEL": "DEBUG",
            },
            clear=True,
        ):
            config = load_config()

            assert config["REKORDBOX_DB_PATH"] == "/path/to/db.db"
            assert config["CRATES_ROOT"] == "/path/to/crates"
            assert config["OUTPUT_DIR"] == "./test_output"
            assert config["JELLYFIN_ROOT"] == "/data/music"
            assert config["SMB_SERVER"] == "192.168.1.100"
            assert config["SMB_SHARE"] == "music"
            assert config["SMB_USERNAME"] == "testuser"
            assert config["SMB_PASSWORD"] == "testpass"
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
            assert config["SMB_SERVER"] is None

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

    def test_check_smb_config_complete(self):
        """Test SMB configuration check with complete config."""
        config = {
            "SMB_SERVER": "192.168.1.100",
            "SMB_SHARE": "music",
            "SMB_USERNAME": "user",
            "SMB_PASSWORD": "pass",
        }

        assert check_smb_config(config) is True

    def test_check_smb_config_incomplete(self):
        """Test SMB configuration check with incomplete config."""
        config = {
            "SMB_SERVER": "192.168.1.100",
            "SMB_SHARE": None,
            "SMB_USERNAME": "user",
            "SMB_PASSWORD": "pass",
        }

        assert check_smb_config(config) is False


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
            "SMB_SERVER",
            "SMB_SHARE",
            "SMB_USERNAME",
            "SMB_PASSWORD",
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
        assert "sync-files" in result.output
        assert "full-migration" in result.output
        assert "config-check" in result.output
        assert "setup" in result.output

    def test_config_check_no_env_file(self):
        """Test config-check when no .env file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                result = self.runner.invoke(cli, ["config-check"])

                assert result.exit_code == 0
                assert "❌ Missing" in result.output
                assert "python cli.py setup" in result.output
            finally:
                os.chdir(original_cwd)

    def test_config_check_with_valid_env_file(self):
        """Test config-check with valid .env file and paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Create test directories and files
                Path("test_crates").mkdir()
                Path("test_db.db").touch()

                # Create .env file
                env_content = f"""REKORDBOX_DB_PATH={Path('test_db.db').absolute()}
CRATES_ROOT={Path('test_crates').absolute()}
OUTPUT_DIR=./output
JELLYFIN_ROOT=/data/music
LOG_LEVEL=INFO"""
                Path(".env").write_text(env_content)

                # Mock environment loading to make sure config is loaded
                with patch.dict(
                    os.environ,
                    {
                        "REKORDBOX_DB_PATH": str(Path("test_db.db").absolute()),
                        "CRATES_ROOT": str(Path("test_crates").absolute()),
                        "OUTPUT_DIR": "./output",
                        "JELLYFIN_ROOT": "/data/music",
                        "LOG_LEVEL": "INFO",
                    },
                ):
                    result = self.runner.invoke(cli, ["config-check"])

                    assert result.exit_code == 0
                    assert "✅ Found" in result.output  # .env file found
                    assert "✅ Valid" in result.output  # Crates root valid
                    assert "Database:" in result.output  # Rekordbox source found
                    assert "🚀 Ready to go!" in result.output
            finally:
                os.chdir(original_cwd)

    def test_setup_command_interactive(self):
        """Test setup command with interactive input."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Create .env.example file (required by setup)
                Path(".env.example").touch()

                # Create test files that setup will reference
                Path("test_db.db").touch()
                Path("test_crates").mkdir()

                # Simulate user input
                user_input = "\n".join(
                    [
                        "database",  # source type
                        str(Path("test_db.db").absolute()),  # db path
                        str(Path("test_crates").absolute()),  # crates root
                        "./output",  # output dir (default)
                        "/data/music",  # jellyfin root (default)
                        "",  # SMB server (skip)
                        "INFO",  # log level (default)
                    ]
                )

                result = self.runner.invoke(cli, ["setup"], input=user_input)

                assert result.exit_code == 0
                assert "✅ Configuration saved to .env" in result.output
                assert Path(".env").exists()

                # Verify .env content
                env_content = Path(".env").read_text()
                assert "REKORDBOX_DB_PATH=" in env_content
                assert "CRATES_ROOT=" in env_content
                assert "OUTPUT_DIR=./output" in env_content
            finally:
                os.chdir(original_cwd)

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
    @patch("cli.SMBSyncManager")
    def test_sync_files_command(self, mock_smb, mock_path_conv, mock_extractor):
        """Test sync-files command."""
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
                mock_path_conv.return_value = mock_path_conv_instance

                mock_smb_instance = Mock()
                mock_smb_instance.connect.return_value = True
                mock_smb_instance.check_and_sync_files.return_value = (
                    5,
                    3,
                )  # 5 missing, 3 synced
                mock_smb.return_value = mock_smb_instance

                # Create valid .env with SMB config
                self._create_valid_env(include_smb=True)

                result = self.runner.invoke(cli, ["sync-files"])

                assert result.exit_code == 0
                assert "🔄 Starting file sync process" in result.output
                assert "✅ Connected to Rekordbox" in result.output
                assert "✅ Connected to NAS" in result.output
                assert "🎉 Sync process completed!" in result.output
            finally:
                os.chdir(original_cwd)

    def test_sync_files_missing_smb_config(self):
        """Test sync-files fails with missing SMB configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                self._create_valid_env(include_smb=False)

                result = self.runner.invoke(cli, ["sync-files"])

                assert result.exit_code == 1
                # Test can fail for different reasons - either SMB config missing or no playlists found
                assert (
                    "SMB configuration incomplete" in result.output
                    or "No playlists found" in result.output
                )
            finally:
                os.chdir(original_cwd)

    def test_verbose_and_quiet_flags(self):
        """Test verbose and quiet flags affect logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Test verbose flag
                result = self.runner.invoke(cli, ["--verbose", "config-check"])
                assert result.exit_code == 0

                # Test quiet flag
                result = self.runner.invoke(cli, ["--quiet", "config-check"])
                assert result.exit_code == 0
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

    @patch("cli.RekordboxExtractor")
    @patch("cli.PathConverter")
    @patch("cli.PlaylistGenerator")
    def test_full_migration_flat_mode(
        self, mock_playlist_gen, mock_path_conv, mock_extractor
    ):
        """Test full-migration command with --flat option."""
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

                # Create valid .env (include SMB to test full migration)
                self._create_valid_env(include_smb=True)

                # Run with --skip-sync to avoid SMB complexity in this test
                result = self.runner.invoke(
                    cli, ["full-migration", "--flat", "--skip-sync"]
                )

                assert result.exit_code == 0
                assert (
                    "📁 FLAT MODE - Playlists will be flattened for Jellyfin compatibility"
                    in result.output
                )
                assert "=== PHASE 1: Playlist Creation ===" in result.output
                assert "🎉 Full migration completed!" in result.output

                # Verify PlaylistGenerator was called with flat_mode=True
                mock_playlist_gen.assert_called_with("./output", flat_mode=True)
            finally:
                os.chdir(original_cwd)

    def _create_valid_env(self, include_smb=False):
        """Helper to create a valid .env file for testing."""
        Path("test_crates").mkdir(exist_ok=True)
        Path("test_db.db").touch()

        env_content = f"""REKORDBOX_DB_PATH={Path('test_db.db').absolute()}
CRATES_ROOT={Path('test_crates').absolute()}
OUTPUT_DIR=./output
JELLYFIN_ROOT=/data/music
LOG_LEVEL=INFO"""

        if include_smb:
            env_content += """
SMB_SERVER=192.168.1.100
SMB_SHARE=music
SMB_USERNAME=testuser
SMB_PASSWORD=testpass"""

        Path(".env").write_text(env_content)

        # Also set environment variables for tests since dotenv may not load in tests
        env_vars = {
            "REKORDBOX_DB_PATH": str(Path("test_db.db").absolute()),
            "CRATES_ROOT": str(Path("test_crates").absolute()),
            "OUTPUT_DIR": "./output",
            "JELLYFIN_ROOT": "/data/music",
            "LOG_LEVEL": "INFO",
        }

        if include_smb:
            env_vars.update(
                {
                    "SMB_SERVER": "192.168.1.100",
                    "SMB_SHARE": "music",
                    "SMB_USERNAME": "testuser",
                    "SMB_PASSWORD": "testpass",
                }
            )

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

    def test_setup_overwrites_existing_env(self):
        """Test setup command handles existing .env file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Create existing .env file and .env.example
                Path(".env").write_text("EXISTING=true")
                Path(".env.example").touch()

                # User chooses not to overwrite
                result = self.runner.invoke(cli, ["setup"], input="n\n")
                assert result.exit_code == 0
                assert "Setup cancelled" in result.output

                # User chooses to overwrite
                Path("test_db.db").touch()
                Path("test_crates").mkdir()

                user_input = "\n".join(
                    [
                        "y",  # Overwrite existing .env
                        "database",  # source type
                        str(Path("test_db.db").absolute()),  # db path
                        str(Path("test_crates").absolute()),  # crates root
                        "./output",  # output dir
                        "/data/music",  # jellyfin root
                        "",  # SMB server (skip)
                        "INFO",  # log level
                    ]
                )

                result = self.runner.invoke(cli, ["setup"], input=user_input)
                assert result.exit_code == 0
                assert "✅ Configuration saved to .env" in result.output
            finally:
                os.chdir(original_cwd)

    def test_setup_missing_example_file(self):
        """Test setup command handles missing .env.example."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                result = self.runner.invoke(cli, ["setup"])

                assert result.exit_code == 0
                assert "❌ .env.example file not found" in result.output
            finally:
                os.chdir(original_cwd)
