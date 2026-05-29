# personal-ai-assistant
My personal AI assistant
## Встановлення додатку
Викачуємо репозиторій:
```bash
git clone https://github.com/asklioped/personal-ai-assistant.git
```

Заходимо в каталог та створюємо віртуальне середовище:
``` bash
python3 -m venv venv
```
Активуємо середовище:
```bash
source venv/bin/activate
```
Встановлюємо залежності:
```bash
pip install -r requirement.txt
```
Створюємо файл .env з такими текстом та вигадуємо складний ключ:
```txt
# Вкажіть складний великий ключ
SECRET_KEY=
# Вкажіть development, якщо середовище розробки або production - якщо це продакшин
ENV=development
# Якщо development - 127.0.0.1, чякщо production - 0.0.0.0
HOST= 
# Порт ставим 8080, якщо необхідно інший, вказуєм відповідний
PORT=
# Шлях до сервера AI у вигляді http://ip-адреса:порт/api/chat
OLLAMA_URL=
# Назва моделі, зазвичай llama3
MODEL_NAME=
```
Додаємо користувача:
```bash
python3 add_user.py
```
Запуск:
```bash
python2 main.py
```