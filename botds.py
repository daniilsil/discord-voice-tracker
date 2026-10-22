import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import time
from datetime import datetime, timedelta, timezone


# Создаем класс бота для удобной синхронизации слеш-команд
class TimeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        # Обычный префикс оставляем на всякий случай, но основной упор на слеш-команды
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Эта строчка автоматически регистрирует слеш-команды на всех серверах при запуске
        await self.tree.sync()
        print("Слеш-команды успешно синхронизированы!")


bot = TimeBot()

DATA_FILE = "voice_stats_v2.json"
voice_data = {}
active_sessions = {}

# Загрузка данных
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            data = json.load(f)
            voice_data = {int(k): v for k, v in data.items()}
        except json.JSONDecodeError:
            voice_data = {}


def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(voice_data, f, indent=4)


@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} запущен со слеш-командами!')


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    user_id = member.id
    current_time = time.time()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if before.channel is None and after.channel is not None:
        active_sessions[user_id] = current_time
    elif before.channel is not None and after.channel is None:
        if user_id in active_sessions:
            join_time = active_sessions.pop(user_id)
            duration = current_time - join_time

            if user_id not in voice_data:
                voice_data[user_id] = {}

            voice_data[user_id][today_str] = voice_data[user_id].get(today_str, 0) + duration
            save_data()


def get_leaderboard_data(days_limit):
    now = datetime.now(timezone.utc)
    target_dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_limit)]
    totals = {}

    for user_id, dates in voice_data.items():
        user_total = 0
        for date in target_dates:
            user_total += dates.get(date, 0)
        if user_total > 0:
            totals[user_id] = user_total

    current_time = time.time()
    today_str = now.strftime("%Y-%m-%d")

    for user_id, join_time in active_sessions.items():
        if today_str in target_dates:
            session_duration = current_time - join_time
            totals[user_id] = totals.get(user_id, 0) + session_duration

    return sorted(totals.items(), key=lambda item: item, reverse=True)


# Создаем слеш-команду /топ
@bot.tree.command(name="топ", description="Показать таблицу лидеров по времени в голосовых каналах")
# Настраиваем всплывающий список для выбора периода
@app_commands.choices(период=[
    app_commands.Choice(name="За день", value="день"),
    app_commands.Choice(name="За неделю", value="неделя"),
    app_commands.Choice(name="За месяц", value="месяц")
])
async def leaderboard(interaction: discord.Interaction, период: app_commands.Choice[str]):
    # Вместо ctx в слеш-командах используется interaction
    period_val = период.value

    if period_val == "день":
        days = 1
        title_period = "за последние 24 часа"
        color = discord.Color.blue()
    elif period_val == "неделя":
        days = 7
        title_period = "за последние 7 дней"
        color = discord.Color.green()
    elif period_val == "месяц":
        days = 30
        title_period = "за последние 30 дней"
        color = discord.Color.gold()

    sorted_users = get_leaderboard_data(days)

    if not sorted_users:
        await interaction.response.send_message(f"Статистика {title_period} пока пуста.")
        return

    embed = discord.Embed(
        title=f"🏆 Таблица лидеров {title_period}",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    description = ""
    for index, (user_id, seconds) in enumerate(sorted_users[:10], start=1):
        user = bot.get_user(user_id)
        user_mention = user.mention if user else f"Пользователь [{user_id}]"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)

        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"**#{index}**"
        description += f"{medal} {user_mention} — **{hours} ч. {minutes} мин.**\n"

    embed.description = description
    embed.set_footer(text=f"Запросил {interaction.user.name}", icon_url=interaction.user.display_avatar.url)

    # Отправляем ответ на слеш-команду
    await interaction.response.send_message(embed=embed)


# Вставьте ваш действующий токен сюда
bot.run('YOUR_DISCORD_TOKEN')


