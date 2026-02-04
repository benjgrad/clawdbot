import sqlite3
import os
from datetime import datetime

class TaskDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.expanduser('~/clawd/taskdb.sqlite')
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                priority INTEGER DEFAULT 2,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                due_date DATETIME,
                tags TEXT,
                context TEXT
            )
        ''')
        self.conn.commit()

    def add_task(self, title, description=None, priority=2, context=None, tags=None, due_date=None):
        tags = tags or ''
        self.cursor.execute('''
            INSERT INTO tasks 
            (title, description, priority, tags, context, due_date) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, description, priority, tags, context, due_date))
        self.conn.commit()
        return self.cursor.lastrowid

    def list_tasks(self, status='pending', priority=None):
        query = 'SELECT * FROM tasks WHERE status = ?'
        params = [status]
        
        if priority is not None:
            query += ' AND priority = ?'
            params.append(priority)
        
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def complete_task(self, task_id):
        self.cursor.execute('''
            UPDATE tasks 
            SET status = 'completed', 
                updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (task_id,))
        self.conn.commit()

    def close(self):
        self.conn.close()

def main():
    db = TaskDatabase()
    # Example usage
    task_id = db.add_task(
        "Update TISC Presentation", 
        description="Prepare slides for membership session",
        priority=1,
        context="Professional"
    )
    print(f"Added task with ID: {task_id}")
    db.close()

if __name__ == '__main__':
    main()