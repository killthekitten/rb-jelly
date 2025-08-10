import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from rekordbox_to_jellyfin import Playlist, Track


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
            playlist_path="Test Playlist",
        ),
        Track(
            title="Track 2",
            artist="Artist 2",
            file_path=Path("/music/Artist 2/Album 2/Track 2.flac"),
            playlist_path="Test Playlist",
        ),
        Track(
            title="Track 3",
            artist="Artist 1",
            file_path=Path("/music/Artist 1/Album 2/Track 3.wav"),
            playlist_path="Test Playlist",
        ),
    ]


@pytest.fixture
def sample_playlists(sample_tracks):
    """Create sample playlists for testing."""
    return [
        Playlist(
            name="Electronic", path="Electronic", tracks=sample_tracks[:2], children=[]
        ),
        Playlist(
            name="Hip Hop", path="Hip Hop", tracks=[sample_tracks[2]], children=[]
        ),
    ]


@pytest.fixture
def mock_rekordbox_db():
    """Mock Rekordbox database with realistic data structure."""
    mock_db = Mock()

    # Mock playlist data
    mock_playlist1 = Mock()
    mock_playlist1.Name = "Electronic"
    mock_playlist1.ID = "1"
    mock_playlist1.ParentID = "root"
    mock_playlist1.Attribute = 0  # 0 = actual playlist with tracks
    mock_playlist1.configure_mock(is_smart_playlist=False)
    mock_playlist1.rb_local_deleted = False

    # Mock songs in playlist
    mock_song1 = Mock()
    mock_content1 = Mock()
    mock_content1.Title = "Strobe"
    mock_content1.Artist = Mock()
    mock_content1.Artist.Name = "Deadmau5"
    mock_content1.FolderPath = (
        "/Users/djuser/Music/Crates/Electronic/Deadmau5/Strobe.mp3"
    )
    mock_content1.FileNameL = "Strobe.mp3"  # Use correct attribute name
    mock_content1.rb_local_deleted = False
    mock_song1.Content = mock_content1

    mock_song2 = Mock()
    mock_content2 = Mock()
    mock_content2.Title = "One More Time"
    mock_content2.Artist = Mock()
    mock_content2.Artist.Name = "Daft Punk"
    mock_content2.FolderPath = (
        "/Users/djuser/Music/Crates/Electronic/Daft Punk/One More Time.wav"
    )
    mock_content2.FileNameL = "One More Time.wav"  # Use correct attribute name
    mock_content2.rb_local_deleted = False
    mock_song2.Content = mock_content2

    mock_playlist1.Songs = [mock_song1, mock_song2]

    # Mock second playlist
    mock_playlist2 = Mock()
    mock_playlist2.Name = "Hip Hop"
    mock_playlist2.ID = "2"
    mock_playlist2.ParentID = "root"
    mock_playlist2.Attribute = 0  # 0 = actual playlist with tracks
    mock_playlist2.configure_mock(is_smart_playlist=False)
    mock_playlist2.rb_local_deleted = False

    mock_song3 = Mock()
    mock_content3 = Mock()
    mock_content3.Title = "Still D.R.E."
    mock_content3.Artist = Mock()
    mock_content3.Artist.Name = "Dr. Dre"
    mock_content3.FolderPath = (
        "/Users/djuser/Music/Crates/Hip Hop/Dr. Dre/Still D.R.E..flac"
    )
    mock_content3.FileNameL = "Still D.R.E..flac"  # Use correct attribute name
    mock_content3.rb_local_deleted = False
    mock_song3.Content = mock_content3

    mock_playlist2.Songs = [mock_song3]

    mock_db.get_playlist.return_value = [mock_playlist1, mock_playlist2]
    return mock_db


@pytest.fixture
def mock_rekordbox_db_with_smart_playlists():
    """Mock Rekordbox database with both regular and smart playlists."""
    mock_db = Mock()

    # Mock regular playlist
    mock_playlist1 = Mock()
    mock_playlist1.Name = "Regular Playlist"
    mock_playlist1.ID = "1"
    mock_playlist1.ParentID = "root"
    mock_playlist1.Attribute = 0
    mock_playlist1.configure_mock(is_smart_playlist=False)
    mock_playlist1.rb_local_deleted = False

    # Mock song in regular playlist
    mock_song = Mock()
    mock_content = Mock()
    mock_content.Title = "Regular Song"
    mock_content.Artist = Mock()
    mock_content.Artist.Name = "Regular Artist"
    mock_content.FolderPath = "/music/regular.mp3"
    mock_content.rb_local_deleted = False
    mock_song.Content = mock_content
    mock_playlist1.Songs = [mock_song]

    # Mock smart playlist
    mock_smart_playlist = Mock()
    mock_smart_playlist.Name = "Bass: Halfstep"
    mock_smart_playlist.ID = "2"
    mock_smart_playlist.ParentID = "root"
    mock_smart_playlist.Attribute = 4  # Smart playlists have Attribute=4
    mock_smart_playlist.configure_mock(is_smart_playlist=True)
    mock_smart_playlist.SmartList = (
        '<NODE Id="123" LogicalOperator="1" AutomaticUpdate="0">'
        '<CONDITION PropertyName="genre" Operator="1" ValueUnit="" ValueLeft="Halfstep" ValueRight=""/>'
        "</NODE>"
    )
    mock_smart_playlist.rb_local_deleted = False

    # Mock database session for smart playlist queries
    mock_session = Mock()
    mock_db.session = mock_session

    # Mock smart playlist query results
    mock_smart_content = Mock()
    mock_smart_content.Title = "Halfstep Track"
    mock_smart_content.Artist = Mock()
    mock_smart_content.Artist.Name = "Bass Artist"
    mock_smart_content.FolderPath = "/music/bass/halfstep.mp3"
    mock_smart_content.rb_local_deleted = False

    mock_query = Mock()
    mock_query.all.return_value = [mock_smart_content]
    mock_session.query.return_value.filter.return_value = mock_query

    mock_db.get_playlist.return_value = [mock_playlist1, mock_smart_playlist]
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
