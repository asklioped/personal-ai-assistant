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
SECRET_KEY=
ENV=production
```
Додаємо користувача:
```bash
python3 add_user.py
```
Запуск, поки що:
```python
unicorn main:app --reload
```