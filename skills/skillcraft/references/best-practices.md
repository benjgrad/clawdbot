# Skill Creation Best Practices — Full Reference

Extended reference for the `skillcraft` skill. This document contains detailed research, examples, and specifications beyond what fits in the main SKILL.md.

## AgentSkills Specification

MoltBot skills follow the **AgentSkills specification** — an open standard developed by Anthropic and adopted by Claude Code, Cursor, VS Code, Gemini CLI, GitHub Copilot, and others. Skills built for MoltBot are portable to any AgentSkills-compatible tool.

## Skill Loading & Precedence

Skills load from these locations (highest to lowest precedence):

1. `<workspace>/skills/` — per-agent, workspace-scoped
2. `~/.clawdbot/skills/` — shared across all agents on the machine
3. Bundled skills — shipped with MoltBot installation
4. `skills.load.extraDirs` — additional folders configured in `moltbot.json`

If a skill name conflicts, the highest-precedence location wins.

### Multi-Agent Setups

Each agent has its own workspace. Per-agent skills live in `<workspace>/skills/`. Shared skills in `~/.clawdbot/skills/` are visible to all agents. Use `skills.load.extraDirs` for common skill packs across multiple agents.

### Plugin Skills

Plugins can ship their own skills by listing skill directories in `moltbot.plugin.json` (paths relative to the plugin root).

## Progressive Disclosure (3-Tier Loading)

Understanding how skills load helps you optimize token usage:

1. **Discovery (~100 tokens):** Only `name` + `description` from frontmatter load for ALL eligible skills, every session. This is why lean descriptions matter.
2. **Activation (<5,000 tokens recommended):** The full SKILL.md body loads when a task matches the description. Keep this focused and actionable.
3. **Execution (as needed):** Files from `scripts/`, `references/`, `assets/` load only when explicitly referenced by the agent. Put detailed docs here.

## Token Cost Calculations

When skills are eligible, MoltBot injects them into the system prompt:

- **Base overhead:** ~195 characters (when >= 1 skill is loaded)
- **Per skill:** ~97 characters + length of name + description + location
- **Rough estimate:** ~4 chars/token, so 97 chars = ~24 tokens per skill (plus your field lengths)

### Optimization Tips

- Keep `description` under 200 characters when possible (saves ~50 tokens per session)
- Use metadata gates to prevent skills from loading in sessions where they're irrelevant
- Set `disable-model-invocation: true` for skills that should only be invoked via `/slash-command`

## Metadata Gates — Complete Reference

### Full Example

```yaml
metadata: {"moltbot":{"always":true,"emoji":"📋","os":["darwin","linux"],"requires":{"bins":["python3","sqlite3"],"anyBins":["nvim","vim","vi"],"env":["OPENAI_API_KEY"],"config":["browser.enabled"]},"primaryEnv":"OPENAI_API_KEY","install":[{"type":"npm","package":"some-tool"},{"type":"download","url":"https://example.com/tool.tar.gz","archive":"tar.gz"}]}}
```

### Field Details

| Field | Type | Purpose |
|-------|------|---------|
| `always` | boolean | Always inject into system prompt (even if task doesn't match) |
| `emoji` | string | Display emoji in UI |
| `os` | string[] | Restrict to platforms: `"darwin"`, `"linux"`, `"win32"` |
| `requires.bins` | string[] | ALL must exist on PATH |
| `requires.anyBins` | string[] | At least ONE must exist |
| `requires.env` | string[] | Environment variable must be set or configured |
| `requires.config` | string[] | Config keys must be truthy |
| `primaryEnv` | string | Main API key — shown in setup UI |
| `install` | object[] | Auto-install instructions (npm, download) |

### Install Options

**npm install:**
```json
{"type": "npm", "package": "tool-name"}
```

**Download install:**
```json
{
  "type": "download",
  "url": "https://example.com/tool.tar.gz",
  "archive": "tar.gz",
  "extract": true,
  "stripComponents": 1,
  "targetDir": "~/.clawdbot/tools/tool-name"
}
```

Node installs honor `skills.install.nodeManager` in `moltbot.json` (default: npm; options: npm/pnpm/yarn/bun).

## Configuration via moltbot.json

Override or configure skills in `~/.clawdbot/moltbot.json`:

```json5
{
  skills: {
    entries: {
      "skill-name": {
        enabled: true,
        apiKey: "SECRET_VALUE",
        env: { "API_VAR": "value" },
        config: { "custom_field": "value" }
      }
    }
  }
}
```

Environment variables from `env` and `apiKey` inject into `process.env` only if not already set. They are scoped to the agent run, not the global shell.

## Session Behavior

- MoltBot **snapshots** eligible skills when a session starts
- Changes to skills or config take effect on the **next new session**
- Skills can also refresh mid-session when the **skills watcher** is enabled or when a new eligible remote node appears (hot reload)

## Effective Patterns

### Template Pattern

Provide structured output formats the agent should replicate:

```markdown
## Output Format

When generating a report, use this structure:

### [Report Title]
**Date:** YYYY-MM-DD
**Summary:** One-line overview

#### Findings
1. Finding with evidence
2. Finding with evidence

#### Recommendations
- Actionable recommendation
```

### Example Pattern

Supply input/output pairs showing desired transformations:

```markdown
## Examples

**Input:** "Add a task to buy groceries with high priority"
**Action:** `python3 {baseDir}/scripts/add.py --title "Buy groceries" --priority 1`
**Output:** "Task #42 created: Buy groceries (priority: high)"
```

### Workflow Pattern

Deliver numbered checklists with explicit commands:

```markdown
## Process

1. Check if the database exists: `ls ~/clawd/data.sqlite`
2. If missing, initialize: `python3 {baseDir}/scripts/init.py`
3. Run the operation: `python3 {baseDir}/scripts/run.py --input "$USER_INPUT"`
4. Verify output: `python3 {baseDir}/scripts/verify.py`
```

### Conditional Pattern

Branch instructions based on context:

```markdown
## Workflow

**If creating a new entry:**
1. Validate input fields
2. Insert into database
3. Confirm creation

**If editing an existing entry:**
1. Fetch current record
2. Apply changes
3. Update timestamp
4. Confirm update
```

## Security Best Practices

- **Audit third-party skills** before enabling — they execute as code on your machine
- **Keep secrets out of SKILL.md** — use `env` and `apiKey` in `moltbot.json` config instead
- **Never log credentials** — ensure scripts don't print API keys or tokens
- **Prefer sandboxed execution** for skills that process untrusted input
- **Use Cisco's Skill Scanner** for automated safety analysis (static + behavioral + LLM-assisted)
- Secrets in `env` and `apiKey` inject into the host process, not Docker sandboxes

## Testing & Validation Checklist

Before publishing or sharing a skill:

1. **Discovery test:** Does the description accurately trigger activation for relevant tasks?
2. **Naming compliance:** Lowercase, hyphens only, 1-64 chars, matches directory?
3. **Token efficiency:** Is the SKILL.md under 500 lines? Is the description lean?
4. **Cross-references:** Do all `{baseDir}` references point to files that exist?
5. **Examples test:** Do the examples produce expected outputs when run?
6. **Fresh session test:** Start a new session and verify the skill activates correctly
7. **Gate test:** Do metadata requirements correctly prevent loading when dependencies are missing?

## Community Resources

- **Official docs:** https://docs.molt.bot/tools/skills
- **Skill registry (ClawdHub):** https://clawdhub.com/skills
- **Community skills (565+):** https://github.com/VoltAgent/awesome-moltbot-skills
- **ClawdHub CLI:** `clawdhub install <slug>`, `clawdhub update --all`, `clawdhub sync --all`
