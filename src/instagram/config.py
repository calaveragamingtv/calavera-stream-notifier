
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config" / "instagram.json"


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Instagram configuration not found: {CONFIG_FILE}"
        )

    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid Instagram configuration: {error}"
        ) from error

    if not isinstance(config, dict):
        raise ValueError("Instagram configuration must be a JSON object.")

    required_keys = {
        "dry_run",
        "session_file",
        "supported_images",
        "supported_videos",
    }

    missing_keys = required_keys - config.keys()

    if missing_keys:
        raise ValueError(
            f"Missing configuration keys: {', '.join(sorted(missing_keys))}"
        )

    if not isinstance(config["dry_run"], bool):
        raise ValueError("'dry_run' must be true or false.")

    if not isinstance(config["session_file"], str) or not config["session_file"].strip():
        raise ValueError("'session_file' must be a non-empty string.")

    for key in ("supported_images", "supported_videos"):
        extensions = config[key]

        if not isinstance(extensions, list) or not extensions:
            raise ValueError(f"'{key}' must be a non-empty list.")

        if not all(
            isinstance(ext, str) and ext.startswith(".")
            for ext in extensions
        ):
            raise ValueError(
                f"Every extension in '{key}' must be a string "
                "starting with a dot."
            )

        config[key] = [ext.lower() for ext in extensions]

    return config
