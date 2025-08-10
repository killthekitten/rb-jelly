import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from rekordbox_to_jellyfin import RekordboxExtractor, Track, Playlist


class TestRekordboxExtractor:
    """Test cases for RekordboxExtractor class."""
    
    def test_connect_with_valid_database(self, temp_dir):
        """Test connection to valid Rekordbox database."""
        db_path = temp_dir / "test.db"
        db_path.touch()  # Create empty file
        
        with patch('rekordbox_to_jellyfin.Rekordbox6Database') as mock_db_class:
            mock_db_instance = Mock()
            mock_db_class.return_value = mock_db_instance
            
            extractor = RekordboxExtractor(db_path=str(db_path))
            result = extractor.connect()
            
            assert result is True
            assert extractor.db == mock_db_instance
            mock_db_class.assert_called_once_with(str(db_path))
    
    def test_connect_with_valid_xml(self, temp_dir):
        """Test connection to valid Rekordbox XML file."""
        xml_path = temp_dir / "test.xml"
        xml_path.touch()
        
        with patch('rekordbox_to_jellyfin.RekordboxXml') as mock_xml_class:
            mock_xml_instance = Mock()
            mock_xml_class.return_value = mock_xml_instance
            
            extractor = RekordboxExtractor(xml_path=str(xml_path))
            result = extractor.connect()
            
            assert result is True
            assert extractor.xml == mock_xml_instance
            mock_xml_class.assert_called_once_with(str(xml_path))
    
    def test_connect_prefers_database_over_xml(self, temp_dir):
        """Test that database is preferred when both db and xml paths are provided."""
        db_path = temp_dir / "test.db"
        xml_path = temp_dir / "test.xml"
        db_path.touch()
        xml_path.touch()
        
        with patch('rekordbox_to_jellyfin.Rekordbox6Database') as mock_db_class:
            with patch('rekordbox_to_jellyfin.RekordboxXml') as mock_xml_class:
                mock_db_instance = Mock()
                mock_db_class.return_value = mock_db_instance
                
                extractor = RekordboxExtractor(db_path=str(db_path), xml_path=str(xml_path))
                result = extractor.connect()
                
                assert result is True
                assert extractor.db == mock_db_instance
                assert extractor.xml is None
                mock_db_class.assert_called_once()
                mock_xml_class.assert_not_called()
    
    def test_connect_with_nonexistent_files(self):
        """Test connection fails when neither file exists."""
        extractor = RekordboxExtractor(
            db_path="/nonexistent/db.db",
            xml_path="/nonexistent/xml.xml"
        )
        result = extractor.connect()
        
        assert result is False
        assert extractor.db is None
        assert extractor.xml is None
    
    def test_connect_handles_exceptions(self, temp_dir):
        """Test connection handles exceptions gracefully."""
        db_path = temp_dir / "test.db"
        db_path.touch()
        
        with patch('rekordbox_to_jellyfin.Rekordbox6Database') as mock_db_class:
            mock_db_class.side_effect = Exception("Connection failed")
            
            extractor = RekordboxExtractor(db_path=str(db_path))
            result = extractor.connect()
            
            assert result is False
            assert extractor.db is None
    
    def test_extract_playlists_from_database(self, mock_rekordbox_db):
        """Test extracting playlists from database."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")
        extractor.db = mock_rekordbox_db
        
        playlists = extractor.extract_playlists()
        
        assert len(playlists) == 2
        
        # Check first playlist (Electronic)
        electronic = playlists[0]
        assert electronic.name == "Electronic"
        assert len(electronic.tracks) == 2
        
        # Check first track
        track1 = electronic.tracks[0]
        assert track1.title == "Strobe"
        assert track1.artist == "Deadmau5"
        assert track1.file_path == Path("/Users/djuser/Music/Crates/Electronic/Deadmau5/Strobe.mp3")
        
        # Check second track
        track2 = electronic.tracks[1]
        assert track2.title == "One More Time"
        assert track2.artist == "Daft Punk"
        assert track2.file_path == Path("/Users/djuser/Music/Crates/Electronic/Daft Punk/One More Time.wav")
        
        # Check second playlist (Hip Hop)
        hip_hop = playlists[1]
        assert hip_hop.name == "Hip Hop"
        assert len(hip_hop.tracks) == 1
        
        track3 = hip_hop.tracks[0]
        assert track3.title == "Still D.R.E."
        assert track3.artist == "Dr. Dre"
        assert track3.file_path == Path("/Users/djuser/Music/Crates/Hip Hop/Dr. Dre/Still D.R.E..flac")
    
    def test_extract_playlists_from_xml(self):
        """Test extracting playlists from XML."""
        extractor = RekordboxExtractor(xml_path="/fake/path.xml")
        
        # Mock XML structure
        mock_xml = Mock()
        extractor.xml = mock_xml
        
        # Mock XML playlists
        mock_xml_playlist = Mock()
        mock_xml_playlist.Name = "Test Playlist"
        mock_xml_playlist.get_tracks.return_value = ["track1", "track2"]
        
        mock_xml.get_playlists.return_value = [mock_xml_playlist]
        
        # Mock track data
        mock_track_data1 = Mock()
        mock_track_data1.Name = "Track 1"
        mock_track_data1.Artist = "Artist 1"
        mock_track_data1.Location = "/path/to/track1.mp3"
        
        mock_track_data2 = Mock()
        mock_track_data2.Name = "Track 2"
        mock_track_data2.Artist = "Artist 2"
        mock_track_data2.Location = "/path/to/track2.mp3"
        
        mock_xml.get_track.side_effect = [mock_track_data1, mock_track_data2]
        
        playlists = extractor.extract_playlists()
        
        assert len(playlists) == 1
        playlist = playlists[0]
        assert playlist.name == "Test Playlist"
        assert len(playlist.tracks) == 2
        
        track1 = playlist.tracks[0]
        assert track1.title == "Track 1"
        assert track1.artist == "Artist 1"
    
    def test_extract_playlists_skips_empty_playlists(self):
        """Test that playlists with no tracks are skipped."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")
        
        mock_db = Mock()
        extractor.db = mock_db
        
        # Mock empty playlist
        mock_playlist = Mock()
        mock_playlist.Name = "Empty Playlist"
        mock_playlist.Songs = []  # No songs
        
        mock_db.get_playlist.return_value = [mock_playlist]
        
        playlists = extractor.extract_playlists()
        
        assert len(playlists) == 0
    
    def test_extract_playlists_handles_missing_content(self):
        """Test extraction handles songs with missing content gracefully."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")
        
        mock_db = Mock()
        extractor.db = mock_db
        
        mock_playlist = Mock()
        mock_playlist.Name = "Test Playlist"
        
        # Mock song with missing content
        mock_song_no_content = Mock()
        mock_song_no_content.Content = None
        
        # Mock song with valid content
        mock_song_with_content = Mock()
        mock_content = Mock()
        mock_content.Title = "Valid Song"
        mock_content.Artist = Mock()
        mock_content.Artist.Name = "Valid Artist"
        mock_content.FolderPath = "/path/to/folder"
        mock_content.Filename = "song.mp3"
        mock_song_with_content.Content = mock_content
        
        mock_playlist.Songs = [mock_song_no_content, mock_song_with_content]
        mock_db.get_playlist.return_value = [mock_playlist]
        
        playlists = extractor.extract_playlists()
        
        assert len(playlists) == 1
        playlist = playlists[0]
        assert len(playlist.tracks) == 1  # Only valid song included
        assert playlist.tracks[0].title == "Valid Song"
    
    def test_extract_playlists_handles_database_errors(self):
        """Test extraction handles database errors gracefully."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")
        
        mock_db = Mock()
        mock_db.get_playlist.side_effect = Exception("Database error")
        extractor.db = mock_db
        
        playlists = extractor.extract_playlists()
        
        assert len(playlists) == 0
    
    def test_extract_playlists_no_connection(self):
        """Test extraction returns empty list when not connected."""
        extractor = RekordboxExtractor()
        # Don't connect
        
        playlists = extractor.extract_playlists()
        
        assert len(playlists) == 0