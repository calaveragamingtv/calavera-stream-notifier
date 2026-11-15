
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_FILE = PROJECT_ROOT / "data" / "last_run_summary.json"


def generate_summary(data: dict) -> dict:
    """
    Normalizes the execution data and generates the final summary.
    Does not call external APIs or publish messages.
    """

    summary = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "execution": data.get("execution", {}),
        "services": data.get("services", {}),
        "stream": data.get("stream", {}),
        "publications": data.get("publications", {}),
        "errors": data.get("errors", []),
    }

    return summary


def save_summary(summary: dict) -> None:
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(SUMMARY_FILE, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=4, ensure_ascii=False)

    print(f"\n[SUMMARY] Saved to: {SUMMARY_FILE}")


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 55)
    print("          CALAVERA STREAM NOTIFIER")
    print("                EXECUTION SUMMARY")
    print("=" * 55)

    execution = summary.get("execution", {})
    services = summary.get("services", {})
    stream = summary.get("stream", {})
    publications = summary.get("publications", {})

    print(f"\nDate: {summary.get('timestamp', 'Unknown')}")
    print(f"Result: {execution.get('status', 'UNKNOWN')}")
    print(f"Reason: {execution.get('reason', 'Not specified')}")

    print("\n--- SERVICES ---")

    for name, result in services.items():
        if isinstance(result, dict):
            status = result.get("status", "NOT_CHECKED")
            detail = result.get("detail", "")
        else:
            status = str(result)
            detail = ""

        print(f"{name.upper():12} {status} {detail}")

    print("\n--- STREAM DETECTION ---")
    print(f"Platform: {stream.get('platform', 'None')}")
    print(f"Status: {stream.get('status', 'UNKNOWN')}")
    print(f"Channel: {stream.get('channel', 'Unknown')}")
    print(f"Game: {stream.get('game', 'Unknown')}")
    print(f"Viewers: {stream.get('viewers', 0)}")
    print(f"Stream ID: {stream.get('stream_id', 'None')}")
    print(f"URL: {stream.get('url', 'None')}")

    print("\n--- PUBLICATIONS ---")

    for name, result in publications.items():
        if not isinstance(result, dict):
            result = {"status": str(result)}

        status = result.get("status", "NOT_CHECKED")
        message = result.get("message")

        print(f"\n{name.upper()}: {status}")

        if message:
            print(f"Message: {message}")

        if result.get("detail"):
            print(f"Detail: {result['detail']}")

    errors = summary.get("errors", [])

    print("\n--- ERRORS ---")

    if errors:
        for error in errors:
            print(f"- {error}")
    else:
        print("No errors.")

    print("\n" + "=" * 55)


def finalize_summary(data: dict) -> dict:
    """
    Generates, prints and saves the execution summary.
    """

    summary = generate_summary(data)
    print_summary(summary)
    save_summary(summary)

    return summary
