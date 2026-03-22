# GameTrack Discord Bot (Python)

A Discord bot to make game tracking easier with:

- **Playtime tracking** (`/startgame`, `/endgame`, `/loggame`)
- **Leveling system** based on total minutes played
- **Leaderboard** by total playtime
- **Simple graphics** using Pillow (`/profile` and image leaderboard)

## Features

- Track active play sessions per user.
- Store data in local SQLite (`gametrack.db`).
- Level progression from total playtime (XP = minutes played).
- Profile card image with:
  - user avatar
  - total playtime
  - level and progress bar
  - top played game
- Leaderboard command with optional generated image.

## Commands

- `/startgame game:<name>` — Start a live session for a game.
- `/endgame` — End your active session and save minutes.
- `/loggame game:<name> minutes:<int>` — Manually log playtime.
- `/profile [member]` — Show stats + profile image card.
- `/leaderboard [limit] [image]` — Show top players by minutes.

## Setup

1. Install Python 3.10+.
2. Create a Discord bot and copy the token.
3. Enable **Message Content Intent** if you extend to prefix commands (slash commands here don't require it).
4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Set environment variable:

```bash
export DISCORD_TOKEN="your_token_here"
```

6. Run:

```bash
python bot.py
```

## Notes

- Slash commands can take up to a minute to appear globally.
- For faster dev iteration, use one guild sync in code if desired.
- Data file `gametrack.db` is created automatically.

## Optional ideas

- Auto-track game presence via Discord activities.
- Weekly/monthly leaderboards.
- Prestige levels and role rewards.
- Charts over time (matplotlib).
