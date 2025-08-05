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
                 issue_time DATETIME NOT NULL)''')
    conn.commit()
    conn.close()

def add_issued_config(user_id, username, full_name, organization, config_file):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    issue_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO issued_configs 
                 (user_id, username, full_name, organization, config_file, issue_time) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, username, full_name, organization, config_file, issue_time))
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