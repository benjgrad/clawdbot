#!/usr/bin/env python3

from taskdb import TaskDatabase
from datetime import datetime, timedelta
import subprocess

def add_calendar_events():
    db = TaskDatabase()
    db.cursor.execute('SELECT id, title, description, due_date FROM tasks')
    tasks = db.cursor.fetchall()
    
    for task in tasks:
        task_id, title, description, due_date = task
        
        # Convert due_date to a datetime object
        try:
            event_time = datetime.fromisoformat(due_date)
        except:
            print(f"Skipping {title} due to invalid date")
            continue
        
        # Prepare gog command
        gog_command = [
            'gog', 'calendar', 'events', 'create',
            '--account', 'bengrady4@gmail.com',
            '--title', title,
            '--start-date', event_time.strftime('%Y-%m-%dT10:00'),
            '--duration', '1h'
        ]
        
        if description:
            gog_command.extend(['--description', description])
        
        # Run the command
        try:
            result = subprocess.run(gog_command, capture_output=True, text=True)
            print(f"Added event: {title}")
            print(result.stdout)
        except Exception as e:
            print(f"Error adding event {title}: {e}")
    
    db.close()

if __name__ == '__main__':
    add_calendar_events()