# Context Map

How data flows through this workspace. Read this when you need to understand
where something lives or how components connect.

## Directory Purposes

| Directory | Role | Key Files |
|-----------|------|-----------|
| `memory/` | Short-term logs, templates, practice guides | `YYYY-MM-DD.md`, `DAILY_TEMPLATE.md`, `stoic_adhd_practice.md` |
| `captures/` | Raw inbound data from all channels | `applications/`, `links/`, `insights/`, `recipes/`, `resume/` |
| `skills/` | Modular capabilities (each has `SKILL.md`) | `browser/`, `job-apply/`, `skillcraft/`, `taskdb/` |
| `tools/` | Shared runtime infrastructure | `browser_agent.py`, `.venv/`, `node_modules/` |
| `scripts/` | Standalone utility scripts | `add_calendar_events.py`, `stoic_practice_tracker.sh` |
| `projects/` | Active development projects | `calendar-integration/` |
| `canvas/`, `link-graph/` | Web UIs | Static HTML/JS apps |

## Core Files (Root)

| File | Purpose | Who Reads It | Who Writes It |
|------|---------|-------------|---------------|
| `SOUL.md` | Clawd's identity and values | Clawd (every session) | Clawd (rarely, with notification) |
| `USER.md` | Ben's profile and needs | Clawd (every session) | Clawd (when learning about Ben) |
| `MEMORY.md` | Long-term curated memory | Clawd (main sessions only) | Clawd (during memory maintenance) |
| `AGENTS.md` | Session startup + behavioral rules | Clawd (every session) | Clawd or Ben (when rules change) |
| `TOOLS.md` | Tool configs and capture paths | Clawd (when using tools) | Clawd (when tools change) |
| `HEARTBEAT.md` | Periodic check instructions | Clawd (on heartbeat poll) | Clawd (to adjust check schedule) |
| `IDENTITY.md` | Name, emoji, avatar | Clawd (on startup) | Rarely |
| `taskdb.sqlite` | Persistent task database | `skills/taskdb/` scripts | `skills/taskdb/` scripts |

## Data Flow: Capture to Memory

```
Inbound event (WhatsApp, email, browser, voice)
    |
    v
captures/<category>/         <-- Raw data lands here
    |                             (links/, insights/, recipes/, applications/)
    |
    v
[Tag with hashtags per TOOLS.md tagging system]
    |
    v
memory/YYYY-MM-DD.md         <-- Daily log records the event + context
    |
    v
[Periodic heartbeat review]
    |
    v
MEMORY.md                    <-- Distilled insights promoted to long-term memory
```

## Data Flow: Job Application

```
Job URL received
    |
    v
skills/job-apply/ cover_letter.py
    |  reads: captures/resume/Benjamin Grady - Senior Software Engineer.pdf
    |  writes: captures/applications/<company>/cover_letter.{html,pdf}
    |
    v
skills/job-apply/ apply.py
    |  uses: tools/.venv/, tools/browser_agent.py (for CAPTCHAs)
    |  reads: cover_letter.pdf, resume PDF
    |  writes: captures/applications/<company>/
    |          {result.json, screenshots/, session.gif, conversation.json,
    |           history.json, storage_state.json, task_prompt.txt}
    |
    v
captures/applications/tracker.md   <-- Append entry with status, steps, URL
    |
    v
memory/YYYY-MM-DD.md               <-- Log the application event
```

## Data Flow: Task Management

```
User mentions a task / to-do / action item
    |
    v
skills/taskdb/taskdb.py            <-- Python API: add, list, complete, search
    |  database: taskdb.sqlite (root of workspace)
    |
    v
list_tasks.py                      <-- Query and display pending tasks
    |
    v
[Tasks inform daily planning in memory/YYYY-MM-DD.md]
```

## Data Flow: Daily Reflection

```
HEARTBEAT.md triggers at 8 PM
    |
    v
memory/DAILY_TEMPLATE.md           <-- Template: morning intention, job search,
    |                                   fitness, love ethic, communication, evening review
    |
    v
memory/YYYY-MM-DD.md               <-- Filled-in daily reflection
    |
    v
memory/stoic_adhd_practice.md      <-- Optional: stoic prompts from
    |                                   stoic_reflection_templates.json
    |
    v
[Weekly/periodic review during heartbeat]
    |
    v
MEMORY.md                          <-- Key patterns and insights promoted
```

## Skill-Tool Dependency Map

| Skill | Tools Used | Captures Written |
|-------|-----------|-----------------|
| `job-apply` | `tools/.venv/`, `tools/browser_agent.py`, `puppeteer` | `captures/applications/<company>/` |
| `browser` | `tools/.venv/`, `tools/browser_agent.py` | None (general purpose) |
| `taskdb` | `python3`, `taskdb.sqlite` | None (database only) |
| `skillcraft` | None (documentation skill) | None |

## Cross-References

- Capture categories and tagging: `TOOLS.md` > "Capture Categories" and "Tagging System"
- Link capture template: `captures/LINK_CAPTURE_TEMPLATE.md`
- Stoic reflection prompts: `memory/stoic_reflection_templates.json`
- Memory maintenance rules: `AGENTS.md` > "Memory Maintenance (During Heartbeats)"
- File editing rules for SOUL.md / USER.md: `.claude/rules.json`
- Operational change methodology: `.claude/instructions.md`
