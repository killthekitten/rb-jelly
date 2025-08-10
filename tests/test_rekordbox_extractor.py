from pathlib import Path
from unittest.mock import Mock, patch

from rekordbox_to_jellyfin import RekordboxExtractor


class TestRekordboxExtractor:
    """Test cases for RekordboxExtractor class."""

    def test_connect_with_valid_database(self, temp_dir):
        """Test connection to valid Rekordbox database."""
        db_path = temp_dir / "test.db"
        db_path.touch()  # Create empty file

        with patch("rekordbox_to_jellyfin.Rekordbox6Database") as mock_db_class:
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

        with patch("rekordbox_to_jellyfin.RekordboxXml") as mock_xml_class:
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

        with patch("rekordbox_to_jellyfin.Rekordbox6Database") as mock_db_class:
            with patch("rekordbox_to_jellyfin.RekordboxXml") as mock_xml_class:
                mock_db_instance = Mock()
                mock_db_class.return_value = mock_db_instance

                extractor = RekordboxExtractor(
                    db_path=str(db_path), xml_path=str(xml_path)
                )
                result = extractor.connect()

                assert result is True
                assert extractor.db == mock_db_instance
                assert extractor.xml is None
                mock_db_class.assert_called_once()
                mock_xml_class.assert_not_called()

    def test_connect_with_nonexistent_files(self):
        """Test connection fails when neither file exists."""
        extractor = RekordboxExtractor(
            db_path="/nonexistent/db.db", xml_path="/nonexistent/xml.xml"
        )
        result = extractor.connect()

        assert result is False
        assert extractor.db is None
        assert extractor.xml is None

    def test_connect_handles_exceptions(self, temp_dir):
        """Test connection handles exceptions gracefully."""
        db_path = temp_dir / "test.db"
        db_path.touch()

        with patch("rekordbox_to_jellyfin.Rekordbox6Database") as mock_db_class:
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
        assert track1.file_path == Path(
            "/Users/djuser/Music/Crates/Electronic/Deadmau5/Strobe.mp3"
        )

        # Check second track
        track2 = electronic.tracks[1]
        assert track2.title == "One More Time"
        assert track2.artist == "Daft Punk"
        assert track2.file_path == Path(
            "/Users/djuser/Music/Crates/Electronic/Daft Punk/One More Time.wav"
        )

        # Check second playlist (Hip Hop)
        hip_hop = playlists[1]
        assert hip_hop.name == "Hip Hop"
        assert len(hip_hop.tracks) == 1

        track3 = hip_hop.tracks[0]
        assert track3.title == "Still D.R.E."
        assert track3.artist == "Dr. Dre"
        assert track3.file_path == Path(
            "/Users/djuser/Music/Crates/Hip Hop/Dr. Dre/Still D.R.E..flac"
        )

    def test_extract_playlists_from_xml(self):
        """Test extracting playlists from XML."""
        extractor = RekordboxExtractor(xml_path="/fake/path.xml")

        # Mock XML structure
        mock_xml = Mock()
        extractor.xml = mock_xml

        # Mock XML playlists
        mock_xml_playlist = Mock()
        mock_xml_playlist.Name = "Test Playlist"
        mock_xml_playlist.rb_local_deleted = False
        mock_xml_playlist.get_tracks.return_value = ["track1", "track2"]

        mock_xml.get_playlists.return_value = [mock_xml_playlist]

        # Mock track data
        mock_track_data1 = Mock()
        mock_track_data1.Name = "Track 1"
        mock_track_data1.Artist = "Artist 1"
        mock_track_data1.Location = "/path/to/track1.mp3"
        mock_track_data1.rb_local_deleted = False

        mock_track_data2 = Mock()
        mock_track_data2.Name = "Track 2"
        mock_track_data2.Artist = "Artist 2"
        mock_track_data2.Location = "/path/to/track2.mp3"
        mock_track_data2.rb_local_deleted = False

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
        mock_playlist.ID = "1"
        mock_playlist.ParentID = "root"
        mock_playlist.Attribute = 0
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
        mock_playlist.ID = "1"
        mock_playlist.ParentID = "root"
        mock_playlist.Attribute = 0
        mock_playlist.configure_mock(is_smart_playlist=False)
        mock_playlist.rb_local_deleted = False

        # Mock song with missing content
        mock_song_no_content = Mock()
        mock_song_no_content.Content = None

        # Mock song with valid content
        mock_song_with_content = Mock()
        mock_content = Mock()
        mock_content.Title = "Valid Song"
        mock_content.Artist = Mock()
        mock_content.Artist.Name = "Valid Artist"
        mock_content.FolderPath = "/path/to/folder/song.mp3"
        mock_content.FileNameL = "song.mp3"
        mock_content.rb_local_deleted = False
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

    @patch("rekordbox_to_jellyfin.SmartList")
    def test_extract_smart_playlists(self, mock_smartlist_class):
        """Test extracting smart playlists with XML parsing."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")

        mock_db = Mock()
        extractor.db = mock_db

        # Mock smart playlist
        mock_smart_playlist = Mock()
        mock_smart_playlist.Name = "Bass: Halfstep"
        mock_smart_playlist.ID = "smart1"
        mock_smart_playlist.ParentID = "root"
        mock_smart_playlist.Attribute = 4  # Smart playlists have Attribute=4
        # Ensure is_smart_playlist is properly set up for hasattr() check
        mock_smart_playlist.configure_mock(is_smart_playlist=True)
        mock_smart_playlist.SmartList = '<NODE Id="123" LogicalOperator="1"><CONDITION PropertyName="genre" Operator="1" ValueLeft="Halfstep"/></NODE>'
        mock_smart_playlist.rb_local_deleted = False

        # Mock regular playlist for comparison
        mock_regular_playlist = Mock()
        mock_regular_playlist.Name = "Regular Playlist"
        mock_regular_playlist.ID = "reg1"
        mock_regular_playlist.ParentID = "root"
        mock_regular_playlist.Attribute = 0
        mock_regular_playlist.configure_mock(is_smart_playlist=False)
        mock_regular_playlist.Songs = []  # Empty regular playlist
        mock_regular_playlist.rb_local_deleted = False

        mock_db.get_playlist.return_value = [mock_smart_playlist, mock_regular_playlist]

        # Mock SmartList parsing and execution
        mock_smartlist_instance = Mock()
        mock_smartlist_class.return_value = mock_smartlist_instance

        # Mock database session and query results
        mock_session = Mock()
        mock_db.session = mock_session

        # Mock smart playlist track results
        mock_track_content = Mock()
        mock_track_content.Title = "Bass Track"
        mock_track_content.Artist = Mock()
        mock_track_content.Artist.Name = "Bass Artist"
        mock_track_content.FolderPath = "/path/to/bass/track.mp3"
        mock_track_content.rb_local_deleted = False

        # Mock the SQLAlchemy query chain
        mock_query = Mock()
        mock_query.all.return_value = [mock_track_content]
        mock_session.query.return_value.filter.return_value = mock_query

        # Mock filter clause generation
        mock_filter_clause = Mock()
        mock_smartlist_instance.filter_clause.return_value = mock_filter_clause

        playlists = extractor.extract_playlists()

        # Verify SmartList was parsed
        mock_smartlist_instance.parse.assert_called_once_with(
            mock_smart_playlist.SmartList
        )

        # Should return both playlists (smart playlist now has tracks, regular is empty but included)
        assert len(playlists) == 2

        # Find the smart playlist (name gets sanitized from "Bass: Halfstep" to "Bass Halfstep")
        smart_playlist = next(p for p in playlists if p.name.endswith("Halfstep"))
        assert smart_playlist.name == "Bass Halfstep"
        assert len(smart_playlist.tracks) == 1

        # Verify smart playlist track
        track = smart_playlist.tracks[0]
        assert track.title == "Bass Track"
        assert track.artist == "Bass Artist"
        assert track.file_path == Path("/path/to/bass/track.mp3")

    @patch("rekordbox_to_jellyfin.SmartList")
    def test_extract_smart_playlist_with_parsing_error(self, mock_smartlist_class):
        """Test smart playlist extraction handles parsing errors gracefully."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")

        mock_db = Mock()
        extractor.db = mock_db

        # Mock smart playlist with invalid XML
        mock_smart_playlist = Mock()
        mock_smart_playlist.Name = "Broken Smart Playlist"
        mock_smart_playlist.ID = "broken1"
        mock_smart_playlist.ParentID = "root"
        mock_smart_playlist.Attribute = 4
        mock_smart_playlist.configure_mock(is_smart_playlist=True)
        mock_smart_playlist.SmartList = "invalid xml"
        mock_smart_playlist.rb_local_deleted = False

        mock_db.get_playlist.return_value = [mock_smart_playlist]

        # Mock SmartList parsing to raise exception
        mock_smartlist_instance = Mock()
        mock_smartlist_class.return_value = mock_smartlist_instance
        mock_smartlist_instance.parse.side_effect = Exception("XML parsing failed")

        # Mock database session
        mock_db.session = Mock()

        playlists = extractor.extract_playlists()

        # Should return playlist but with no tracks due to parsing error
        assert len(playlists) == 1
        playlist = playlists[0]
        assert playlist.name == "Broken Smart Playlist"
        assert len(playlist.tracks) == 0

    @patch("rekordbox_to_jellyfin.SmartList")
    def test_extract_smart_playlist_with_no_smartlist_data(self, mock_smartlist_class):
        """Test smart playlist extraction when SmartList is None or empty."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")

        mock_db = Mock()
        extractor.db = mock_db

        # Mock smart playlist with no SmartList data
        mock_smart_playlist = Mock()
        mock_smart_playlist.Name = "Empty Smart Playlist"
        mock_smart_playlist.ID = "empty1"
        mock_smart_playlist.ParentID = "root"
        mock_smart_playlist.Attribute = 4
        mock_smart_playlist.configure_mock(is_smart_playlist=True)
        mock_smart_playlist.SmartList = None  # No smart list data
        mock_smart_playlist.rb_local_deleted = False

        mock_db.get_playlist.return_value = [mock_smart_playlist]
        mock_db.session = Mock()

        playlists = extractor.extract_playlists()

        # Should return playlist but with no tracks
        assert len(playlists) == 1
        playlist = playlists[0]
        assert playlist.name == "Empty Smart Playlist"
        assert len(playlist.tracks) == 0

        # SmartList should not be instantiated
        mock_smartlist_class.assert_not_called()

    @patch("rekordbox_to_jellyfin.SmartList")
    def test_extract_mixed_regular_and_smart_playlists(self, mock_smartlist_class):
        """Test extracting a mix of regular and smart playlists."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")

        mock_db = Mock()
        extractor.db = mock_db

        # Mock regular playlist with tracks
        mock_regular_playlist = Mock()
        mock_regular_playlist.Name = "Regular Playlist"
        mock_regular_playlist.ID = "reg1"
        mock_regular_playlist.ParentID = "root"
        mock_regular_playlist.Attribute = 0
        mock_regular_playlist.configure_mock(is_smart_playlist=False)

        # Mock regular playlist song
        mock_song = Mock()
        mock_content = Mock()
        mock_content.Title = "Regular Song"
        mock_content.Artist = Mock()
        mock_content.Artist.Name = "Regular Artist"
        mock_content.FolderPath = "/path/to/regular/song.mp3"
        mock_content.rb_local_deleted = False
        mock_song.Content = mock_content
        mock_regular_playlist.Songs = [mock_song]
        mock_regular_playlist.rb_local_deleted = False

        # Mock smart playlist
        mock_smart_playlist = Mock()
        mock_smart_playlist.Name = "Smart Playlist"
        mock_smart_playlist.ID = "smart1"
        mock_smart_playlist.ParentID = "root"
        mock_smart_playlist.Attribute = 4
        mock_smart_playlist.configure_mock(is_smart_playlist=True)
        mock_smart_playlist.SmartList = (
            '<NODE><CONDITION PropertyName="bpm" Operator="2" ValueLeft="140"/></NODE>'
        )
        mock_smart_playlist.rb_local_deleted = False

        mock_db.get_playlist.return_value = [mock_regular_playlist, mock_smart_playlist]

        # Mock SmartList execution
        mock_smartlist_instance = Mock()
        mock_smartlist_class.return_value = mock_smartlist_instance

        mock_session = Mock()
        mock_db.session = mock_session

        # Mock smart playlist results
        mock_smart_content = Mock()
        mock_smart_content.Title = "Smart Song"
        mock_smart_content.Artist = Mock()
        mock_smart_content.Artist.Name = "Smart Artist"
        mock_smart_content.FolderPath = "/path/to/smart/song.mp3"
        mock_smart_content.rb_local_deleted = False

        mock_query = Mock()
        mock_query.all.return_value = [mock_smart_content]
        mock_session.query.return_value.filter.return_value = mock_query

        playlists = extractor.extract_playlists()

        assert len(playlists) == 2

        # Find regular playlist
        regular_playlist = next(p for p in playlists if p.name == "Regular Playlist")
        assert len(regular_playlist.tracks) == 1
        assert regular_playlist.tracks[0].title == "Regular Song"

        # Find smart playlist
        smart_playlist = next(p for p in playlists if p.name == "Smart Playlist")
        assert len(smart_playlist.tracks) == 1
        assert smart_playlist.tracks[0].title == "Smart Song"

    def test_extract_smart_playlist_skips_deleted_tracks(self):
        """Test smart playlist extraction skips deleted tracks."""
        extractor = RekordboxExtractor(db_path="/fake/path.db")

        mock_db = Mock()
        extractor.db = mock_db

        with patch("rekordbox_to_jellyfin.SmartList") as mock_smartlist_class:
            # Mock smart playlist
            mock_smart_playlist = Mock()
            mock_smart_playlist.Name = "Smart with Deleted"
            mock_smart_playlist.ID = "smart_del"
            mock_smart_playlist.ParentID = "root"
            mock_smart_playlist.Attribute = 4
            mock_smart_playlist.configure_mock(is_smart_playlist=True)
            mock_smart_playlist.SmartList = "<NODE><CONDITION/></NODE>"
            mock_smart_playlist.rb_local_deleted = False

            mock_db.get_playlist.return_value = [mock_smart_playlist]

            # Mock SmartList
            mock_smartlist_instance = Mock()
            mock_smartlist_class.return_value = mock_smartlist_instance

            mock_session = Mock()
            mock_db.session = mock_session

            # Mock tracks - one deleted, one valid
            mock_deleted_track = Mock()
            mock_deleted_track.rb_local_deleted = True
            mock_deleted_track.Title = "Deleted Song"

            mock_valid_track = Mock()
            mock_valid_track.rb_local_deleted = False
            mock_valid_track.Title = "Valid Song"
            mock_valid_track.Artist = Mock()
            mock_valid_track.Artist.Name = "Valid Artist"
            mock_valid_track.FolderPath = "/path/to/valid.mp3"

            mock_query = Mock()
            mock_query.all.return_value = [mock_deleted_track, mock_valid_track]
            mock_session.query.return_value.filter.return_value = mock_query

            playlists = extractor.extract_playlists()

            assert len(playlists) == 1
            playlist = playlists[0]
            assert len(playlist.tracks) == 1  # Only valid track
            assert playlist.tracks[0].title == "Valid Song"
