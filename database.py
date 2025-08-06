import sqlite3
import os
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'issued.db')

def init_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Проверяем существование таблицы
        c.execute('''SELECT name FROM sqlite_master WHERE type='table' AND name='issued_configs' ''')
        table_exists = c.fetchone()
        
        if not table_exists:
            # Создаем таблицу с правильной структурой
            c.execute('''CREATE TABLE issued_configs (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER NOT NULL,
                         username TEXT,
                         full_name TEXT NOT NULL,
                         organization TEXT NOT NULL,
                         config_file TEXT NOT NULL,
                         issue_time DATETIME NOT NULL,
                         issue_type TEXT NOT NULL)''')
            logger.info("Таблица issued_configs создана")
        else:
            # Проверяем структуру существующей таблицы
            c.execute("PRAGMA table_info(issued_configs)")
            columns = [col[1] for col in c.fetchall()]
            required_columns = ['id', 'user_id', 'username', 'full_name', 'organization', 'config_file', 'issue_time', 'issue_type']
            
            # Добавляем отсутствующие колонки
            for col in required_columns:
                if col not in columns:
                    if col == 'issue_type':
                        c.execute("ALTER TABLE issued_configs ADD COLUMN issue_type TEXT NOT NULL DEFAULT 'standard'")
                    elif col == 'issue_time':
                        c.execute("ALTER TABLE issued_configs ADD COLUMN issue_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
                    else:
                        # Для других колонок определяем тип
                        col_type = 'TEXT'
                        if col in ['id', 'user_id']:
                            col_type = 'INTEGER'
                        c.execute(f"ALTER TABLE issued_configs ADD COLUMN {col} {col_type} {'NOT NULL' if col != 'username' else ''} DEFAULT ''")
                    
                    logger.warning(f"Добавлена колонка {col} в таблицу issued_configs")
        
        conn.commit()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

def add_issued_config(user_id, username, full_name, organization, config_file, issue_type="standard"):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        issue_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute('''INSERT INTO issued_configs 
                     (user_id, username, full_name, organization, config_file, issue_time, issue_type) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, username, full_name, organization, config_file, issue_time, issue_type))
        conn.commit()
        logger.info(f"Добавлен конфиг в БД: {config_file} для {user_id}")
    except Exception as e:
        logger.error(f"Ошибка добавления записи в БД: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

def get_issued_configs(limit=5, offset=0):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM issued_configs ORDER BY issue_time DESC LIMIT ? OFFSET ?", (limit, offset))
        results = c.fetchall()
        logger.info(f"Получено записей из БД: {len(results)}")
        return results
    except Exception as e:
        logger.error(f"Ошибка получения записей из БД: {e}", exc_info=True)
        return []
    finally:
        if conn:
            conn.close()

def get_issued_config_by_id(record_id):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM issued_configs WHERE id = ?", (record_id,))
        result = c.fetchone()
        return result
    except Exception as e:
        logger.error(f"Ошибка получения записи по ID: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()

def delete_issued_config(record_id):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM issued_configs WHERE id = ?", (record_id,))
        conn.commit()
        logger.info(f"Удалена запись #{record_id} из БД")
    except Exception as e:
        logger.error(f"Ошибка удаления записи из БД: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

def count_issued_configs():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM issued_configs")
        count = c.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Ошибка подсчета записей в БД: {e}", exc_info=True)
        return 0
    finally:
        if conn:
            conn.close()

# Инициализация БД при импорте
init_db()