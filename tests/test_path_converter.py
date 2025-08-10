import pytest
from pathlib import Path

from rekordbox_to_jellyfin import PathConverter


class TestPathConverter:
    """Test cases for PathConverter class."""
    
    def test_validate_and_convert_path_valid_path(self, crates_root):
        """Test path validation and conversion for paths within Crates directory."""
        converter = PathConverter(crates_root, "/data/music")
        
        test_path = Path(crates_root) / "Electronic" / "Deadmau5" / "Strobe.mp3"
        result = converter.validate_and_convert_path(test_path)
        
        assert result == "/data/music/Electronic/Deadmau5/Strobe.mp3"
        assert len(converter.get_invalid_paths()) == 0
    
    def test_validate_and_convert_path_invalid_path_outside_crates(self, crates_root):
        """Test path validation rejects paths outside Crates directory."""
        converter = PathConverter(crates_root, "/data/music")
        
        # Path outside of crates directory
        invalid_path = Path("/some/other/directory/track.mp3")
        result = converter.validate_and_convert_path(invalid_path)
        
        assert result is None
        invalid_paths = converter.get_invalid_paths()
        assert len(invalid_paths) == 1
        assert str(invalid_path) in invalid_paths
    
    def test_validate_and_convert_path_relative_path(self, crates_root):
        """Test path validation with relative paths that resolve within Crates."""
        converter = PathConverter(crates_root, "/data/music")
        
        # Create a relative path that resolves within crates
        crates_path = Path(crates_root)
        relative_path = crates_path / "Hip Hop" / ".." / "Electronic" / "Deadmau5" / "Strobe.mp3"
        
        result = converter.validate_and_convert_path(relative_path)
        
        assert result == "/data/music/Electronic/Deadmau5/Strobe.mp3"
        assert len(converter.get_invalid_paths()) == 0
    
    def test_validate_and_convert_path_symlink_outside_crates(self, temp_dir, crates_root):
        """Test that symlinks pointing outside Crates are rejected."""
        converter = PathConverter(crates_root, "/data/music")
        
        # Create a directory outside crates
        outside_dir = temp_dir / "outside_crates"
        outside_dir.mkdir()
        outside_file = outside_dir / "external_track.mp3"
        outside_file.touch()
        
        # Create symlink inside crates pointing to external file
        crates_path = Path(crates_root)
        symlink_path = crates_path / "Electronic" / "symlinked_track.mp3"
        
        try:
            symlink_path.symlink_to(outside_file)
            result = converter.validate_and_convert_path(symlink_path)
            
            # Should be rejected because it resolves outside crates
            assert result is None
            invalid_paths = converter.get_invalid_paths()
            assert len(invalid_paths) == 1
        except OSError:
            # Skip test if symlinks aren't supported on this system
            pytest.skip("Symlinks not supported")
    
    def test_validate_and_convert_path_custom_jellyfin_root(self, crates_root):
        """Test path conversion with custom Jellyfin root path."""
        custom_root = "/custom/music/path"
        converter = PathConverter(crates_root, custom_root)
        
        test_path = Path(crates_root) / "Hip Hop" / "Dr. Dre" / "Still D.R.E..flac"
        result = converter.validate_and_convert_path(test_path)
        
        assert result == "/custom/music/path/Hip Hop/Dr. Dre/Still D.R.E..flac"
    
    def test_validate_and_convert_path_handles_exceptions(self, crates_root):
        """Test that path validation handles exceptions gracefully."""
        converter = PathConverter(crates_root, "/data/music")
        
        # Create a Mock path that raises exception on resolve()
        from unittest.mock import Mock
        mock_path = Mock(spec=Path)
        mock_path.resolve.side_effect = OSError("Simulated error")
        
        result = converter.validate_and_convert_path(mock_path)
        
        assert result is None
    
    def test_get_invalid_paths_returns_copy(self, crates_root):
        """Test that get_invalid_paths returns a copy, not reference to internal set."""
        converter = PathConverter(crates_root, "/data/music")
        
        # Add some invalid paths
        invalid_path1 = Path("/invalid/path1.mp3")
        invalid_path2 = Path("/invalid/path2.mp3")
        
        converter.validate_and_convert_path(invalid_path1)
        converter.validate_and_convert_path(invalid_path2)
        
        invalid_paths = converter.get_invalid_paths()
        original_len = len(invalid_paths)
        
        # Modify returned set
        invalid_paths.add("new_path")
        
        # Original should be unchanged
        assert len(converter.get_invalid_paths()) == original_len
        assert "new_path" not in converter.get_invalid_paths()
    
    def test_validate_and_convert_handles_unicode_paths(self, temp_dir):
        """Test path validation with Unicode characters in filenames."""
        # Create crates directory with Unicode filename
        crates_dir = temp_dir / "Crates"
        crates_dir.mkdir()
        
        unicode_dir = crates_dir / "电子音乐"  # "Electronic Music" in Chinese
        unicode_dir.mkdir()
        unicode_file = unicode_dir / "测试歌曲.mp3"  # "Test Song" in Chinese
        unicode_file.touch()
        
        converter = PathConverter(str(crates_dir), "/data/music")
        result = converter.validate_and_convert_path(unicode_file)
        
        assert result == "/data/music/电子音乐/测试歌曲.mp3"
        assert len(converter.get_invalid_paths()) == 0