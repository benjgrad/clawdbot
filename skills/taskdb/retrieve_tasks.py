#!/usr/bin/env python3

from taskdb import TaskDatabase

def list_tasks():
    db = TaskDatabase()
    tasks = db.list_tasks()
    print("Current Tasks:")
    for task in tasks:
        print(f"ID: {task[0]}, Title: {task[1]}, Priority: {task[3]}, Status: {task[4]}")
    db.close()

if __name__ == '__main__':
    list_tasks()