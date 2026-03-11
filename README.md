# Resinly

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord&logoColor=white)
![genshin.py](https://img.shields.io/badge/genshin.py-supported-2E8B57)
![Last Commit](https://img.shields.io/github/last-commit/ecgregorio/Resinly)
![Repo Size](https://img.shields.io/github/repo-size/ecgregorio/Resinly)

Resinly is a Discord bot for tracking resin in Genshin Impact.

## Invite Link
Feel free to try out Resinly!

- [Resinly]https://discord.com/oauth2/authorize?client_id=1481178070114238506&permissions=274877975552&integration_type=0&scope=bot+applications.commands

## What It Does
- Stores each user's UID.
- Supports per-user HoYoLab cookies.
- Checks resin on an interval.
- Sends a DM when resin is full.
- Avoids duplicate full notifications until resin drops below full again.

## Stack
- Python
- `discord.py`
- `genshin.py`
- `cryptography` (Fernet)

## User Commands
- `!setuid <uid>`
- `!myuid`
- `!resin`
- `!notify on|off`
- `!setcookies <ltuid_v2> <ltoken_v2>` (DM only)
- `!clearcookies`

## Slash Setup
- `/setup` opens a private setup flow (ephemeral button + modal) for UID and cookie input.

## Security Guarantees
- Resinly does not ask users to post cookies in public channels.
- Cookie setup is DM-only or via private slash modal flow.
- User cookies are encrypted at rest before being written to disk.
- Secrets are explicitly intended to stay local and are excluded from git.

## Operational Notes
- If a HoYoLab cookie is expired, user resin checks may fail until cookies are updated.