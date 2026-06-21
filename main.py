#! /usr/bin/env python3
"""Command line interface for InstagramOSINT."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from banner import banner
from InstagramOSINT import InstagramOSINT, InstagramOSINTError, colors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect public Instagram profile metadata")
    parser.add_argument("--username", help="profile username, with or without @", required=True)
    parser.add_argument(
        "--downloadPhotos",
        help="download visible public post thumbnails in addition to post metadata",
        action="store_true",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("."),
        type=Path,
        help="directory where scan output folders are created (default: current directory)",
    )
    parser.add_argument(
        "--no-profile-picture",
        action="store_true",
        help="skip downloading the profile picture",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(colors.OKBLUE + banner + colors.ENDC)
    try:
        osint = InstagramOSINT(username=args.username, output_dir=args.output_dir)
        print(colors.OKGREEN + f"[*] Starting Scan on {osint.username}" + colors.ENDC)
        osint.save_data(download_profile_picture=not args.no_profile_picture)
        if args.downloadPhotos:
            osint.scrape_posts(download_images=True)
        else:
            osint.scrape_posts(download_images=False)
        osint.print_profile_data()
    except (InstagramOSINTError, ValueError) as exc:
        print(colors.FAIL + str(exc) + colors.ENDC, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
