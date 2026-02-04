#!/usr/bin/env python3

from taskdb import TaskDatabase
from datetime import datetime, timedelta

def update_tasks_with_schedule():
    db = TaskDatabase()
    
    # Calculate next DND date (2 weeks from last one)
    next_dnd = datetime.now() + timedelta(weeks=2)
    next_dnd = next_dnd.replace(hour=5, minute=0, second=0, microsecond=0)
    
    # Task updates with scheduling considerations
    tasks_schedule = [
        {
            'id': 2,
            'title': 'Update TISC Membership session presentation slides',
            'due_date': (datetime.now() + timedelta(days=3)).isoformat(),
            'notes': 'Priority task, schedule around DND and other commitments'
        },
        {
            'id': 3,
            'title': 'Book doctor appointment',
            'due_date': (datetime.now() + timedelta(days=7)).isoformat(),
            'notes': f'Avoid scheduling during DND time ({next_dnd.strftime("%Y-%m-%d")})'
        },
        {
            'id': 4,
            'title': 'Book camping trip',
            'due_date': (datetime.now() + timedelta(days=14)).isoformat(),
            'notes': 'Flexible scheduling, consider weekends'
        },
        {
            'id': 5,
            'title': 'Update driver\'s license',
            'due_date': (datetime.now() + timedelta(days=30)).isoformat(),
            'notes': 'Non-urgent, can be scheduled when convenient'
        },
        {
            'id': 6,
            'title': 'Update passport',
            'due_date': (datetime.now() + timedelta(days=60)).isoformat(),
            'notes': 'No immediate travel plans, long-term task'
        }
    ]
    
    for task in tasks_schedule:
        db.cursor.execute('''
            UPDATE tasks 
            SET due_date = ?, description = ? 
            WHERE id = ?
        ''', (task['due_date'], task['notes'], task['id']))
    
    db.conn.commit()
    
    # Retrieve and print updated tasks
    db.cursor.execute('SELECT id, title, due_date, description FROM tasks')
    print("Updated Tasks:")
    for task in db.cursor.fetchall():
        print(f"ID: {task[0]}, Title: {task[1]}, Due: {task[2]}, Notes: {task[3]}")
    
    db.close()

if __name__ == '__main__':
    update_tasks_with_schedule()