# Quorum Bot

Telegram bot for organizing D&D sessions. GMs create games, post them to a dedicated announcements channel, and players sign up.

## How it works

- **GMs** create game sessions in DMs and publish them to the announcements channel
- **Players** sign up by pressing a button on the posted message
- **Slots** prevent first-come-first-serve — players need a slot to sign up (GMs hand them out weekly)
- If a game starts in less than 24 hours, anyone can join without a slot
- GMs get notified when someone joins or leaves their game
- Editing a game auto-updates the posted announcement
- Deleting a game removes the announcement and refunds slots to players
- Player names are resolved from group tags/titles (character names)

## Roles

| Role | What they can do |
|------|-----------------|
| Admin | Everything + manage roles and users |
| GM | Create/edit/delete games, give out slots, post to announcements, rollcall |
| Player | Sign up for games, check slots |

## Commands

**For everyone:**
- `/myslots` — check your slot balance
- `/whoami` — see your role and slots
- `/help` — list available commands

**For GMs:**
- `/create` — create a new game (in DMs), with option to publish immediately
- `/view` / `/edit` / `/delete` — manage your games (in DMs)
- `/post` — publish a game to the announcements channel (in DMs)
- `/rollcall` — ping all signed-up players
- `/giveslot @user [N]` — give slots to a player (negative to correct)
- `/giveslots [N]` — give N slots to all players (default 1)
- `/register` — post a registration button in the group

**For admins:**
- `/setrole @user gm|user` — change someone's role
- `/users` — list all users

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Set up a PostgreSQL database
3. Copy `.env.example` to `.env` and fill in your values
4. Deploy with `./deploy.sh` or run locally with `python run_dev.py`

The bot runs migrations automatically on startup. Disable via BotFather so the bot can see messages in groups.

## Deployment

```bash
./deploy.sh
```

Builds the Docker image locally, transfers it to the server(you need to configure it in deploy.sh) via SSH, and restarts the container.
