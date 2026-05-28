import json
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from fastapi import BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from services import ollama_client
from database import queries
from database.connection import init_db, get_db_connection
from auth.security import (
    verifi_password,
    create_access_token,
    get_current_user_id,
    COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_DAYS
)
# Додаткова модель для валідації вхідного повідомлення
from pydantic import BaseModel
class MessageInput(BaseModel):
    message: str

app = FastAPI(title="Персональний AI помічник")

# Запускаємо ініціалізацію бази даних при старті додатка
@app.on_event("startup")
def startup_event():
    init_db()


#  --- ЕНДПОЇНТИ АУТЕНТИФІКАЦІЇ - - -
@app.post("/api/auth/login")
def login(response: Response, from_data: OAuth2PasswordRequestForm = Depends()):
    """Екндпоїнт для входу. FastAPI сам розпарсить логін та пароль з body запиту"""
    conn = get_db_connection()
    cursor = conn.cursor()

   # Шукаємо користувача в базі
    cursor.execute("SELECT * FROM users WHERE username = ?;", (from_data.username,))
    user = cursor.fetchone()
    conn.close()
    
    # КРОК 1: Перевіряємо, чи користувач взагалі існує
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильний логін або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # КРОК 2: Перевіряємо пароль, бо тепер ми на 100% впевнені, що user існує
    if not verifi_password(from_data.password, user["hashed_password"]):
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
        max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,    # Час життя в секундах
        expires=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",                                      # Захитс від CSRF атак
        secure=False                                        # Постав True, якщо в майбутньому буде HTTPS (для localhost - False)
    )

    return {"status": "Успішний вихід", "username": user["username"]}


@app.post("/api/auth/logout")
def logout(response: Response):
    """Ендпоінт для виходу. Просто видаляємо куку."""
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax")
    return {"status": "Успішний вихід"}


# --- ТЕСТОВИЙ ЗАХИЩЕНИЙ ЕНДПОІНТ ---
@app.get("/api/protected-test")
def protected_test(user_id: int = Depends(get_current_user_id)):
    """Цей ендпоінт недоступний без валідного токена в куках.
    Завдяки Depends(get_current_user_id), FastAPI спочатку запустить перевірку.
    Якщо токена немає або він битий — до цього коду виконання навіть не дійде."""
    return {
        "status": "Доступ дозволено!",
        "your_user_id": user_id,
        "message": "Ти успішно пройшов верифікацію системи безпеки."
    }

# --- ЕНДПОІНТИ ДЛЯ РОБОТИ З ЧАТАМИ ---

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
    """Отримати історію повідомлень для конкретного чату.
    Для старту віддамо трохи більше історії, наприклад останні 50 повідомлень,
    щоб користувач бачив свій старий діалог при перемиканні чатів."""
    # Примітка: тут в ідеалі перевірити, чи належить цей session_id нашому user_id.
    # Але для спрощення поки просто дістаємо історію.
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
    """Головний ендпоінт розмови: приймає повідомлення, записує в базу 
    та повертає «живий» потік тексту (SSE) від Ollama."""
    
    user_message = payload.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Повідомлення не може бути порожнім")
        
    # 1. Зберігаємо повідомлення користувача в базу даних
    queries.save_message(session_id, "user", user_message)
    
    # 2. Перевіряємо, чи це перше повідомлення в чаті (щоб згенерувати назву)
    # Якщо в історії до цього було 0 повідомлень (зараз там вже 1 — те, що ми щойно зберегли)
    chat_history = queries.get_chat_history(session_id, limit=2)
    is_first_message = len(chat_history) <= 1

    # Внутрішня функція-обгортка, яка запише відповідь бота в базу ПІСЛЯ того, як стрімінг закінчиться
    async def sse_wrapper():
        full_assistant_reply = ""
        # Запускаємо наш стрімінг з ollama_client
        async for chunk in ollama_client.stream_chat(session_id, user_message):
            yield chunk
            
            # Збираємо повну відповідь шматочок за шматочком для бази даних
            if chunk.startswith("data: "):
                try:
                    # Витягуємо чистий текст з SSE-формату
                    json_str = chunk[6:].strip()
                    chunk_data = json.loads(json_str)
                    full_assistant_reply += chunk_data.get("text", "")
                except Exception:
                    pass
                    
        # Коли стрімінг завершився — зберігаємо фінальну відповідь асистента в базу
        if full_assistant_reply:
            queries.save_message(session_id, "assistant", full_assistant_reply)
            
        # Якщо це був старт чату, запускаємо фонову генерацію назви
        if is_first_message:
            background_tasks.add_task(run_title_generation, session_id, user_message)

    # Функція, яка виконається на задньому плані
    async def run_title_generation(sid: str, msg: str):
        new_title = await ollama_client.generate_chat_title(msg)
        queries.update_chat_title(sid, new_title)

    # Повертаємо StreamingResponse з правильним медіа-типом для SSE
    return StreamingResponse(sse_wrapper(), media_type="text/event-stream")


# Монтуємо папку static, щоб файли всередині (js, css) були доступні браузеру
app.mount("/static", StaticFiles(directory="static"), name="static")

# Головна сторінка чату
@app.get("/")
def index():
    return FileResponse("static/index.html")

# Сторінка входу
@app.get("/login")
def login_page():
    return FileResponse("static/login.html")