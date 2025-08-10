# Testing Guide for Rekordbox to Jellyfin Migration Script

This directory contains comprehensive tests for the Rekordbox to Jellyfin migration functionality.

## Setup

Install test dependencies:
```bash
pip install -r requirements.txt
```

## Running Tests

Run all tests:
```bash
python -m pytest
```

Run with verbose output:
```bash
python -m pytest -v
```

Run specific test file:
```bash
python -m pytest tests/test_playlist_generator.py -v
```

Run specific test:
```bash
python -m pytest tests/test_playlist_generator.py::TestPlaylistGenerator::test_create_playlist_structure_generates_m3u_files -v
```

## Test Structure

### Core Test Files

- **`test_playlist_generator.py`** - Tests for M3U playlist generation and file structure creation
- **`test_path_converter.py`** - Tests for path validation and conversion from Crates to Jellyfin paths  
- **`test_rekordbox_extractor.py`** - Tests for Rekordbox database and XML extraction
- **`test_real_database_mock.py`** - Realistic mock data based on actual Rekordbox database structure

### Test Fixtures

**`conftest.py`** provides shared fixtures:
- `temp_dir` - Temporary directory for file operations
- `sample_tracks` - Basic track data for testing
- `sample_playlists` - Basic playlist structures
- `mock_rekordbox_db` - Mock database with realistic structure
- `crates_root` - Mock Crates directory with sample files

## Key Test Features

### Path Security Testing
Tests verify that the path validation correctly:
- Accepts files within the Crates directory
- Rejects files outside the Crates directory (security feature)
- Handles symlinks and relative paths correctly
- Supports Unicode filenames

### Playlist Generation Testing
Tests verify that M3U playlists:
- Are created with proper format (`#EXTM3U` header, `#EXTINF` entries)
- Include only valid tracks (within Crates directory)
- Handle empty playlists gracefully
- Create proper directory structure

### Realistic Database Mocking
The `test_real_database_mock.py` file provides mocks based on actual pyrekordbox structure:
- Realistic artist/album/track metadata
- Genre-based folder organization
- Multiple audio formats (.mp3, .flac, .wav, .m4a)
- Orphaned tracks handling
- Complex nested folder structures

### Database Connection Testing
Tests verify:
- Connection to Rekordbox database files (.db)
- Connection to Rekordbox XML exports (.xml)
- Preference for database over XML when both exist
- Graceful handling of connection failures

## Mock Data Examples

The realistic mocks include:
- **Electronic Music**: deadmau5 - Strobe, Daft Punk - One More Time, Avicii - Levels
- **Hip Hop**: Dr. Dre - Still D.R.E., Eminem - Lose Yourself
- **Complex folder structures**: Genre/Artist organization
- **Various formats**: MP3, FLAC, WAV, M4A files

## Test Coverage

The tests cover:
- ✅ Core playlist generation functionality
- ✅ Path validation and security
- ✅ Database/XML extraction
- ✅ Error handling and edge cases
- ✅ Unicode support
- ✅ Multiple audio formats
- ✅ Empty/invalid data handling

## Running Individual Components

Test just the playlist generator:
```bash
python -m pytest tests/test_playlist_generator.py -v
```

Test with realistic database mock:
```bash  
python -m pytest tests/test_real_database_mock.py -v
```

Test path security features:
```bash
python -m pytest tests/test_path_converter.py::TestPathConverter::test_validate_and_convert_path_invalid_path_outside_crates -v
```