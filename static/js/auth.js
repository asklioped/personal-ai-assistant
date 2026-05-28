document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault(); // Зупиняємо перезавантаження сторінки
    
    const usernameInput = document.getElementById('username').value;
    const passwordInput = document.getElementById('password').value;
    const errorDiv = document.getElementById('errorMessage');
    
    errorDiv.classList.add('hidden');

    // Формуємо дані у форматі форми для FastAPI
    const formData = new URLSearchParams();
    formData.append('username', usernameInput);
    formData.append('password', passwordInput);

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            // Якщо вхід успішний, перенаправляємо на головну сторінку чату
            window.location.href = '/';
        } else {
            // Якщо бекенд повернув помилку
            errorDiv.innerText = data.detail || 'Помилка авторизації';
            errorDiv.classList.remove('hidden');
        }
    } catch (err) {
        errorDiv.innerText = 'Немає зв\'язку з сервером';
        errorDiv.classList.remove('hidden');
    }
});