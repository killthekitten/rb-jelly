#!/usr/bin/env python3
"""
Rekordbox to Jellyfin CLI Tool

A command-line interface for migrating Rekordbox playlists to Jellyfin
and optionally syncing files to a NAS.
"""

import click
import logging
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    click.echo(click.style("Error: python-dotenv not installed. Run: pip install python-dotenv", fg='red'))
    sys.exit(1)

# Import our existing modules
try:
    from rekordbox_to_jellyfin import (
        RekordboxExtractor, PathConverter, PlaylistGenerator, SMBSyncManager, setup_logging
    )
except ImportError as e:
    click.echo(click.style(f"Error importing modules: {e}", fg='red'))
    sys.exit(1)


def load_config():
    """Load configuration from environment variables."""
    load_dotenv()
    return {
        'REKORDBOX_DB_PATH': os.getenv('REKORDBOX_DB_PATH'),
        'REKORDBOX_XML_PATH': os.getenv('REKORDBOX_XML_PATH'),
        'CRATES_ROOT': os.getenv('CRATES_ROOT'),
        'OUTPUT_DIR': os.getenv('OUTPUT_DIR', './output'),
        'JELLYFIN_ROOT': os.getenv('JELLYFIN_ROOT', '/data/music'),
        'SMB_SERVER': os.getenv('SMB_SERVER'),
        'SMB_SHARE': os.getenv('SMB_SHARE'),
        'SMB_USERNAME': os.getenv('SMB_USERNAME'),
        'SMB_PASSWORD': os.getenv('SMB_PASSWORD'),
        'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO')
    }


def validate_required_config(config: dict) -> bool:
    """Validate required configuration parameters."""
    if not config['CRATES_ROOT']:
        click.echo(click.style("Error: CRATES_ROOT environment variable is required", fg='red'))
        return False
    
    if not (config['REKORDBOX_DB_PATH'] or config['REKORDBOX_XML_PATH']):
        click.echo(click.style("Error: Either REKORDBOX_DB_PATH or REKORDBOX_XML_PATH must be set", fg='red'))
        return False
    
    return True


def check_smb_config(config: dict) -> bool:
    """Check if SMB configuration is complete."""
    return all([
        config['SMB_SERVER'],
        config['SMB_SHARE'], 
        config['SMB_USERNAME'],
        config['SMB_PASSWORD']
    ])


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Quiet mode - minimal output')
@click.pass_context
def cli(ctx, verbose, quiet):
    """Rekordbox to Jellyfin migration tool."""
    ctx.ensure_object(dict)
    
    if verbose:
        log_level = 'DEBUG'
    elif quiet:
        log_level = 'WARNING'
    else:
        log_level = 'INFO'
    
    ctx.obj['log_level'] = log_level
    setup_logging(log_level)


@cli.command()
@click.option('--output-dir', '-o', help='Output directory for playlists (overrides .env)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without creating files')
@click.pass_context
def create_playlists(ctx, output_dir, dry_run):
    """Create Jellyfin playlists from Rekordbox without syncing files."""
    config = load_config()
    
    if not validate_required_config(config):
        sys.exit(1)
    
    if output_dir:
        config['OUTPUT_DIR'] = output_dir
    
    logger = logging.getLogger(__name__)
    
    if dry_run:
        click.echo(click.style("🔍 DRY RUN MODE - No files will be created", fg='yellow', bold=True))
    
    click.echo(click.style("🎵 Starting playlist creation", fg='green', bold=True))
    
    # Initialize components
    extractor = RekordboxExtractor(config['REKORDBOX_DB_PATH'], config['REKORDBOX_XML_PATH'])
    path_converter = PathConverter(config['CRATES_ROOT'], config['JELLYFIN_ROOT'])
    
    if not dry_run:
        playlist_generator = PlaylistGenerator(config['OUTPUT_DIR'])
    
    # Connect to Rekordbox
    click.echo(click.style("📀 Connecting to Rekordbox...", fg='blue'))
    if not extractor.connect():
        click.echo(click.style("❌ Failed to connect to Rekordbox", fg='red'))
        sys.exit(1)
    
    click.echo(click.style("✅ Connected to Rekordbox", fg='green'))
    
    # Extract playlists
    click.echo(click.style("📋 Extracting playlists...", fg='blue'))
    playlists = extractor.extract_playlists()
    if not playlists:
        click.echo(click.style("❌ No playlists found", fg='red'))
        sys.exit(1)
    
    click.echo(click.style(f"✅ Found {len(playlists)} playlists", fg='green'))
    
    if dry_run:
        click.echo(click.style("\n📁 Playlists that would be created:", fg='cyan', bold=True))
        total_tracks = 0
        for playlist in playlists:
            valid_tracks = 0
            for track in playlist.tracks:
                if path_converter.validate_and_convert_path(track.file_path):
                    valid_tracks += 1
            
            total_tracks += valid_tracks
            status_color = 'green' if valid_tracks > 0 else 'yellow'
            click.echo(f"  {click.style('•', fg=status_color)} {playlist.name} ({valid_tracks} tracks)")
        
        click.echo(f"\n{click.style('Total:', fg='cyan', bold=True)} {len(playlists)} playlists, {total_tracks} valid tracks")
    else:
        # Clean output directory and generate playlist structure
        click.echo(click.style("🧹 Cleaning output directory...", fg='blue'))
        playlist_generator.clean_output_directory()
        
        click.echo(click.style("📝 Creating playlist files...", fg='blue'))
        created_playlists = playlist_generator.create_playlist_structure(playlists, path_converter)
        
        click.echo(click.style(f"✅ Created {len(created_playlists)} playlist files", fg='green'))
        click.echo(click.style(f"📂 Output location: {config['OUTPUT_DIR']}", fg='cyan'))
    
    # Report invalid paths
    invalid_paths = path_converter.get_invalid_paths()
    if invalid_paths:
        click.echo(click.style(f"\n⚠️  Found {len(invalid_paths)} paths outside Crates directory", fg='yellow'))
        if ctx.obj['log_level'] == 'DEBUG':
            for path in invalid_paths:
                click.echo(f"  • {path}")
    
    click.echo(click.style("\n🎉 Playlist creation completed!", fg='green', bold=True))


@cli.command()
@click.option('--check-only', is_flag=True, help='Only check for missing files, do not sync')
@click.pass_context 
def sync_files(ctx, check_only):
    """Sync missing files to NAS via SMB."""
    config = load_config()
    
    if not validate_required_config(config):
        sys.exit(1)
    
    if not check_smb_config(config):
        click.echo(click.style("❌ SMB configuration incomplete. Please check your .env file.", fg='red'))
        click.echo("Required variables: SMB_SERVER, SMB_SHARE, SMB_USERNAME, SMB_PASSWORD")
        sys.exit(1)
    
    logger = logging.getLogger(__name__)
    
    if check_only:
        click.echo(click.style("🔍 CHECK ONLY MODE - No files will be synced", fg='yellow', bold=True))
    
    click.echo(click.style("🔄 Starting file sync process", fg='green', bold=True))
    
    # Initialize components
    extractor = RekordboxExtractor(config['REKORDBOX_DB_PATH'], config['REKORDBOX_XML_PATH'])
    path_converter = PathConverter(config['CRATES_ROOT'], config['JELLYFIN_ROOT'])
    smb_manager = SMBSyncManager(
        config['SMB_SERVER'], 
        config['SMB_SHARE'], 
        config['SMB_USERNAME'], 
        config['SMB_PASSWORD']
    )
    
    # Connect to Rekordbox
    click.echo(click.style("📀 Connecting to Rekordbox...", fg='blue'))
    if not extractor.connect():
        click.echo(click.style("❌ Failed to connect to Rekordbox", fg='red'))
        sys.exit(1)
    
    click.echo(click.style("✅ Connected to Rekordbox", fg='green'))
    
    # Connect to NAS
    click.echo(click.style("🌐 Connecting to NAS...", fg='blue'))
    if not smb_manager.connect():
        click.echo(click.style("❌ Failed to connect to NAS", fg='red'))
        sys.exit(1)
    
    click.echo(click.style("✅ Connected to NAS", fg='green'))
    
    # Extract playlists and collect all tracks
    click.echo(click.style("📋 Extracting tracks from playlists...", fg='blue'))
    playlists = extractor.extract_playlists()
    if not playlists:
        click.echo(click.style("❌ No playlists found", fg='red'))
        sys.exit(1)
    
    all_tracks = []
    for playlist in playlists:
        all_tracks.extend(playlist.tracks)
    
    click.echo(click.style(f"✅ Found {len(all_tracks)} tracks across {len(playlists)} playlists", fg='green'))
    
    # Check and optionally sync files
    if check_only:
        click.echo(click.style("🔍 Checking for missing files...", fg='blue'))
        # We need to modify the SMB manager to support check-only mode
        missing_count, synced_count = smb_manager.check_and_sync_files(all_tracks, path_converter)
        click.echo(click.style(f"📊 Found {missing_count} missing files on NAS", fg='cyan'))
    else:
        click.echo(click.style("🔄 Syncing missing files...", fg='blue'))
        missing_count, synced_count = smb_manager.check_and_sync_files(all_tracks, path_converter)
        
        if synced_count == missing_count:
            click.echo(click.style(f"✅ Successfully synced all {synced_count} missing files", fg='green'))
        else:
            click.echo(click.style(f"⚠️  Synced {synced_count}/{missing_count} missing files", fg='yellow'))
    
    click.echo(click.style("\n🎉 Sync process completed!", fg='green', bold=True))


@cli.command()
@click.option('--output-dir', '-o', help='Output directory for playlists (overrides .env)')
@click.option('--skip-sync', is_flag=True, help='Skip file synchronization')
@click.pass_context
def full_migration(ctx, output_dir, skip_sync):
    """Run complete migration: create playlists and sync files."""
    config = load_config()
    
    if not validate_required_config(config):
        sys.exit(1)
    
    if output_dir:
        config['OUTPUT_DIR'] = output_dir
    
    has_smb_config = check_smb_config(config)
    
    if not skip_sync and not has_smb_config:
        click.echo(click.style("⚠️  SMB configuration incomplete. File sync will be skipped.", fg='yellow'))
        skip_sync = True
    
    click.echo(click.style("🚀 Starting full migration", fg='green', bold=True))
    
    # Run playlist creation
    click.echo(click.style("\n=== PHASE 1: Playlist Creation ===", fg='cyan', bold=True))
    ctx.invoke(create_playlists, output_dir=output_dir, dry_run=False)
    
    # Run file sync if configured and not skipped
    if not skip_sync:
        click.echo(click.style("\n=== PHASE 2: File Synchronization ===", fg='cyan', bold=True))
        ctx.invoke(sync_files, check_only=False)
    else:
        click.echo(click.style("\n📝 File sync skipped", fg='yellow'))
    
    click.echo(click.style("\n🎉 Full migration completed!", fg='green', bold=True))


@cli.command()
def setup():
    """Interactive setup to create .env configuration file."""
    click.echo(click.style("🚀 Rekordbox to Jellyfin Setup", fg='green', bold=True))
    click.echo()
    
    env_path = Path('.env')
    example_path = Path('.env.example')
    
    if env_path.exists():
        if not click.confirm(click.style("⚠️  .env file already exists. Overwrite?", fg='yellow')):
            click.echo("Setup cancelled.")
            return
    
    if not example_path.exists():
        click.echo(click.style("❌ .env.example file not found. Cannot proceed with setup.", fg='red'))
        return
    
    click.echo(click.style("📝 Please provide the following information:", fg='cyan'))
    click.echo()
    
    # Rekordbox source
    click.echo(click.style("1. Rekordbox Source", fg='cyan', bold=True))
    source_type = click.prompt(
        "Choose source type",
        type=click.Choice(['database', 'xml']),
        default='database'
    )
    
    if source_type == 'database':
        rekordbox_path = click.prompt("Path to Rekordbox database file (master.db)")
        rekordbox_db = rekordbox_path
        rekordbox_xml = ""
    else:
        rekordbox_path = click.prompt("Path to Rekordbox XML export file")
        rekordbox_db = ""
        rekordbox_xml = rekordbox_path
    
    # Crates root
    click.echo()
    click.echo(click.style("2. Music Library", fg='cyan', bold=True))
    crates_root = click.prompt("Path to your music library root directory")
    
    # Output settings
    click.echo()
    click.echo(click.style("3. Output Settings", fg='cyan', bold=True))
    output_dir = click.prompt("Output directory for playlists", default="./output")
    jellyfin_root = click.prompt("Jellyfin music root path", default="/data/music")
    
    # SMB settings
    click.echo()
    click.echo(click.style("4. NAS/SMB Settings (optional - press Enter to skip)", fg='cyan', bold=True))
    smb_server = click.prompt("SMB server IP or hostname", default="", show_default=False)
    
    if smb_server:
        smb_share = click.prompt("SMB share name", default="")
        smb_username = click.prompt("SMB username", default="")
        smb_password = click.prompt("SMB password", hide_input=True, default="")
    else:
        smb_share = smb_username = smb_password = ""
    
    # Log level
    click.echo()
    log_level = click.prompt(
        "Log level",
        type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
        default='INFO'
    )
    
    # Create .env file
    env_content = f"""# Rekordbox to Jellyfin Migration Configuration
# Generated by setup command

# Rekordbox Database Configuration
{"REKORDBOX_DB_PATH=" + rekordbox_db if rekordbox_db else "# REKORDBOX_DB_PATH="}
{"REKORDBOX_XML_PATH=" + rekordbox_xml if rekordbox_xml else "# REKORDBOX_XML_PATH="}

# Path Configuration
CRATES_ROOT={crates_root}
OUTPUT_DIR={output_dir}
JELLYFIN_ROOT={jellyfin_root}

# NAS/SMB Configuration
{"SMB_SERVER=" + smb_server if smb_server else "# SMB_SERVER="}
{"SMB_SHARE=" + smb_share if smb_share else "# SMB_SHARE="}
{"SMB_USERNAME=" + smb_username if smb_username else "# SMB_USERNAME="}
{"SMB_PASSWORD=" + smb_password if smb_password else "# SMB_PASSWORD="}

# Logging Configuration
LOG_LEVEL={log_level}
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    click.echo()
    click.echo(click.style("✅ Configuration saved to .env", fg='green', bold=True))
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. " + click.style("python cli.py config-check", fg='cyan') + " - Verify your configuration")
    click.echo("  2. " + click.style("python cli.py create-playlists --dry-run", fg='cyan') + " - Test playlist creation")
    click.echo("  3. " + click.style("python cli.py create-playlists", fg='cyan') + " - Create playlists")


@cli.command()
def config_check():
    """Check configuration and show current settings."""
    config = load_config()
    
    click.echo(click.style("⚙️  Configuration Status", fg='cyan', bold=True))
    click.echo()
    
    # Check if .env exists
    env_exists = Path('.env').exists()
    env_status = "✅ Found" if env_exists else "❌ Missing"
    env_color = 'green' if env_exists else 'red'
    click.echo(f"📄 .env file: {click.style(env_status, fg=env_color)}")
    
    if not env_exists:
        click.echo()
        click.echo(click.style("💡 Tip: Run 'python cli.py setup' to create configuration", fg='yellow'))
        return
    
    click.echo()
    
    # Check Rekordbox source
    rekordbox_valid = False
    if config['REKORDBOX_DB_PATH'] and Path(config['REKORDBOX_DB_PATH']).exists():
        rekordbox_source = f"Database: {config['REKORDBOX_DB_PATH']}"
        status_color = 'green'
        rekordbox_valid = True
    elif config['REKORDBOX_XML_PATH'] and Path(config['REKORDBOX_XML_PATH']).exists():
        rekordbox_source = f"XML: {config['REKORDBOX_XML_PATH']}"
        status_color = 'green'
        rekordbox_valid = True
    else:
        rekordbox_source = "❌ No valid source found"
        status_color = 'red'
        rekordbox_valid = False
    
    click.echo(f"📀 Rekordbox Source: {click.style(rekordbox_source, fg=status_color)}")
    
    # Check Crates root
    crates_valid = config['CRATES_ROOT'] and Path(config['CRATES_ROOT']).exists()
    crates_status = "✅ Valid" if crates_valid else "❌ Missing/Invalid"
    crates_color = 'green' if crates_valid else 'red'
    click.echo(f"📁 Crates Root: {click.style(crates_status, fg=crates_color)} ({config['CRATES_ROOT']})")
    
    # Check output directory  
    click.echo(f"📂 Output Directory: {click.style(config['OUTPUT_DIR'], fg='cyan')}")
    click.echo(f"🎵 Jellyfin Root: {click.style(config['JELLYFIN_ROOT'], fg='cyan')}")
    
    # Check SMB configuration
    click.echo()
    click.echo(click.style("🌐 SMB Configuration:", fg='cyan', bold=True))
    smb_complete = check_smb_config(config)
    
    smb_fields = {
        'Server': config['SMB_SERVER'],
        'Share': config['SMB_SHARE'], 
        'Username': config['SMB_USERNAME'],
        'Password': '***' if config['SMB_PASSWORD'] else None
    }
    
    for field, value in smb_fields.items():
        status = "✅" if value else "❌"
        color = 'green' if value else 'red'
        click.echo(f"  {field}: {click.style(status, fg=color)} {value or 'Not set'}")
    
    overall_status = "✅ Ready for sync" if smb_complete else "⚠️  Sync not available"
    status_color = 'green' if smb_complete else 'yellow'
    click.echo(f"  Overall: {click.style(overall_status, fg=status_color)}")
    
    click.echo()
    click.echo(click.style("📝 Log Level:", fg='cyan', bold=True))
    click.echo(f"  Current: {click.style(config['LOG_LEVEL'], fg='cyan')}")
    
    # Show next steps
    if crates_valid and rekordbox_valid:
        click.echo()
        click.echo(click.style("🚀 Ready to go! Try:", fg='green', bold=True))
        click.echo("  • " + click.style("python cli.py create-playlists --dry-run", fg='cyan') + " - Preview playlists")
        click.echo("  • " + click.style("python cli.py create-playlists", fg='cyan') + " - Create playlists")
        if smb_complete:
            click.echo("  • " + click.style("python cli.py sync-files --check-only", fg='cyan') + " - Check missing files")
            click.echo("  • " + click.style("python cli.py full-migration", fg='cyan') + " - Run complete migration")


if __name__ == '__main__':
    cli()