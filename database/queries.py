import uuid
from database.connection import get_db_connection

# === РОБОТА З ЧАТАМИ (СЕСІЯМИ) ===

def create_chat_session(user_id: int) -> str:
    """Створює новий порожній чат для користувача і повертає його UUID."""
    session_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO sessions (id, user_id, title) VALUES (?, ?, ?);",
        (session_id, user_id, "Новий чат")
    )
    
    conn.commit()
    conn.close()
    return session_id

def get_user_chats(user_id: int):
    """Повертає список усіх чатів користувача, відсортованих від найсвіжіших."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, title, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC;",
        (user_id,)
    )
    chats = cursor.fetchall()
    conn.close()
    
    # Перетворюємо sqlite3.Row в список звичайних словників для FastAPI
    return [dict(chat) for chat in chats]

def update_chat_title(session_id: str, new_title: str):
    """Оновлює назву чату (знадобиться, коли Ollama згенерує красивий тайтл)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
        (new_title, session_id)
    )
    
    conn.commit()
    conn.close()

def delete_chat_session(session_id: str, user_id: int) -> bool:
    """Видаляє чат. Додатково перевіряє user_id для безпеки, 
    щоб ніхто не міг видалити чужий чат, знаючи його UUID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "DELETE FROM sessions WHERE id = ? AND user_id = ?;",
        (session_id, user_id)
    )
    # rowcount покаже, чи дійсно був видалений рядок (якщо чат існує і він належить цьому юзеру)
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    return deleted


# === РОБОТА З ПОВІДОМЛЕННЯМИ ===

def save_message(session_id: str, role: str, content: str):
    """Зберігає репліку (користувача або асистента) в базу даних 
    та оновлює час останньої активності чату."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Зберігаємо повідомлення
    cursor.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?);",
        (session_id, role, content)
    )
    
    # 2. Оновлюємо updated_at чату, щоб він піднявся вгору в списку
    cursor.execute(
        "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
        (session_id,)
    )
    
    conn.commit()
    conn.close()

def get_chat_history(session_id: str, limit: int = 10):
    """Дістає останні повідомлення чату для нашого 'ковзного вікна'.
    Беремо останні репліки, але повертаємо їх у правильному хронологічному порядку."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Беремо останні N повідомлень, сортуючи назад (DESC)
    cursor.execute(
        """SELECT role, content FROM messages 
           WHERE session_id = ? 
           ORDER BY created_at DESC LIMIT ?;""",
        (session_id, limit)
    )
    messages = cursor.fetchall()
    conn.close()
    
    # Перетворюємо в словники та розгортаємо список назад, щоб хронологія була правильною (від старих до нових)
    history = [dict(msg) for msg in messages]
    history.reverse()
    
    return history