import io
import math
import os
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import discord
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

DB_PATH = "gametrack.db"


@dataclass
class PlayerStats:
    user_id: int
    total_minutes: int
    level: int
    minutes_in_level: int
    minutes_to_next_level: int
    top_game: Optional[str]
    top_game_minutes: int


class GameTrackDB:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init_db(self):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    start_ts INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS playtime (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    minutes INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, game)
                )
                """
            )
            conn.commit()

    @staticmethod
    def _norm_game(game: str) -> str:
        return game.strip()

    def start_session(self, guild_id: int, user_id: int, game: str) -> Tuple[bool, Optional[Tuple[str, int]]]:
        game = self._norm_game(game)
        now = int(time.time())
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT game, start_ts FROM sessions WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            existing = cur.fetchone()
            if existing:
                return False, (existing[0], existing[1])

            cur.execute(
                "INSERT INTO sessions (guild_id, user_id, game, start_ts) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, game, now),
            )
            conn.commit()
            return True, None

    def end_session(self, guild_id: int, user_id: int) -> Optional[Tuple[str, int]]:
        now = int(time.time())
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT game, start_ts FROM sessions WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None

            game, start_ts = row[0], row[1]
            minutes = max(1, int((now - start_ts) // 60))
            self.add_minutes(guild_id, user_id, game, minutes, conn=conn)

            cur.execute(
                "DELETE FROM sessions WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            conn.commit()
            return game, minutes

    def add_minutes(
        self,
        guild_id: int,
        user_id: int,
        game: str,
        minutes: int,
        conn: Optional[sqlite3.Connection] = None,
    ):
        game = self._norm_game(game)
        minutes = max(0, int(minutes))
        if minutes <= 0:
            return

        if conn is None:
            with self._connect() as own_conn:
                self.add_minutes(guild_id, user_id, game, minutes, conn=own_conn)
                own_conn.commit()
                return

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO playtime (guild_id, user_id, game, minutes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id, game)
            DO UPDATE SET minutes = minutes + excluded.minutes
            """,
            (guild_id, user_id, game, minutes),
        )

    def get_player_totals(self, guild_id: int, user_id: int) -> Tuple[int, Optional[Tuple[str, int]]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(SUM(minutes), 0) FROM playtime WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            total = cur.fetchone()[0] or 0

            cur.execute(
                """
                SELECT game, minutes FROM playtime
                WHERE guild_id = ? AND user_id = ?
                ORDER BY minutes DESC, game ASC
                LIMIT 1
                """,
                (guild_id, user_id),
            )
            top_game = cur.fetchone()
            return int(total), (top_game[0], top_game[1]) if top_game else None

    def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Tuple[int, int]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id, SUM(minutes) AS total
                FROM playtime
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY total DESC, user_id ASC
                LIMIT ?
                """,
                (guild_id, limit),
            )
            return [(int(r[0]), int(r[1])) for r in cur.fetchall()]


def total_minutes_for_level(level: int) -> int:
    # Quadratic progression: level n requires 120*n^2 total minutes.
    return 120 * level * level


def level_from_minutes(minutes: int) -> Tuple[int, int, int]:
    minutes = max(0, int(minutes))
    level = int(math.sqrt(minutes / 120))

    current_base = total_minutes_for_level(level)
    next_base = total_minutes_for_level(level + 1)
    in_level = minutes - current_base
    need = next_base - current_base
    return level, in_level, need


def format_minutes(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h == 0:
        return f"{m}m"
    return f"{h}h {m}m"


async def get_avatar_bytes(user: discord.abc.User) -> Optional[bytes]:
    avatar = user.display_avatar
    if not avatar:
        return None
    return await avatar.read()


def make_profile_card(
    username: str,
    total_minutes: int,
    level: int,
    in_level: int,
    need_for_next: int,
    top_game: Optional[str],
    top_game_minutes: int,
    avatar_bytes: Optional[bytes] = None,
) -> io.BytesIO:
    width, height = 840, 260
    img = Image.new("RGB", (width, height), (20, 24, 34))
    draw = ImageDraw.Draw(img)

    # Accent panel
    draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=20, fill=(32, 39, 55))

    # Avatar block
    if avatar_bytes:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGB").resize((150, 150))
        mask = Image.new("L", (150, 150), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 150, 150), fill=255)
        img.paste(avatar, (45, 55), mask)
    else:
        draw.ellipse((45, 55, 195, 205), fill=(68, 76, 98))

    font_title = ImageFont.load_default()
    font_body = ImageFont.load_default()

    draw.text((230, 45), f"{username}", font=font_title, fill=(236, 240, 255))
    draw.text((230, 75), f"Level {level}", font=font_body, fill=(169, 180, 211))
    draw.text((230, 102), f"Total playtime: {format_minutes(total_minutes)}", font=font_body, fill=(169, 180, 211))

    top_game_text = f"Top game: {top_game} ({format_minutes(top_game_minutes)})" if top_game else "Top game: n/a"
    draw.text((230, 129), top_game_text, font=font_body, fill=(169, 180, 211))

    # Progress bar
    bar_x1, bar_y1, bar_x2, bar_y2 = 230, 170, 780, 205
    draw.rounded_rectangle((bar_x1, bar_y1, bar_x2, bar_y2), radius=12, fill=(55, 65, 89))
    ratio = 0 if need_for_next <= 0 else max(0.0, min(1.0, in_level / need_for_next))
    fill_w = int((bar_x2 - bar_x1) * ratio)
    if fill_w > 0:
        draw.rounded_rectangle((bar_x1, bar_y1, bar_x1 + fill_w, bar_y2), radius=12, fill=(88, 166, 255))
    draw.text((230, 210), f"Progress: {in_level}/{need_for_next} min", font=font_body, fill=(169, 180, 211))

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out


def make_leaderboard_card(rows: List[Tuple[str, int]]) -> io.BytesIO:
    width = 700
    height = 90 + 48 * max(1, len(rows))
    img = Image.new("RGB", (width, height), (18, 21, 30))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=16, fill=(32, 39, 55))
    draw.text((40, 35), "GameTrack Leaderboard", font=font, fill=(235, 241, 255))

    y = 75
    for i, (name, mins) in enumerate(rows, start=1):
        color = (200, 210, 235) if i > 3 else (255, 223, 128)
        draw.text((40, y), f"#{i}", font=font, fill=color)
        draw.text((95, y), name[:28], font=font, fill=(235, 241, 255))
        draw.text((500, y), format_minutes(mins), font=font, fill=(130, 210, 255))
        y += 42

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out


class GameTrackBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.db = GameTrackDB()

    async def setup_hook(self):
        await self.tree.sync()


bot = GameTrackBot()


@bot.tree.command(name="startgame", description="Start tracking your game session")
@app_commands.describe(game="Name of the game")
async def startgame(interaction: discord.Interaction, game: str):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    ok, existing = bot.db.start_session(guild.id, interaction.user.id, game)
    if not ok and existing:
        existing_game, start_ts = existing
        await interaction.response.send_message(
            f"You're already tracking **{existing_game}** since <t:{start_ts}:R>. Use `/endgame` first.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(f"Started tracking **{game}**. Use `/endgame` when done.")


@bot.tree.command(name="endgame", description="End your current tracked game session")
async def endgame(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    result = bot.db.end_session(guild.id, interaction.user.id)
    if not result:
        await interaction.response.send_message("No active session found. Start one with `/startgame`.", ephemeral=True)
        return

    game, minutes = result
    total, _ = bot.db.get_player_totals(guild.id, interaction.user.id)
    lvl, in_lvl, need = level_from_minutes(total)
    await interaction.response.send_message(
        f"Saved **{format_minutes(minutes)}** for **{game}**. "
        f"Total: **{format_minutes(total)}** | Level **{lvl}** ({in_lvl}/{need} min)"
    )


@bot.tree.command(name="loggame", description="Manually add game time")
@app_commands.describe(game="Name of the game", minutes="Minutes played")
async def loggame(interaction: discord.Interaction, game: str, minutes: app_commands.Range[int, 1, 1440]):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    bot.db.add_minutes(guild.id, interaction.user.id, game, minutes)
    total, _ = bot.db.get_player_totals(guild.id, interaction.user.id)
    lvl, in_lvl, need = level_from_minutes(total)
    await interaction.response.send_message(
        f"Added **{format_minutes(minutes)}** to **{game}**. "
        f"Total: **{format_minutes(total)}** | Level **{lvl}** ({in_lvl}/{need} min)"
    )


@bot.tree.command(name="profile", description="Show a player's game tracking profile")
@app_commands.describe(member="Member to inspect (default: you)")
async def profile(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    target = member or interaction.user
    total, top_row = bot.db.get_player_totals(guild.id, target.id)
    top_game, top_minutes = (top_row[0], int(top_row[1])) if top_row else (None, 0)
    lvl, in_lvl, need = level_from_minutes(total)

    avatar_bytes = await get_avatar_bytes(target)
    card = make_profile_card(
        username=target.display_name,
        total_minutes=total,
        level=lvl,
        in_level=in_lvl,
        need_for_next=need,
        top_game=top_game,
        top_game_minutes=top_minutes,
        avatar_bytes=avatar_bytes,
    )

    file = discord.File(card, filename="profile.png")
    embed = discord.Embed(title=f"{target.display_name}'s Game Profile", color=discord.Color.blurple())
    embed.set_image(url="attachment://profile.png")
    embed.set_footer(text="GameTrack Bot")

    await interaction.response.send_message(embed=embed, file=file)


@bot.tree.command(name="leaderboard", description="Show playtime leaderboard")
@app_commands.describe(limit="How many players to show", image="Generate image card")
async def leaderboard(
    interaction: discord.Interaction,
    limit: app_commands.Range[int, 3, 20] = 10,
    image: bool = True,
):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    rows = bot.db.get_leaderboard(guild.id, limit=limit)
    if not rows:
        await interaction.response.send_message("No playtime data yet. Use `/startgame` or `/loggame`.")
        return

    resolved: List[Tuple[str, int]] = []
    for uid, mins in rows:
        member = guild.get_member(uid)
        name = member.display_name if member else f"User {uid}"
        resolved.append((name, mins))

    lines = [f"**#{i}** {name} — `{format_minutes(mins)}`" for i, (name, mins) in enumerate(resolved, start=1)]
    embed = discord.Embed(title="🏆 Playtime Leaderboard", description="\n".join(lines), color=discord.Color.gold())

    if image:
        card = make_leaderboard_card(resolved)
        file = discord.File(card, filename="leaderboard.png")
        embed.set_image(url="attachment://leaderboard.png")
        await interaction.response.send_message(embed=embed, file=file)
        return

    await interaction.response.send_message(embed=embed)


def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set.")
    bot.run(token)


if __name__ == "__main__":
    main()
