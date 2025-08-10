# rb-jelly

A Python script that mirrors your Rekordbox DJ playlist structure as `.m3u` files to be used with Jellyfin and other audio players. Currently, the following features are confirmed working:

- Reading the Rekordbox 6/7 database without the need to export the XML.
- Smart playlist extraction.
- Supports flat and nested `.m3u` playlist output (no audio players I know currently support nested playlists except for Apple Music).
- Substitutes the absolute path in the playlist from your local folder (`CRATES_ROOT`) to the Jellyfin library folder (`JELLYFIN_ROOT`).

## ⚠️ Disclaimer

This codebase is 100% generated with Claude Code to scratch my own itch and has not been properly tested or reviewed. The SMB sync functionality doesn't quite work properly. You are expected to:

1. Generate the playlists using this tool
2. Manually upload the generated M3U files to your Jellyfin server's Library folder under `playlists/`
3. Resync metadata on that library in Jellyfin

Use at your own risk and always backup your data before running any operations.

**P.S.** Since this codebase is AI-generated, any musical references found in the code do not represent my personal musical taste and will be replaced with more tasteful alternatives when I have more time ¯\\\_(ツ)\_/¯

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

**Other Settings:**

- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR - default: INFO)

## Usage

### Basic Usage

For the list of available commands see this:

```bash
python cli.py 
```

The only command that I have fully tested and confirmed working is this:

```bash
python cli.py create-playlists --flat
```
