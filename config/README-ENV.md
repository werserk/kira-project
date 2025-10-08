# Environment Configuration

## File Structure

```
kira-project/
├── .env.example          # ← Template file (committed to git)
├── .env                  # ← Your actual secrets (NOT committed, in .gitignore)
└── config/
    └── kira.yaml         # YAML configuration
```

## Quick Setup

```bash
# 1. Copy the template
cp .env.example .env

# 2. Edit with your secrets
nano .env

# 3. Add your API keys:
#    - OPENROUTER_API_KEY=...
#    - TELEGRAM_BOT_TOKEN=...
#    - etc.
```

## Important Notes

- **`.env.example`** - Template with placeholders, safe to commit
- **`.env`** - Your actual secrets, NEVER commit (in .gitignore)
- Location: Both files should be in project root (not in config/)

## Why .env in Root?

Standard practice for most tools (Docker, poetry, dotenv libraries):
- They look for `.env` in project root by default
- No need to configure custom paths
- Works with `docker-compose`, `poetry run`, etc.

## See Also

- [QUICKSTART.md](../QUICKSTART.md) - Full setup guide
- [config/README.md](README.md) - YAML configuration guide

