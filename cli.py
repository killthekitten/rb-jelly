#!/usr/bin/env python3
"""
Rekordbox to Jellyfin CLI Tool

A command-line interface for migrating Rekordbox playlists to Jellyfin
and optionally syncing files to a NAS.
"""

import logging
import os
import sys
from pathlib import Path

import click

from dotenv import load_dotenv
from rekordbox_to_jellyfin import (
    PathConverter,
    PlaylistGenerator,
    RekordboxExtractor,
    setup_logging,
)


def load_config():
    """Load configuration from environment variables."""
    load_dotenv()
    return {
        "REKORDBOX_DB_PATH": os.getenv("REKORDBOX_DB_PATH"),
        "REKORDBOX_XML_PATH": os.getenv("REKORDBOX_XML_PATH"),
        "CRATES_ROOT": os.getenv("CRATES_ROOT"),
        "OUTPUT_DIR": os.getenv("OUTPUT_DIR", "./output"),
        "JELLYFIN_ROOT": os.getenv("JELLYFIN_ROOT", "/data/music"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    }


def validate_required_config(config: dict) -> bool:
    """Validate required configuration parameters."""
    if not config["CRATES_ROOT"]:
        click.echo(
            click.style("Error: CRATES_ROOT environment variable is required", fg="red")
        )
        return False

    if not (config["REKORDBOX_DB_PATH"] or config["REKORDBOX_XML_PATH"]):
        click.echo(
            click.style(
                "Error: Either REKORDBOX_DB_PATH or REKORDBOX_XML_PATH must be set",
                fg="red",
            )
        )
        return False

    return True


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode - minimal output")
@click.pass_context
def cli(ctx, verbose, quiet):
    """Rekordbox to Jellyfin migration tool."""
    ctx.ensure_object(dict)

    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "WARNING"
    else:
        log_level = "INFO"

    ctx.obj["log_level"] = log_level
    setup_logging(log_level)


@cli.command()
@click.option(
    "--output-dir", "-o", help="Output directory for playlists (overrides .env)"
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without creating files"
)
@click.option(
    "--flat",
    is_flag=True,
    help="Generate flat playlist structure (Jellyfin compatible)",
)
@click.pass_context
def create_playlists(ctx, output_dir, dry_run, flat):
    """Create Jellyfin playlists from Rekordbox without syncing files."""
    config = load_config()

    if not validate_required_config(config):
        sys.exit(1)

    if output_dir:
        config["OUTPUT_DIR"] = output_dir

    logging.getLogger(__name__)

    if dry_run:
        click.echo(
            click.style(
                "🔍 DRY RUN MODE - No files will be created", fg="yellow", bold=True
            )
        )

    if flat:
        click.echo(
            click.style(
                "📁 FLAT MODE - Playlists will be flattened for Jellyfin compatibility",
                fg="cyan",
                bold=True,
            )
        )

    click.echo(click.style("🎵 Starting playlist creation", fg="green", bold=True))

    # Initialize components
    extractor = RekordboxExtractor(
        config["REKORDBOX_DB_PATH"], config["REKORDBOX_XML_PATH"]
    )
    path_converter = PathConverter(config["CRATES_ROOT"], config["JELLYFIN_ROOT"])

    if not dry_run:
        playlist_generator = PlaylistGenerator(config["OUTPUT_DIR"], flat_mode=flat)

    # Connect to Rekordbox
    click.echo(click.style("📀 Connecting to Rekordbox...", fg="blue"))
    if not extractor.connect():
        click.echo(click.style("❌ Failed to connect to Rekordbox", fg="red"))
        sys.exit(1)

    click.echo(click.style("✅ Connected to Rekordbox", fg="green"))

    # Extract playlists
    click.echo(click.style("📋 Extracting playlists...", fg="blue"))
    playlists = extractor.extract_playlists()
    if not playlists:
        click.echo(click.style("❌ No playlists found", fg="red"))
        sys.exit(1)

    click.echo(click.style(f"✅ Found {len(playlists)} playlists", fg="green"))

    if dry_run:
        click.echo(
            click.style("\n📁 Playlists that would be created:", fg="cyan", bold=True)
        )
        total_tracks = 0
        for playlist in playlists:
            valid_tracks = 0
            for track in playlist.tracks:
                if path_converter.validate_and_convert_path(track.file_path):
                    valid_tracks += 1

            total_tracks += valid_tracks
            status_color = "green" if valid_tracks > 0 else "yellow"
            click.echo(
                f"  {click.style('•', fg=status_color)} {playlist.name} ({valid_tracks} tracks)"
            )

        click.echo(
            f"\n{click.style('Total:', fg='cyan', bold=True)} {len(playlists)} playlists, {total_tracks} valid tracks"
        )
    else:
        # Clean output directory and generate playlist structure
        click.echo(click.style("🧹 Cleaning output directory...", fg="blue"))
        playlist_generator.clean_output_directory()

        click.echo(click.style("📝 Creating playlist files...", fg="blue"))
        created_playlists = playlist_generator.create_playlist_structure(
            playlists, path_converter
        )

        click.echo(
            click.style(
                f"✅ Created {len(created_playlists)} playlist files", fg="green"
            )
        )
        click.echo(
            click.style(f"📂 Output location: {config['OUTPUT_DIR']}", fg="cyan")
        )

    # Report invalid paths
    invalid_paths = path_converter.get_invalid_paths()
    if invalid_paths:
        click.echo(
            click.style(
                f"\n⚠️  Found {len(invalid_paths)} paths outside Crates directory",
                fg="yellow",
            )
        )
        click.echo("\n".join(invalid_paths))
        if ctx.obj["log_level"] == "DEBUG":
            for path in invalid_paths:
                click.echo(f"  • {path}")

    click.echo(click.style("\n🎉 Playlist creation completed!", fg="green", bold=True))


if __name__ == "__main__":
    cli()
