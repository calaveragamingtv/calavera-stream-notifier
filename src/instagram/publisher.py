
import argparse
import os
from pathlib import Path

from instagrapi import Client

from src.instagram.config import load_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORY_ASSETS = {
    "twitch": "assets/instagram/on_twitch.mp4",
    "kick": "assets/instagram/on_kick.mp4",
}


def publish_story(platform: str, config: dict):
    platform = platform.lower().strip()

    if platform not in STORY_ASSETS:
        raise ValueError(
            f"Unsupported platform: {platform}. "
            f"Supported platforms: {', '.join(STORY_ASSETS)}"
        )

    media_file = PROJECT_ROOT / STORY_ASSETS[platform]

    if not media_file.is_file():
        raise FileNotFoundError(
            f"Instagram Story asset not found: {media_file}"
        )

    if media_file.suffix.lower() not in config["supported_videos"]:
        raise ValueError(
            f"Unsupported video format: {media_file.suffix}"
        )

    print(f"[INSTAGRAM] Platform: {platform}")
    print(f"[INSTAGRAM] File: {media_file}")
    print("[INSTAGRAM] Media type: video")

    if config["dry_run"]:
        print(
            "[INSTAGRAM] DRY RUN enabled. "
            "Validation successful. Nothing was published."
        )
        return

    session_id = os.getenv("IG_SESSIONID")

    if not session_id:
        raise ValueError("Missing IG_SESSIONID environment variable.")

    session_file = PROJECT_ROOT / config["session_file"]

    client = Client()

    print("[INSTAGRAM] Authenticating with session ID...")
    client.login_by_sessionid(session_id)

    session_file.parent.mkdir(parents=True, exist_ok=True)
    client.dump_settings(session_file)

    print(f"[INSTAGRAM] Publishing {platform} Story...")

    story = client.video_upload_to_story(media_file)

    print(
        f"[INSTAGRAM] Story published successfully. ID: {story.pk}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Publish a platform-specific Instagram Story."
    )

    parser.add_argument(
        "--platform",
        required=True,
        choices=sorted(STORY_ASSETS.keys()),
        help="Streaming platform: twitch or kick"
    )

    args = parser.parse_args()

    config = load_config()

    publish_story(args.platform, config)


if __name__ == "__main__":
    main()
