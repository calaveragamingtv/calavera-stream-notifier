import argparse
import os
import sys
from pathlib import Path

from instagrapi import Client

from .config import PROJECT_ROOT, load_config


def validate_file(path: Path, config: dict) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    extension = path.suffix.lower()

    if extension in config["supported_images"]:
        return "photo"

    if extension in config["supported_videos"]:
        return "video"

    raise ValueError(
        f"Unsupported format: {extension}"
    )


def publish_story(path: Path, media_type: str, config: dict):
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")

    if not username or not password:
        raise ValueError(
            "Missing IG_USERNAME or IG_PASSWORD environment variables."
        )

    session_file = PROJECT_ROOT / config["session_file"]

    client = Client()

    if session_file.exists():
        print("[INSTAGRAM] Loading saved session...")
        client.load_settings(session_file)

    print("[INSTAGRAM] Logging in...")
    client.login_legacy(username, password)

    session_file.parent.mkdir(parents=True, exist_ok=True)
    client.dump_settings(session_file)

    print(f"[INSTAGRAM] Publishing {media_type} story...")

    if media_type == "photo":
        story = client.photo_upload_to_story(path)
    else:
        story = client.video_upload_to_story(path)

    print(
        f"[INSTAGRAM] Story published successfully. ID: {story.pk}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Instagram Stories Publisher"
    )

    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="Image or video file to publish."
    )

    args = parser.parse_args()

    try:
        config = load_config()

        media_type = validate_file(args.file, config)

        print(f"[INSTAGRAM] File: {args.file}")
        print(f"[INSTAGRAM] Media type: {media_type}")

        if config["dry_run"]:
            print(
                "[INSTAGRAM] DRY RUN enabled. "
                "Validation successful. Nothing was published."
            )
            return 0

        publish_story(args.file, media_type, config)
        return 0

    except Exception as error:
        print(f"[INSTAGRAM] ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
