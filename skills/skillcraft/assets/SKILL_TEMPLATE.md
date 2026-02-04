---
name: skill-name
description: What this skill does. When to activate it. Domain-specific trigger words.
<!-- REQUIRED: name must match directory name. Lowercase, hyphens, 1-64 chars. -->
<!-- REQUIRED: description in third person. Include capabilities AND activation triggers. Under 1,024 chars. -->
<!-- OPTIONAL fields (uncomment as needed):
user-invocable: true
disable-model-invocation: false
command-dispatch: tool
command-tool: Bash
command-arg-mode: raw
homepage: https://example.com
metadata: {"moltbot":{"os":["darwin","linux"],"requires":{"bins":["python3"],"env":["API_KEY"]}}}
-->
---

# Skill Name

<!-- One-line summary of what this skill does. -->

## When to Use

<!-- List specific scenarios and trigger conditions. Be concrete — the agent uses this to decide activation. -->
- User asks to ...
- User mentions ...
- You need to ...

## Quick Start

<!-- Minimal example showing the most common usage. -->

```bash
python3 {baseDir}/scripts/main.py --action "example"
```

## Process

<!-- Numbered steps for the main workflow. -->

1. Step one
2. Step two
3. Step three

## Examples

<!-- Concrete input/output pairs. At least one. -->

**Input:** "example user request"
**Action:** `python3 {baseDir}/scripts/main.py --action "example"`
**Output:** "Expected result"

## Error Handling

<!-- Common issues and how to resolve them. -->

| Error | Cause | Fix |
|-------|-------|-----|
| `FileNotFoundError` | Database not initialized | Run `python3 {baseDir}/scripts/init.py` |

## References

<!-- Link to detailed docs if needed. Keep SKILL.md lean. -->
<!-- For detailed information, see `{baseDir}/references/detailed-guide.md`. -->
