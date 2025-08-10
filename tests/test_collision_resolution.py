"""
Comprehensive test suite for collision resolution and filename sanitization.

Tests the UniqueNameResolver class and its integration with the playlist
generation system to ensure that sanitized filenames remain unique.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
import tempfile
import shutil

from rekordbox_to_jellyfin import (
    UniqueNameResolver, Track, Playlist, PlaylistGenerator, PathConverter
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def crates_root(temp_dir):
    """Create a mock Crates directory structure."""
    crates_path = temp_dir / "crates"
    crates_path.mkdir()
    
    # Create some test files
    (crates_path / "subdir").mkdir()
    (crates_path / "test_file.mp3").touch()
    (crates_path / "subdir" / "nested_file.mp3").touch()
    
    return crates_path


class TestUniqueNameResolver:
    """Test the UniqueNameResolver class."""
    
    @pytest.fixture
    def resolver(self):
        """Create a fresh resolver for each test."""
        return UniqueNameResolver()
    
    def test_basic_sanitization(self, resolver):
        """Test basic filename sanitization without collisions."""
        test_cases = [
            ("Normal Name", "Normal Name"),
            ("Plugin ears / Hovercat", "Plugin ears  Hovercat"),
            ("Test*Name?Here", "TestNameHere"),
            ("File<>Name", "FileName"),
            ('Quote"Name', "QuoteName"),
            ("Pipe|Name", "PipeName"),
            ("Colon:Name", "ColonName"),
        ]
        
        for original, expected in test_cases:
            result = resolver.get_unique_name(original)
            assert result == expected, f"Expected '{expected}' for '{original}', got '{result}'"
    
    def test_collision_resolution(self, resolver):
        """Test collision resolution with duplicate sanitized names."""
        # First occurrence gets the base name
        first = resolver.get_unique_name("Plugin ears / Hovercat")
        assert first == "Plugin ears  Hovercat"
        
        # Second occurrence with same sanitized result gets (1) suffix
        second = resolver.get_unique_name("Plugin ears  Hovercat")
        assert second == "Plugin ears  Hovercat (1)"
        
        # Third occurrence with different sanitized result (pathvalidate removes double slashes differently)
        third = resolver.get_unique_name("Plugin ears//Hovercat")  # Sanitizes to "Plugin earsHovercat"
        assert third == "Plugin earsHovercat"  # Different from first two, so no collision
    
    def test_duplicate_inputs(self, resolver):
        """Test that identical inputs return identical results."""
        original_name = "Plugin ears / Hovercat"
        
        # Call multiple times with same input
        result1 = resolver.get_unique_name(original_name)
        result2 = resolver.get_unique_name(original_name)
        result3 = resolver.get_unique_name(original_name)
        
        # Should all return the same result
        assert result1 == result2 == result3 == "Plugin ears  Hovercat"
    
    def test_complex_collision_scenario(self, resolver):
        """Test complex scenario with multiple collision types."""
        test_inputs = [
            "Test*Name",      # Sanitizes to "TestName"
            "Test Name",      # Already clean
            "Test?Name",      # Sanitizes to "TestName" - collision with first
            "Test<>Name",     # Sanitizes to "TestName" - collision  
            "Test Name",      # Duplicate input - should return same as second
        ]
        
        expected_results = [
            "TestName",       # First unique
            "Test Name",      # No collision
            "TestName (1)",   # First collision
            "TestName (2)",   # Second collision
            "Test Name",      # Duplicate returns cached result
        ]
        
        results = [resolver.get_unique_name(name) for name in test_inputs]
        assert results == expected_results
    
    def test_empty_and_special_names(self, resolver):
        """Test edge cases like empty strings and special names."""
        # Test empty string - pathvalidate returns empty string, our resolver should handle this
        empty_result = resolver.get_unique_name("")
        # Our resolver should generate a fallback name for empty strings
        assert len(empty_result) > 0, "Empty string should generate a non-empty result"
        
        # Test whitespace only
        whitespace_result = resolver.get_unique_name("   ")
        assert len(whitespace_result) > 0, "Whitespace should generate a non-empty result"
        
        # Test reserved names (Windows reserved names) - pathvalidate should handle these
        reserved_names = ["CON", "PRN", "AUX", "NUL"]
        for reserved in reserved_names:
            result = resolver.get_unique_name(reserved)
            # pathvalidate should sanitize Windows reserved names
            assert result != reserved, f"Reserved name '{reserved}' should be sanitized, got '{result}'"
    
    def test_very_long_names(self, resolver):
        """Test handling of very long playlist names."""
        long_name = "A" * 300  # Very long name
        result = resolver.get_unique_name(long_name)
        
        # Should be sanitized and not cause issues
        assert len(result) > 0
        assert isinstance(result, str)
    
    def test_unicode_and_international_names(self, resolver):
        """Test Unicode and international characters."""
        unicode_names = [
            "Späti Night",
            "Café Music",
            "東京 Night",
            "Москва Beats",
            "🎵 Music 🎵",
        ]
        
        for name in unicode_names:
            result = resolver.get_unique_name(name)
            assert len(result) > 0, f"Unicode name '{name}' should produce valid result"
            assert isinstance(result, str)


class TestPluginEarsCollisionScenario:
    """Test the specific Plugin ears / Hovercat scenario mentioned by the user."""
    
    def test_plugin_ears_collision_scenario(self):
        """Test the specific Plugin ears / Hovercat scenario mentioned."""
        resolver = UniqueNameResolver()
        
        # Simulate having both variations in Rekordbox
        names = [
            "Plugin ears / Hovercat",     # Sanitizes to "Plugin ears  Hovercat" 
            "Plugin ears  Hovercat",      # Already has double space - collision!
            "Plugin ears// Hovercat",     # Sanitizes to "Plugin ears Hovercat" (different)
        ]
        
        results = [resolver.get_unique_name(name) for name in names]
        
        # Should get unique names
        assert len(set(results)) == 3, f"All results should be unique: {results}"
        
        # First should be base sanitized name
        assert results[0] == "Plugin ears  Hovercat"
        
        # Second should get collision suffix since it sanitizes to the same thing
        assert results[1] == "Plugin ears  Hovercat (1)", f"Second result should have suffix: {results[1]}"
        
        # Third should be different (pathvalidate handles // differently than single /)
        assert "Plugin ears" in results[2] and "Hovercat" in results[2], f"Third result should contain expected parts: {results[2]}"


class TestHierarchicalUniqueness:
    """Test that names only need to be unique within their folder level."""
    
    def test_hierarchical_uniqueness(self):
        """Test that names only need to be unique within their folder level."""
        # Same name in different folders should be allowed
        root_resolver = UniqueNameResolver()
        folder_resolver = UniqueNameResolver()
        
        # Same name in root and in folder should both work without collision
        root_name = root_resolver.get_unique_name("Duplicate Name")
        folder_name = folder_resolver.get_unique_name("Duplicate Name")
        
        # Both should get the same clean name since they're in different contexts
        assert root_name == "Duplicate Name"
        assert folder_name == "Duplicate Name"
    
    def test_complex_hierarchy_with_collisions(self):
        """Test complex hierarchy with multiple levels and collisions."""
        resolvers = {
            "root": UniqueNameResolver(),
            "Sessions": UniqueNameResolver(),
            "UKG": UniqueNameResolver(),
        }
        
        # Test names that would cause collisions in each level
        test_scenarios = [
            ("root", "Test*Playlist", "TestPlaylist"),
            ("root", "Test Playlist", "Test Playlist"),
            ("root", "Test?Playlist", "TestPlaylist (1)"),  # Collision with first
            ("Sessions", "Test*Playlist", "TestPlaylist"),  # Same name, different context
            ("Sessions", "Test/Playlist", "TestPlaylist (1)"),  # Collision in Sessions context
            ("UKG", "Test*Playlist", "TestPlaylist"),  # Same name, different context again
        ]
        
        for context, input_name, expected in test_scenarios:
            result = resolvers[context].get_unique_name(input_name)
            assert result == expected, f"Failed for {input_name} in {context}: got {result}, expected {expected}"


class TestExtremeCollisionScenarios:
    """Test scenarios with many collisions."""
    
    def test_extreme_collision_scenario(self):
        """Test scenario with many collisions."""
        resolver = UniqueNameResolver()
        
        # Create 10 names that all sanitize to the same thing
        problematic_names = [
            "Test*Name",
            "Test?Name", 
            "Test<Name",
            "Test>Name",
            "Test:Name",
            "Test\"Name",
            "Test|Name",
            "Test\\Name",
            "Test/Name",
            "Test//Name"
        ]
        
        results = [resolver.get_unique_name(name) for name in problematic_names]
        
        # All results should be unique
        assert len(results) == len(set(results)), f"All results should be unique: {results}"
        
        # First should be base name, others should have incremental suffixes
        assert results[0] == "TestName"
        for i, result in enumerate(results[1:], 1):
            assert result == f"TestName ({i})", f"Result {i} should be 'TestName ({i})', got '{result}'"


class TestIntegrationWithPlaylistGenerator:
    """Integration tests with the playlist generation system."""
    
    def test_playlist_structure_creation_with_collisions(self, temp_dir, crates_root):
        """Test creating playlist structure when collision resolution is needed."""
        output_dir = temp_dir / "output"
        
        # Create playlists that would cause naming collisions
        collision_playlists = [
            Playlist(
                name="Plugin ears / Hovercat",  # Will be sanitized
                path="",
                tracks=[Track("Track 1", "Artist 1", crates_root / "test_file.mp3", "Plugin ears / Hovercat")],
                children=[]
            ),
            Playlist(
                name="Plugin ears  Hovercat",  # Collision after sanitization
                path="",
                tracks=[Track("Track 2", "Artist 2", crates_root / "test_file.mp3", "Plugin ears  Hovercat")],
                children=[]
            ),
        ]
        
        # Mock path converter
        mock_path_converter = Mock()
        mock_path_converter.validate_and_convert_path.return_value = "/data/music/test_file.mp3"
        
        # Generate playlists
        generator = PlaylistGenerator(str(output_dir))
        generator.clean_output_directory()
        
        created = generator.create_playlist_structure(collision_playlists, mock_path_converter)
        
        # Should create unique files
        assert len(created) == 2
        created_names = list(created.keys())
        assert len(set(created_names)) == 2, f"Created playlist names should be unique: {created_names}"
    
    def test_nested_playlist_collision_resolution(self, temp_dir, crates_root):
        """Test collision resolution in nested playlist structures."""
        output_dir = temp_dir / "output"
        
        # Create nested playlists that would cause collisions within a folder
        nested_playlists = [
            Playlist(
                name="Test*Name",  # Will sanitize to "TestName"
                path="Sessions",
                tracks=[Track("Track 1", "Artist 1", crates_root / "test_file.mp3", "Test*Name")],
                children=[]
            ),
            Playlist(
                name="Test?Name",  # Will also sanitize to "TestName" - collision!
                path="Sessions", 
                tracks=[Track("Track 2", "Artist 2", crates_root / "test_file.mp3", "Test?Name")],
                children=[]
            ),
        ]
        
        # Mock path converter
        mock_path_converter = Mock()
        mock_path_converter.validate_and_convert_path.return_value = "/data/music/test_file.mp3"
        
        # Generate playlists
        generator = PlaylistGenerator(str(output_dir))
        generator.clean_output_directory()
        
        created = generator.create_playlist_structure(nested_playlists, mock_path_converter)
        
        # Should create unique files in the Sessions folder
        assert len(created) == 2
        sessions_files = [name for name in created.keys() if name.startswith("Sessions/")]
        assert len(sessions_files) == 2
        
        # The playlist files should have unique names
        playlist_names = [name.split("/")[1] for name in sessions_files]
        assert len(set(playlist_names)) == 2, f"Playlist names in Sessions folder should be unique: {playlist_names}"


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_pathvalidate_integration(self):
        """Test integration with pathvalidate library."""
        from pathvalidate import sanitize_filename
        
        resolver = UniqueNameResolver()
        
        # Test that our resolver uses pathvalidate correctly
        test_name = "Test<>:|?*Name"
        our_result = resolver.get_unique_name(test_name)
        pathvalidate_result = sanitize_filename(test_name)
        
        # Our result should match pathvalidate for the first occurrence
        assert our_result == pathvalidate_result
    
    def test_memory_efficiency(self):
        """Test that the resolver doesn't consume excessive memory."""
        resolver = UniqueNameResolver()
        
        # Add many names and check that data structures don't grow unbounded
        for i in range(1000):
            resolver.get_unique_name(f"Name {i}")
        
        # Should have exactly 1000 entries in each structure
        assert len(resolver.name_mapping) == 1000
        assert len(resolver.used_names) == 1000
    
    def test_consistency_across_runs(self):
        """Test that results are consistent across multiple resolver instances."""
        names_to_test = [
            "Plugin ears / Hovercat",
            "Test*Name?Here",
            "Normal Name",
            "Another / Name"
        ]
        
        # Run with first resolver
        resolver1 = UniqueNameResolver()
        results1 = [resolver1.get_unique_name(name) for name in names_to_test]
        
        # Run with second resolver
        resolver2 = UniqueNameResolver()
        results2 = [resolver2.get_unique_name(name) for name in names_to_test]
        
        # Results should be identical
        assert results1 == results2


class TestRealWorldScenarios:
    """Test real-world scenarios from actual usage."""
    
    def test_stream_w_hovercat_sanitization(self):
        """Test sanitization of real playlist names from the user's database."""
        resolver = UniqueNameResolver()
        
        real_names = [
            "2024-05-18 Stream w/ Hovercat",
            "Plugin ears / Hovercat", 
            "2024-07-13 Flakturm B2B Hovercat",
        ]
        
        results = [resolver.get_unique_name(name) for name in real_names]
        
        # Should all be unique and properly sanitized
        assert len(set(results)) == len(results), f"All results should be unique: {results}"
        
        # Check specific expected sanitizations
        assert "2024-05-18 Stream w Hovercat" in results  # / becomes space
        assert "Plugin ears  Hovercat" in results         # / becomes space
        assert "2024-07-13 Flakturm B2B Hovercat" in results  # No change needed
    
    def test_german_and_special_characters(self):
        """Test German characters and special names from user's database."""
        resolver = UniqueNameResolver()
        
        german_names = [
            "2025-06-21 Späti Night",
            "2025-06-21 Späti Day", 
            "2025-06-21 Späti Grime Instrumentals",
            "2025-03-22 Der Kegel",
        ]
        
        results = [resolver.get_unique_name(name) for name in german_names]
        
        # Should preserve German characters and be unique
        assert len(set(results)) == len(results)
        for result in results:
            assert "Späti" in result or "Der Kegel" in result