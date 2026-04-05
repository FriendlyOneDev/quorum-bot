# Quorum Bot

Telegram bot for organizing D&D sessions. GMs create games, post them to the group, and players sign up.

## How it works

- **GMs** create game sessions and post them to a group chat
- **Players** sign up by pressing a button on the posted message
- **Slots** prevent first-come-first-serve — players need a slot to sign up (GMs hand them out weekly)
- If a game starts in less than 24 hours, anyone can join without a slot
- GMs get notified when someone joins or leaves their game

## Roles

| Role | What they can do |
|------|-----------------|
| Admin | Everything + manage roles and users |
| GM | Create/edit/delete games, give out slots, post to group, rollcall |
| Player | Sign up for games, check slots |

## Commands

**For everyone:**
- `/myslots` — check your slot balance
- `/whoami` — see your role and slots
- `/help` — list available commands

**For GMs:**
- `/create` — create a new game (in DMs)
- `/view` / `/edit` / `/delete` — manage your games (in DMs)
- `/post` — post a game to the group
- `/rollcall` — ping all signed-up players
- `/giveslot @user [N]` — give slots to a player
- `/giveslots` — give 1 slot to all players
- `/register` — post a registration button in the group

**For admins:**
- `/setrole @user gm|user` — change someone's role
- `/users` — list all users

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set up a PostgreSQL database and create a `quorum` database
3. Copy `.env.example` to `.env` and fill in your token, admin ID, and database connection string
4. Deploy with `./deploy.sh` or run locally with `python run_dev.py`

The bot runs migrations automatically on startup. Disable Privacy Mode via BotFather so the bot can see messages in groups.
