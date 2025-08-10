#!/usr/bin/env python3
"""
Rekordbox to Jellyfin Library Migration Script

This script extracts playlist structure from Rekordbox, mirrors the folder/playlist
hierarchy for Jellyfin, converts paths from Crates directory to /data/music,
and syncs missing files to NAS via SMB.
"""

import logging
import os
import shutil
from pathlib import Path, PurePath
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

try:
    from dotenv import load_dotenv
except ImportError:
    print("Error: python-dotenv not installed. Run: pip install python-dotenv")
    exit(1)

try:
    from pyrekordbox import Rekordbox6Database, RekordboxXml
except ImportError:
    print("Error: pyrekordbox not installed. Run: pip install pyrekordbox")
    exit(1)

try:
    import smbclient
    from smbprotocol.connection import Connection
except ImportError:
    print("Error: smbprotocol not installed. Run: pip install smbprotocol")
    exit(1)


@dataclass
class Track:
    """Represents a music track with its metadata and path."""

    title: str
    artist: str
    file_path: Path
    playlist_path: str


@dataclass
class Playlist:
    """Represents a playlist with its tracks and nested structure."""

    name: str
    path: str
    tracks: List[Track]
    children: List["Playlist"]
    parent: Optional["Playlist"] = None


class RekordboxExtractor:
    """Handles extraction of playlists and tracks from Rekordbox database."""

    def __init__(self, db_path: Optional[str] = None, xml_path: Optional[str] = None):
        self.db_path = db_path
        self.xml_path = xml_path
        self.db = None
        self.xml = None
        self.logger = logging.getLogger(__name__)

    def connect(self) -> bool:
        """Connect to Rekordbox database or XML file."""
        try:
            print("Path:", self.db_path, Path(self.db_path))
            if self.db_path and Path(self.db_path).exists():
                self.db = Rekordbox6Database(self.db_path)
                self.logger.info(f"Connected to Rekordbox database: {self.db_path}")
                return True
            elif self.xml_path and Path(self.xml_path).exists():
                self.xml = RekordboxXml(self.xml_path)
                self.logger.info(f"Connected to Rekordbox XML: {self.xml_path}")
                return True
            else:
                self.logger.error("No valid Rekordbox database or XML file found")
                return False
        except Exception as e:
            self.logger.error(f"Failed to connect to Rekordbox: {e}")
            return False

    def extract_playlists(self) -> List[Playlist]:
        """Extract all playlists with their nested structure."""
        playlists = []

        try:
            if self.db:
                playlists = self._extract_from_database()
            elif self.xml:
                playlists = self._extract_from_xml()

            self.logger.info(f"Extracted {len(playlists)} playlists from Rekordbox")
            return playlists

        except Exception as e:
            self.logger.error(f"Failed to extract playlists: {e}")
            return []

    def _extract_from_database(self) -> List[Playlist]:
        """Extract playlists from Rekordbox 6 database."""
        playlists = []

        try:
            rb_playlists = self.db.get_playlist()

            for rb_playlist in rb_playlists:
                tracks = []

                # Extract tracks from playlist
                for song in rb_playlist.Songs:
                    if hasattr(song, "Content") and song.Content:
                        content = song.Content
                        track = Track(
                            title=content.Title or "Unknown",
                            artist=content.Artist.Name if content.Artist else "Unknown",
                            file_path=(
                                Path(content.FolderPath) / content.Filename
                                if content.FolderPath and content.Filename
                                else Path()
                            ),
                            playlist_path=rb_playlist.Name,
                        )
                        tracks.append(track)

                # Only include playlists with tracks
                if tracks:
                    playlist = Playlist(
                        name=rb_playlist.Name,
                        path=rb_playlist.Name,
                        tracks=tracks,
                        children=[],
                    )
                    playlists.append(playlist)

        except Exception as e:
            self.logger.error(f"Error extracting from database: {e}")

        return playlists

    def _extract_from_xml(self) -> List[Playlist]:
        """Extract playlists from Rekordbox XML export."""
        playlists = []

        try:
            # Get all playlists from XML
            xml_playlists = self.xml.get_playlists()

            for xml_playlist in xml_playlists:
                tracks = []
                track_keys = xml_playlist.get_tracks()

                for track_key in track_keys:
                    track_data = self.xml.get_track(track_key)
                    if track_data and hasattr(track_data, "Location"):
                        track = Track(
                            title=getattr(track_data, "Name", "Unknown"),
                            artist=getattr(track_data, "Artist", "Unknown"),
                            file_path=(
                                Path(track_data.Location).resolve()
                                if track_data.Location
                                else Path()
                            ),
                            playlist_path=xml_playlist.Name,
                        )
                        tracks.append(track)

                if tracks:
                    playlist = Playlist(
                        name=xml_playlist.Name,
                        path=xml_playlist.Name,
                        tracks=tracks,
                        children=[],
                    )
                    playlists.append(playlist)

        except Exception as e:
            self.logger.error(f"Error extracting from XML: {e}")

        return playlists


class PathConverter:
    """Handles path validation and conversion from Crates to /data/music."""

    def __init__(self, crates_root: str, jellyfin_root: str = "/data/music"):
        self.crates_root = Path(crates_root).resolve()
        self.jellyfin_root = jellyfin_root
        self.logger = logging.getLogger(__name__)
        self.invalid_paths = set()

    def validate_and_convert_path(self, file_path: Path) -> Optional[str]:
        """Validate path is within Crates and convert to Jellyfin path."""
        try:
            resolved_path = file_path.resolve()

            # Check if path is within Crates directory
            try:
                relative_path = resolved_path.relative_to(self.crates_root)
            except ValueError:
                # Path is outside Crates directory
                self.invalid_paths.add(str(file_path))
                self.logger.warning(f"Path outside Crates directory: {file_path}")
                return None

            # Convert to Jellyfin path
            jellyfin_path = f"{self.jellyfin_root}/{relative_path.as_posix()}"
            return jellyfin_path

        except Exception as e:
            self.logger.error(f"Error processing path {file_path}: {e}")
            return None

    def get_invalid_paths(self) -> Set[str]:
        """Return set of invalid paths that were rejected."""
        return self.invalid_paths.copy()


class PlaylistGenerator:
    """Generates M3U playlists and folder structure for Jellyfin."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.logger = logging.getLogger(__name__)

    def clean_output_directory(self):
        """Clean the output directory before creating new playlists."""
        if self.output_dir.exists():
            self.logger.info(f"Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Created clean output directory: {self.output_dir}")

    def create_playlist_structure(
        self, playlists: List[Playlist], path_converter: PathConverter
    ) -> Dict[str, str]:
        """Create folder structure and M3U files for playlists."""
        created_playlists = {}

        for playlist in playlists:
            playlist_dir = self.output_dir / playlist.name
            playlist_dir.mkdir(parents=True, exist_ok=True)

            # Generate M3U playlist file
            m3u_path = playlist_dir / f"{playlist.name}.m3u"
            valid_tracks = []

            for track in playlist.tracks:
                jellyfin_path = path_converter.validate_and_convert_path(
                    track.file_path
                )
                if jellyfin_path:
                    valid_tracks.append((track, jellyfin_path))

            if valid_tracks:
                self._write_m3u_file(m3u_path, valid_tracks)
                created_playlists[playlist.name] = str(m3u_path)
                self.logger.info(
                    f"Created playlist: {m3u_path} with {len(valid_tracks)} tracks"
                )
            else:
                self.logger.warning(f"Playlist {playlist.name} has no valid tracks")

        return created_playlists

    def _write_m3u_file(self, m3u_path: Path, tracks: List[Tuple[Track, str]]):
        """Write M3U playlist file."""
        try:
            with open(m3u_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for track, jellyfin_path in tracks:
                    f.write(f"#EXTINF:-1,{track.artist} - {track.title}\n")
                    f.write(f"{jellyfin_path}\n")
        except Exception as e:
            self.logger.error(f"Error writing M3U file {m3u_path}: {e}")


class SMBSyncManager:
    """Manages SMB connection and file synchronization with NAS."""

    def __init__(self, smb_server: str, smb_share: str, username: str, password: str):
        self.smb_server = smb_server
        self.smb_share = smb_share
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)

    def connect(self) -> bool:
        """Establish SMB connection to NAS."""
        try:
            smbclient.ClientConfig(username=self.username, password=self.password)
            self.logger.info(f"SMB connection configured for {self.smb_server}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to configure SMB connection: {e}")
            return False

    def check_and_sync_files(
        self, tracks: List[Track], path_converter: PathConverter
    ) -> Tuple[int, int]:
        """Check file existence on NAS and sync missing files."""
        missing_files = []
        synced_files = 0

        for track in tracks:
            jellyfin_path = path_converter.validate_and_convert_path(track.file_path)
            if not jellyfin_path:
                continue

            # Convert jellyfin path to SMB path
            smb_path = self._jellyfin_to_smb_path(jellyfin_path)

            if not self._file_exists_on_nas(smb_path):
                missing_files.append((track, smb_path))

        self.logger.info(f"Found {len(missing_files)} missing files on NAS")

        # Sync missing files
        for track, smb_path in missing_files:
            if self._sync_file_to_nas(track.file_path, smb_path):
                synced_files += 1

        return len(missing_files), synced_files

    def _jellyfin_to_smb_path(self, jellyfin_path: str) -> str:
        """Convert Jellyfin path to SMB path."""
        # Remove /data/music prefix and prepend SMB share
        relative_path = jellyfin_path.replace("/data/music/", "")
        return f"//{self.smb_server}/{self.smb_share}/{relative_path}"

    def _file_exists_on_nas(self, smb_path: str) -> bool:
        """Check if file exists on NAS via SMB."""
        try:
            with smbclient.open_file(smb_path, mode="rb") as f:
                return True
        except Exception:
            return False

    def _sync_file_to_nas(self, local_path: Path, smb_path: str) -> bool:
        """Copy local file to NAS via SMB."""
        try:
            # Ensure remote directory exists
            remote_dir = "/".join(smb_path.split("/")[:-1])
            self._ensure_remote_directory(remote_dir)

            # Copy file
            with open(local_path, "rb") as src:
                with smbclient.open_file(smb_path, mode="wb") as dst:
                    shutil.copyfileobj(src, dst)

            self.logger.info(f"Synced file: {local_path} -> {smb_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to sync file {local_path}: {e}")
            return False

    def _ensure_remote_directory(self, remote_dir: str):
        """Ensure remote directory exists on NAS."""
        try:
            smbclient.mkdir(remote_dir, exist_ok=True)
        except Exception as e:
            self.logger.debug(f"Directory creation failed (may already exist): {e}")


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("rekordbox_to_jellyfin.log"),
            logging.StreamHandler(),
        ],
    )


def main():
    """Main orchestration function."""
    # Load environment variables
    load_dotenv()

    # Configuration from environment variables
    REKORDBOX_DB_PATH = os.getenv("REKORDBOX_DB_PATH")
    REKORDBOX_XML_PATH = os.getenv("REKORDBOX_XML_PATH")
    CRATES_ROOT = os.getenv("CRATES_ROOT")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
    JELLYFIN_ROOT = os.getenv("JELLYFIN_ROOT", "/data/music")
    SMB_SERVER = os.getenv("SMB_SERVER")
    SMB_SHARE = os.getenv("SMB_SHARE")
    SMB_USERNAME = os.getenv("SMB_USERNAME")
    SMB_PASSWORD = os.getenv("SMB_PASSWORD")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Validate required configuration
    if not CRATES_ROOT:
        print("Error: CRATES_ROOT environment variable is required")
        return 1

    if not (REKORDBOX_DB_PATH or REKORDBOX_XML_PATH):
        print("Error: Either REKORDBOX_DB_PATH or REKORDBOX_XML_PATH must be set")
        return 1

    if not all([SMB_SERVER, SMB_SHARE, SMB_USERNAME, SMB_PASSWORD]):
        print("Warning: SMB configuration incomplete. File sync will be skipped.")

    setup_logging(LOG_LEVEL)
    logger = logging.getLogger(__name__)

    logger.info("Starting Rekordbox to Jellyfin migration")

    # Initialize components
    extractor = RekordboxExtractor(REKORDBOX_DB_PATH, REKORDBOX_XML_PATH)
    path_converter = PathConverter(CRATES_ROOT, JELLYFIN_ROOT)
    playlist_generator = PlaylistGenerator(OUTPUT_DIR)

    # Only initialize SMB manager if configuration is complete
    smb_manager = None
    if all([SMB_SERVER, SMB_SHARE, SMB_USERNAME, SMB_PASSWORD]):
        smb_manager = SMBSyncManager(SMB_SERVER, SMB_SHARE, SMB_USERNAME, SMB_PASSWORD)

    # Connect to Rekordbox
    if not extractor.connect():
        logger.error("Failed to connect to Rekordbox. Exiting.")
        return 1

    # Extract playlists
    playlists = extractor.extract_playlists()
    if not playlists:
        logger.error("No playlists found. Exiting.")
        return 1

    # Clean output directory and generate playlist structure
    playlist_generator.clean_output_directory()
    created_playlists = playlist_generator.create_playlist_structure(
        playlists, path_converter
    )

    # Log invalid paths
    invalid_paths = path_converter.get_invalid_paths()
    if invalid_paths:
        logger.warning(f"Found {len(invalid_paths)} paths outside Crates directory")
        for path in invalid_paths:
            logger.warning(f"Invalid path: {path}")

    # Connect to NAS and sync files
    if smb_manager and smb_manager.connect():
        all_tracks = []
        for playlist in playlists:
            all_tracks.extend(playlist.tracks)

        missing_count, synced_count = smb_manager.check_and_sync_files(
            all_tracks, path_converter
        )
        logger.info(
            f"Sync completed: {synced_count}/{missing_count} missing files synced"
        )
    else:
        if smb_manager:
            logger.error(
                "Failed to connect to NAS. Playlist files created but sync skipped."
            )
        else:
            logger.info(
                "SMB configuration not provided. Playlist files created but sync skipped."
            )

    logger.info(f"Migration completed. Created {len(created_playlists)} playlists")
    return 0


if __name__ == "__main__":
    exit(main())
