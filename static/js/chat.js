let currentSessionId = null;

// Елементи DOM
const chatsList = document.getElementById('chatsList');
const messagesContainer = document.getElementById('messagesContainer');
const messageForm = document.getElementById('messageForm');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const currentChatTitle = document.getElementById('currentChatTitle');
const deleteChatBtn = document.getElementById('deleteChatBtn');
const newChatBtn = document.getElementById('newChatBtn');
const logoutBtn = document.getElementById('logoutBtn');

// === ДОПОМІЖНІ ФУНКЦІЇ ===

// Універсальний обробник запитів з перевіркою на 401 (Auth)
async function apiFetch(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (response.status === 401) {
            window.location.href = '/login';
            return null;
        }
        return response;
    } catch (err) {
        console.error("Помилка мережі:", err);
        return null;
    }
}

// Рендер окремого повідомлення на екран
function appendMessage(role, text) {
    const isUser = role === 'user';
    const msgHtml = `
        <div class="flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in">
            <div class="max-w-2xl px-4 py-3 rounded-2xl shadow-md text-sm leading-relaxed ${
                isUser ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-slate-800 text-slate-100 rounded-bl-none border border-slate-700'
            }">
                <div class="font-bold text-xs mb-1 opacity-60">${isUser ? 'Ви' : 'AI Помічник'}</div>
                <div class="whitespace-pre-wrap">${text}</div>
            </div>
        </div>
    `;
    messagesContainer.insertAdjacentHTML('beforeend', msgHtml);
    messagesContainer.scrollTop = messagesContainer.scrollHeight; // Скрол донизу
}

// === ЛОГІКА РОБОТИ З АПІ ===

// Завантажити список чатів
async function loadChats() {
    const res = await apiFetch('/api/chats');
    if (!res) return;
    const chats = await res.json();
    
    chatsList.innerHTML = '';
    if (chats.length === 0) {
        chatsList.innerHTML = '<div class="text-slate-500 text-sm p-2 text-center">Немає активних чатів</div>';
        return;
    }

    chats.forEach(chat => {
        const isActive = chat.id === currentSessionId;
        const btn = document.createElement('button');
        btn.className = `w-full text-left px-4 py-3 rounded-xl text-sm transition-all flex items-center justify-between cursor-pointer ${
            isActive ? 'bg-slate-700 text-white font-medium border border-slate-650' : 'text-slate-400 hover:bg-slate-750 hover:text-slate-200'
        }`;
        btn.innerHTML = `<span class="truncate pr-2">${chat.title}</span>`;
        btn.onclick = () => selectChat(chat.id, chat.title);
        chatsList.appendChild(btn);
    });
}

// Вибрати конкретну сесію чату
async function selectChat(sessionId, title) {
    currentSessionId = sessionId;
    currentChatTitle.innerText = title;
    deleteChatBtn.classList.remove('hidden');
    messageInput.disabled = false;
    sendBtn.disabled = false;

    // Оновлюємо активний клас у списку бокової панелі
    loadChats();

    // Завантажуємо історію повідомлень
    messagesContainer.innerHTML = '<div class="text-center text-slate-500 mt-10">Завантаження історії...</div>';
    const res = await apiFetch(`/api/chats/${sessionId}/messages`);
    if (!res) return;
    const messages = await res.json();

    messagesContainer.innerHTML = '';
    if (messages.length === 0) {
        messagesContainer.innerHTML = '<div class="text-center text-slate-500 mt-10">Тут ще немає повідомлень. Напишіть щось!</div>';
    } else {
        messages.forEach(msg => appendMessage(msg.role, msg.content));
    }
}

// Створити новий чаt
newChatBtn.onclick = async () => {
    const res = await apiFetch('/api/chats', { method: 'POST' });
    if (!res) return;
    const data = await res.json();
    selectChat(data.session_id, data.title);
};

// Видалити поточний чат
deleteChatBtn.onclick = async () => {
    if (!currentSessionId || !confirm("Ви впевнені, що хочете видалити цей чат?")) return;
    const res = await apiFetch(`/api/chats/${currentSessionId}`, { method: 'DELETE' });
    if (res && res.ok) {
        currentSessionId = null;
        currentChatTitle.innerText = "Оберіть або створіть чат";
        deleteChatBtn.classList.add('hidden');
        messageInput.disabled = true;
        sendBtn.disabled = true;
        messagesContainer.innerHTML = '<div class="text-center text-slate-500 mt-20">Чат видалено.</div>';
        loadChats();
    }
};

// Вихід з системи
logoutBtn.onclick = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
};

// === НАДІСЛАТИ ПОВІДОМЛЕННЯ + СТРІМІНГ ===
messageForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || !currentSessionId) return;

    // Якщо це було найперше повідомлення — очистимо заглушку на екрані
    if (messagesContainer.querySelector('.text-center')) {
        messagesContainer.innerHTML = '';
    }

    // Виводимо повідомлення користувача
    appendMessage('user', text);
    messageInput.value = ''; // Очищаємо інпут

    // Готуємо місце під відповідь ШІ
    appendMessage('assistant', '');
    const allMessages = messagesContainer.querySelectorAll('.whitespace-pre-wrap');
    const lastMessageDiv = allMessages[allMessages.length - 1]; // Останній div куди будемо "лити" текст

    // Блокуємо інтерфейс під час генерації
    messageInput.disabled = true;
    sendBtn.disabled = true;

    try {
        const response = await fetch(`/api/chats/${currentSessionId}/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

        // --- ОБРОБКА STREAMING (SSE) ---
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let aiReplyBuffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            // SSE пакує дані рядками виду "data: {...}\n\n"
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6).strip; 
                        const data = JSON.parse(line.slice(6));
                        aiReplyBuffer += data.text;
                        lastMessageDiv.innerText = aiReplyBuffer; // Оновлюємо текст на екрані
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    } catch (e) {
                        // Ігноруємо порожні або неповні шматки JSON
                    }
                }
            }
        }
    } catch (err) {
        lastMessageDiv.innerText = "Помилка зв'язку з сервером генерації.";
    } finally {
        // Розблоковуємо інтерфейс
        messageInput.disabled = false;
        sendBtn.disabled = false;
        messageInput.focus();
        // Фоново оновлюємо список чатів, бо Ollama могла згенерувати красиву назву чату
        setTimeout(loadChats, 1000);
    }
});

// Запуск при завантаженні сторінки
loadChats();