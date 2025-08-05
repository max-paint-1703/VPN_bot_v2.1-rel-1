### Полное руководство по развертыванию Telegram-бота для выдачи WireGuard конфигов с расширенной функциональностью

---

#### 1. Структура проекта
```
/wireguard-bot
├── /configs
│   ├── /available         # Исходные конфиги (.conf файлы)
│   └── /used              # Использованные конфиги
├── /data
│   ├── issued.db          # База данных выданных конфигов
│   └── bot.log            # Файл логов
├── .env                   # Конфигурационные переменные
├── bot.py                 # Основной код бота
├── database.py            # Работа с базой данных
├── Dockerfile             # Конфигурация Docker
├── docker-compose.yml     # Конфигурация Docker Compose
└── requirements.txt       # Зависимости Python
```

---

#### 2. Файлы конфигурации

**.env**:
```ini
TOKEN=ваш_токен_от_BotFather
ADMIN_ID=ваш_telegram_id
```

**requirements.txt**:
```
python-telegram-bot==20.3
python-dotenv==1.0.0
sqlite3
```

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/configs/available /app/configs/used /app/data

CMD ["python", "bot.py"]
```

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  telegram-bot:
    build: .
    container_name: wireguard-bot
    restart: unless-stopped
    volumes:
      - ./configs:/app/configs
      - ./data:/app/data
    env_file:
      - .env
```

---

#### 3. База данных (database.py)

```python
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'issued.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS issued_configs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER NOT NULL,
                 username TEXT,
                 full_name TEXT NOT NULL,
                 organization TEXT NOT NULL,
                 config_file TEXT NOT NULL,
                 issue_time DATETIME NOT NULL,
                 issue_type TEXT NOT NULL)''')
    conn.commit()
    conn.close()

def add_issued_config(user_id, username, full_name, organization, config_file, issue_type="standard"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    issue_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO issued_configs 
                 (user_id, username, full_name, organization, config_file, issue_time, issue_type) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, username, full_name, organization, config_file, issue_time, issue_type))
    conn.commit()
    conn.close()

def get_issued_configs(limit=5, offset=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM issued_configs ORDER BY issue_time DESC LIMIT ? OFFSET ?", (limit, offset))
    results = c.fetchall()
    conn.close()
    return results

def get_issued_config_by_id(record_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM issued_configs WHERE id = ?", (record_id,))
    result = c.fetchone()
    conn.close()
    return result

def delete_issued_config(record_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM issued_configs WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

def count_issued_configs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM issued_configs")
    count = c.fetchone()[0]
    conn.close()
    return count

# Инициализация БД при импорте
init_db()
```

---

#### 4. Основной код бота (bot.py)

```python
import os
import shutil
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler
)
import database as db

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Пути к директориям
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AVAILABLE_DIR = os.path.join(BASE_DIR, 'configs', 'available')
USED_DIR = os.path.join(BASE_DIR, 'configs', 'used')
LOG_FILE = os.path.join(BASE_DIR, 'data', 'bot.log')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename=LOG_FILE
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
FIO, ORG = range(2)

# Глобальные структуры данных
pending_requests = {}
list_state = {}

def check_configs():
    """Проверка наличия доступных конфигов"""
    if not os.path.exists(AVAILABLE_DIR):
        os.makedirs(AVAILABLE_DIR)
    if not os.path.exists(USED_DIR):
        os.makedirs(USED_DIR)
    
    configs = [f for f in os.listdir(AVAILABLE_DIR) if f.endswith('.conf')]
    logger.info(f"Доступно конфигов: {len(configs)}")
    return configs

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    user = update.message.from_user
    logger.info(f"Пользователь {user.id} запустил бота")
    
    keyboard = [[InlineKeyboardButton("🔑 Запросить конфиг", callback_data='request_config')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        "Я бот для выдачи конфигураций WireGuard VPN\n\n"
        "⚠️ Для работы бота необходимо:\n"
        "1. Начать приватный чат со мной (@KaratVpn_bot)\n"
        "2. Не блокировать бота",
        reply_markup=reply_markup
    )

async def request_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопки 'Запросить конфиг'"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите ваше ФИО:")
    return FIO

async def get_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ФИО от пользователя"""
    user = update.message.from_user
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text("Введите вашу организацию:")
    return ORG

async def get_org(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение организации от пользователя и отправка запроса администратору"""
    user = update.message.from_user
    organization = update.message.text
    full_name = context.user_data['full_name']
    
    configs = check_configs()
    if not configs:
        await update.message.reply_text("⚠️ Все ключи временно закончились. Администратор уведомлен.")
        await notify_admin(context, "⚠️ ВНИМАНИЕ! Закончились доступные конфиги!")
        return ConversationHandler.END
    
    config_file = configs[0]
    pending_requests[user.id] = {
        'config_file': config_file,
        'full_name': full_name,
        'organization': organization
    }
    
    username = f"@{user.username}" if user.username else "нет username"
    request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admin_message = (
        f"🆕 Новый запрос конфига:\n"
        f"👤 Имя: {user.full_name}\n"
        f"📌 Username: {username}\n"
        f"🆔 ID: {user.id}\n"
        f"🏢 Организация: {organization}\n"
        f"👨‍💼 ФИО: {full_name}\n"
        f"🕒 Время: {request_time}\n"
        f"📁 Файл: {config_file}"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Принять", callback_data=f"approve_{user.id}"),
         InlineKeyboardButton("❌ Отказать", callback_data=f"reject_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            reply_markup=reply_markup
        )
        await update.message.reply_text("✅ Ваш запрос отправлен администратору. Ожидайте решения.")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения администратору: {e}")
        await update.message.reply_text("⚠️ Ошибка при обработке запроса. Попробуйте позже.")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена процесса запроса"""
    await update.message.reply_text("Запрос отменен.")
    return ConversationHandler.END

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий администратора"""
    query = update.callback_query
    await query.answer()
    
    try:
        data_parts = query.data.split('_')
        action = data_parts[0]
        user_id = int(data_parts[1])
        
        request_data = pending_requests.get(user_id)
        if not request_data:
            await query.message.reply_text("⚠️ Запрос не найден или уже обработан")
            return
        
        config_file = request_data['config_file']
        full_name = request_data['full_name']
        organization = request_data['organization']
        
        if action == "approve":
            src_path = os.path.join(AVAILABLE_DIR, config_file)
            dest_path = os.path.join(USED_DIR, config_file)
            
            try:
                # Отправка конфига пользователю
                await context.bot.send_document(
                    chat_id=user_id,
                    document=open(src_path, 'rb'),
                    caption=f"✅ Ваш конфиг: {config_file}"
                )
                shutil.move(src_path, dest_path)
                
                # Запись в базу данных
                user_data = await context.bot.get_chat(user_id)
                username = user_data.username if user_data.username else None
                db.add_issued_config(user_id, username, full_name, organization, config_file)
                
                # Уведомление администратора
                await query.message.reply_text(
                    f"✅ Конфиг {config_file} выдан пользователю ID: {user_id}\n"
                    f"👤 ФИО: {full_name}\n"
                    f"🏢 Организация: {organization}"
                )
            except Exception as e:
                logger.error(f"Ошибка выдачи конфига {user_id}: {e}")
                await query.message.reply_text(f"🚫 Ошибка выдачи конфига: {e}")
            finally:
                if user_id in pending_requests:
                    del pending_requests[user_id]
        
        elif action == "reject":
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Ваш запрос на получение конфига отклонён администратором"
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {user_id}: {e}")
            
            await query.message.reply_text(f"❌ Запрос пользователя ID: {user_id} отклонён")
            if user_id in pending_requests:
                del pending_requests[user_id]
    
    except Exception as e:
        logger.error(f"Ошибка в обработке callback: {e}")
        await query.message.reply_text("⚠️ Ошибка при обработке запроса")

async def list_issued(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для вывода списка выданных конфигов"""
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ Эта команда доступна только администратору")
        return
    
    # Сброс состояния
    context.user_data['list_page'] = 0
    await show_list_page(update, context)

async def show_list_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение страницы списка"""
    page = context.user_data.get('list_page', 0)
    limit = 5
    offset = page * limit
    
    configs = db.get_issued_configs(limit, offset)
    total_count = db.count_issued_configs()
    
    if not configs and page == 0:
        await update.message.reply_text("📭 Список выданных конфигов пуст")
        return
    
    message = f"📋 Список выданных конфигов (страница {page + 1}):\n\n"
    for i, config in enumerate(configs, start=1):
        record_id, user_id, username, full_name, organization, config_file, issue_time, issue_type = config
        message += (
            f"🔹 #{record_id}\n"
            f"👤 Пользователь: @{username or 'N/A'} (ID: {user_id})\n"
            f"👨‍💼 ФИО: {full_name}\n"
            f"🏢 Организация: {organization}\n"
            f"🔑 Конфиг: {config_file}\n"
            f"🕒 Время выдачи: {issue_time}\n"
            f"⚡️ Тип: {'Быстрая выдача' if issue_type == 'fast' else 'Стандартная'}\n\n"
        )
    
    # Создаем клавиатуру для навигации
    keyboard = []
    
    # Кнопка "Удалить"
    if configs:
        keyboard.append([InlineKeyboardButton("❌ Удалить запись", callback_data="delete_record")])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data="list_prev"))
    if offset + limit < total_count:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data="list_next"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def handle_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий в списке"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    page = context.user_data.get('list_page', 0)
    
    if action == "list_prev":
        context.user_data['list_page'] = max(0, page - 1)
    elif action == "list_next":
        context.user_data['list_page'] = page + 1
    elif action == "delete_record":
        await query.message.reply_text("Введите ID записи для удаления:")
        context.user_data['awaiting_delete_id'] = True
        return
    
    await show_list_page(update, context)

async def handle_delete_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка удаления записи"""
    if not context.user_data.get('awaiting_delete_id', False):
        return
    
    try:
        record_id = int(update.message.text)
        config_data = db.get_issued_config_by_id(record_id)
        
        if not config_data:
            await update.message.reply_text("⚠️ Запись с таким ID не найдена")
            return
        
        db.delete_issued_config(record_id)
        await update.message.reply_text(f"✅ Запись #{record_id} успешно удалена")
        
        # Обновляем список
        context.user_data['awaiting_delete_id'] = False
        await show_list_page(update, context)
    except ValueError:
        await update.message.reply_text("⚠️ Пожалуйста, введите числовой ID записи")

async def get_fast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скрытая команда для быстрой выдачи конфига без верификации"""
    user = update.message.from_user
    logger.info(f"Быстрая выдача запрошена пользователем {user.id} через /getfast")
    
    configs = check_configs()
    if not configs:
        await update.message.reply_text("⚠️ Все ключи временно закончились!")
        return
    
    config_file = configs[0]
    src_path = os.path.join(AVAILABLE_DIR, config_file)
    dest_path = os.path.join(USED_DIR, config_file)
    
    try:
        # Отправка конфига пользователю
        await context.bot.send_document(
            chat_id=user.id,
            document=open(src_path, 'rb'),
            caption=f"⚡️ Ваш конфиг (быстрая выдача): {config_file}"
        )
        shutil.move(src_path, dest_path)
        
        # Запись в базу данных
        username = f"@{user.username}" if user.username else None
        db.add_issued_config(
            user.id, 
            username, 
            "Быстрая выдача", 
            "Не указана", 
            config_file,
            issue_type="fast"
        )
        
        # Уведомление администратора
        username_display = username if username else f"ID: {user.id}"
        await notify_admin(
            context, 
            f"⚡️ Быстрая выдача по команде /getfast!\n"
            f"🔑 Конфиг: {config_file}\n"
            f"👤 Пользователь: {username_display}\n"
            f"🕒 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await update.message.reply_text(
            f"✅ Конфиг {config_file} успешно выдан!\n"
            "Администратор уведомлен о выдаче."
        )
    except Exception as e:
        logger.error(f"Ошибка быстрой выдачи: {e}")
        await update.message.reply_text(
            "⚠️ Не удалось выдать конфиг. Убедитесь, что:\n"
            "1. Вы начали приватный чат с ботом\n"
            "2. Не блокировали бота"
        )

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Уведомление администратора"""
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления администратора: {e}")

def main():
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('get_config', request_config),
            CallbackQueryHandler(request_config, pattern='^request_config$')
        ],
        states={
            FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio)],
            ORG: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_org)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_issued))
    application.add_handler(CommandHandler("getfast", get_fast))
    application.add_handler(CallbackQueryHandler(handle_admin_callback, pattern='^approve_|^reject_'))
    application.add_handler(CallbackQueryHandler(handle_list_callback, pattern='^list_|^delete_record'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_record))
    
    # Проверка начальных условий
    configs = check_configs()
    if not configs:
        logger.warning("Нет доступных конфигов!")
        notify_admin(application, "⚠️ ВНИМАНИЕ! На старте нет доступных конфигов!")
    
    # Запуск бота
    logger.info("Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()
```

---

### Пошаговая инструкция по запуску

1. **Подготовка сервера**:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install docker.io docker-compose -y
sudo systemctl enable docker
```

2. **Создание структуры проекта**:
```bash
mkdir -p wireguard-bot/{configs/available,data}
cd wireguard-bot
touch .env Dockerfile docker-compose.yml requirements.txt bot.py database.py
```

3. **Заполнение файлов**:
- Скопируйте содержимое каждого файла из инструкции
- Поместите WireGuard конфиги в `configs/available`
- Заполните `.env` своими данными:
  ```
  TOKEN=ваш_токен_от_BotFather
  ADMIN_ID=ваш_telegram_id
  ```

4. **Запуск в Docker**:
```bash
docker-compose up -d --build
```

5. **Проверка работы**:
```bash
docker logs -f wireguard-bot
```

---

### Ключевые особенности реализации

1. **Скрытая команда быстрой выдачи**:
   - Реализована команда `/getfast` доступная всем пользователям
   - Не отображается в интерфейсе бота (скрытая функция)
   - Выдает конфиг без верификации администратора
   - Автоматически уведомляет администратора о выдаче

2. **Сбор данных пользователя**:
   - При стандартном запросе бот запрашивает ФИО и организацию
   - Данные отображаются администратору при обработке запроса
   - После выдачи данные сохраняются в базе данных

3. **Управление историей выдачи**:
   - Команда `/list` для администратора выводит историю выданных конфигов
   - Пагинация по 5 записей на странице с навигацией
   - Возможность удаления записей по ID
   - Отображение типа выдачи (стандартная/быстрая)

4. **База данных**:
   - SQLite для хранения истории выдачи
   - Сохраняет все данные: ФИО, организацию, username, тип выдачи, время
   - Данные сохраняются между перезапусками бота

5. **Уведомления администратора**:
   - Уведомления о новых запросах
   - Уведомления о быстрых выдачах
   - Уведомления о проблемах (закончились конфиги)
   - Сообщения никогда не удаляются из чата

---

### Инструкция для пользователей

1. **Стандартная выдача конфига**:
   - Отправьте команду `/start`
   - Нажмите "🔑 Запросить конфиг"
   - Введите ФИО и организацию
   - Ожидайте подтверждения администратора

2. **Быстрая выдача (скрытая команда)**:
   - Отправьте команду `/getfast`
   - Конфиг будет выдан немедленно
   - Администратор получит уведомление о выдаче

3. **Для администраторов**:
   - `/list` - просмотр истории выдачи
   - Кнопки "Принять/Отклонить" в запросах
   - Уведомления о всех действиях в системе

---

### Важные примечания

1. **Безопасность и скрытность**:
   - Команда `/getfast` не анонсируется в боте
   - Сообщается только доверенным менеджерам
   - Все использования логируются и уведомляют администратора

2. **Первоначальная настройка**:
   - Поместите конфиги в `configs/available` перед запуском
   - Убедитесь, что файл `.env` заполнен корректно
   - Проверьте права доступа: `chmod -R 700 wireguard-bot`

3. **Мониторинг**:
   - Регулярно проверяйте логи: `docker logs -f wireguard-bot`
   - Следите за уведомлениями о быстрых выдачах
   - Контролируйте количество доступных конфигов

4. **Обновление бота**:
```bash
docker-compose down
# Внесите изменения в файлы
docker-compose up -d --build
```

5. **Добавление новых конфигов**:
   - Поместите новые .conf файлы в `configs/available`
   - Перезапустите контейнер: `docker-compose restart`

Данная реализация предоставляет гибкую систему выдачи WireGuard конфигов со стандартной процедурой верификации и скрытой командой для экстренной выдачи. Все действия фиксируются в базе данных и уведомляют администратора, обеспечивая полный контроль над процессом выдачи.
