import telebot
import sqlite3
from config import TOKEN

bot = telebot.TeleBot(TOKEN)

DB_PATH = 'Users.db'


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
            bot.send_message(message.chat.id, "Вы уже зарегистрированы")
        else:
            cursor.execute(
                "INSERT INTO Users (User_id, username) VALUES (?, ?)",
                (user_id, user_name)
            )
            conn.commit()
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn = telebot.types.KeyboardButton("Добавить информацию")
            markup.add(btn)
            bot.send_message(message.chat.id, "Вы успешно зарегистрированы", reply_markup=markup)


user_states = {}


@bot.message_handler(func=lambda message: message.text == "Добавить информацию")
def add(message):
    user_id = message.from_user.id
    user_states[user_id] = 'waiting_first_name'
    bot.send_message(message.chat.id, "Напишите своё имя: ")


@bot.message_handler(func=lambda message:
message.from_user.id in user_states and
user_states[message.from_user.id] == 'waiting_first_name')
def get_first_name(message):
    user_id = message.from_user.id
    first_name = message.text.strip()
    user_states[user_id] = {'first_name': first_name, 'state': 'waiting_last_name'}
    bot.send_message(message.chat.id, "Напишите свою фамилию: ")


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
        conn.commit()

    del user_states[user_id]
    bot.send_message(message.chat.id, f"Данные успешно обновлены!\n"
                                      f"Имя: {first_name}\n"
                                      f"Фамилия: {last_name}")


init_db()
bot.polling(none_stop=True)
