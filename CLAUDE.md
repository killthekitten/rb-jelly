# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python script that migrates Rekordbox DJ library playlists to Jellyfin media server format. It extracts playlists from Rekordbox (database or XML), validates file paths, converts them to Jellyfin-compatible paths, and optionally syncs missing files to a NAS via SMB.

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Setup configuration
cp .env.example .env
# Edit .env with actual paths and credentials

# Run the migration
python rekordbox_to_jellyfin.py

# Check logs
tail -f rekordbox_to_jellyfin.log

# Run tests (uses pytest)
python -m pytest
python -m pytest -v  # verbose output
python -m pytest tests/test_collision_resolution.py -v  # specific test file

# Code formatting and linting
black *.py tests/  # Format code with black
isort *.py tests/  # Sort imports with isort
flake8 *.py tests/  # Check for linting issues with flake8
```

## Architecture

The script follows a modular class-based architecture with clear separation of concerns:

### Core Classes

1. **RekordboxExtractor** - Handles connection to and extraction from Rekordbox database (.db) or XML exports
2. **PathConverter** - Validates paths stay within Crates directory and converts absolute paths to Jellyfin-relative paths (`/data/music`)
3. **PlaylistGenerator** - Creates M3U playlist files and folder structure, includes output directory cleaning
4. **SMBSyncManager** - Manages SMB connection to NAS and handles file existence checking/synchronization

### Data Models

- **Track** - Represents individual music files with metadata and paths
- **Playlist** - Contains tracks and supports nested structure

### Execution Flow

1. Load environment configuration via dotenv
2. Connect to Rekordbox (database preferred, XML fallback)
3. Extract all playlists containing tracks (orphaned tracks ignored)
4. Validate all track paths are within Crates directory (security feature)
5. Clean and recreate output directory
6. Generate M3U playlists with converted paths
7. Optionally sync missing files to NAS via SMB

## Configuration System

Uses dotenv (.env) for configuration with these critical variables:
- `CRATES_ROOT` - Required. Music library root directory for path validation
- `REKORDBOX_DB_PATH` or `REKORDBOX_XML_PATH` - Required. Source of playlist data
- `OUTPUT_DIR` - Default: "./output". Gets cleaned on each run
- SMB variables - Optional. If incomplete, sync is skipped gracefully

## Security Considerations

The script includes path traversal protection - any track path outside the `CRATES_ROOT` directory is rejected and logged. This prevents potential security issues when processing playlist data.

## Collision Resolution and Filename Sanitization

The system includes sophisticated collision resolution to handle sanitized filenames:

- **UniqueNameResolver class** - Ensures sanitized filenames remain unique within their folder context
- **Cross-platform sanitization** - Uses `pathvalidate` library for filesystem-safe names
- **Hierarchical uniqueness** - Names only need to be unique within their parent folder
- **Smart collision handling** - Adds numbered suffixes like "(1)", "(2)" when collisions occur
- **Example**: "Plugin ears / Hovercat" and "Plugin ears  Hovercat" become unique sanitized names

## Testing

The project uses pytest for comprehensive testing:

- **Core test files** in `/tests/` directory
- **pytest.ini** configuration with test discovery patterns
- **Collision resolution tests** - Extensive coverage of filename sanitization edge cases
- **Integration tests** - Test playlist generation with collision scenarios
- **Real-world scenario tests** - Based on actual user playlist names

Run tests with: `python -m pytest -v`

## Error Handling

- Graceful degradation when SMB configuration is incomplete
- Comprehensive logging to `rekordbox_to_jellyfin.log`
- Early validation of required configuration
- Import error handling with helpful messages