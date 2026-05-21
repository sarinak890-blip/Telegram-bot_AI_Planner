import os
import logging
import aiosqlite
from datetime import datetime

DB_NAME = "planner_bot.db"
 
logger = logging.getLogger(__name__)
 
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                aim TEXT,
                start_date TEXT,
                end_date TEXT,
                weekends TEXT,
                remind_time TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_date TEXT,
                description TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        """)

        await db.commit()
    logger.info("База данных успешно инициализирована.")
 
 
async def user_has_plan(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result is not None
 
 
async def save_user_settings(user_id: int, aim: str, start_date: str, end_date: str, weekends: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, aim, start_date, end_date, weekends)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, aim, start_date, end_date, weekends))
        await db.commit()
 
 
async def save_remind_time(user_id: int, remind_time: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET remind_time = ? WHERE user_id = ?", (remind_time, user_id))
        await db.commit()
 
 
async def save_plan_tasks(user_id: int, tasks_list: list):
    async with aiosqlite.connect(DB_NAME) as db:
        data_to_insert = [(user_id, date, desc) for date, desc in tasks_list]
        await db.executemany("""
            INSERT INTO tasks (user_id, task_date, description)
            VALUES (?, ?, ?)
        """, data_to_insert)
        
        await db.commit()
 
 
async def get_current_plan_text(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT task_date, description FROM tasks WHERE user_id = ? ORDER BY id ASC", 
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            
            if not rows:
                return None

            plan_text = ""
            for idx, row in enumerate(rows, 1):
                date, desc = row
                plan_text += f"{idx}. [{date}] — {desc}\n"
            return plan_text
 
 
async def update_plan_text(user_id: int, new_plan_raw: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
            lines = new_plan_raw.strip().split("\n")
            tasks_to_insert = []
            
            for line in lines:
                if not line:
                    continue
                start_bracket = line.find("[")
                end_bracket = line.find("]")
                dash = line.find("—")
                
                if start_bracket != -1 and end_bracket != -1 and dash != -1:
                    date_str = line[start_bracket + 1:end_bracket]
                    desc_str = line[dash + 1:].strip()
                    tasks_to_insert.append((user_id, date_str, desc_str))
            
            if tasks_to_insert:
                await db.executemany("""
                    INSERT INTO tasks (user_id, task_date, description)
                    VALUES (?, ?, ?)
                """, tasks_to_insert)
                await db.commit()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при ручном обновлении плана в БД: {e}")
            return False
 
 
async def delete_user_plan(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
 
 
async def get_tasks_for_remind(current_date: str, current_time: str) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT t.user_id, t.description 
            FROM tasks t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.task_date = ? AND u.remind_time = ?
        """, (current_date, current_time)) as cursor:
            return await cursor.fetchall()