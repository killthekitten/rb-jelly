# Rekordbox to Jellyfin Library Migration

A Python script that mirrors your Rekordbox DJ library structure to Jellyfin, handling playlist nesting, path conversion, and file synchronization via SMB.

## ⚠️ Disclaimer

This codebase is 100% generated with Claude Code to scratch my own itch and has not been properly tested or reviewed. The SMB sync functionality doesn't quite work properly. You are expected to:

1. Generate the playlists using this tool
2. Manually upload the generated M3U files to your Jellyfin server's Library folder under `playlists/`
3. Resync metadata on that library in Jellyfin

Use at your own risk and always backup your data before running any operations.

**P.S.** Since this codebase is AI-generated, any musical references found in the code do not represent my personal musical taste and will be replaced with more tasteful alternatives when I have more time ¯\\\_(ツ)\_/¯

## Features

- **Playlist Extraction**: Extracts playlists from Rekordbox database or XML exports
- **Structure Mirroring**: Recreates nested playlist folder structure for Jellyfin
- **Path Conversion**: Converts absolute Crates paths to `/data/music` relative paths
- **Security Validation**: Ensures all paths stay within Crates directory hierarchy
- **SMB Sync**: Connects to NAS via SMB to check and sync missing files
- **Comprehensive Logging**: Detailed logs for all operations and invalid paths

## Requirements

- Python 3.7+
- Rekordbox (for database access) or XML export
- SMB-enabled NAS (for file synchronization)

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy and configure environment variables:
   ```bash
   cp .env.example .env
   ```

## Configuration

Edit `.env` with your specific settings:

### Environment Variables

**Rekordbox Configuration:**

- `REKORDBOX_DB_PATH`: Path to your Rekordbox master.db file
- `REKORDBOX_XML_PATH`: Path to your exported XML file (alternative to database)
- **Database Location**: Usually found at:
  - macOS: `~/Library/Pioneer/rekordbox/master.db`
  - Windows: `%APPDATA%\\Pioneer\\rekordbox\\master.db`

**Path Configuration:**

- `CRATES_ROOT`: Your music Crates directory (where Rekordbox tracks are stored)
- `OUTPUT_DIR`: Where to create the Jellyfin playlist files (default: `./output`)
- `JELLYFIN_ROOT`: The root path that Jellyfin uses to access music on your NAS (default: `/data/music`)

**NAS/SMB Configuration (optional):**

- `SMB_SERVER`: IP address of your NAS
- `SMB_SHARE`: SMB share name containing your music
- `SMB_USERNAME`: NAS username
- `SMB_PASSWORD`: NAS password

**Other Settings:**

- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR - default: INFO)

## Usage

### Basic Usage

```bash
python rekordbox_to_jellyfin.py
```

### Configuration Validation

The script will validate required environment variables on startup:

- `CRATES_ROOT` is required
- Either `REKORDBOX_DB_PATH` or `REKORDBOX_XML_PATH` must be set
- SMB variables are optional (sync will be skipped if not provided)

## How It Works

1. **Connect to Rekordbox**: Accesses your Rekordbox database or XML export
2. **Extract Playlists**: Retrieves all playlists with their tracks and metadata
3. **Validate Paths**: Ensures all track paths are within the Crates directory
4. **Convert Paths**: Rewrites absolute Crates paths to Jellyfin-compatible `/data/music` paths
5. **Generate Structure**: Creates folder structure and M3U playlist files
6. **Connect to NAS**: Establishes SMB connection to your NAS
7. **Sync Files**: Checks for missing files and copies them to the NAS

## Output Structure

The script creates a clean output directory for each run:

```
output/
├── Playlist 1/
│   └── Playlist 1.m3u
├── Playlist 2/
│   └── Playlist 2.m3u
└── ...
```

Each M3U file contains:

- Track metadata (artist, title)
- Converted file paths pointing to `/data/music/...`

## Security Features

- **Path Validation**: Automatically rejects any track paths that escape the Crates directory
- **Logging**: All rejected paths are logged for review
- **Safe Defaults**: Conservative error handling prevents data corruption

## Logging

The script creates detailed logs in `rekordbox_to_jellyfin.log`:

- Playlist extraction progress
- Path validation results
- SMB connection status
- File sync operations
- Any errors or warnings

## Troubleshooting

### "No valid Rekordbox database or XML file found"

- Verify your `REKORDBOX_DB_PATH` or `REKORDBOX_XML_PATH` is correct

### SMB Connection Issues

- Verify NAS IP address and credentials
- Check that SMB/CIFS is enabled on your NAS
- Ensure the music share is accessible

### Path Outside Crates Directory

- Check the `rekordbox_to_jellyfin.log` for specific paths
- Verify your `CRATES_ROOT` setting is correct
- Some Rekordbox installations may reference files outside the main library

### Missing Dependencies

```bash
pip install -r requirements.txt
```

### Environment Configuration Issues

- Ensure `.env` file exists and contains required variables
- Check that paths exist and are accessible
- Verify NAS connectivity if using SMB sync

## Limitations

- Only processes tracks that are assigned to playlists (orphaned tracks are ignored)
- Requires either direct database access or XML export from Rekordbox
- SMB sync requires network access to your NAS

## License

This script is provided as-is for personal use. Please ensure you have proper backups before running any synchronization operations.
