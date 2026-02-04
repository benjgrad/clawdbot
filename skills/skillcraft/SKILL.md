---
name: skillcraft
description: Create, design, and package Clawdbot/MoltBot skills following AgentSkills best practices. Use when creating a new skill, improving an existing skill, reviewing skill quality, or when the user asks about skill authoring.
---

# Skillcraft

Guide for creating and improving MoltBot/Clawdbot skills that follow the AgentSkills specification.

## When to Use

- User asks to create a new skill
- User wants to improve or audit an existing skill
- User asks about skill structure, frontmatter, or best practices
- You need to package functionality as a reusable skill

## Skill Directory Structure

```
skills/skill-name/
  SKILL.md          # Required: YAML frontmatter + instructions
  scripts/          # Optional: executable code
  references/       # Optional: supplementary docs (loaded on demand)
  assets/           # Optional: templates, data files
```

A copy-paste template is available at `{baseDir}/assets/SKILL_TEMPLATE.md`.

## YAML Frontmatter (Required)

Every `SKILL.md` must start with YAML frontmatter:

```yaml
---
name: skill-name
description: What this skill does. Activation triggers. When to use it.
---
```

### Naming Rules

- 1-64 characters, lowercase alphanumeric + hyphens only
- No consecutive hyphens, no leading hyphens
- Must match the directory name exactly

### Optional Frontmatter Fields

| Field | Purpose |
|-------|---------|
| `metadata` | JSON object with gating/requirements (see below) |
| `user-invocable` | Expose as `/slash-command` (default: true) |
| `disable-model-invocation` | Hide from model prompt (default: false) |
| `command-dispatch` | Set to `"tool"` for direct tool dispatch |
| `command-tool` | Tool name to invoke when dispatched |
| `command-arg-mode` | `"raw"` passes args directly to tool |
| `homepage` | URL for UI display |

### Metadata Gates

Control when a skill loads via `metadata`:

```yaml
metadata: {"moltbot":{"os":["darwin","linux"],"requires":{"bins":["python3"],"env":["API_KEY"]}}}
```

- `requires.bins` — all listed binaries must exist on PATH
- `requires.anyBins` — at least one must exist
- `requires.env` — environment variables must be set (or in config)
- `requires.config` — config keys must be truthy
- `os` — restrict to specific platforms

## Writing the Description

The `description` field is **the most important field** — agents use it to decide whether to activate the skill.

**Rules:**
1. Write in **third person** (not "I" or "you")
2. Include **capabilities** AND **activation triggers**
3. Use **domain-specific terminology** the user would actually say
4. Stay under **1,024 characters**

**Good:** "Manage tasks in a SQLite database. Add, list, complete, prioritize, and search tasks. Use when the user mentions tasks, to-dos, or tracking work items."

**Bad:** "Helps with tasks" (too vague), "I manage your to-do list" (wrong perspective)

## Body Content Guidelines

### Token Budget

- SKILL.md body: **under 500 lines** (loaded when skill activates)
- Move detailed reference material to `references/` (loaded only when explicitly read)
- Use `{baseDir}` to reference files in the skill directory

### Recommended Sections

1. **When to Use** — specific trigger conditions and scenarios
2. **Quick Start** — minimal example to get going
3. **Step-by-Step Process** — numbered instructions for the main workflow
4. **Examples** — concrete input/output pairs
5. **Error Handling** — common issues and solutions

### Conciseness Standards

- Assume the agent has baseline technical knowledge
- Challenge each paragraph: does it earn its token cost?
- One concept per section, no redundancy
- Prefer tables and lists over prose

## Authoring Principles

1. **Be specific and decisive.** Don't list every option — recommend one approach. "Use pdfplumber for text extraction" beats "You could use pdfplumber, PyMuPDF, or tabula."

2. **Consistent terminology.** Pick one term per concept. Don't alternate between "task," "item," "entry," and "record."

3. **Appropriate constraint levels:**
   - High freedom (text guidance) — multiple valid approaches exist
   - Medium freedom (pseudocode/templates) — preferred patterns exist
   - Low freedom (exact scripts) — consistency is critical

4. **No time-sensitive instructions.** State the current method. Don't write "if before version X, do Y."

5. **Use `{baseDir}` for paths.** Never hardcode absolute paths in instructions.

## Anti-Patterns

| Problem | Why It Fails |
|---------|-------------|
| Vague activation triggers | Agent can't decide when to load the skill |
| Explaining basics the agent knows | Wastes tokens on "what is a database" type content |
| Inconsistent terminology | Agent misinterprets scope of instructions |
| Deeply nested reference chains | Agent loses context hopping between files |
| Missing frontmatter | Skill can't be discovered at all |
| Platform-specific paths | Breaks on other OS; use `{baseDir}` instead |

## Skill Creation Checklist

Before considering a skill complete, verify:

- [ ] `SKILL.md` has valid YAML frontmatter with `name` and `description`
- [ ] `name` matches directory name (lowercase, hyphens, 1-64 chars)
- [ ] `description` is third-person, includes capabilities + triggers, <1,024 chars
- [ ] Body has "When to Use" section with specific trigger conditions
- [ ] Body includes at least one concrete example
- [ ] All file paths use `{baseDir}`, no hardcoded absolute paths
- [ ] Total SKILL.md is under 500 lines
- [ ] Verbose reference material is in `references/`, not inline
- [ ] Required binaries/env declared in `metadata` if applicable
- [ ] No time-sensitive or version-gated instructions

## Detailed Reference

For full research including token cost calculations, security best practices, metadata gate examples, common patterns, and the complete AgentSkills specification details, read `{baseDir}/references/best-practices.md`.
