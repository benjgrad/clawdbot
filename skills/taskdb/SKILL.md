---
name: taskdb
description: Manage tasks in a persistent SQLite database. Add, list, complete, prioritize, and search tasks with tags, priorities, and due dates. Use when the user mentions tasks, to-dos, tracking work items, or task management.
metadata: {"moltbot":{"os":["darwin","linux"],"requires":{"bins":["python3"]}}}
---

# TaskDB

Persistent, SQLite-backed task management for Clawdbot.

## When to Use

- User asks to add, list, complete, or search tasks
- User mentions to-dos, action items, or work tracking
- User wants to prioritize or organize tasks
- You need to check what tasks are pending

## Quick Start

```bash
# List pending tasks
python3 {baseDir}/list_tasks.py

# Add a task via Python
python3 -c "
from taskdb import TaskDatabase
db = TaskDatabase()
db.add_task('Task title', description='Details', priority=1, tags='#work')
db.close()
"
```

## Database

**Location:** `~/clawd/taskdb.sqlite`

**Schema:**

| Column | Type | Default |
|--------|------|---------|
| id | INTEGER (PK) | autoincrement |
| title | TEXT | required |
| description | TEXT | null |
| priority | INTEGER | 2 (1=high, 2=medium, 3=low) |
| status | TEXT | "pending" |
| created_at | DATETIME | now |
| updated_at | DATETIME | now |
| due_date | DATETIME | null |
| tags | TEXT | empty |
| context | TEXT | null |

## Available Scripts

All scripts are in `{baseDir}/`:

| Script | Purpose |
|--------|---------|
| `taskdb.py` | Core `TaskDatabase` class — import and use directly |
| `list_tasks.py` | Print all pending tasks |
| `bulk_add_tasks.py` | Add multiple tasks at once |
| `clean_duplicate_tasks.py` | Remove duplicate entries |

## Core API

```python
from taskdb import TaskDatabase

db = TaskDatabase()                          # connects to ~/clawd/taskdb.sqlite
db.add_task(title, description, priority, context, tags, due_date)
db.list_tasks(status='pending', priority=None)
db.complete_task(task_id)
db.close()
```

## Examples

**Add a task:**
```python
db.add_task("Review PR #42", description="Check test coverage", priority=1, tags="#work #code-review")
```

**List high-priority pending tasks:**
```python
tasks = db.list_tasks(status='pending', priority=1)
```

**Complete a task:**
```python
db.complete_task(42)
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `sqlite3.OperationalError: no such table` | Database not initialized | Instantiate `TaskDatabase()` — it auto-creates the table |
| `FileNotFoundError` on db_path | `~/clawd/` directory missing | Create directory: `mkdir -p ~/clawd` |
| Duplicate tasks | Same task added multiple times | Run `python3 {baseDir}/clean_duplicate_tasks.py` |
