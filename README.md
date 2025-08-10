# rb-jelly

A Python script that uses [pyrekordbox](https://github.com/dylanljones/pyrekordbox) to export your Rekordbox DJ playlist structure as `.m3u` files. It is intended to be used with Jellyfin and other audio players, and works similarly to [rekordbox-plexamp-sync](https://github.com/dvcrn/rekordbox-plexamp-sync). Here's what it can do so far:

- Read the Rekordbox 6/7 database directly. You do not need to open Rekordbox for this to work.
- Generate the `.m3u` playlists with respect to folder structure in your Rekordbox.
- Recognize and export smart playlists, thanks to [pyrekordbox](https://github.com/dylanljones/pyrekordbox) 🙇.
- Substitute the absolute path in the playlist from your local folder (`CRATES_ROOT`) to the Jellyfin library folder (`JELLYFIN_ROOT`).

Using this tool still involves quite a bit of manual work, but the end goal is to automate the process as much as possible.

## ⚠️ Disclaimer

This code has not been properly tested or reviewed, use at your own risk and always backup your data before running any operations. You should know that all of it, including the test suite, was generated with Claude Code without much supervision. 

I wanted to scratch my own itch, and that worked wonders, but your mileage can vary. Having said that, I'd be happy to help you out should you have any problems, just open an issue and let me know! 

**P.S.** Since this codebase is AI-generated, any musical references found in the code do not represent my personal musical taste and will be replaced with more tasteful alternatives when I have more time ¯\\\_(ツ)\_/¯

## Installation

1. Clone or download this repository.
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

- `REKORDBOX_DB_PATH`: Path to your Rekordbox master.db file, usually found here:
  - macOS: `~/Library/Pioneer/rekordbox/master.db`
  - Windows: `%APPDATA%\\Pioneer\\rekordbox\\master.db`

**Path Configuration:**

- `CRATES_ROOT`: Your music Crates directory (where Rekordbox tracks are stored)
- `JELLYFIN_ROOT`: The root path that Jellyfin uses to access music on your NAS (default: `/data/music`)

**Other Settings:**

- `OUTPUT_DIR`: Where to create the Jellyfin playlist files (default: `./output`)
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR - default: INFO)

## Usage

For the list of available commands see this:

```bash
python cli.py 
```

### 1. Generate the playlists

This command would generate a flat playlist structure in the folder that you specified as `OUTPUT_DIR` (by default it is `./output`):

```bash
python cli.py create-playlists --flat
```

The `--flat` flag is optional, but it makes the experience with Jellyfin a little bit better. It would change the playlist names to include all the parent folder names, so the related playlists will appear sorted in the Jellyfin UI as you would expect them to.

### 2. Upload playlists to your Jellyfin instance

Inside of the folder that you assigned to your music library on Jellyfin, you need to create a subdirectory `playlists` and upload all the playlists there. 

In my case I run Jellyfin on an Unraid NAS, and the library is mapped to `/cache/Music`. Here is how it looks like in the NAS UI:

<img width="800" alt="Screenshot of the Unraid file manager interface that lists the playlists in Jellyfin's folder" src="https://github.com/user-attachments/assets/c48c464d-ecda-4dab-bf6f-5866d113c1bd" />

### 3. Refresh metadata

You need to locate the library on Jellyfin's homepage, click on the icon in the bottom-right corner, and select "Refresh metadata":

<img width="800" alt="A screenshot of Jellyfin's interface with a highlighted refresh metadata menu" src="https://github.com/user-attachments/assets/786774c2-da0d-4d7e-b6b7-5b4f8005128b" />

Then in the popup select "Scan for new and updated files" and confirm:

<img width="800" alt="A screenshot of the refresh metadata popup. The selected option in the dropdown says 'Scan for new and updated files'." src="https://github.com/user-attachments/assets/6c4caa88-9c82-4cc6-9ecd-7813e9123ff5" />

It will take a few moments, and if it all went well, when you go into the Playlists tab of your library, you will see your playlists:

<img width="800" alt="A screenshot of Jellyfin's Playlists tab" src="https://github.com/user-attachments/assets/28085b61-934a-4305-865d-9bc1b1b69774" />
