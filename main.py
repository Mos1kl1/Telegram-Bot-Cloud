import telebot
import sqlite3
import logging
from config import TOKEN

bot = telebot.TeleBot(TOKEN)

logger = logging.getLogger(__name__)
DB_PATH = 'Users.db'

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def init_db():
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER NOT NULL UNIQUE PRIMARY KEY,
            User_id INTEGER,
            username TEXT,
            FirstName TEXT,
            LastName TEXT
        )
        """)
        conn.commit()


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    with sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10) as conn:
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
    user_name = message.text.strip()
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
    user_name = message.text.strip()
    bot.send_message(message.chat.id, '''Your history:''')
    logger.info(f"Name: {user_name}, ID: {user_id}, {message.text}")

init_db()
bot.polling(none_stop=True)
