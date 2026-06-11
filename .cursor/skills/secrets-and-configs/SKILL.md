---
name: secrets-and-configs
description: Secrets & Configuration
When to use:
  - Any work involving keys, tokens, passwords, or connection details.
  - Adding new config options for venues, brokers, or services.
---

Instructions for the skill go here. Provide relative paths to other resources in the skill directory as needed.

Goals:
  - Zero secrets in source control.
  - Clear mapping from config files to environment variables.

Workflow:
1. If a new secret is needed:
   - Choose a descriptive environment variable name (e.g., `BINANCE_API_KEY`).
   - Document it in `.env.example` and relevant config templates.
2. In config files, reference secrets via environment variables, not literal values.
3. Never log or print full secrets; if needed for debugging, mask all but a few characters.
4. If you encounter existing hard‑coded secrets:
   - Replace them with env var references.
   - Add a comment explaining the change.
5. For environment‑specific behavior (dev/paper/prod):
   - Use separate config files under `config/` and select them via environment variables or CLI arguments.