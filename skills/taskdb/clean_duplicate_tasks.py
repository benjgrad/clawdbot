#!/usr/bin/env python3

from taskdb import TaskDatabase

def clean_duplicate_tasks():
    db = TaskDatabase()
    
    # Find and remove duplicate TISC presentation tasks
    db.cursor.execute('''
        DELETE FROM tasks 
        WHERE id = 1 AND title = 'Update TISC Presentation'
    ''')
    
    print(f"Rows deleted: {db.cursor.rowcount}")
    db.conn.commit()
    
    # Verify remaining tasks
    db.cursor.execute('SELECT id, title FROM tasks')
    print("\nRemaining Tasks:")
    for task in db.cursor.fetchall():
        print(f"ID: {task[0]}, Title: {task[1]}")
    
    db.close()

if __name__ == '__main__':
    clean_duplicate_tasks()