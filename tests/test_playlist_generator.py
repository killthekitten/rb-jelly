import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import tempfile
import shutil

from rekordbox_to_jellyfin import (
    Track, Playlist, PlaylistGenerator, PathConverter, 
    RekordboxExtractor
)


class TestPlaylistGenerator:
    """Test cases for PlaylistGenerator class."""
    
    def test_clean_output_directory_removes_existing_files(self, temp_dir):
        """Test that clean_output_directory removes existing files and creates clean directory."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        # Create some files in the output directory
        (output_dir / "old_playlist.m3u").touch()
        (output_dir / "subfolder").mkdir()
        (output_dir / "subfolder" / "another_file.txt").touch()
        
        generator = PlaylistGenerator(str(output_dir))
        generator.clean_output_directory()
        
        assert output_dir.exists()
        assert len(list(output_dir.iterdir())) == 0
    
    def test_clean_output_directory_creates_new_directory(self, temp_dir):
        """Test that clean_output_directory creates directory if it doesn't exist."""
        output_dir = temp_dir / "new_output"
        
        generator = PlaylistGenerator(str(output_dir))
        generator.clean_output_directory()
        
        assert output_dir.exists()
        assert output_dir.is_dir()
    
    def test_create_playlist_structure_generates_m3u_files(self, temp_dir, crates_root):
        """Test that create_playlist_structure generates proper M3U files."""
        output_dir = temp_dir / "playlists"
        
        # Create sample tracks with paths in crates directory
        tracks = [
            Track(
                title="Strobe",
                artist="Deadmau5",
                file_path=Path(crates_root) / "Electronic" / "Deadmau5" / "Strobe.mp3",
                playlist_path="Electronic"
            ),
            Track(
                title="One More Time",
                artist="Daft Punk", 
                file_path=Path(crates_root) / "Electronic" / "Daft Punk" / "One More Time.wav",
                playlist_path="Electronic"
            )
        ]
        
        playlists = [
            Playlist(
                name="Electronic",
                path="Electronic",
                tracks=tracks,
                children=[]
            )
        ]
        
        generator = PlaylistGenerator(str(output_dir))
        path_converter = PathConverter(crates_root, "/data/music")
        
        generator.clean_output_directory()
        created_playlists = generator.create_playlist_structure(playlists, path_converter)
        
        # Check that playlist directory was created
        playlist_dir = output_dir / "Electronic"
        assert playlist_dir.exists()
        
        # Check that M3U file was created
        m3u_file = playlist_dir / "Electronic.m3u"
        assert m3u_file.exists()
        assert "Electronic/Electronic" in created_playlists
        
        # Check M3U file content
        content = m3u_file.read_text(encoding='utf-8')
        assert "#EXTM3U" in content
        assert "Deadmau5 - Strobe" in content
        assert "Daft Punk - One More Time" in content
        assert "/data/music/Electronic/Deadmau5/Strobe.mp3" in content
        assert "/data/music/Electronic/Daft Punk/One More Time.wav" in content
    
    def test_create_playlist_structure_skips_invalid_tracks(self, temp_dir, crates_root):
        """Test that playlists with invalid tracks (outside crates) are handled properly."""
        output_dir = temp_dir / "playlists"
        
        # Mix of valid and invalid tracks
        tracks = [
            Track(
                title="Valid Track",
                artist="Artist 1",
                file_path=Path(crates_root) / "Electronic" / "Deadmau5" / "Strobe.mp3", 
                playlist_path="Mixed"
            ),
            Track(
                title="Invalid Track",
                artist="Artist 2",
                file_path=Path("/some/other/path/track.mp3"),  # Outside crates
                playlist_path="Mixed"
            )
        ]
        
        playlists = [
            Playlist(
                name="Mixed",
                path="Mixed", 
                tracks=tracks,
                children=[]
            )
        ]
        
        generator = PlaylistGenerator(str(output_dir))
        path_converter = PathConverter(crates_root, "/data/music")
        
        generator.clean_output_directory()
        created_playlists = generator.create_playlist_structure(playlists, path_converter)
        
        # Playlist should still be created with only valid tracks
        assert "Mixed/Mixed" in created_playlists
        
        m3u_file = Path(created_playlists["Mixed/Mixed"])
        content = m3u_file.read_text(encoding='utf-8')
        
        # Should contain valid track
        assert "Artist 1 - Valid Track" in content
        assert "/data/music/Electronic/Deadmau5/Strobe.mp3" in content
        
        # Should not contain invalid track
        assert "Artist 2 - Invalid Track" not in content
        assert "/some/other/path/track.mp3" not in content
    
    def test_create_playlist_structure_handles_empty_playlists(self, temp_dir, crates_root):
        """Test that playlists with no valid tracks are handled appropriately."""
        output_dir = temp_dir / "playlists"
        
        # Playlist with only invalid tracks
        tracks = [
            Track(
                title="Invalid Track 1",
                artist="Artist 1",
                file_path=Path("/invalid/path1.mp3"),
                playlist_path="Empty"
            ),
            Track(
                title="Invalid Track 2", 
                artist="Artist 2",
                file_path=Path("/invalid/path2.mp3"),
                playlist_path="Empty"
            )
        ]
        
        playlists = [
            Playlist(
                name="Empty",
                path="Empty",
                tracks=tracks,
                children=[]
            )
        ]
        
        generator = PlaylistGenerator(str(output_dir))
        path_converter = PathConverter(crates_root, "/data/music")
        
        generator.clean_output_directory()
        
        # Don't mock the logger, just check the behavior
        created_playlists = generator.create_playlist_structure(playlists, path_converter)
        
        # Playlist should not be created
        assert "Empty" not in created_playlists
    
    def test_write_m3u_file_format(self, temp_dir):
        """Test that M3U files are written in correct format."""
        generator = PlaylistGenerator(str(temp_dir))
        
        tracks_with_paths = [
            (
                Track("Song 1", "Artist 1", Path("/test"), "playlist"),
                "/data/music/path1.mp3"
            ),
            (
                Track("Song 2", "Artist 2", Path("/test"), "playlist"),
                "/data/music/path2.flac"
            )
        ]
        
        m3u_path = temp_dir / "test.m3u"
        generator._write_m3u_file(m3u_path, tracks_with_paths)
        
        content = m3u_path.read_text(encoding='utf-8')
        lines = content.strip().split('\n')
        
        # Check M3U format
        assert lines[0] == "#EXTM3U"
        assert lines[1] == "#EXTINF:-1,Artist 1 - Song 1"
        assert lines[2] == "/data/music/path1.mp3"
        assert lines[3] == "#EXTINF:-1,Artist 2 - Song 2" 
        assert lines[4] == "/data/music/path2.flac"
    
    def test_write_m3u_file_handles_errors(self, temp_dir):
        """Test that M3U file writing handles errors gracefully."""
        generator = PlaylistGenerator(str(temp_dir))
        
        tracks_with_paths = [
            (Track("Song", "Artist", Path("/test"), "playlist"), "/path.mp3")
        ]
        
        # Try to write to invalid path
        invalid_path = temp_dir / "nonexistent" / "test.m3u"
        
        # Should not raise exception, just log error and continue
        generator._write_m3u_file(invalid_path, tracks_with_paths)
        
        # File should not exist
        assert not invalid_path.exists()
    
    def test_create_playlist_structure_flat_mode_with_nested_playlists(self, temp_dir, crates_root):
        """Test that flat mode generates flattened playlist names with separator."""
        output_dir = temp_dir / "playlists"
        
        # Create nested playlists with different path levels
        tracks1 = [
            Track(
                title="Deep House Track",
                artist="Artist 1",
                file_path=Path(crates_root) / "Electronic" / "Deep" / "track1.mp3",
                playlist_path="Electronic/Deep House"
            )
        ]
        
        tracks2 = [
            Track(
                title="Rock Track", 
                artist="Artist 2",
                file_path=Path(crates_root) / "Rock" / "track2.mp3",
                playlist_path="Rock"
            )
        ]
        
        tracks3 = [
            Track(
                title="Root Track",
                artist="Artist 3", 
                file_path=Path(crates_root) / "track3.mp3",
                playlist_path=""
            )
        ]
        
        playlists = [
            Playlist(
                name="Deep House",
                path="Electronic",  # Nested under Electronic
                tracks=tracks1,
                children=[]
            ),
            Playlist(
                name="Classic Rock",
                path="Rock",  # Nested under Rock
                tracks=tracks2,
                children=[]
            ),
            Playlist(
                name="Favorites",
                path="",  # Root level
                tracks=tracks3,
                children=[]
            )
        ]
        
        # Test flat mode
        generator = PlaylistGenerator(str(output_dir), flat_mode=True)
        path_converter = PathConverter(crates_root, "/data/music")
        
        generator.clean_output_directory()
        created_playlists = generator.create_playlist_structure(playlists, path_converter)
        
        # Check that all files are in root directory (no subdirectories)
        assert len(list(output_dir.glob("*/"))) == 0  # No subdirectories
        
        # Check flattened playlist names
        assert "Electronic - Deep House" in created_playlists
        assert "Rock - Classic Rock" in created_playlists
        assert "Favorites" in created_playlists  # Root level keeps same name
        
        # Check that M3U files exist with correct names
        assert (output_dir / "Electronic - Deep House.m3u").exists()
        assert (output_dir / "Rock - Classic Rock.m3u").exists()
        assert (output_dir / "Favorites.m3u").exists()
        
        # Verify file content
        content = (output_dir / "Electronic - Deep House.m3u").read_text(encoding='utf-8')
        assert "Artist 1 - Deep House Track" in content
        assert "/data/music/Electronic/Deep/track1.mp3" in content

    def test_create_playlist_structure_nested_mode_vs_flat_mode(self, temp_dir, crates_root):
        """Test that nested mode and flat mode produce different outputs for same playlists."""
        output_dir_nested = temp_dir / "nested"
        output_dir_flat = temp_dir / "flat"
        
        tracks = [
            Track(
                title="Test Track",
                artist="Test Artist",
                file_path=Path(crates_root) / "Genre" / "Subgenre" / "track.mp3",
                playlist_path="Genre/Subgenre"
            )
        ]
        
        playlists = [
            Playlist(
                name="Test Playlist",
                path="Genre/Subgenre",
                tracks=tracks,
                children=[]
            )
        ]
        
        path_converter = PathConverter(crates_root, "/data/music")
        
        # Test nested mode (default)
        generator_nested = PlaylistGenerator(str(output_dir_nested), flat_mode=False)
        generator_nested.clean_output_directory()
        created_nested = generator_nested.create_playlist_structure(playlists, path_converter)
        
        # Test flat mode
        generator_flat = PlaylistGenerator(str(output_dir_flat), flat_mode=True)
        generator_flat.clean_output_directory()
        created_flat = generator_flat.create_playlist_structure(playlists, path_converter)
        
        # Nested mode creates subdirectories
        assert (output_dir_nested / "Genre" / "Subgenre").exists()
        assert (output_dir_nested / "Genre" / "Subgenre" / "Test Playlist.m3u").exists()
        assert "Genre/Subgenre/Test Playlist" in created_nested
        
        # Flat mode creates no subdirectories
        assert len(list(output_dir_flat.glob("*/"))) == 0  # No subdirectories
        assert (output_dir_flat / "Genre - Subgenre - Test Playlist.m3u").exists()
        assert "Genre - Subgenre - Test Playlist" in created_flat
        
        # Both should have same track content
        nested_content = (output_dir_nested / "Genre" / "Subgenre" / "Test Playlist.m3u").read_text()
        flat_content = (output_dir_flat / "Genre - Subgenre - Test Playlist.m3u").read_text()
        
        assert nested_content == flat_content  # Same track content

    def test_create_playlist_structure_flat_mode_multiple_playlists(self, temp_dir, crates_root):
        """Test that flat mode correctly handles multiple playlists without conflicts."""
        output_dir = temp_dir / "playlists"
        
        # Create multiple playlists with different paths and names
        tracks1 = [
            Track(
                title="Electronic Track",
                artist="Artist 1",
                file_path=Path(crates_root) / "electronic.mp3",
                playlist_path="Electronic"
            )
        ]
        
        tracks2 = [
            Track(
                title="Rock Track", 
                artist="Artist 2",
                file_path=Path(crates_root) / "rock.mp3",
                playlist_path="Rock"
            )
        ]
        
        tracks3 = [
            Track(
                title="Jazz Track", 
                artist="Artist 3",
                file_path=Path(crates_root) / "jazz.mp3",
                playlist_path=""  # Root level
            )
        ]
        
        playlists = [
            Playlist(
                name="House",
                path="Electronic", 
                tracks=tracks1,
                children=[]
            ),
            Playlist(
                name="Alternative",
                path="Rock",
                tracks=tracks2, 
                children=[]
            ),
            Playlist(
                name="Favorites",
                path="",  # Root level
                tracks=tracks3,
                children=[]
            )
        ]
        
        generator = PlaylistGenerator(str(output_dir), flat_mode=True)
        path_converter = PathConverter(crates_root, "/data/music")
        
        generator.clean_output_directory()
        created_playlists = generator.create_playlist_structure(playlists, path_converter)
        
        # All playlists should be created
        assert len(created_playlists) == 3
        
        # Check expected flat names
        assert "Electronic - House" in created_playlists
        assert "Rock - Alternative" in created_playlists  
        assert "Favorites" in created_playlists  # Root level playlist
        
        # Check that all M3U files exist
        m3u_files = list(output_dir.glob("*.m3u"))
        assert len(m3u_files) == 3
        
        # Verify specific file names
        file_names = [f.stem for f in m3u_files]
        assert "Electronic - House" in file_names
        assert "Rock - Alternative" in file_names
        assert "Favorites" in file_names