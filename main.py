from fastapi import FastAPI
from database.connection import init_db

app = FastAPI(title="Персональний AI помічник")

# Запускаємо ініціалізацію бази даних при старті додатка
@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def read_root():
    return{"status": "Backend працює, база готова!"}