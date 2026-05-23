import aiosqlite
import json
import os
from typing import List, Dict, Optional
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'memory.db')

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_used TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        ''')
        await db.commit()

async def get_session(session_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM sessions WHERE session_id = ?', (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def create_session(session_id: str) -> Dict:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            'INSERT INTO sessions (session_id, created_at, updated_at) VALUES (?, ?, ?)',
            (session_id, now, now)
        )
        await db.commit()
    return {'session_id': session_id, 'created_at': now, 'updated_at': now}

async def get_or_create_session(session_id: str) -> Dict:
    session = await get_session(session_id)
    if session is None:
        session = await create_session(session_id)
    return session

async def add_message(session_id: str, role: str, content: str, tool_used: Optional[str] = None):
    await get_or_create_session(session_id)
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            'INSERT INTO messages (session_id, role, content, tool_used, timestamp) VALUES (?, ?, ?, ?, ?)',
            (session_id, role, content, tool_used, now)
        )
        await db.execute(
            'UPDATE sessions SET updated_at = ? WHERE session_id = ?',
            (now, session_id)
        )
        await db.commit()

async def get_conversation_history(session_id: str, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT role, content, tool_used, timestamp FROM messages
               WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?''',
            (session_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

async def clear_session(session_id: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute('DELETE FROM messages WHERE session_id = ?', (session_id,))
        await db.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
        await db.commit()

async def get_all_sessions() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT session_id, created_at, updated_at FROM sessions ORDER BY updated_at DESC'
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
