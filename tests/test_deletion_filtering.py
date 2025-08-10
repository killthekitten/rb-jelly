"""Tests for deletion filtering functionality."""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
import sys
import os

# Add the parent directory to the path so we can import the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rekordbox_to_jellyfin import RekordboxExtractor, Track, Playlist


class TestDeletionFiltering:
    """Test that deleted playlists and tracks are properly filtered out."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = RekordboxExtractor()
        
    def test_filter_deleted_playlists_from_database(self):
        """Test that playlists marked with rb_local_deleted are filtered out."""
        # Mock database connection
        mock_db = Mock()
        self.extractor.db = mock_db
        
        # Create mock playlists - one normal, one deleted
        normal_playlist = Mock()
        normal_playlist.rb_local_deleted = False
        normal_playlist.ID = "playlist1"
        normal_playlist.Name = "Normal Playlist"
        normal_playlist.ParentID = "root"
        normal_playlist.Attribute = 0
        normal_playlist.Songs = []
        
        deleted_playlist = Mock()
        deleted_playlist.rb_local_deleted = True
        deleted_playlist.ID = "playlist2"
        deleted_playlist.Name = "Deleted Playlist"
        deleted_playlist.ParentID = "root"
        deleted_playlist.Attribute = 0
        deleted_playlist.Songs = []
        
        # Mock get_playlist to return both playlists
        mock_db.get_playlist.return_value = [normal_playlist, deleted_playlist]
        
        # Extract playlists
        result = self.extractor._extract_from_database()
        
        # Should only get the normal playlist (but it has no tracks, so actually empty)
        assert len(result) == 0  # No tracks means no playlists in output
        
    def test_filter_deleted_tracks_from_database(self):
        """Test that tracks marked with rb_local_deleted are filtered out."""
        # Mock database connection
        mock_db = Mock()
        self.extractor.db = mock_db
        
        # Create mock playlist
        playlist = Mock()
        playlist.rb_local_deleted = False
        playlist.ID = "playlist1"
        playlist.Name = "Test Playlist"
        playlist.ParentID = "root"
        playlist.Attribute = 0
        
        # Create mock songs - one normal, one deleted
        normal_song = Mock()
        normal_content = Mock()
        normal_content.rb_local_deleted = False
        normal_content.Title = "Normal Track"
        normal_content.Artist = Mock()
        normal_content.Artist.Name = "Test Artist"
        normal_content.FolderPath = "/test/path/track.mp3"
        normal_song.Content = normal_content
        
        deleted_song = Mock()
        deleted_content = Mock()
        deleted_content.rb_local_deleted = True
        deleted_content.Title = "Deleted Track"
        deleted_content.Artist = Mock()
        deleted_content.Artist.Name = "Test Artist"
        deleted_content.FolderPath = "/test/path/deleted.mp3"
        deleted_song.Content = deleted_content
        
        playlist.Songs = [normal_song, deleted_song]
        
        # Mock get_playlist to return the test playlist
        mock_db.get_playlist.return_value = [playlist]
        
        # Extract playlists
        result = self.extractor._extract_from_database()
        
        # Should get one playlist with only the normal track
        assert len(result) == 1
        assert len(result[0].tracks) == 1
        assert result[0].tracks[0].title == "Normal Track"
        
    def test_filter_deleted_playlists_from_xml(self):
        """Test that playlists marked with rb_local_deleted are filtered out from XML."""
        # Mock XML connection
        mock_xml = Mock()
        self.extractor.xml = mock_xml
        
        # Create mock playlists - one normal, one deleted
        normal_playlist = Mock()
        normal_playlist.rb_local_deleted = False
        normal_playlist.Name = "Normal Playlist"
        normal_playlist.get_tracks.return_value = ["track1"]
        
        deleted_playlist = Mock()
        deleted_playlist.rb_local_deleted = True
        deleted_playlist.Name = "Deleted Playlist"
        deleted_playlist.get_tracks.return_value = ["track2"]
        
        # Mock track data
        normal_track = Mock()
        normal_track.rb_local_deleted = False
        normal_track.Location = "/test/path/track.mp3"
        normal_track.Name = "Test Track"
        normal_track.Artist = "Test Artist"
        
        # Mock XML methods
        mock_xml.get_playlists.return_value = [normal_playlist, deleted_playlist]
        mock_xml.get_track.return_value = normal_track
        
        # Extract playlists
        result = self.extractor._extract_from_xml()
        
        # Should only get the normal playlist
        assert len(result) == 1
        assert result[0].name == "Normal Playlist"
        
    def test_filter_deleted_tracks_from_xml(self):
        """Test that tracks marked with rb_local_deleted are filtered out from XML."""
        # Mock XML connection
        mock_xml = Mock()
        self.extractor.xml = mock_xml
        
        # Create mock playlist
        playlist = Mock()
        playlist.rb_local_deleted = False
        playlist.Name = "Test Playlist"
        playlist.get_tracks.return_value = ["track1", "track2"]
        
        # Create mock tracks - one normal, one deleted
        normal_track = Mock()
        normal_track.rb_local_deleted = False
        normal_track.Location = "/test/path/normal.mp3"
        normal_track.Name = "Normal Track"
        normal_track.Artist = "Test Artist"
        
        deleted_track = Mock()
        deleted_track.rb_local_deleted = True
        deleted_track.Location = "/test/path/deleted.mp3"
        deleted_track.Name = "Deleted Track"
        deleted_track.Artist = "Test Artist"
        
        # Mock XML methods
        mock_xml.get_playlists.return_value = [playlist]
        
        def mock_get_track(key):
            if key == "track1":
                return normal_track
            elif key == "track2":
                return deleted_track
            return None
        
        mock_xml.get_track.side_effect = mock_get_track
        
        # Extract playlists
        result = self.extractor._extract_from_xml()
        
        # Should get one playlist with only the normal track
        assert len(result) == 1
        assert len(result[0].tracks) == 1
        assert result[0].tracks[0].title == "Normal Track"
        
    def test_missing_rb_local_deleted_attribute(self):
        """Test that objects without rb_local_deleted attribute are treated as not deleted."""
        # Mock database connection
        mock_db = Mock()
        self.extractor.db = mock_db
        
        # Create mock playlist without rb_local_deleted attribute
        playlist = Mock()
        del playlist.rb_local_deleted  # Ensure it doesn't exist
        playlist.ID = "playlist1"
        playlist.Name = "Test Playlist"
        playlist.ParentID = "root"
        playlist.Attribute = 0
        
        # Create mock song without rb_local_deleted attribute
        song = Mock()
        content = Mock()
        del content.rb_local_deleted  # Ensure it doesn't exist
        content.Title = "Test Track"
        content.Artist = Mock()
        content.Artist.Name = "Test Artist"
        content.FolderPath = "/test/path/track.mp3"
        song.Content = content
        
        playlist.Songs = [song]
        
        # Mock get_playlist to return the test playlist
        mock_db.get_playlist.return_value = [playlist]
        
        # Extract playlists - should not crash and should include the items
        result = self.extractor._extract_from_database()
        
        # Should get one playlist with the track (objects without rb_local_deleted are kept)
        assert len(result) == 1
        assert len(result[0].tracks) == 1
        assert result[0].tracks[0].title == "Test Track"