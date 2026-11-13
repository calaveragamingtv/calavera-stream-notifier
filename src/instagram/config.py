
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config" / "instagram.json"


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Instagram configuration not found: {CONFIG_FILE}"
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = json.load(file)

    return config
