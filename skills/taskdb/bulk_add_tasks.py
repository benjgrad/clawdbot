#!/usr/bin/env python3

from taskdb import TaskDatabase

def add_tasks():
    tasks = [
        {
            'title': 'Update TISC Membership session presentation slides',
            'description': 'Prepare and update slides for TISC Membership session',
            'priority': 1,
            'context': 'Professional'
        },
        {
            'title': 'Book doctor appointment',
            'description': 'Schedule medical check-up, verify insurance',
            'priority': 2,
            'context': 'Health'
        },
        {
            'title': 'Book camping trip',
            'description': 'Research sites, check availability, confirm dates',
            'priority': 2,
            'context': 'Personal'
        },
        {
            'title': "Update driver's license",
            'description': 'Update address on driver\'s license',
            'priority': 3,
            'context': 'Administrative'
        },
        {
            'title': 'Update passport',
            'description': 'Prepare and update passport documentation',
            'priority': 4,
            'context': 'Administrative'
        }
    ]

    db = TaskDatabase()
    for task in tasks:
        task_id = db.add_task(**task)
        print(f"Added task: {task['title']} (ID: {task_id})")
    
    db.close()

if __name__ == '__main__':
    add_tasks()