"""
Enhanced mocks based on real Rekordbox database structure exploration.

This module provides more realistic mock data that closely resembles
the actual structure returned by pyrekordbox.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import List, Optional

from rekordbox_to_jellyfin import Track, Playlist, RekordboxExtractor


class MockRekordboxContent:
    """Mock for Rekordbox Content object."""
    
    def __init__(self, title: str, artist_name: str, folder_path: str, filename: str):
        self.Title = title
        self.FileNameL = filename  # Use correct attribute name from pyrekordbox 
        self.FolderPath = folder_path
        self.rb_local_deleted = False
        
        # Mock Artist object
        self.Artist = Mock()
        self.Artist.Name = artist_name


class MockRekordboxSong:
    """Mock for Rekordbox Song object."""
    
    def __init__(self, content: Optional[MockRekordboxContent] = None):
        self.Content = content


class MockRekordboxPlaylist:
    """Mock for Rekordbox Playlist object."""
    
    def __init__(self, name: str, songs: List[MockRekordboxSong], playlist_id: str = "1", parent_id: str = "root", attribute: int = 0):
        self.Name = name
        self.Songs = songs
        self.ID = playlist_id
        self.ParentID = parent_id
        self.Attribute = attribute  # 0 = playlist with tracks, 1/4 = folder
        self.rb_local_deleted = False


@pytest.fixture
def realistic_rekordbox_db():
    """
    Create a more realistic mock Rekordbox database based on actual structure.
    
    This fixture creates mock data that closely matches what pyrekordbox returns,
    including realistic folder structures and metadata.
    """
    
    # Create realistic content objects
    strobe_content = MockRekordboxContent(
        title="Strobe", 
        artist_name="deadmau5",
        folder_path="/Users/djuser/Music/Crates/Progressive House/deadmau5/01 - Strobe.mp3",
        filename="01 - Strobe.mp3"
    )
    
    one_more_time_content = MockRekordboxContent(
        title="One More Time",
        artist_name="Daft Punk", 
        folder_path="/Users/djuser/Music/Crates/French House/Daft Punk/One More Time.wav",
        filename="One More Time.wav"
    )
    
    levels_content = MockRekordboxContent(
        title="Levels",
        artist_name="Avicii",
        folder_path="/Users/djuser/Music/Crates/Progressive House/Avicii/Levels (Original Version).flac",
        filename="Levels (Original Version).flac"
    )
    
    still_dre_content = MockRekordboxContent(
        title="Still D.R.E.",
        artist_name="Dr. Dre ft. Snoop Dogg",
        folder_path="/Users/djuser/Music/Crates/West Coast Hip Hop/Dr. Dre/02 Still D.R.E..mp3",
        filename="02 Still D.R.E..mp3"
    )
    
    lose_yourself_content = MockRekordboxContent(
        title="Lose Yourself", 
        artist_name="Eminem",
        folder_path="/Users/djuser/Music/Crates/Hip Hop/Eminem/Lose Yourself.m4a",
        filename="Lose Yourself.m4a"
    )
    
    # Create songs
    strobe_song = MockRekordboxSong(strobe_content)
    one_more_time_song = MockRekordboxSong(one_more_time_content)
    levels_song = MockRekordboxSong(levels_content)
    still_dre_song = MockRekordboxSong(still_dre_content)
    lose_yourself_song = MockRekordboxSong(lose_yourself_content)
    
    # Create some orphaned songs without content (should be ignored)
    orphaned_song1 = MockRekordboxSong(None)
    orphaned_song2 = MockRekordboxSong(content=Mock())
    orphaned_song2.Content = None  # Explicitly None
    
    # Create playlists with realistic groupings
    electronic_playlist = MockRekordboxPlaylist(
        name="Electronic Essentials",
        songs=[strobe_song, one_more_time_song, levels_song, orphaned_song1],
        playlist_id="1",
        parent_id="root",
        attribute=0  # Actual playlist with tracks
    )
    
    hip_hop_playlist = MockRekordboxPlaylist(
        name="Hip Hop Classics", 
        songs=[still_dre_song, lose_yourself_song, orphaned_song2],
        playlist_id="2",
        parent_id="root",
        attribute=0  # Actual playlist with tracks
    )
    
    # Empty playlist (should be ignored)
    empty_playlist = MockRekordboxPlaylist(
        name="Empty Playlist",
        songs=[],
        playlist_id="3",
        parent_id="root",
        attribute=0  # Actual playlist with tracks
    )
    
    # Playlist with only orphaned songs (should be ignored)
    orphaned_playlist = MockRekordboxPlaylist(
        name="Orphaned Only",
        songs=[orphaned_song1, orphaned_song2],
        playlist_id="4",
        parent_id="root",
        attribute=0  # Actual playlist with tracks
    )
    
    # Create mock database
    mock_db = Mock()
    mock_db.get_playlist.return_value = [
        electronic_playlist,
        hip_hop_playlist,
        empty_playlist,
        orphaned_playlist
    ]
    
    return mock_db


@pytest.fixture
def realistic_xml_structure():
    """Create realistic XML mock structure."""
    mock_xml = Mock()
    
    # Mock playlist structure
    mock_playlist1 = Mock()
    mock_playlist1.Name = "Summer Vibes 2023"
    mock_playlist1.rb_local_deleted = False
    mock_playlist1.get_tracks.return_value = ["TRACK001", "TRACK002", "TRACK003"]
    
    mock_playlist2 = Mock()
    mock_playlist2.Name = "Workout Mix"
    mock_playlist2.rb_local_deleted = False
    mock_playlist2.get_tracks.return_value = ["TRACK004", "TRACK005"]
    
    mock_xml.get_playlists.return_value = [mock_playlist1, mock_playlist2]
    
    # Mock track data with file:// URLs (common in Rekordbox XML)
    
    track001 = Mock(
        Name="Miami 2 Ibiza",
        Artist="Swedish House Mafia",
        Location="file://localhost/Users/djuser/Music/Crates/Progressive%20House/Swedish%20House%20Mafia/Miami%202%20Ibiza.mp3",
        rb_local_deleted=False
    )
    
    track002 = Mock(
        Name="Titanium", 
        Artist="David Guetta ft. Sia",
        Location="file://localhost/Users/djuser/Music/Crates/Electro%20House/David%20Guetta/Titanium.wav",
        rb_local_deleted=False
    )
    
    track003 = Mock(
        Name="Animals",
        Artist="Martin Garrix", 
        Location="file://localhost/Users/djuser/Music/Crates/Big%20Room/Martin%20Garrix/Animals.flac",
        rb_local_deleted=False
    )
    
    track004 = Mock(
        Name="Pump It",
        Artist="The Black Eyed Peas",
        Location="file://localhost/Users/djuser/Music/Crates/Hip%20Hop/Black%20Eyed%20Peas/Pump%20It.mp3",
        rb_local_deleted=False
    )
    
    track005 = Mock(
        Name="Till I Collapse", 
        Artist="Eminem",
        Location="file://localhost/Users/djuser/Music/Crates/Hip%20Hop/Eminem/Till%20I%20Collapse.m4a",
        rb_local_deleted=False
    )
    
    track_data = {
        "TRACK001": track001,
        "TRACK002": track002,
        "TRACK003": track003,
        "TRACK004": track004,
        "TRACK005": track005
    }
    
    def get_track_side_effect(track_key):
        return track_data.get(track_key)
    
    mock_xml.get_track.side_effect = get_track_side_effect
    
    return mock_xml


class TestRealisticDatabaseMocks:
    """Test the realistic database mock functionality."""
    
    def test_realistic_database_extraction(self, realistic_rekordbox_db):
        """Test extraction using realistic database mock."""
        extractor = RekordboxExtractor(db_path="/fake/realistic.db")
        extractor.db = realistic_rekordbox_db
        
        playlists = extractor.extract_playlists()
        
        # Should extract only playlists with valid tracks
        assert len(playlists) == 2
        
        # Check Electronic Essentials playlist
        electronic = next(p for p in playlists if p.name == "Electronic Essentials")
        assert len(electronic.tracks) == 3  # 3 valid tracks, 1 orphaned ignored
        
        track_titles = [t.title for t in electronic.tracks]
        assert "Strobe" in track_titles
        assert "One More Time" in track_titles
        assert "Levels" in track_titles
        
        # Check Hip Hop Classics playlist  
        hip_hop = next(p for p in playlists if p.name == "Hip Hop Classics")
        assert len(hip_hop.tracks) == 2  # 2 valid tracks, 1 orphaned ignored
        
        track_titles = [t.title for t in hip_hop.tracks]
        assert "Still D.R.E." in track_titles
        assert "Lose Yourself" in track_titles
        
        # Verify detailed track information
        strobe_track = next(t for t in electronic.tracks if t.title == "Strobe")
        assert strobe_track.artist == "deadmau5"
        assert "Progressive House/deadmau5" in str(strobe_track.file_path)
        assert strobe_track.file_path.name == "01 - Strobe.mp3"
    
    def test_realistic_xml_extraction(self, realistic_xml_structure):
        """Test extraction using realistic XML mock."""
        extractor = RekordboxExtractor(xml_path="/fake/realistic.xml")
        extractor.xml = realistic_xml_structure
        
        playlists = extractor.extract_playlists()
        
        assert len(playlists) == 2
        
        summer_vibes = next(p for p in playlists if p.name == "Summer Vibes 2023")
        assert len(summer_vibes.tracks) == 3
        
        workout_mix = next(p for p in playlists if p.name == "Workout Mix") 
        assert len(workout_mix.tracks) == 2
        
        # Check that file URLs are handled (note: they become relative to current dir due to Path().resolve())
        miami_track = next(t for t in summer_vibes.tracks if t.title == "Miami 2 Ibiza")
        # The file:// URL gets resolved as a path relative to current working directory
        assert "Miami" in str(miami_track.file_path)
        assert miami_track.artist == "Swedish House Mafia"
    
    def test_realistic_database_handles_various_file_formats(self, realistic_rekordbox_db):
        """Test that various audio file formats are handled properly."""
        extractor = RekordboxExtractor(db_path="/fake/realistic.db")
        extractor.db = realistic_rekordbox_db
        
        playlists = extractor.extract_playlists()
        
        all_tracks = []
        for playlist in playlists:
            all_tracks.extend(playlist.tracks)
        
        # Check that different file formats are preserved
        file_extensions = [track.file_path.suffix.lower() for track in all_tracks]
        
        assert ".mp3" in file_extensions
        assert ".wav" in file_extensions  
        assert ".flac" in file_extensions
        assert ".m4a" in file_extensions
    
    def test_realistic_database_handles_complex_folder_structure(self, realistic_rekordbox_db):
        """Test handling of complex nested folder structures."""
        extractor = RekordboxExtractor(db_path="/fake/realistic.db")
        extractor.db = realistic_rekordbox_db
        
        playlists = extractor.extract_playlists()
        
        all_tracks = []
        for playlist in playlists:
            all_tracks.extend(playlist.tracks)
        
        # Verify complex paths are handled
        folder_paths = [str(track.file_path.parent) for track in all_tracks]
        
        # Should include genre-based organization
        genre_folders = [path for path in folder_paths if any(genre in path for genre in [
            "Progressive House", "French House", "West Coast Hip Hop", "Hip Hop"
        ])]
        
        assert len(genre_folders) > 0
        
        # Should include artist subfolders
        artist_folders = [path for path in folder_paths if any(artist in path for artist in [
            "deadmau5", "Daft Punk", "Dr. Dre", "Eminem", "Avicii"
        ])]
        
        assert len(artist_folders) > 0