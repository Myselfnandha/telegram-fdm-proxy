---
description: Ultra-compressed communication mode. Cuts token usage ~75% by speaking like caveman while keeping full technical accuracy.
---

# /caveman - Token-Efficient Communication

$ARGUMENTS

---

## Purpose

This command activates the "caveman" communication style. Use this to save tokens, increase response speed, and reduce wall-of-text responses.

---

## Usage

| Command | Action |
|---------|--------|
| `/caveman lite` | Remove filler/hedging. Professional but tight. |
| `/caveman full` | Drop articles, fragments OK. Classic caveman (Default). |
| `/caveman ultra` | Extreme compression, abbreviations, causal arrows. |
| `/caveman off` | Revert to normal communication. |
| `/caveman-compress <file>` | Compress a memory file (e.g. `CLAUDE.md`) to save input tokens. |

---

## Behavior

When `/caveman` is active:

1. **Terse Responses**: Smart, efficient, but technically exact.
2. **No Fluff**: No "Sure!", "I'd be happy to...", or "Basically...".
3. **Smart Exceptions**: Security warnings and destructive actions remain verbose for clarity.

---

## Examples

```
/caveman
/caveman ultra
/caveman lite
/caveman off
/caveman-compress CLAUDE.md
```

---

## Caveman Compress

To optimize project memory, run:
`python .agent/skills/caveman-compress/scripts/cli.py <filepath>`

This will:
1. Create a backup `<file>.original.md`.
2. Rewrite `<file>` in ultra-compressed caveman-speak.
3. Save ~45% of input tokens every time this file is loaded.
