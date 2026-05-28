import uvicorn
import json
import os
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from fastapi import BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services import ollama_client
from database import queries
from database.connection import init_db, get_db_connection
from auth.security import (
    verify_password,  # Виправлено чисту назву функції безпеки
    create_access_token,
    get_current_user_id,
    COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_DAYS
)

# Вказуємо константи IP адреси та порту, на якому працює програма
HOST = "127.0.0.1"
PORT = 8080

# Перевіряємо, в якому режимі запускаємось. Якщо не вказано — вважаємо, що це продакшн (захищений)
ENV = os.getenv("ENV", "production")

# Створюємо додаток ОДИН раз із правильними налаштуваннями безпеки
app = FastAPI(
    title="Персональний AI помічник",
    # Якщо ENV == "development", документація (/docs) буде. Якщо "production" — замість неї буде 404 помилка
    docs_url="/docs" if ENV == "development" else None,
    redoc_url="/redoc" if ENV == "development" else None
)

# Модель для валідації вхідного повідомлення
class MessageInput(BaseModel):
    message: str

# Запускаємо ініціалізацію бази даних при старті додатка
@app.on_event("startup")
def startup_event():
    init_db()


#  --- ЕНДПОЇНТИ АУТЕНТИФІКАЦІЇ ---
@app.post("/api/auth/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """Ендпоінт для входу. FastAPI сам розпарсить логін та пароль з body запиту"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Шукаємо користувача в базі
    cursor.execute("SELECT * FROM users WHERE username = ?;", (form_data.username,))
    user = cursor.fetchone()
    conn.close()
    
    # КРОК 1: Перевіряємо, чи користувач взагалі існує
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильний логін або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # КРОК 2: Перевіряємо пароль
    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильний логін або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Якщо все OK, створюємо токен
    token_data = {"user_id": user["id"], "username": user["username"]}
    token = create_access_token(token_data)

    # Записуємо токен в HttpOnly Cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        expires=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",
        secure=False  # Постав True, якщо в майбутньому буде HTTPS
    )

    return {"status": "Успішний вхід", "username": user["username"]}


@app.post("/api/auth/logout")
def logout(response: Response):
    """Ендпоінт для виходу. Просто видаляємо куку."""
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax")
    return {"status": "Успішний вихід"}


# --- ЕНДПОЇНТИ ДЛЯ РОБОТИ З ЧАТАМИ ---

@app.get("/api/chats")
def get_chats(user_id: int = Depends(get_current_user_id)):
    """Отримати всі чати поточного користувача."""
    return queries.get_user_chats(user_id)


@app.post("/api/chats")
def create_chat(user_id: int = Depends(get_current_user_id)):
    """Створити новий чат."""
    new_session_id = queries.create_chat_session(user_id)
    return {"session_id": new_session_id, "title": "Новий чат"}


@app.get("/api/chats/{session_id}/messages")
def get_messages(session_id: str, user_id: int = Depends(get_current_user_id)):
    """Отримати історію повідомлень для конкретного чату (останні 50)."""
    return queries.get_chat_history(session_id, limit=50)


@app.delete("/api/chats/{session_id}")
def delete_chat(session_id: str, user_id: int = Depends(get_current_user_id)):
    """Видалити чат."""
    success = queries.delete_chat_session(session_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Чат не знайдено або доступ заборонено")
    return {"status": "Чат успішно видалено"}


@app.post("/api/chats/{session_id}/send")
async def send_message(
    session_id: str, 
    payload: MessageInput, 
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id)
):
    """Головний ендпоінт розмови з підтримкою SSE стрімінгу від Ollama."""
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Повідомлення не може бути порожнім")
        
    queries.save_message(session_id, "user", user_message)
    
    chat_history = queries.get_chat_history(session_id, limit=2)
    is_first_message = len(chat_history) <= 1

    async def sse_wrapper():
        full_assistant_reply = ""
        async for chunk in ollama_client.stream_chat(session_id, user_message):
            yield chunk
            
            if chunk.startswith("data: "):
                try:
                    json_str = chunk[6:].strip()
                    chunk_data = json.loads(json_str)
                    full_assistant_reply += chunk_data.get("text", "")
                except Exception:
                    pass
                    
        if full_assistant_reply:
            queries.save_message(session_id, "assistant", full_assistant_reply)
            
        if is_first_message:
            background_tasks.add_task(run_title_generation, session_id, user_message)

    async def run_title_generation(sid: str, msg: str):
        new_title = await ollama_client.generate_chat_title(msg)
        queries.update_chat_title(sid, new_title)

    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")


# Монтуємо статику
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.get("/login")
def login_page():
    return FileResponse("static/login.html")

# Основний запуск програми
if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)