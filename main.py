import telebot
import sqlite3
import logging
import os
from PIL import Image
import pillow_heif
from config import TOKEN

bot = telebot.TeleBot(TOKEN)
pillow_heif.register_heif_opener()

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = 'Users.db'
save_dir = os.path.join(os.getcwd(), 'downloads')

file_info = {}
user_states = {}

if not os.path.exists(save_dir):
    os.makedirs(save_dir)

def init_db():
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                User_id INTEGER UNIQUE,
                username TEXT,
                FirstName TEXT,
                LastName TEXT
            )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserActions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                User_id INTEGER,
                action TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

def log_user_action(user_id, action):
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO UserActions (User_id, action) VALUES (?, ?)",
                (user_id, action)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging action for user {user_id}: {e}")

def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("/addinfo"), telebot.types.KeyboardButton("/history"))
    markup.add(telebot.types.KeyboardButton("/konvert"))
    return markup

def get_format_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("/png", "/jpg", "/webp")
    markup.row("/heic", "/tiff")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "User"
    first_name = message.from_user.first_name or ""
    log_user_action(user_id, "Запустил бота (/start)")
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT User_id FROM Users WHERE User_id = ?", (user_id,))
            if cursor.fetchone():
                msg = f"Добрый день, {username}! Вы уже зарегистрированы."
            else:
                cursor.execute(
                    "INSERT INTO Users (User_id, username, FirstName) VALUES (?, ?, ?)",
                    (user_id, username, first_name)
                )
                conn.commit()
                msg = "Вы успешно зарегистрировались!"
            bot.send_message(message.chat.id, msg, reply_markup=get_main_keyboard())
            if os.path.exists('start.jpg'):
                with open('start.jpg', 'rb') as photo:
                    bot.send_photo(message.chat.id, photo,
                                   caption="**Функционал:**\n1. /addinfo - Профиль\n2. /history - История\n3. /konvert - Конвертер",
                                   parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, "Команды:\n/addinfo, /history, /konvert")
    except Exception as e:
        logger.error(f"Error in start command: {e}")

@bot.message_handler(commands=['history'])
@bot.message_handler(func=lambda message: message.text == "/history")
def history(message):
    user_id = message.from_user.id
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT action, timestamp FROM UserActions WHERE User_id = ? ORDER BY timestamp DESC LIMIT 10",
                (user_id,)
            )
            actions = cursor.fetchall()
        if actions:
            response = "📜 **Ваши последние действия:**\n\n"
            for action, timestamp in actions:
                response += f"▫️ `{timestamp}`: {action}\n"
        else:
            response = "Ваша история пока пуста."
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"History error: {e}")
        bot.send_message(message.chat.id, "Ошибка при получении истории.")

@bot.message_handler(func=lambda message: message.text == "/addinfo")
def add_info_start(message):
    user_id = message.from_user.id
    user_states[user_id] = 'waiting_first_name'
    bot.send_message(message.chat.id, "Введите ваше имя:")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_first_name')
def get_first_name(message):
    user_id = message.from_user.id
    first_name = message.text.strip()
    user_states[user_id] = {'first_name': first_name, 'state': 'waiting_last_name'}
    bot.send_message(message.chat.id, f"Приятно познакомиться, {first_name}! Теперь введите фамилию:")

@bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id), dict) and user_states[m.from_user.id].get('state') == 'waiting_last_name')
def get_last_name(message):
    user_id = message.from_user.id
    last_name = message.text.strip()
    first_name = user_states[user_id]['first_name']
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE Users SET FirstName = ?, LastName = ? WHERE User_id = ?",
                           (first_name, last_name, user_id))
            conn.commit()
        log_user_action(user_id, f"Обновил профиль: {first_name} {last_name}")
        bot.send_message(message.chat.id, f"Данные сохранены: {first_name} {last_name}",
                         reply_markup=get_main_keyboard())
        del user_states[user_id]
    except Exception as e:
        logger.error(f"DB Update error: {e}")
        bot.send_message(message.chat.id, "Ошибка сохранения.")

@bot.message_handler(func=lambda message: message.text == "/konvert")
def konvert_start(message):
    bot.send_message(message.chat.id, "Пришлите фото, которое нужно сконвертировать.",
                     reply_markup=telebot.types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo', 'document'])
def handle_docs_photo(message):
    user_id = message.from_user.id
    try:
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
        else:
            file_id = message.document.file_id
        file_info_tg = bot.get_file(file_id)
        ext = file_info_tg.file_path.split('.')[-1].lower()
        file_name = f"{file_id}.{ext}"
        local_path = os.path.join(save_dir, file_name)
        downloaded = bot.download_file(file_info_tg.file_path)
        with open(local_path, 'wb') as f:
            f.write(downloaded)
        file_info[user_id] = {'path': local_path, 'name': file_name}
        bot.send_message(user_id, "В какой формат перевести?", reply_markup=get_format_keyboard())
    except Exception as e:
        logger.error(f"Upload error: {e}")
        bot.send_message(user_id, "Ошибка при загрузке.")

@bot.message_handler(func=lambda m: m.text in ["/png", "/jpg", "/webp", "/heic", "/tiff"])
def apply_convert(message):
    user_id = message.from_user.id
    target = message.text[1:].upper()
    if target == "JPG": target = "JPEG"
    if target == "HEIC": target = "HEIF"
    if user_id not in file_info:
        bot.send_message(user_id, "Сначала пришлите фото!")
        return
    try:
        input_path = file_info[user_id]['path']
        output_ext = "heic" if target == "HEIF" else target.lower()
        output_path = os.path.splitext(input_path)[0] + f".{output_ext}"
        with Image.open(input_path) as img:
            if (target == "JPEG" or target == "HEIF") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            if target == "TIFF":
                img.save(output_path, format=target, compression="tiff_lzw")
            else:
                img.save(output_path, format=target)
        with open(output_path, 'rb') as f:
            bot.send_document(user_id, f, caption=f"Готово! Формат: {target.replace('HEIF', 'HEIC')}")
        log_user_action(user_id, f"Конвертация в {target}")
        os.remove(input_path)
        os.remove(output_path)
        del file_info[user_id]
        bot.send_message(user_id, "Что делаем дальше?", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Convert error: {e}")
        bot.send_message(user_id, f"Ошибка конвертации: {e}")

@bot.message_handler(func=lambda message: True)
def log_everything(message):
    if message.text and not message.text.startswith('/'):
        log_user_action(message.from_user.id, f"Сообщение: {message.text[:20]}...")

def cleanup_temp_files():
    if os.path.exists(save_dir):
        for f in os.listdir(save_dir):
            try:
                os.unlink(os.path.join(save_dir, f))
            except:
                pass

if __name__ == "__main__":
    init_db()
    cleanup_temp_files()
    bot.polling(none_stop=True)    with sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT User_id FROM Users WHERE User_id = ?", (user_id,))
        user = cursor.fetchone()

        if user:
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn1 = telebot.types.KeyboardButton("/addinfo")
            btn2 = telebot.types.KeyboardButton("/command")
            btn3 = telebot.types.KeyboardButton("/history")
            markup.add(btn1, btn2, btn3)
            bot.send_message(message.chat.id, "You are already registered", reply_markup=markup)
        else:
            cursor.execute(
                "INSERT INTO Users (User_id, username) VALUES (?, ?)",
                (user_id, user_name)
            )
            conn.commit()
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn1 = telebot.types.KeyboardButton("/addinfo")
            btn2 = telebot.types.KeyboardButton("/command")
            btn3 = telebot.types.KeyboardButton("/history")
            markup.add(btn1, btn2, btn3)
            bot.send_message(message.chat.id, "You have successfully registered.", reply_markup=markup)
            logger.info(f"Registered {user_name}, ID: {user_id}")


user_states = {}


@bot.message_handler(func=lambda message: message.text == "/addinfo")
def add(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    user_states[user_id] = 'waiting_first_name'
    bot.send_message(message.chat.id, "Write your first name: ")
    logger.info(f"Name: {user_name}, ID: {user_id}, {message.text}")


@bot.message_handler(func=lambda message:
message.from_user.id in user_states and
user_states[message.from_user.id] == 'waiting_first_name')
def get_first_name(message):
    user_id = message.from_user.id
    first_name = message.text.strip()
    user_states[user_id] = {'first_name': first_name, 'state': 'waiting_last_name'}
    bot.send_message(message.chat.id, "Write your last name: ")


@bot.message_handler(func=lambda message:
message.from_user.id in user_states and
isinstance(user_states[message.from_user.id], dict) and
user_states[message.from_user.id]['state'] == 'waiting_last_name')
def get_last_name(message):
    user_id = message.from_user.id
    last_name = message.text.strip()
    first_name = user_states[user_id]['first_name']

    with sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Users SET FirstName = ?, LastName = ? WHERE User_id = ?",
            (first_name, last_name, user_id)
        )
        logger.info(f"Updated {user_id}, ID: {user_id}")
        conn.commit()

    del user_states[user_id]
    bot.send_message(message.chat.id, f"Data updated successfully!\n"
                                      f"First Name: {first_name}\n"
                                      f"Last Name: {last_name}")

@bot.message_handler(func=lambda message: message.text == "/command")
def command(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    bot.send_message(message.chat.id, '''
    1) /start - Launch the bot and register in it\n
2) /addinfo - Add information (First name, Last name)\n
3) /command - Display all commands\n
4) /history - Display all user queries\n
    ''')
    logger.info(f"Name: {user_name}, ID: {user_id}, {message.text}")

@bot.message_handler(func=lambda message: message.text == "/history")
def history(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    bot.send_message(message.chat.id, '''Your history:''')
    logger.info(f"Name: {user_name}, ID: {user_id}, {message.text}")

init_db()
bot.polling(none_stop=True)
