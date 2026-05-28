import httpx
import json
from database.queries import get_chat_history

# Адреса твоєї локальної Ollama
OLLAMA_URL = "http://192.168.217.70:11434/api/chat"
# Назва моделі, яку ти завантажив в Ollama (наприклад: llama3, mistral, qwen2.5 і т.д.)
MODEL_NAME = "llama3" 

SYSTEM_PROMPT = {
    "role": "system",
    "content": "Ти — корисний, розумний та лаконічний персональний помічник. Відповідай українською мовою. Використовуй Markdown для форматування коду, списків та жирного тексту."
}

async def stream_chat(session_id: str, new_message: str):
    """Асинхронний генератор для стрімінгу відповіді від Ollama.
    Реалізує логіку ковзного вікна контексту."""
    
    # 1. Дістаємо з бази останні 10 повідомлень (ковзне вікно)
    history = get_chat_history(session_id, limit=10)
    
    # 2. Формуємо масив повідомлень для Ollama
    messages = [SYSTEM_PROMPT]
    
    # Додаємо історію
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    # Додаємо останнє, свіже повідомлення користувача
    messages.append({"role": "user", "content": new_message})
    
    # Payload для запиту до Ollama API
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True # Вмикаємо стрімінг!
    }
    
    # 3. Робимо асинхронний запит до Ollama та транслюємо токени
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", OLLAMA_URL, json=payload) as response:
            if response.status_code != 200:
                yield "data: Помилка зв'язку з Ollama API\n\n"
                return
                
            # Читаємо потік від Ollama рядок за рядком
            async for line in response.aiter_lines():
                if line:
                    # Ollama повертає рядки в форматі JSON-lines
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        # Формат SSE (Server-Sent Events) вимагає префікс 'data: ' і два переноси рядка в кінці
                        yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"


async def generate_chat_title(first_message: str) -> str:
    """Фонова задача для генерації назви чату на основі першого повідомлення."""
    prompt = f"Сформулюй коротку назву (максимум 3-4 слова) для чату, який починається з цього повідомлення: '{first_message}'. Видай ТІЛЬКИ назву, без лапок, пояснень чи знаків пунктуації в кінці."
    
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False # Тут стрімінг не потрібен, хочемо отримати все одним рядком
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(OLLAMA_URL, json=payload)
            if res.status_code == 200:
                data = res.json()
                title = data.get("message", {}).get("content", "").strip()
                return title if title else "Продовження розмови"
    except Exception:
        pass
    return "Новий чат"