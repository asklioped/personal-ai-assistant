from datetime import datetime, timedelta
import bcrypt
import jwt
from fastapi import Request, HTTPException, status

# Налаштування безпеки, в майбутьному їх краще винести в .env
SECRET_KEY = "SUPER_SECRET_KEY_JAKYI_NIHTO_NE_ZNAJE"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
COOKIE_NAME = "access_token"

def hash_password(password: str) -> str:
    """Перетворює чистий пароль на безпечний хеш"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verifity_password(plain_password: str, hashed_password: str) -> bool:
    """Перевіряє, чи збігається введений пароль із хешем з бази."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    """Герерує JWT-токен із терміном дії"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user_id(request: Request) -> int:
    """Функція-захисник (Dependency). Дістає токен з кук, 
    перевіряє його і повертає user_id. Якщо щось не так — кидає 401 помилку."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Немає токена авторизації. Вхід заборонено!"
        )
    try:
        playload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = playload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалідний токен")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Термін дії токена закінчився")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Помилка авторизації")