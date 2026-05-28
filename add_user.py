import sqlite3
import getpass
from auth.security import hash_password
from database.connection import init_db, DB_PATH

def create_user_via_terminal():
    print("===Реєстрація нового користувача===")

    # Переконуємось, що база та таблиці взагалі існують
    init_db()

    username = input("Введіть логін (username): ").strip()
    if not username:
        print("Помилка: Логін не може бути порожнім!")
        return
    
    # getpass ховає введення пароля в терміналі
    password = getpass.getpass("Введіть пароль (він не відображається!): ")
    password_confirm = getpass.getpass("Підтвердіть пароль: ")

    if password != password_confirm:
        print("Паролі не збігаються!")
        return
    
    if len(password) < 6:
        print("Помилка: Параоль має бути не менше 6 символів!")
        return
    
    hashed = hash_password(password)
    
    conn =sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, hashed_password) VALUES (?, ?);",
            (username, hashed)
        )
        conn.commit()
        print(f"\n Успіх! Кроистувача'{username}' успішно додано до системи!")
    except sqlite3.IntegrityError:
        print(f"\n Помилка: Користувач з логіном '{username}' вже існує в базі!")
    finally:
        conn.close()

if __name__ == "__main__":
    create_user_via_terminal()