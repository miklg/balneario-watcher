import json
import os
from pathlib import Path

import requests


COVERMANAGER_URL = (
    "https://www.covermanager.com/reserve/crossellingFuture/"
)

RESTAURANT = "restaurante-balneario.beach-club-tarifa"
PEOPLE = "4"
REFERENCE_DATE = "2026-08-10"
REFERENCE_HOUR = "15:00"

INTERESTING_HOURS = {"13:30", "15:00"}

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = Path("balneario_estado.json")


def get_availability() -> dict[str, list[str]]:
    payload = {
        "language": "spanish",
        "restaurant": RESTAURANT,
        "hour": REFERENCE_HOUR,
        "date": REFERENCE_DATE,
        "people": PEOPLE,
        "extra": "",
    }

    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.covermanager.com",
        "Referer": (
            "https://www.covermanager.com/reserve/module_restaurant/"
            "restaurante-balneario.beach-club-tarifa/spanish"
        ),
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 Chrome/150 Safari/537.36"
        ),
    }

    response = requests.post(
        COVERMANAGER_URL,
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except requests.JSONDecodeError as exc:
        raise RuntimeError(
            f"CoverManager no devolvió JSON: {response.text[:500]!r}"
        ) from exc

    availability: dict[str, list[str]] = {}

    for item in data.get("restaurant_crosseling_future", []):
        date_value = item.get("date")
        available_hours = item.get("hoursdisp", [])

        matching_hours = sorted(
            hour
            for hour in available_hours
            if hour in INTERESTING_HOURS
        )

        if date_value and matching_hours:
            availability[date_value] = matching_hours

    return availability


def load_previous_state() -> dict[str, list[str]]:
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, list[str]]) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def send_telegram(message: str) -> None:
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    response.raise_for_status()


def format_date(date_value: str) -> str:
    year, month, day = date_value.split("-")
    return f"{day}/{month}/{year}"


def main() -> None:
    current = get_availability()
    previous = load_previous_state()

    print("Disponibilidad actual:")

    if not current:
        print("No hay disponibilidad para 13:30 ni 15:00.")

    for date_value, hours in sorted(current.items()):
        print(f"{format_date(date_value)}: {', '.join(hours)}")

    new_slots: list[tuple[str, str]] = []

    for date_value, current_hours in current.items():
        previous_hours = previous.get(date_value, [])

        for hour in current_hours:
            if hour not in previous_hours:
                new_slots.append((date_value, hour))

    if new_slots:
        lines = [
            "🏖️ Nueva disponibilidad en Balneario Beach Club Tarifa",
            "",
        ]

        for date_value, hour in sorted(new_slots):
            lines.append(
                f"📅 {format_date(date_value)}"
                f" — 🕒 {hour}"
                f" — 👥 {PEOPLE}"
            )

        lines.extend(
            [
                "",
                (
                    "Reserva: https://www.covermanager.com/reserve/"
                    "module_restaurant/"
                    "restaurante-balneario.beach-club-tarifa/spanish"
                ),
            ]
        )

        send_telegram("\n".join(lines))
        print("Notificación enviada por Telegram.")
    else:
        print("No hay nuevas disponibilidades.")

    save_state(current)


if __name__ == "__main__":
    main()
