"""
Remove.bg Telegram Bot

📌 Возможности:
- Принимает изображение и удаляет фон через API remove.bg.
- Гибкие настройки: качество, размер, формат, тип изображения, цвет фона.
- Поддержка платных подписок (премиум) для HD/4K.
- Инлайн-кнопки и обычные кнопки меню.
- История последних обработок.

🧰 Команды:
  /start     — краткая инструкция
  /help      — подсказка
  /settings  — текущие настройки
  /history   — история последних обработок

🔧 Настройка:
- Укажите API_ID, API_HASH и BOT_TOKEN от Telegram.
- Укажите REMOVEBG_API_KEY от remove.bg.
- Список премиум пользователей (платная подписка):
  PREMIUM_USER_IDS=123,456
- Можно задать через переменные окружения:
  TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, REMOVEBG_API_KEY
"""

import asyncio
import os
import tempfile
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, Optional

import requests
from telethon import Button, TelegramClient, events

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
REMOVEBG_API_KEY = os.getenv("REMOVEBG_API_KEY", "")
PREMIUM_USER_IDS = {
    int(user_id)
    for user_id in os.getenv("PREMIUM_USER_IDS", "").split(",")
    if user_id.strip().isdigit()
}

SESSION_NAME = "removebg_bot"

QUALITY_TO_SIZE = {
    "draft": "preview",
    "standard": "regular",
    "hd": "hd",
    "4k": "4k",
}

ALLOWED_FORMATS = {"png", "jpg"}
ALLOWED_TYPES = {"auto", "person", "product", "car"}

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


@dataclass
class UserSettings:
    quality: str = "standard"
    image_format: str = "png"
    image_type: str = "auto"
    bg_color: str = ""


user_settings: Dict[int, UserSettings] = {}
user_history: Dict[int, Deque[str]] = {}


def config_is_ready() -> bool:
    return all([API_ID, API_HASH, BOT_TOKEN, REMOVEBG_API_KEY])


def is_premium(user_id: int) -> bool:
    return user_id in PREMIUM_USER_IDS


def get_settings(user_id: int) -> UserSettings:
    if user_id not in user_settings:
        user_settings[user_id] = UserSettings()
    return user_settings[user_id]


def append_history(user_id: int, entry: str) -> None:
    history = user_history.setdefault(user_id, deque(maxlen=5))
    history.appendleft(entry)


def format_settings(user_id: int) -> str:
    settings = get_settings(user_id)
    premium_mark = "✅" if is_premium(user_id) else "❌"
    return (
        "⚙️ Текущие настройки:\n"
        f"Качество: {settings.quality}\n"
        f"Формат: {settings.image_format}\n"
        f"Тип: {settings.image_type}\n"
        f"Цвет фона: {settings.bg_color or 'прозрачный'}\n"
        f"Премиум: {premium_mark}"
    )


def remove_background(input_path: Path, output_path: Path, settings: UserSettings) -> None:
    with input_path.open("rb") as image_file:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": image_file},
            data={
                "size": QUALITY_TO_SIZE.get(settings.quality, "regular"),
                "format": settings.image_format,
                "type": settings.image_type,
                "bg_color": settings.bg_color or "",
            },
            headers={"X-Api-Key": REMOVEBG_API_KEY},
            timeout=60,
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"remove.bg error {response.status_code}: {response.text.strip()}"
        )
    output_path.write_bytes(response.content)


async def remove_background_async(
    input_path: Path, output_path: Path, settings: UserSettings
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, remove_background, input_path, output_path, settings)


def main_menu_buttons() -> list:
    return [
        [Button.text("⚙️ Настройки"), Button.text("🧾 История")],
        [Button.text("🎚 Качество"), Button.text("🖼 Формат")],
        [Button.text("🧍 Тип"), Button.text("🎨 Фон")],
        [Button.text("ℹ️ Помощь")],
    ]


def quality_buttons(user_id: int) -> list:
    premium = is_premium(user_id)
    buttons = [
        Button.inline("Draft", data=b"quality:draft"),
        Button.inline("Standard", data=b"quality:standard"),
    ]
    if premium:
        buttons.extend(
            [Button.inline("HD", data=b"quality:hd"), Button.inline("4K", data=b"quality:4k")]
        )
    return [buttons]


def format_buttons() -> list:
    return [
        [Button.inline("PNG", data=b"format:png"), Button.inline("JPG", data=b"format:jpg")]
    ]


def type_buttons() -> list:
    return [
        [
            Button.inline("Auto", data=b"type:auto"),
            Button.inline("Person", data=b"type:person"),
            Button.inline("Product", data=b"type:product"),
            Button.inline("Car", data=b"type:car"),
        ]
    ]


def bg_buttons() -> list:
    return [
        [Button.inline("Прозрачный", data=b"bg:clear")],
        [Button.inline("Белый", data=b"bg:ffffff"), Button.inline("Чёрный", data=b"bg:000000")],
        [Button.inline("Красный", data=b"bg:ff0000"), Button.inline("Синий", data=b"bg:0000ff")],
    ]


@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    await event.respond(
        "Привет! Отправь мне изображение, и я удалю фон через remove.bg.\n"
        "Используй кнопки меню для настроек или /help.",
        buttons=main_menu_buttons(),
    )


@client.on(events.NewMessage(pattern="/help"))
async def help_handler(event):
    await event.respond(
        "🧰 Команды:\n"
        "/start — краткая инструкция\n"
        "/help — подсказка\n"
        "/settings — показать текущие настройки\n"
        "/history — история последних обработок\n\n"
        "Отправь фото или файл с изображением — я верну PNG/JPG без фона.",
        buttons=main_menu_buttons(),
    )


@client.on(events.NewMessage(pattern="/settings"))
async def settings_handler(event):
    await event.respond(format_settings(event.sender_id), buttons=main_menu_buttons())


@client.on(events.NewMessage(pattern="/history"))
async def history_handler(event):
    history = user_history.get(event.sender_id)
    if not history:
        await event.respond("История пуста.", buttons=main_menu_buttons())
        return
    await event.respond("🧾 Последние операции:\n" + "\n".join(history))


@client.on(events.NewMessage)
async def menu_handler(event):
    if not event.text:
        return

    text = event.text.strip().lower()
    if text in {"⚙️ настройки", "настройки"}:
        await event.respond(format_settings(event.sender_id), buttons=main_menu_buttons())
        return
    if text in {"🧾 история", "история"}:
        await event.respond("Выберите /history для просмотра истории.")
        return
    if text in {"🎚 качество", "качество"}:
        await event.respond("Выберите качество:", buttons=quality_buttons(event.sender_id))
        return
    if text in {"🖼 формат", "формат"}:
        await event.respond("Выберите формат:", buttons=format_buttons())
        return
    if text in {"🧍 тип", "тип"}:
        await event.respond("Выберите тип изображения:", buttons=type_buttons())
        return
    if text in {"🎨 фон", "фон"}:
        await event.respond("Выберите фон:", buttons=bg_buttons())
        return
    if text in {"ℹ️ помощь", "помощь"}:
        await help_handler(event)


@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode("utf-8")
    settings = get_settings(event.sender_id)

    if data.startswith("quality:"):
        quality = data.split(":", 1)[1]
        if quality in {"hd", "4k"} and not is_premium(event.sender_id):
            await event.answer("HD/4K доступны только по подписке.", alert=True)
            return
        settings.quality = quality
        await event.answer(f"Качество: {quality}")
        await event.edit(format_settings(event.sender_id), buttons=main_menu_buttons())
        return

    if data.startswith("format:"):
        image_format = data.split(":", 1)[1]
        if image_format in ALLOWED_FORMATS:
            settings.image_format = image_format
            await event.answer(f"Формат: {image_format}")
            await event.edit(format_settings(event.sender_id), buttons=main_menu_buttons())
        return

    if data.startswith("type:"):
        image_type = data.split(":", 1)[1]
        if image_type in ALLOWED_TYPES:
            settings.image_type = image_type
            await event.answer(f"Тип: {image_type}")
            await event.edit(format_settings(event.sender_id), buttons=main_menu_buttons())
        return

    if data.startswith("bg:"):
        color = data.split(":", 1)[1]
        settings.bg_color = "" if color == "clear" else color
        await event.answer("Фон обновлён")
        await event.edit(format_settings(event.sender_id), buttons=main_menu_buttons())


@client.on(events.NewMessage)
async def image_handler(event):
    if event.text and event.text.startswith("/"):
        return

    if not config_is_ready():
        await event.respond(
            "⚠️ Бот не настроен. Проверьте TELEGRAM_API_ID, TELEGRAM_API_HASH, "
            "TELEGRAM_BOT_TOKEN и REMOVEBG_API_KEY."
        )
        return

    if not (event.photo or (event.document and event.document.mime_type)):
        return

    mime_type: Optional[str] = None
    if event.document:
        mime_type = event.document.mime_type

    if mime_type and not mime_type.startswith("image/"):
        await event.respond("⚠️ Отправьте изображение (JPEG/PNG).")
        return

    await event.respond("⏳ Удаляю фон, подождите...")

    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "input"
        output_path = Path(temp_dir) / "output.png"
        await event.download_media(file=str(input_path))

        settings = get_settings(event.sender_id)
        if settings.quality in {"hd", "4k"} and not is_premium(event.sender_id):
            settings.quality = "standard"

        try:
            await remove_background_async(input_path, output_path, settings)
        except Exception as exc:
            await event.respond(f"❌ Ошибка remove.bg: {exc}")
            return

        timestamp = datetime.now().strftime("%d.%m %H:%M")
        append_history(
            event.sender_id,
            f"{timestamp} — {settings.quality}, {settings.image_format}, {settings.image_type}",
        )
        await event.respond(file=str(output_path), message="✅ Готово!")


async def main() -> None:
    if not config_is_ready():
        print(
            "⚠️ Не все параметры заданы. Проверьте переменные окружения: "
            "TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, REMOVEBG_API_KEY"
        )
    await client.start(bot_token=BOT_TOKEN)
    print("Бот запущен. Ожидаю сообщения...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
