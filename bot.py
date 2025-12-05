import telebot
from telebot import types
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date

# ================== НАСТРОЙКИ ==================
TOKEN = "8477174849:AAG1s_JnqPya_8K7sN7f5ErFljj3YNp_TgQ"
ADMIN_IDS = [1011324289,1626629740]  # <- вставьте свой цифровой ID
DISCO_DATE = date(2025, 12, 25)  # Дата дискотеке

RULES_TEXT = """Правила школьной дискотеки:
1. Запрещается употребление алкоголя, никотина и др.
2. Уважайте других участников и организаторов.
3. Соблюдайте Dress-Code.
4. Танцуйте с удовольствием, но не нарушайте личное пространство.
5. Все треки воспроизводятся по решению организаторов.
"""

# ================== ИНИЦИАЛИЗАЦИЯ ==================
bot = telebot.TeleBot(TOKEN)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("key.json", scope)
client = gspread.authorize(creds)

# Google Sheets
sheet = client.open("school_disco")  # название таблицы
playlist_sheet = sheet.worksheet("playlist")
live_sheet = sheet.worksheet("live_requests")

# ================== /start ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    today = date.today()

    if today < DISCO_DATE:
        btn1 = types.InlineKeyboardButton("Этап 1 — Предложение трека", callback_data="add_playlist")
        markup.add(btn1)
    else:
        btn2 = types.InlineKeyboardButton("Этап 2 — Онлайн заказ", callback_data="add_live")
        markup.add(btn2)

    bot.send_message(message.chat.id, "Привет! Выбери действие:", reply_markup=markup)

# ================== /admin ==================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "Только админ может пользоваться этой панелью!")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("Очередь треков на утверждение")
    btn2 = types.KeyboardButton("Утверждённые треки")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

# ================== CALLBACK ==================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    # Проверка админа для утверждения/отклонения
    if call.data.startswith("approve_") or call.data.startswith("reject_"):
        if call.from_user.id not in ADMIN_IDS:
            bot.answer_callback_query(call.id, "Только админ!")
            return
        action = "approved" if call.data.startswith("approve_") else "rejected"
        row_number = int(call.data.split("_")[1])

        user_id = live_sheet.cell(row_number, 1).value
        track_name = live_sheet.cell(row_number, 3).value
        artist = live_sheet.cell(row_number, 4).value

        live_sheet.update_cell(row_number, 5, action)
        bot.answer_callback_query(call.id, f"Трек '{track_name}' {action}.")
        bot.send_message(int(user_id), f"Ваш трек '{track_name} — {artist}' был {action}!")
        return

    # Этап 1
    if call.data == "add_playlist":
        msg = bot.send_message(call.message.chat.id, "Отправьте трек в формате: Название Исполнитель")
        bot.register_next_step_handler(msg, add_playlist_track)
        bot.answer_callback_query(call.id)
        return

    # Этап 2
    if call.data == "add_live":
        msg = bot.send_message(call.message.chat.id, "Отправьте трек в формате: Название Исполнитель")
        bot.register_next_step_handler(msg, add_live_track)
        bot.answer_callback_query(call.id)
        return

# ================== ФУНКЦИИ ==================
def add_playlist_track(message):
    text = message.text.strip()
    parts = text.split(" ", 1)
    track_name, artist = (parts if len(parts) == 2 else (parts[0], ""))
    playlist_sheet.append_row([
        message.from_user.id,
        message.from_user.username,
        track_name,
        artist,
        datetime.now().strftime("%d.%m.%Y %H:%M")
    ])
    bot.send_message(message.chat.id, f"Ваш трек '{track_name} — {artist}' добавлен в плейлист!")
    bot.send_message(message.chat.id, RULES_TEXT)

def add_live_track(message):
    text = message.text.strip()
    parts = text.split(" ", 1)
    track_name, artist = (parts if len(parts) == 2 else (parts[0], ""))

    row_number = len(live_sheet.get_all_values()) + 1
    live_sheet.append_row([
        message.from_user.id,
        message.from_user.username,
        track_name,
        artist,
        "pending",
        datetime.now().strftime("%d.%m.%Y %H:%M")
    ])
    bot.send_message(message.chat.id,
                     f"Ваш трек '{track_name} — {artist}' добавлен на рассмотрение!")
    bot.send_message(message.chat.id, RULES_TEXT)

    # уведомление админа с кнопками
    for admin_id in ADMIN_IDS:
        markup = types.InlineKeyboardMarkup()
        approve = types.InlineKeyboardButton("✔ Утвердить", callback_data=f"approve_{row_number}")
        reject = types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{row_number}")
        markup.add(approve, reject)
        bot.send_message(admin_id,
                         f"Новый трек от @{message.from_user.username}:\n{track_name} — {artist}",
                         reply_markup=markup)

# ================== Обработка кнопок админ-панели ==================
@bot.message_handler(func=lambda m: m.from_user.id in ADMIN_IDS)
def handle_admin_buttons(message):
    if message.text == "Очередь треков на утверждение":
        pending_tracks = live_sheet.get_all_values()[1:]
        text = "Треки на утверждение:\n"
        count = 0
        for i, row in enumerate(pending_tracks, start=2):
            if row[4] == "pending":
                text += f"{i-1}. {row[2]} — {row[3]} (от @{row[1]})\n"
                count += 1
        if count == 0:
            text = "Нет треков на утверждение."
        bot.send_message(message.chat.id, text)

    elif message.text == "Утверждённые треки":
        approved_tracks = live_sheet.get_all_values()[1:]
        text = "Утверждённые треки:\n"
        count = 0
        for i, row in enumerate(approved_tracks, start=2):
            if row[4] == "approved":
                text += f"{i-1}. {row[2]} — {row[3]} (от @{row[1]})\n"
                count += 1
        if count == 0:
            text = "Пока нет утверждённых треков."
        bot.send_message(message.chat.id, text)

# ================== ЗАПУСК БОТА ==================
bot.polling(none_stop=True)
