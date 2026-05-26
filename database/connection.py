import sqlite3
import os
from auth.security import hash_password

DB_PATH = "database.db"

def get_db_connection():
    """Функція для створення підключення до бази даних.
    Вмикаємо foreign keys, щоб працювало каскадне видалення чатів."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # Це дозволить діставати дані у вигляді словників, а не кортежів
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Створення таблиць, якщо вони не існують"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблиця користувачів
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP                   
    );
    """)

    # Таблиця сесій (чатів)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        title TEXT DEFAULT 'Новий чат',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE               
    );
    """)

    # Таблиця повідомлень
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );
    """)


    # Створення першого користувача для "Закритого клуба"
    cursor.execute("SELECT COUNT(*) FROM users;")
    if cursor.fetchone()[0] == 0:
        # Якщо користувачів нема, створюєм дфолтного
        admin_username = "admin"
        admin_password = "tua_49RD"     # <------ пароль який потім змінемо

        hashed = hash_password(admin_password)
        cursor.execute(
            "INSERT INTO users (username, hashed_password) VALUES (?, ?);",
            (admin_username, hashed)
        )
        print(f"Створено першого користувача! Login: {admin_username}, Password: {admin_password}")


    conn.commit()
    conn.close()
    print("Базу даних успішно ініціалізовано!")


   