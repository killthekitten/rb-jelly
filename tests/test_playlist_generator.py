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
        assert "Electronic" in created_playlists
        
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
        assert "Mixed" in created_playlists
        
        m3u_file = Path(created_playlists["Mixed"])
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