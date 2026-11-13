
import argparse
import os
import sys
from pathlib import Path

from instagrapi import Client


SUPPORTED_PHOTO = {".jpg", ".jpeg"}
SUPPORTED_VIDEO = {".mp4"}


def validate_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    extension = path.suffix.lower()

    if extension in SUPPORTED_PHOTO:
        return "photo"

    if extension in SUPPORTED_VIDEO:
        return "video"

    raise ValueError(
        f"Unsupported format: {extension}. "
        "Supported formats: JPG, JPEG, MP4."
    )


def publish_story(path: Path, caption: str = "") -> None:
    username = os.getenv("IG_USERNAME")
    password = os.getenv("IG_PASSWORD")
    session_file = Path(
        os.getenv("IG_SESSION_FILE", "instagram/session.json")
    )

    if not username or not password:
        raise ValueError(
            "Missing IG_USERNAME or IG_PASSWORD environment variables."
        )

    client = Client()

    if session_file.exists():
        print("[INSTAGRAM] Loading saved session...")
        client.load_settings(session_file)

    print("[INSTAGRAM] Logging in...")
    client.login(username, password)

    session_file.parent.mkdir(parents=True, exist_ok=True)
    client.dump_settings(session_file)

    media_type = validate_file(path)

    print(f"[INSTAGRAM] Publishing {media_type} story...")

    if media_type == "photo":
        story = client.photo_upload_to_story(
            path,
            caption=caption,
        )
    else:
        story = client.video_upload_to_story(
            path,
            caption=caption,
        )

    print(f"[INSTAGRAM] Story published successfully. ID: {story.pk}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish an image or video to Instagram Stories."
    )

    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="Image or video file to publish.",
    )

    parser.add_argument(
        "--caption",
        default="",
        help="Optional story caption.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the file without connecting to Instagram.",
    )

    args = parser.parse_args()

    try:
        media_type = validate_file(args.file)

        print(f"[INSTAGRAM] File: {args.file}")
        print(f"[INSTAGRAM] Media type: {media_type}")

        if args.dry_run:
            print("[INSTAGRAM] Dry run successful. Nothing was published.")
            return 0

        publish_story(args.file, args.caption)
        return 0

    except Exception as error:
        print(f"[INSTAGRAM] ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
