import pytest
from pathlib import Path
from typing import List
from unittest.mock import Mock
import tempfile
import shutil

from rekordbox_to_jellyfin import Track, Playlist, RekordboxExtractor, PathConverter, PlaylistGenerator


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_tracks():
    """Create sample tracks for testing."""
    return [
        Track(
            title="Track 1",
            artist="Artist 1", 
            file_path=Path("/music/Artist 1/Album 1/Track 1.mp3"),
            playlist_path="Test Playlist"
        ),
        Track(
            title="Track 2", 
            artist="Artist 2",
            file_path=Path("/music/Artist 2/Album 2/Track 2.flac"),
            playlist_path="Test Playlist"
        ),
        Track(
            title="Track 3",
            artist="Artist 1",
            file_path=Path("/music/Artist 1/Album 2/Track 3.wav"),
            playlist_path="Test Playlist"
        )
    ]


@pytest.fixture  
def sample_playlists(sample_tracks):
    """Create sample playlists for testing."""
    return [
        Playlist(
            name="Electronic",
            path="Electronic", 
            tracks=sample_tracks[:2],
            children=[]
        ),
        Playlist(
            name="Hip Hop",
            path="Hip Hop",
            tracks=[sample_tracks[2]],
            children=[]
        )
    ]


@pytest.fixture
def mock_rekordbox_db():
    """Mock Rekordbox database with realistic data structure."""
    mock_db = Mock()
    
    # Mock playlist data
    mock_playlist1 = Mock()
    mock_playlist1.Name = "Electronic"
    
    # Mock songs in playlist
    mock_song1 = Mock()
    mock_content1 = Mock()
    mock_content1.Title = "Strobe"
    mock_content1.Artist = Mock()
    mock_content1.Artist.Name = "Deadmau5"
    mock_content1.FolderPath = "/Users/djuser/Music/Crates/Electronic/Deadmau5"
    mock_content1.Filename = "Strobe.mp3"
    mock_song1.Content = mock_content1
    
    mock_song2 = Mock()
    mock_content2 = Mock()
    mock_content2.Title = "One More Time"
    mock_content2.Artist = Mock()
    mock_content2.Artist.Name = "Daft Punk"
    mock_content2.FolderPath = "/Users/djuser/Music/Crates/Electronic/Daft Punk"
    mock_content2.Filename = "One More Time.wav"
    mock_song2.Content = mock_content2
    
    mock_playlist1.Songs = [mock_song1, mock_song2]
    
    # Mock second playlist
    mock_playlist2 = Mock()
    mock_playlist2.Name = "Hip Hop"
    
    mock_song3 = Mock() 
    mock_content3 = Mock()
    mock_content3.Title = "Still D.R.E."
    mock_content3.Artist = Mock()
    mock_content3.Artist.Name = "Dr. Dre"
    mock_content3.FolderPath = "/Users/djuser/Music/Crates/Hip Hop/Dr. Dre"
    mock_content3.Filename = "Still D.R.E..flac"
    mock_song3.Content = mock_content3
    
    mock_playlist2.Songs = [mock_song3]
    
    mock_db.get_playlist.return_value = [mock_playlist1, mock_playlist2]
    return mock_db


@pytest.fixture
def crates_root(temp_dir):
    """Create a mock Crates directory structure."""
    crates_dir = temp_dir / "Crates"
    crates_dir.mkdir()
    
    # Create some sample directories and files
    (crates_dir / "Electronic" / "Deadmau5").mkdir(parents=True)
    (crates_dir / "Electronic" / "Daft Punk").mkdir(parents=True)
    (crates_dir / "Hip Hop" / "Dr. Dre").mkdir(parents=True)
    
    # Create some sample music files
    (crates_dir / "Electronic" / "Deadmau5" / "Strobe.mp3").touch()
    (crates_dir / "Electronic" / "Daft Punk" / "One More Time.wav").touch()
    (crates_dir / "Hip Hop" / "Dr. Dre" / "Still D.R.E..flac").touch()
    
    return str(crates_dir)