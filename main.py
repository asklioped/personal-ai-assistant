from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from database.connection import init_db, get_db_connection
from auth.security import (
    verifity_password,
    create_access_token,
    get_current_user_id,
    COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_DAYS
)

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