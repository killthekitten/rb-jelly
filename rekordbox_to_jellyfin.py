#!/usr/bin/env python3
"""
Rekordbox to Jellyfin Library Migration Script

This script extracts playlist structure from Rekordbox, mirrors the folder/playlist
hierarchy for Jellyfin, converts paths from Crates directory to /data/music,
and syncs missing files to NAS.
"""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from pyrekordbox import Rekordbox6Database, RekordboxXml
from pyrekordbox.db6.smartlist import SmartList

from pathvalidate import sanitize_filename


class UniqueNameResolver:
    """Handles collision resolution for sanitized filenames."""

    def __init__(self):
        self.name_mapping = {}  # original_name -> unique_sanitized_name
        self.used_names = set()  # track all used sanitized names

    def get_unique_name(self, original_name: str) -> str:
        """Get a unique sanitized filename, resolving collisions."""
        # Return cached mapping if we've seen this name before
        if original_name in self.name_mapping:
            return self.name_mapping[original_name]

        # Start with basic sanitization
        base_sanitized = sanitize_filename(original_name)

        # Handle empty results from sanitization
        if not base_sanitized or base_sanitized.isspace():
            base_sanitized = f"playlist_{hash(original_name) % 10000}"

        # If no collision, use it directly
        if base_sanitized not in self.used_names:
            self.name_mapping[original_name] = base_sanitized
            self.used_names.add(base_sanitized)
            return base_sanitized

        # Handle collision by finding a unique suffix
        counter = 1
        while True:
            # Try appending counter: "name (2)", "name (3)", etc.
            candidate = f"{base_sanitized} ({counter})"
            if candidate not in self.used_names:
                self.name_mapping[original_name] = candidate
                self.used_names.add(candidate)
                return candidate
            counter += 1


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
        try:
            # Get all playlists and filter out deleted ones
            all_playlists = list(self.db.get_playlist())
            rb_playlists = [
                p for p in all_playlists if not getattr(p, "rb_local_deleted", False)
            ]
            deleted_playlists_count = len(all_playlists) - len(rb_playlists)

            self.logger.info(
                f"Found {len(all_playlists)} total playlists, {deleted_playlists_count} deleted (skipped)"
            )
            if deleted_playlists_count > 0:
                self.logger.debug(
                    f"Skipped deleted playlists: {[p.Name for p in all_playlists if getattr(p, 'rb_local_deleted', False)]}"
                )

            # Build hierarchy map and name resolvers
            playlists_by_id = {}
            name_resolvers = {}  # path -> UniqueNameResolver for that path level

            def get_name_resolver(path: str) -> UniqueNameResolver:
                """Get or create a name resolver for a specific path level."""
                if path not in name_resolvers:
                    name_resolvers[path] = UniqueNameResolver()
                return name_resolvers[path]

            # Track deletion statistics
            total_deleted_tracks = 0

            # First pass: create all playlist objects with temporary names
            for rb_playlist in rb_playlists:
                tracks = []
                playlist_deleted_tracks = 0

                # Debug logging for ALL playlists to understand structure
                is_smart = (
                    hasattr(rb_playlist, "is_smart_playlist")
                    and rb_playlist.is_smart_playlist
                )
                attribute = getattr(rb_playlist, "Attribute", "Unknown")
                self.logger.debug(
                    f"Playlist '{rb_playlist.Name}': is_smart_playlist={is_smart}, "
                    f"Attribute={attribute}"
                )

                # Extract tracks from playlist
                # Attribute 0 = actual playlist with tracks
                # Attribute 1 or 4 = folders/containers
                # Smart playlists can have Attribute=4 but still need track processing
                should_process_tracks = hasattr(rb_playlist, "Attribute") and (
                    rb_playlist.Attribute == 0 or is_smart
                )

                if should_process_tracks:

                    if is_smart:
                        # Handle smart playlists by executing their SmartList query
                        self.logger.debug(
                            f"Processing smart playlist '{rb_playlist.Name}'"
                        )
                        try:
                            if (
                                hasattr(rb_playlist, "SmartList")
                                and rb_playlist.SmartList
                            ):
                                self.logger.debug(
                                    f"SmartList type for '{rb_playlist.Name}': {type(rb_playlist.SmartList)}"
                                )
                                self.logger.debug(
                                    f"SmartList content: {rb_playlist.SmartList}"
                                )

                                # The SmartList might be a string representation, need to parse it
                                if isinstance(rb_playlist.SmartList, str):
                                    self.logger.debug(
                                        f"Parsing SmartList XML for '{rb_playlist.Name}'"
                                    )
                                    try:
                                        # Parse the XML string into a SmartList object
                                        smart_list = SmartList()
                                        smart_list.parse(rb_playlist.SmartList)

                                        # Query tracks using the smart list filter
                                        from pyrekordbox.db6.tables import DjmdContent

                                        filter_clause = smart_list.filter_clause()
                                        smart_tracks_query = self.db.session.query(
                                            DjmdContent
                                        ).filter(filter_clause)
                                        smart_tracks_list = smart_tracks_query.all()
                                        self.logger.debug(
                                            f"Smart playlist '{rb_playlist.Name}' returned {len(smart_tracks_list)} tracks"
                                        )

                                        for content in smart_tracks_list:
                                            # Skip deleted tracks
                                            if getattr(
                                                content, "rb_local_deleted", False
                                            ):
                                                playlist_deleted_tracks += 1
                                                continue

                                            track = Track(
                                                title=content.Title or "Unknown",
                                                artist=(
                                                    content.Artist.Name
                                                    if content.Artist
                                                    else "Unknown"
                                                ),
                                                file_path=(
                                                    Path(content.FolderPath)
                                                    if content.FolderPath
                                                    else Path()
                                                ),
                                                playlist_path=rb_playlist.Name,
                                            )
                                            tracks.append(track)
                                    except Exception as smart_parse_error:
                                        self.logger.warning(
                                            f"Failed to parse SmartList for '{rb_playlist.Name}': {smart_parse_error}"
                                        )
                                else:
                                    self.logger.debug(
                                        f"Executing SmartList query for '{rb_playlist.Name}'"
                                    )
                                    # Execute smart list query to get matching tracks
                                    smart_tracks = rb_playlist.SmartList.execute(
                                        self.db.session
                                    )
                                    self.logger.debug(
                                        f"Smart playlist '{rb_playlist.Name}' returned {len(list(smart_tracks))} tracks"
                                    )

                                    # Need to re-execute since we consumed the iterator
                                    smart_tracks = rb_playlist.SmartList.execute(
                                        self.db.session
                                    )
                                    for content in smart_tracks:
                                        # Skip deleted tracks
                                        if getattr(content, "rb_local_deleted", False):
                                            playlist_deleted_tracks += 1
                                            continue

                                        track = Track(
                                            title=content.Title or "Unknown",
                                            artist=(
                                                content.Artist.Name
                                                if content.Artist
                                                else "Unknown"
                                            ),
                                            file_path=(
                                                Path(content.FolderPath)
                                                if content.FolderPath
                                                else Path()
                                            ),
                                            playlist_path=rb_playlist.Name,
                                        )
                                        tracks.append(track)
                            else:
                                self.logger.debug(
                                    f"Smart playlist '{rb_playlist.Name}' has no SmartList object"
                                )
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to execute smart playlist '{rb_playlist.Name}': {e}"
                            )
                    else:
                        # Handle regular playlists
                        for song in rb_playlist.Songs:
                            if hasattr(song, "Content") and song.Content:
                                content = song.Content
                                # Skip deleted tracks
                                if getattr(content, "rb_local_deleted", False):
                                    playlist_deleted_tracks += 1
                                    continue

                                track = Track(
                                    title=content.Title or "Unknown",
                                    artist=(
                                        content.Artist.Name
                                        if content.Artist
                                        else "Unknown"
                                    ),
                                    file_path=(
                                        Path(content.FolderPath)
                                        if content.FolderPath
                                        else Path()
                                    ),
                                    playlist_path=rb_playlist.Name,
                                )
                                tracks.append(track)

                total_deleted_tracks += playlist_deleted_tracks
                if playlist_deleted_tracks > 0:
                    self.logger.debug(
                        f"Playlist '{rb_playlist.Name}': skipped {playlist_deleted_tracks} deleted tracks"
                    )

                playlist = Playlist(
                    name=rb_playlist.Name,  # Keep original name for now
                    path="",  # Will be calculated later
                    tracks=tracks,
                    children=[],
                )

                playlists_by_id[rb_playlist.ID] = {
                    "playlist": playlist,
                    "parent_id": rb_playlist.ParentID,
                    "is_folder": rb_playlist.Attribute in (1, 4),
                    "original_name": rb_playlist.Name,
                    "rb_playlist": rb_playlist,
                }

            # Second pass: calculate paths with proper parent context
            def calculate_path_info(playlist_id, visited=None):
                if visited is None:
                    visited = set()
                if playlist_id in visited:
                    return [], ""  # Circular reference protection
                visited.add(playlist_id)

                if playlist_id not in playlists_by_id:
                    return [], ""

                playlist_data = playlists_by_id[playlist_id]
                parent_id = playlist_data["parent_id"]
                original_name = playlist_data["original_name"]

                if parent_id == "root":
                    # Root level - use root resolver
                    resolver = get_name_resolver("root")
                    unique_name = resolver.get_unique_name(original_name)
                    return [unique_name], "root"
                else:
                    parent_path_components, _ = calculate_path_info(
                        parent_id, visited.copy()
                    )
                    parent_path = "/".join(parent_path_components)

                    # Get resolver for this parent path
                    resolver = get_name_resolver(parent_path)
                    unique_name = resolver.get_unique_name(original_name)

                    return parent_path_components + [unique_name], parent_path

            # Calculate unique names and paths for all playlists
            result_playlists = []

            for playlist_id, playlist_data in playlists_by_id.items():
                playlist = playlist_data["playlist"]

                # Include all playlists (folders and empty playlists too)
                path_components, _ = calculate_path_info(playlist_id)

                # Update playlist name to unique sanitized version
                playlist.name = path_components[
                    -1
                ]  # Last component is the playlist name

                # Build the folder path (excluding the playlist name itself)
                if len(path_components) > 1:
                    folder_path = "/".join(path_components[:-1])
                    playlist.path = folder_path
                else:
                    playlist.path = ""  # Root level playlist

                result_playlists.append(playlist)

            # Log deletion statistics
            if total_deleted_tracks > 0:
                self.logger.info(
                    f"Skipped {total_deleted_tracks} deleted tracks from database playlists"
                )

            return result_playlists

        except Exception as e:
            self.logger.error(f"Error extracting from database: {e}")
            return []

    def _extract_from_xml(self) -> List[Playlist]:
        """Extract playlists from Rekordbox XML export."""
        playlists = []

        try:
            # Get all playlists from XML
            all_xml_playlists = self.xml.get_playlists()
            deleted_playlists_count = 0
            total_deleted_tracks = 0

            for xml_playlist in all_xml_playlists:
                # Skip deleted playlists
                if getattr(xml_playlist, "rb_local_deleted", False):
                    deleted_playlists_count += 1
                    continue

                tracks = []
                track_keys = xml_playlist.get_tracks()
                playlist_deleted_tracks = 0

                for track_key in track_keys:
                    track_data = self.xml.get_track(track_key)
                    if track_data and hasattr(track_data, "Location"):
                        # Skip deleted tracks
                        if getattr(track_data, "rb_local_deleted", False):
                            playlist_deleted_tracks += 1
                            continue

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

                total_deleted_tracks += playlist_deleted_tracks
                if playlist_deleted_tracks > 0:
                    self.logger.debug(
                        f"Playlist '{xml_playlist.Name}': skipped {playlist_deleted_tracks} deleted tracks"
                    )

                if tracks:
                    playlist = Playlist(
                        name=xml_playlist.Name,
                        path=xml_playlist.Name,
                        tracks=tracks,
                        children=[],
                    )
                    playlists.append(playlist)

            # Log deletion statistics
            self.logger.info(
                f"Found {len(all_xml_playlists)} total playlists, {deleted_playlists_count} deleted (skipped)"
            )
            if total_deleted_tracks > 0:
                self.logger.info(
                    f"Skipped {total_deleted_tracks} deleted tracks from XML playlists"
                )

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

    def __init__(self, output_dir: str, flat_mode: bool = False):
        self.output_dir = Path(output_dir)
        self.flat_mode = flat_mode
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
        """Create nested folder structure and M3U files for playlists."""
        created_playlists = {}

        # Initialize collision resolver for flat mode
        if self.flat_mode:
            name_resolver = UniqueNameResolver()

        for playlist in playlists:
            # Determine the full path for the M3U file
            if self.flat_mode:
                # Flat mode - all M3U files go directly in output directory
                if playlist.path:
                    # Replace forward slashes with " - " separator before sanitization
                    path_with_separators = playlist.path.replace("/", " - ")
                    flat_name_raw = f"{path_with_separators} - {playlist.name}"
                else:
                    # Root level playlist
                    flat_name_raw = playlist.name

                # Apply collision resolution and sanitization
                flat_name = name_resolver.get_unique_name(flat_name_raw)
                m3u_path = self.output_dir / f"{flat_name}.m3u"
                full_path = flat_name
            else:
                # Original nested mode
                if playlist.path:
                    # Nested playlist - create folder structure and put M3U inside
                    playlist_dir = self.output_dir / playlist.path
                    playlist_dir.mkdir(parents=True, exist_ok=True)
                    m3u_path = playlist_dir / f"{playlist.name}.m3u"
                    full_path = f"{playlist.path}/{playlist.name}"
                else:
                    # Root level playlist - M3U goes directly in output directory
                    m3u_path = self.output_dir / f"{playlist.name}.m3u"
                    full_path = playlist.name

            # Generate M3U playlist file
            valid_tracks = []
            for track in playlist.tracks:
                jellyfin_path = path_converter.validate_and_convert_path(
                    track.file_path
                )
                if jellyfin_path:
                    valid_tracks.append((track, jellyfin_path))

            if valid_tracks:
                self._write_m3u_file(m3u_path, valid_tracks)
                created_playlists[full_path] = str(m3u_path)
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
