# =========================
# Standard Library
# =========================
import os
import io
import re
import json
import time
import random
import string
import asyncio
from datetime import datetime, timedelta

# =========================
# Third-Party Libraries
# =========================
import discord
from discord import app_commands, Interaction, Embed, ui
from discord.ext import tasks, commands
import aiohttp
import feedparser
import requests
from dotenv import load_dotenv

# =========================
# Local Modules
# =========================
try:
    from ping_server import server_on
except ImportError:
    def server_on():
        pass

# =========================
# Environment Setup
# =========================
# load_dotenv()

# =========================
# Event Data Storage
# =========================
event_entries = {}
event_winners = {}
event_configs = {}
event_active = {}

# =========================
# HWID Reset System
# =========================
hwid_reset_timestamps = {}
hwid_reset_cooldown = timedelta(days=1)

# =========================
# Admin / Permissions
# =========================
admin_ids = [
    1300017174886350899,
    1209783415759704085
]
timeout_duration = 5

# =========================
# YouTube Feeds
# =========================
feed_url_youtube = {
    "English":  "https://www.youtube.com/feeds/videos.xml?channel_id=UC5abJGhz74y-cw88wFqX0Jw",
    "Thailand": "https://www.youtube.com/feeds/videos.xml?channel_id=UCoLxgTtHYNA8AjOJB1rU-2g",
}
youtube_xecret_hub_channel = "https://www.youtube.com/@XecretHub"

# =========================
# Discord Channel / Roles
# =========================
howtobuy_channel = "https://discord.com/channels/1328392700294070313/1426171154707775569"

channel_id_purchase = 1430745830716870827
panel_channel_id = 1430611712679350333
showcase_channel_id = 1328406450489393253

showcase_role = 1383766143939903528
buyer_role_id = 1328393648957558955

TICKET_CATEGORY_ID = 1348103529436549250
TRANSCRIPT_CHANNEL_ID = 1347789044133793903
SUPPORT_ROLE_ID = 1395727901361704960

support_ticket = "https://discord.com/channels/1328392700294070313/1348578938024104006"

# =========================
# External Links & Media
# =========================
discord_link = "https://discord.com/invite/xecrethub"
website_link = "https://xecrethub.com/"

thumbnail_logo = "https://i.ibb.co/VY59bxqd/Xecret-remove-1.png"
image_logo = "https://i.ibb.co/HLbtfWwV/We-are-Xecret-Hub.png"

gif_information = "https://i.pinimg.com/originals/cd/0c/3f/cd0c3f12008404cae0a8cbc20e880d21.gif"
banner_gif = "https://i.pinimg.com/originals/e6/da/c1/e6dac1038095d76596e8b1bd9653f569.gif"

# =========================
# API / Project Keys
# =========================
bot_token   = os.getenv("BOT_TOKEN")
api_key     = os.getenv("API_KEY")
project_id  = os.getenv("PROJECT_ID")
keys_json   = os.getenv("KEYS_JSON")
loader_json = os.getenv("LOADER_JSON")

headers_master_key = {
    "X-Master-Key": os.getenv("MASTER_KEY")
}

url_project_users     = f"https://api.luarmor.net/v3/projects/{project_id}/users"
url_resethwid_users   = f"https://api.luarmor.net/v3/projects/{project_id}/users/resethwid"

headers = {
    "Authorization": api_key,
    "Content-Type": "application/json"
}

response = requests.get(loader_json, headers=headers_master_key)

# =========================
# Discord Bot Setup
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)

sent_video_ids = set()

# =========================
# 1) Time Parsing / Format
# =========================
def parse_cooldown_duration(duration: str):
    if not duration:
        return None

    duration = duration.lower().strip()

    if duration.endswith("d"):
        try:
            return timedelta(days=int(duration[:-1]))
        except: return None

    if duration.endswith("h"):
        try:
            return timedelta(hours=int(duration[:-1]))
        except: return None

    return None


def format_timedelta(delta):
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


def format_expire_time(auth_expire):
    if auth_expire == -1:
        return "Never"

    expire_date = datetime.fromtimestamp(auth_expire)
    remaining = expire_date - datetime.now()

    if remaining.total_seconds() <= 0:
        return "Expired"

    days = remaining.days
    hours, r = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(r, 60)

    if days >= 365:
        return f"{days // 365} year(s) left"
    if days >= 30:
        return f"{days // 30} month(s) left"
    return f"{days} day(s) {hours}h {minutes}m left"


def ts_to_datetime(ts):
    if ts in (None, 0, -1):
        return "Unknown"
    return datetime.fromtimestamp(int(ts)).strftime("%d/%m/%Y %H:%M:%S")

# =========================
# 2) Role / Permission Utils
# =========================
def is_support_or_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True

        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        if support_role and support_role in interaction.user.roles:
            return True

        raise app_commands.CheckFailure("You don't have permission to use this command.")
    return app_commands.check(predicate)

# =========================
# 3) API Core Utils
# =========================
def fetch_scripts(response):
    if response.status_code == 200:
        return response.json().get("record", {})
    return {}

def load_key_database():
    res = requests.get(keys_json, headers=headers_master_key)
    if res.status_code != 200:
        return None
    return res.json().get("record", {})

def match_redeem_key(record, key):
    for key_id, info in record.items():
        if info.get("key") == key:
            return info
    return None

# =========================
# 4) Whitelist / Key Functions
# =========================
def fetch_user_key(interaction):
    params = {"discord_id": interaction.user.id}
    res = requests.get(url_project_users, headers=headers, params=params)
    if res.status_code == 200:
        return res.json()["users"][0]["user_key"]
    return None


def fetch_user_data(interaction):
    params = {"discord_id": str(interaction.user.id)}
    res = requests.get(url_project_users, headers=headers, params=params)
    if res.status_code != 200:
        return None
    data = res.json()
    users = data.get("users", [])
    return users[0] if users else None


def fetch_user_data_from_id(discord_id: int):
    params = {"discord_id": str(discord_id)}
    res = requests.get(url_project_users, headers=headers, params=params)
    if res.status_code != 200:
        return None
    users = res.json().get("users", [])
    return users[0] if users else None

def redeem_key_api(interaction, matched_key):
    body = {
        "discord_id": str(interaction.user.id),
        "note": "Redeem Key Via Xecret Hub",
        "key_days": matched_key.get("day", [0])[0],
    }
    return requests.post(url_project_users, headers=headers, json=body).json()

def create_user_key(discord_id: int, days: int, note: str):
    body = {"discord_id": str(discord_id), "key_days": days, "note": note or "None"}
    return requests.post(url_project_users, headers=headers, json=body).json()


def delete_user_key(user_key: str):
    delete_url = f"{url_project_users}?user_key={user_key}"
    return requests.delete(delete_url, headers=headers).json()

# =========================
# 5) HWID Functions
# =========================
def check_hwid_cooldown(user_id, now):
    last_reset = hwid_reset_timestamps.get(user_id)
    if last_reset and now - last_reset < hwid_reset_cooldown:
        return hwid_reset_cooldown - (now - last_reset)
    hwid_reset_timestamps[user_id] = now
    return None


def reset_hwid_api(user_key: str):
    body = {"user_key": user_key, "force": True}
    return requests.post(url_resethwid_users, headers=headers, json=body).json()

# =========================
# 6) Blacklist / Unblacklist Functions
# =========================
def parse_duration(duration: str):
    if not duration:
        return -1, "Permanent"

    duration = duration.lower().strip()
    now = datetime.now()

    if duration.endswith("d"):
        days = int(duration[:-1])
        expire_time = now + timedelta(days=days)
        return int(expire_time.timestamp()), f"{days} day(s)"

    if duration.endswith("h"):
        hours = int(duration[:-1])
        expire_time = now + timedelta(hours=hours)
        return int(expire_time.timestamp()), f"{hours} hour(s)"

    raise ValueError("Invalid duration format")


def blacklist_user(user_key: str, reason: str, ban_expire: int):
    url = f"https://api.luarmor.net/v3/projects/{project_id}/users/blacklist"
    body = {"user_key": user_key, "ban_reason": reason, "ban_expire": ban_expire}
    return requests.post(url, headers=headers, json=body).json()


def unblacklist_user(unban_token: str):
    url = f"https://api.luarmor.net/v3/projects/{project_id}/users/unban?unban_token={unban_token}"
    return requests.get(url)

# =========================
# 7) Script / Loader Functions
# =========================
def fetch_scripts_data():
    res = requests.get(loader_json, headers=headers_master_key)
    if res.status_code != 200:
        return {}
    return res.json().get("record", {})


async def script_autocomplete(interaction, current):
    try:
        scripts_data = fetch_scripts_data()
        choices = []
        for key, script in scripts_data.items():
            label = script.get("name", key)
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=key))
        return choices[:25]
    except:
        return []


def build_select_options(scripts_data):
    return [
        discord.SelectOption(
            label=f"{script.get('name', key)} Script",
            description=f"Xecret Hub {script.get('name', key)} Loader",
            value=key
        )
        for key, script in scripts_data.items()
    ]

# =========================
# 8) Ticket System Functions
# =========================
def check_ticket_cooldown(user_id: int, cooldowns: dict, cooldown_seconds: int = 3600):
    now = time.time()
    last_used = cooldowns.get(user_id)
    if last_used and now - last_used < cooldown_seconds:
        remaining = int((cooldown_seconds - (now - last_used)) // 60)
        return False, remaining
    cooldowns[user_id] = now
    return True, 0


def find_existing_ticket(category, username):
    return discord.utils.get(category.text_channels, name=f"ticket-{username}")


async def create_ticket_channel(guild, category, user, ticket_type):
    username = user.name.lower().replace(" ", "-")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }

    support = guild.get_role(SUPPORT_ROLE_ID)
    if support:
        overwrites[support] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    return await guild.create_text_channel(
        name=f"ticket-{username}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket created by {user}"
    )


async def send_ticket_message(channel, user, ticket_type):
    embed = discord.Embed(title=f"{ticket_type} Ticket", color=discord.Color.blurple())
    embed.set_footer(text=f"User ID: {user.id}")

    msg = await channel.send(user.mention)
    await msg.delete()

    await channel.send(embed=embed, view=TicketControlView(user, ticket_type, channel))

# =========================
# 9) Showcase (YouTube)
# =========================
def preload_latest_video_ids():
    """โหลด video id ล่าสุดเข้าชุดกันซ้ำ"""
    for url in feed_url_youtube.values():
        feed = feedparser.parse(url)
        if feed.entries:
            latest = feed.entries[0]
            video_id = latest.yt_videoid
            sent_video_ids.add(video_id)


async def fetch_latest_video(feed_url: str):
    """โหลดข้อมูลวิดีโอล่าสุดจาก YouTube Feed"""
    feed = feedparser.parse(feed_url)
    
    if not feed.entries:
        return None

    latest = feed.entries[0]
    video_id = latest.yt_videoid

    return {
        "id": video_id,
        "title": latest.title,
        "link": latest.link,
        "published": latest.published,
        "author": getattr(latest, "author", None),
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        "updated": getattr(latest, "updated", latest.published),
        "description": getattr(latest, "summary", "")
    }


def build_youtube_embed(data):
    """สร้าง Embed ใช้ประกาศ Video ใหม่"""
    title = data["title"]
    description = data["description"]

    short_title = title[:50] + "..." if len(title) > 50 else title
    short_desc = description[:70] + "..." if len(description) > 70 else description

    embed = discord.Embed(
        title=short_title,
        url=data["link"],
        description=short_desc,
        color=discord.Color.from_rgb(200, 0, 0),
    )

    embed.set_author(
        name="Xecret Hub has posted a new video",
        url=youtube_xecret_hub_channel,
        icon_url=thumbnail_logo,
    )

    embed.set_thumbnail(url=thumbnail_logo)
    embed.set_image(url=data["thumbnail"])
    embed.set_footer(
        text=f"@Posted by Xecret Hub | Published ({data['published']}) and Updated ({data['updated']})",
        icon_url=thumbnail_logo,
    )

    return embed


async def send_showcase_video(video_data):
    """ส่งวิดีโอลง Showcase Channel"""
    channel = bot.get_channel(showcase_channel_id)
    if not channel:
        return
    
    embed = build_youtube_embed(video_data)
    view = VideoButtons(video_data["link"], youtube_xecret_hub_channel)

    await channel.send(
        f"<@&{showcase_role}>",
        embed=embed,
        view=view
    )
    
# =========================
# 10) Event System
# =========================
def resolve_role(guild, allowed_role_str):
    """แปลงข้อความ @Role หรือ Role Name ให้เป็น role object"""
    match = re.match(r"<@&(\d+)>", allowed_role_str)
    if match:
        return guild.get_role(int(match.group(1)))
    return discord.utils.get(guild.roles, name=allowed_role_str.replace("@", "").strip())


def check_allowed_role(user, guild, allowed_role):
    """เช็คว่า user มีสิทธิ์เข้าร่วม event หรือไม่"""
    if allowed_role.lower() == "skip":
        return True
    role_obj = resolve_role(guild, allowed_role)
    return role_obj in user.roles if role_obj else False


def build_event_embed(text, user, duration_minutes, max_winners):
    """สร้าง Embed Event ก่อนเริ่ม"""
    embed = discord.Embed(
        title=f"🎁 Xecret Hub - Event | {text} Giveaway!",
        url=discord_link,
        description=(
            f"After you win, go to {support_ticket} and submit proof.\n\n"
            f"Ends: {duration_minutes} minutes\n"
            f"Entries: 0\n"
            f"Winners: {max_winners}"
        ),
        color=discord.Color.red(),
    )

    embed.set_thumbnail(url=thumbnail_logo)
    embed.set_image(url=image_logo)

    embed.set_author(
        name=f"{user.display_name} has created a giveaway activity",
        url=f"https://discord.com/users/{user.id}",
        icon_url=user.display_avatar.url,
    )

    now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Hosted by {user.display_name} • {now}",
        icon_url=user.display_avatar.url
    )

    embed.add_field(name="🤝 Join Event", value="Join the event to receive rewards.", inline=True)
    embed.add_field(name="👋 Leave Event", value="Leave Event to cancel receiving the prize", inline=True)

    return embed


def update_event_embed(embed, entries, duration_minutes, winners_text="None"):
    """อัปเดตจำนวนคนเข้าร่วม + เวลาที่เหลือ"""
    embed.description = (
        f"After you win, go to {support_ticket} and submit proof.\n\n"
        f"Ends: {duration_minutes}\n"
        f"Entries: {entries}\n"
        f"Winners: {winners_text}"
    )
    return embed


async def finish_event(interaction, message, entries, max_winners, text, user):
    """สุ่มผู้ชนะและประกาศ"""
    winners = random.sample(entries, min(max_winners, len(entries)))
    event_winners[message.id] = winners
    winner_mentions = ", ".join(f"<@{uid}>" for uid in winners)

    embed = message.embeds[0]
    now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")

    embed.description = (
        f"After you win, go to {support_ticket} and submit proof.\n\n"
        f"Ended: {now}\n"
        f"Entries: {len(entries)}\n"
        f"Winners: {winner_mentions}"
    )

    embed.set_author(
        name=f"{user.display_name} has created a giveaway activity",
        url=f"https://discord.com/users/{user.id}",
        icon_url=user.display_avatar.url,
    )

    await message.edit(embed=embed)

    for uid in winners:
        await interaction.channel.send(
            f"🎉 Congratulations <@{uid}>! You won the giveaway **{text}**!"
        )


async def update_event_timer(message, message_id, duration_minutes):
    """อัปเดตเวลานับถอยหลังทุก 1 วินาที"""
    total_seconds = duration_minutes * 60

    for remaining in range(total_seconds, 0, -1):
        if not event_active.get(message_id, False):
            break

        embed = message.embeds[0]
        entries = len(event_entries.get(message_id, []))
        minutes_left = remaining // 60
        seconds_left = remaining % 60

        embed.description = (
            f"After you win, go to {support_ticket} and submit proof.\n\n"
            f"Ends: {minutes_left:02d}:{seconds_left:02d}\n"
            f"Entries: {entries}\n"
            f"Winners: {event_configs.get(message_id, {}).get('max_winners', 0)}"
        )

        await message.edit(embed=embed)
        await asyncio.sleep(1)

# =========================
# 11) Embed Builders (Info/Script)
# =========================
def build_script_embed(interaction, script_info, user_key):
    script_name = script_info.get("name", "Unknown Script")
    loader_url = script_info.get("url", "")

    value_embed = (
        "```lua\n"
        f'script_key = "{user_key}"\n'
        f'loadstring(game:HttpGet("{loader_url}"))()\n'
        "```"
    )

    embed = discord.Embed(
        title="Xecret Hub | Script Loader",
        url=loader_url,
        color=discord.Color.blurple(),
    )

    embed.set_author(
        name=f"{interaction.user.display_name} has got the script",
        url=f"https://discord.com/users/{interaction.user.id}",
        icon_url=interaction.user.display_avatar.url,
    )

    embed.add_field(
        name=f"{script_name} Script",
        value=value_embed,
        inline=False,
    )

    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_image(url=banner_gif)

    now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Xecret Hub • {now}",
        icon_url=thumbnail_logo,
    )

    return embed


def build_user_info_embed(interaction, user, target_user=None):
    target = target_user or interaction.user

    user_key = user.get("user_key", "Unknown")
    identifier = user.get("identifier", "Unknown")
    identifier_type = user.get("identifier_type", "Unknown")
    status = user.get("status", "Unknown").capitalize()
    last_reset = ts_to_datetime(user.get("last_reset"))
    ban_expire = ts_to_datetime(user.get("ban_expire"))

    total_resets = user.get("total_resets", "Unknown")
    total_executions = user.get("total_executions", "Unknown")
    ban_reason = user.get("ban_reason", "None")
    ban_ip = user.get("ban_ip", "Unknown")
    note = user.get("note", "None")

    key_days = user.get("key_days", -1)
    key_days_display = "Lifetime" if key_days == -1 else str(key_days)

    expire_display = format_expire_time(int(user.get("auth_expire", -1)))
    banned_status = "Yes" if user.get("banned", 0) == 1 else "No"

    embed = discord.Embed(
        title=f"Information | {target.display_name} ({target.name})",
        url=f"https://discord.com/users/{target.id}",
        description=(
            f"**User Key:** ||{user_key}||\n"
            f"**Key Status:** {status}\n"
            f"**Key Days:** {key_days_display}\n"
            f"**Key Expires at:** {expire_display}\n"
            "\n"
            f"**HWID Key:** {identifier}\n"
            f"**HWID Type:** {identifier_type}\n"
            f"**Last HWID Reset:** {last_reset}\n"
            "\n"
            f"**Total Executions:** {total_executions}\n"
            f"**Total HWID Resets:** {total_resets}\n"
            "\n"
            f"**Banned:** {banned_status}\n"
            f"**Ban Expires At:** {ban_expire}\n"
            f"**Ban IP:** {ban_ip}\n"
            f"**Ban Reason:** {ban_reason}\n"
            "\n"
            f"**Note:** {note}\n"
        ),
        color=discord.Color.blurple()
    )

    embed.set_author(
        name=f"📊 {target.display_name}’s Information",
        url=f"https://discord.com/users/{target.id}",
        icon_url=target.display_avatar.url
    )

    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_image(url=gif_information)

    now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Infos requested by {interaction.user.display_name} • {now}",
        icon_url=interaction.user.display_avatar.url
    )

    return embed

# =========================
# 12) Logs
# =========================
def send_purchase_log(interaction, status_text, key):
    channel = interaction.guild.get_channel(channel_id_purchase)
    if not channel:
        return

    embed = discord.Embed(
        title="Key Redeem Status",
        description=f"User: {interaction.user.mention}\nKey: ||{key}||\nStatus: {status_text}",
        color=discord.Color.green() if "success" in status_text.lower() else discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"User ID: {interaction.user.id}")

    return channel.send(embed=embed)

def send_action_log(guild, member, title, description, color):
    channel = guild.get_channel(panel_channel_id)
    if not channel:
        return None

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"User ID: {member.id}")

    return channel.send(embed=embed)

def send_whitelist_log(guild, member, description, color):
    channel = guild.get_channel(panel_channel_id)
    if not channel:
        return None

    embed = discord.Embed(
        title="Whitelist Status",
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"User ID: {member.id}")

    return channel.send(embed=embed)

# =========================
# Start
# =========================
@bot.event
async def on_ready():
    preload_latest_video_ids()
    check_youtube_feeds.start()
    await bot.tree.sync()
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching, name=website_link
        ),
    )
    print(bot.user)

# =========================
# Showcase
# =========================
class VideoButtons(discord.ui.View):
    def __init__(self, video_url: str, channel_url: str):
        super().__init__()
        self.add_item(discord.ui.Button(label="Watch Video", url=video_url))
        self.add_item(discord.ui.Button(label="Visit Channel", url=channel_url))

@tasks.loop(minutes=5)
async def check_youtube_feeds():
    for lang, url in feed_url_youtube.items():
        video = await fetch_latest_video(url)
        if not video:
            continue

        if video["id"] in sent_video_ids:
            continue

        sent_video_ids.add(video["id"])

        await send_showcase_video(video)

# ============================
# Event
# ============================
class JoinEventButton(discord.ui.Button):
    def __init__(self, message_id):
        super().__init__(label="🤝 Join Event", style=discord.ButtonStyle.success)
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        msg_id = self.message_id

        if not event_active.get(msg_id, False):
            await interaction.response.send_message("This event has already ended.", ephemeral=True)
            return

        allowed_role = event_configs.get(msg_id, {}).get("allowed_role", "skip")
        if not check_allowed_role(user, interaction.guild, allowed_role):
            await interaction.response.send_message("Your role doesn't allow you to join this event.", ephemeral=True)
            return

        if user.id in event_entries[msg_id]:
            await interaction.response.send_message("You've already joined this event!", ephemeral=True)
            return

        event_entries[msg_id].append(user.id)
        message = await interaction.channel.fetch_message(msg_id)
        embed = message.embeds[0]

        entries = len(event_entries[msg_id])
        duration_minutes = event_configs[msg_id]["duration_minutes"]

        embed = update_event_embed(embed, entries, duration_minutes)
        await message.edit(embed=embed)
        await interaction.response.send_message("You've joined the event!", ephemeral=True)

class LeaveEventButton(discord.ui.Button):
    def __init__(self, message_id):
        super().__init__(label="👋 Leave Event", style=discord.ButtonStyle.danger)
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        msg_id = self.message_id

        if not event_active.get(msg_id, False):
            await interaction.response.send_message("This event has already ended.", ephemeral=True)
            return

        allowed_role = event_configs.get(msg_id, {}).get("allowed_role", "skip")
        if not check_allowed_role(user, interaction.guild, allowed_role):
            await interaction.response.send_message("Your role doesn't allow you to leave this event.", ephemeral=True)
            return

        if user.id not in event_entries[msg_id]:
            await interaction.response.send_message("You haven't joined this event yet.", ephemeral=True)
            return

        event_entries[msg_id].remove(user.id)
        message = await interaction.channel.fetch_message(msg_id)
        embed = message.embeds[0]

        entries = len(event_entries[msg_id])
        duration_minutes = event_configs[msg_id]["duration_minutes"]

        embed = update_event_embed(embed, entries, duration_minutes)
        await message.edit(embed=embed)
        await interaction.response.send_message("You've left the event.", ephemeral=True)

class EventView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.add_item(JoinEventButton(message_id))
        self.add_item(LeaveEventButton(message_id))

@bot.tree.command(name="set-event", description="Create a new Xecret Hub giveaway event")
@app_commands.describe(
    text="Event title",
    max_winners="Maximum number of winners",
    duration_minutes="Duration of event in minutes",
    allowed_role="Role allowed to participate or 'skip'",
)
@is_support_or_admin()
async def set_event(interaction: discord.Interaction, text: str, max_winners: int, duration_minutes: int, allowed_role: str):

    user = interaction.user
    allowed_role_clean = allowed_role.strip()

    if allowed_role_clean.lower() == "skip":
        role_event = discord.utils.get(interaction.guild.roles, name="Events Ping")
        ping_text = f"@here {role_event.mention}" if role_event else "@here"
    else:
        role_obj = resolve_role(interaction.guild, allowed_role_clean)
        ping_text = role_obj.mention if role_obj else "@here"

    msg = await interaction.channel.send(ping_text)
    await msg.delete()

    embed = build_event_embed(text, user, duration_minutes, max_winners)
    message = await interaction.channel.send(embed=embed)

    view = EventView(message.id)
    await message.edit(view=view)

    event_configs[message.id] = {
        "max_winners": max_winners,
        "duration_minutes": duration_minutes,
        "allowed_role": allowed_role_clean,
    }

    event_entries[message.id] = []
    event_active[message.id] = True

    await interaction.response.send_message("Event has been created!", ephemeral=True)

    asyncio.create_task(update_event_timer(message, message.id, duration_minutes))

    await asyncio.sleep(duration_minutes * 60)
    event_active[message.id] = False

    if not event_entries[message.id]:
        await interaction.channel.send("The event has ended, but no one joined.")
        return

    await finish_event(
        interaction,
        message,
        event_entries[message.id],
        max_winners,
        text,
        user
    )

# ============================
# Script Panal
# ============================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(GetScriptButton(row=0))
        self.add_item(GetBuyerRoleButton(row=0))
        self.add_item(
            discord.ui.Button(
                label="💵 Purchase",
                url=website_link + "purchase",
                row=0,
            )
        )

        self.add_item(RedeemKeyButton(row=1))
        self.add_item(ResetHWIDButton(row=1))
        self.add_item(InfosButton(row=1))

class ScriptDropdown(discord.ui.Select):
    def __init__(self):

        scripts_data = fetch_scripts(response)
        options = build_select_options(scripts_data)

        super().__init__(
            placeholder="Choose your script",
            min_values=1,
            max_values=1,
            options=options,
        )

        self.scripts_data = scripts_data

    async def callback(self, interaction: discord.Interaction):

        user_key = fetch_user_key(interaction)
        if not user_key:
            return

        selected_value = self.values[0]
        script_info = self.scripts_data.get(selected_value, {})

        embed = build_script_embed(interaction, script_info, user_key)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ScriptDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ScriptDropdown())

class GetScriptButton(discord.ui.Button):
    def __init__(self, row: int = 0):
        super().__init__(
            label="📜 Get Script",
            style=discord.ButtonStyle.blurple,
            custom_id="get_script",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):

        user_key = fetch_user_key(interaction)

        if not user_key:
            await interaction.response.send_message(
                "You are not whitelisted.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Please choose your script below:",
            view=ScriptDropdownView(),
            ephemeral=True,
        )

class RedeemKeyModal(discord.ui.Modal, title="Redeem a Key"):
    key_input = discord.ui.TextInput(
        label="Enter your key:",
        placeholder="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        style=discord.TextStyle.short,
        required=True,
        min_length=32,
        max_length=32,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        key = self.key_input.value.strip()

        record = load_key_database()
        if not record:
            status_text = "Failed to load key database."
            await interaction.followup.send(status_text, ephemeral=True)
            await send_purchase_log(interaction, status_text, key)
            return

        matched_key = match_redeem_key(record, key)
        if not matched_key:
            status_text = "Invalid or already used key."
            await interaction.followup.send(status_text, ephemeral=True)
            await send_purchase_log(interaction, status_text, key)
            return

        result = redeem_key_api(interaction, matched_key)
        if not result.get("success"):
            status_text = f"Failed to redeem key: {result.get('message')}"
            await interaction.followup.send(status_text, ephemeral=True)
            await send_purchase_log(interaction, status_text, key)
            return

        role = interaction.guild.get_role(buyer_role_id)
        if role:
            await interaction.user.add_roles(role, reason="Key redeemed successfully")

        status_text = "Key redeemed successfully!"
        await interaction.followup.send(status_text, ephemeral=True)

        await send_purchase_log(interaction, status_text, key)

class RedeemKeyButton(discord.ui.Button):
    def __init__(self, row: int = 0):
        super().__init__(
            label="🗝️ Redeem Key",
            style=discord.ButtonStyle.blurple,
            custom_id="redeem_key",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RedeemKeyModal())

class GetBuyerRoleButton(discord.ui.Button):
    def __init__(self, row: int = 0):
        super().__init__(
            label="🌟 Get Buyer Role",
            style=discord.ButtonStyle.green,
            custom_id="get_buyer_role",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):

        user_key = fetch_user_key(interaction)

        if not user_key:
            await interaction.response.send_message(
                "You are not whitelisted.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        buyer_role = guild.get_role(buyer_role_id)

        if buyer_role in member.roles:
            await interaction.response.send_message(
                "You already have the buyer role.",
                ephemeral=True
            )
            return

        # Try add role
        try:
            await member.add_roles(buyer_role, reason="Verified buyer via Luarmor")
            await interaction.response.send_message(
                "Buyer role successfully!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to get role: {e}",
                ephemeral=True
            )

class ResetHWIDButton(discord.ui.Button):
    def __init__(self, row: int = 0):
        super().__init__(
            label="⚙️ Reset HWID",
            style=discord.ButtonStyle.green,
            custom_id="reset_hardware_identifier",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        now = datetime.now()

        await interaction.response.send_message(
            "Processing your HWID reset...",
            ephemeral=True
        )

        cooldown_left = check_hwid_cooldown(user_id, now)
        if cooldown_left:
            await interaction.followup.send(
                f"You can reset HWID again in {format_timedelta(cooldown_left)}.",
                ephemeral=True
            )
            return

        user_key = fetch_user_key(interaction)
        if not user_key:
            await interaction.followup.send("You are not whitelisted.", ephemeral=True)
            return

        result = await asyncio.to_thread(reset_hwid_api, user_key)

        if result.get("success"):
            await interaction.followup.send("Successfully reset your HWID.", ephemeral=True)
        else:
            await interaction.followup.send("HWID reset failed.", ephemeral=True)

class InfosButton(discord.ui.Button):
    def __init__(self, row: int = 0):
        super().__init__(
            label="📊 Infos",
            style=discord.ButtonStyle.red,
            custom_id="info",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):

        user = fetch_user_data(interaction)

        if not user:
            await interaction.response.send_message(
                "You are not whitelisted.",
                ephemeral=True
            )
            return

        embed = build_user_info_embed(interaction, user)

        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set-panel", description="Set the Xecret Hub script panel")
@is_support_or_admin()
async def set_panel(interaction: discord.Interaction):
    await interaction.response.defer()
    embed = discord.Embed(
        title="📄 Xecret Hub | Script Loader!",
        url=website_link,
        description=(
            "A new and popular Roblox script that has a lot of buyers and allows you to earn money from our script without getting banned."
        ),
        color=discord.Color.purple(),
    )
    embed.set_author(
        name="Xecret Hub High Quality Script",
        url=discord_link,
        icon_url=thumbnail_logo,
    )

    embed.add_field(
        name="📜 Get Script",
        value="Get the Script and use it if you are already whitelisted.",
        inline=True,
    )
    embed.add_field(
        name="🗝️ Redeem Key",
        value="Redeem Key when you receive the key through the website.",
        inline=True,
    )
    embed.add_field(
        name="🌟 Get Buyer Role",
        value="You can get the buyer role if you have already purchased.",
        inline=True,
    )
    embed.add_field(
        name="⚙️ Reset HWID",
        value="You can reset the Hardware IDentifier if you change computers or Executor and it will cooldown for one day.",
        inline=True,
    )
    embed.add_field(
        name="📊 Infos",
        value="You can check your Information Whitelist such as Total Executions and more.",
        inline=True,
    )

    embed.set_thumbnail(url=thumbnail_logo)
    embed.set_image(url=image_logo)
    datatime_now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Created by {interaction.user.display_name} • {datatime_now}",
        icon_url=interaction.user.display_avatar.url,
    )

    view = PanelView()
    await interaction.followup.send(embed=embed, view=view)

# ============================
# Whitelist-Infos
# ============================
@bot.tree.command(name="whitelist-infos", description="Check whitelist info of a user")
@app_commands.describe(member="The member to check whitelist information")
@is_support_or_admin()
async def whitelist_infos(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    user = fetch_user_data_from_id(member.id) 

    if not user:
        await interaction.followup.send(
            "This user is not whitelisted.", ephemeral=True
        )
        return

    embed = build_user_info_embed(interaction, user, target_user=member)

    await interaction.followup.send(embed=embed, ephemeral=True)

# ============================
# Generate Key
# ============================
def generate_key(length=32):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def generate_keys(amount, days):
    if not isinstance(days, list):
        days = [days]

    keys = {}
    part_size = amount // len(days)
    remainder = amount % len(days)

    key_count = 0
    for d in days:
        count = part_size + (1 if remainder > 0 else 0)
        if remainder > 0:
            remainder -= 1

        for _ in range(count):
            key_count += 1
            key_id = f"Key{key_count}"
            keys[key_id] = {
                "key": generate_key(),
                "day": [d]
            }

    return keys

class KeyDownloadView(discord.ui.View):
    def __init__(self, keys: dict):
        super().__init__(timeout=None)
        self.keys = keys

    @discord.ui.button(label="Download TXT", style=discord.ButtonStyle.blurple)
    async def download_txt(self, interaction: discord.Interaction, button: discord.ui.Button):
        grouped = {}
        for info in self.keys.values():
            day = info["day"][0]
            grouped.setdefault(day, []).append(info["key"])

        txt_blocks = []
        for day, keys in grouped.items():
            block = "\n".join(keys)
            txt_blocks.append(block)

        txt_data = "\n\n".join(txt_blocks)  

        file = discord.File(io.StringIO(txt_data), filename="keys.txt")
        await interaction.response.send_message("Here is your TXT file:", file=file, ephemeral=True)

    @discord.ui.button(label="Download JSON", style=discord.ButtonStyle.green)
    async def download_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        json_data = json.dumps(self.keys, indent=2)
        file = discord.File(io.StringIO(json_data), filename="keys.json")
        await interaction.response.send_message("Here is your JSON file:", file=file, ephemeral=True)


@bot.tree.command(
    name="generate-key",
    description="Generate keys and download as .txt and .json (Minami Only)"
)
@app_commands.describe(
    amount="Number of keys to generate",
    day="Number of days per key (ex: 0 or 0,30)"
)
@is_support_or_admin()
async def generate_key_command(interaction: discord.Interaction, amount: int, day: str):
    try:
        days = [int(d.strip()) for d in day.split(",")]
    except ValueError:
        await interaction.response.send_message("Invalid day format! Example: 0 or 0,30", ephemeral=True)
        return

    generated_keys = generate_keys(amount, days)
    await interaction.response.send_message(
        f"Generated {amount} key(s) divided across {days} day(s). (Minami Only)",
        view=KeyDownloadView(generated_keys),
        ephemeral=True
    )

# ============================
# Ticket 
# ============================
class TicketTypeDropdown(ui.Select):
    cooldowns = {}

    def __init__(self):
        options = [
            discord.SelectOption(label="Purchase", description="Help with buying or payment"),
            discord.SelectOption(label="Bug Report", description="Report a bug or any issues"),
            discord.SelectOption(label="Question", description="Ask a question or get help"),
        ]
        super().__init__(placeholder="Choose your ticket type", options=options)

    async def callback(self, interaction: Interaction):
        ticket_type = self.values[0]
        user = interaction.user
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        allowed, remaining = check_ticket_cooldown(user.id, self.cooldowns)
        if not allowed:
            return await interaction.response.send_message(
                f"You can create another ticket in {remaining} minute(s).",
                ephemeral=True
            )

        username = user.name.lower().replace(" ", "-")
        existing = find_existing_ticket(category, username)
        if existing:
            return await interaction.response.send_message(
                f"You already have an open ticket: {existing.mention}",
                ephemeral=True
            )

        channel = await create_ticket_channel(guild, category, user, ticket_type)

        await send_ticket_message(channel, user, ticket_type)

        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}",
            ephemeral=True
        )

class TicketDropdownView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeDropdown())

class TicketControlView(ui.View):
    def __init__(self, creator: discord.User, ticket_type: str, ticket_channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.creator = creator
        self.ticket_type = ticket_type
        self.ticket_channel = ticket_channel

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: Interaction, button: ui.Button):
        if interaction.channel != self.ticket_channel:
            return await interaction.response.send_message("This button doesn't belong here.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        transcript_lines = []
        async for msg in self.ticket_channel.history(limit=None, oldest_first=True):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            content = msg.content or ""
            transcript_lines.append(f"[{timestamp}] {msg.author.name}: {content}")

        transcript = "\n".join(transcript_lines)
        file = discord.File(fp=io.StringIO(transcript), filename=f"{self.ticket_channel.name}_transcript.txt")  
        log_channel = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID)
        if log_channel:
            embed = Embed(
                title=f"{self.ticket_type} Ticket Transcript",
                description=(
                    f"**Created by:** {self.creator.mention}\n"
                    f"**Channel:** `{self.ticket_channel.name}`"
                ),
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"User ID: {self.creator.id}")
            await log_channel.send(embed=embed)
            await log_channel.send(file=file)

        await self.ticket_channel.delete(reason="Ticket closed and transcript saved")

@bot.tree.command(name="set-ticket", description="Send the ticket panel with dropdown options")
@is_support_or_admin()
async def set_ticket(interaction: Interaction):
    embed = Embed(
        title="Xecret Hub | Support Ticket",
        description="Need help? Choose a ticket type below to get started.",
        color=discord.Color.blurple(),
    )
    datatime_now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Xecret Hub Ticket System • {datatime_now}"
    )

    await interaction.response.send_message(embed=embed, view=TicketDropdownView())

# ============================
# Get Script
# ============================
@bot.tree.command(name="get-script", description="Get your Xecret Hub script")
@app_commands.describe(script="Choose your script")
@app_commands.autocomplete(script=script_autocomplete)
async def get_script(interaction: discord.Interaction, script: str):

    user_key = fetch_user_key(interaction)
    if not user_key:
        await interaction.response.send_message(
            "You are not whitelisted.",
            ephemeral=True
        )
        return

    scripts_data = fetch_scripts_data()
    script_info = scripts_data.get(script)

    if not script_info:
        await interaction.response.send_message(
            "Script not found.",
            ephemeral=True
        )
        return

    embed = build_script_embed(interaction, script_info, user_key)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================
# Resethwid Cooldown
# ============================
@bot.tree.command(name="resethwid-cooldown", description="Set HWID reset cooldown (e.g. 2d or 12h)")
@app_commands.describe(duration="Cooldown duration like '2d' or '12h'")
@is_support_or_admin()
async def resethwid_cooldown(interaction: discord.Interaction, duration: str):
    global hwid_reset_cooldown

    parsed = parse_cooldown_duration(duration)

    if parsed is None:
        await interaction.response.send_message(
            "Invalid format. Use like '2d' or '12h'.",
            ephemeral=True
        )
        return

    hwid_reset_cooldown = parsed

    await interaction.response.send_message(
        f"Cooldown updated to {hwid_reset_cooldown}.",
        ephemeral=True
    )

# ============================
# Whitelist and UnWhitelist
# ============================
@bot.tree.command(name="whitelist", description="Whitelist a user or adjust their days")
@app_commands.describe(
    member="The member to whitelist",
    days="Number of days to add/subtract (0 = lifetime)",
    note="Optional note for the whitelist"
)
@is_support_or_admin()
async def whitelist(interaction: discord.Interaction, member: discord.Member, days: int, note: str = ""):
    await interaction.response.defer(ephemeral=True)

    user = fetch_user_data_from_id(member.id)

    if user:
        user_key = user["user_key"]
        current_days = user.get("key_days", 0)

        new_days = current_days + days

        if new_days <= 0:
            result = delete_user_key(user_key)

            if not result.get("success"):
                return await interaction.followup.send(
                    f"Failed to unwhitelist {member.display_name}: {result.get('message')}",
                    ephemeral=True
                )

            buyer_role = interaction.guild.get_role(buyer_role_id)
            if buyer_role and buyer_role in member.roles:
                await member.remove_roles(buyer_role)

            await send_whitelist_log(
                interaction.guild,
                member,
                f"User: {member.mention}\nKey: ||{user_key}||\nReason: Days reached **0**, user unwhitelisted.",
                discord.Color.red()
            )

            return await interaction.followup.send(
                f"{member.display_name} has been unwhitelisted.",
                ephemeral=True
            )

        delete_result = delete_user_key(user_key)
        if not delete_result.get("success"):
            return await interaction.followup.send(
                f"Failed to update whitelist for {member.display_name}.",
                ephemeral=True
            )

        create_result = create_user_key(member.id, new_days, note)
        if not create_result.get("success"):
            return await interaction.followup.send(
                f"Failed to re-whitelist {member.display_name}: {create_result.get('message')}",
                ephemeral=True
            )

        new_key = create_result.get("user_key")

        buyer_role = interaction.guild.get_role(buyer_role_id)
        if buyer_role and buyer_role not in member.roles:
            await member.add_roles(buyer_role)

        await send_whitelist_log(
            interaction.guild,
            member,
            f"User: {member.mention}\nKey: ||{new_key}||\nDays adjusted to **{new_days}**.",
            discord.Color.blurple()
        )

        return await interaction.followup.send("Whitelist updated.", ephemeral=True)

    create_result = create_user_key(member.id, days, note)
    if not create_result.get("success"):
        return await interaction.followup.send(
            f"Failed to whitelist {member.display_name}.",
            ephemeral=True
        )

    new_key = create_result["user_key"]

    buyer_role = interaction.guild.get_role(buyer_role_id)
    if buyer_role and buyer_role not in member.roles:
        await member.add_roles(buyer_role)

    await send_whitelist_log(
        interaction.guild,
        member,
        f"User: {member.mention}\nKey: ||{new_key}||\nWhitelisted for **{days if days!=0 else 'Lifetime'}**.",
        discord.Color.blurple()
    )

    await interaction.followup.send("Whitelist created.", ephemeral=True)

@bot.tree.command(name="unwhitelist", description="Remove a user's whitelist key")
@app_commands.describe(member="The member to remove from whitelist")
@is_support_or_admin()
async def unwhitelist(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    user = fetch_user_data_from_id(member.id)
    if not user:
        return await interaction.followup.send("User has no whitelist.", ephemeral=True)

    user_key = user["user_key"]

    delete_result = delete_user_key(user_key)
    if not delete_result.get("success"):
        return await interaction.followup.send(
            f"Failed to unwhitelist {member.display_name}: {delete_result.get('message')}",
            ephemeral=True
        )

    buyer_role = interaction.guild.get_role(buyer_role_id)
    if buyer_role and buyer_role in member.roles:
        await member.remove_roles(buyer_role)

    await send_whitelist_log(
        interaction.guild,
        member,
        f"User: {member.mention}\nKey: ||{user_key}||\nStatus: Unwhitelisted.",
        discord.Color.red()
    )

    await interaction.followup.send(f"{member.display_name} has been unwhitelisted.", ephemeral=True)

@bot.tree.command(name="resethwid", description="Reset a user's HWID")
@app_commands.describe(member="The member whose HWID will be reset")
@is_support_or_admin()
async def resethwid(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    user = fetch_user_data_from_id(member.id)
    if not user:
        return await interaction.followup.send(
            f"No whitelist found for {member.display_name}.",
            ephemeral=True
        )

    user_key = user.get("user_key")
    if not user_key:
        return await interaction.followup.send(
            f"No user_key found for {member.display_name}.",
            ephemeral=True
        )

    result = reset_hwid_api(user_key)

    if result.get("success"):
        status_text = "HWID reset successfully!"
        color = discord.Color.green()
    else:
        status_text = f"Failed to reset HWID: {result.get('message')}"
        color = discord.Color.red()

    await interaction.followup.send(
        f"{status_text} for {member.display_name}.",
        ephemeral=True
    )

    await send_action_log(
        interaction.guild,
        member,
        "HWID Reset Status",
        f"User: {member.mention}\nKey: ||{user_key}||\nStatus: {status_text}",
        color
    )

# ============================
# Blacklist and UnBlacklist
# ============================
@bot.tree.command(name="blacklist", description="Blacklist a user's key permanently or temporarily")
@app_commands.describe(
    member="The member to blacklist",
    reason="Reason for blacklisting",
    duration="Duration like '2d' or '12h' (leave empty for permanent)"
)
@is_support_or_admin()
async def blacklist(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
    duration: str = None
):
    await interaction.response.defer(ephemeral=True)

    user = fetch_user_data_from_id(member.id)
    if not user:
        return await interaction.followup.send("User not found in whitelist.", ephemeral=True)

    user_key = user.get("user_key")
    unban_token = user.get("unban_token")

    try:
        ban_expire, expire_text = parse_duration(duration)
    except ValueError:
        return await interaction.followup.send(
            "Invalid duration format. Use '2d' or '12h'.",
            ephemeral=True
        )

    result = blacklist_user(user_key, reason, ban_expire)

    if not result.get("success"):
        status_text = f"Failed to blacklist: {result.get('message')}"
        color = discord.Color.red()
    else:
        status_text = f"User blacklisted ({expire_text})"
        color = discord.Color.red()

    await interaction.followup.send(
        f"{member.display_name} {status_text}.",
        ephemeral=True
    )
    await send_action_log(
        interaction.guild,
        member,
        "Blacklist Status",
        f"User: {member.mention}\nKey: ||{user_key}||\nStatus: {status_text}\nReason: {reason}\nExpire: {expire_text}",
        color
    )

@bot.tree.command(name="unblacklist", description="Remove a user from blacklist")
@app_commands.describe(member="The member to unblacklist")
@is_support_or_admin()
async def unblacklist(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    user = fetch_user_data_from_id(member.id)
    if not user:
        return await interaction.followup.send("User not found in whitelist.", ephemeral=True)

    user_key = user.get("user_key")
    unban_token = user.get("unban_token")

    if not unban_token:
        return await interaction.followup.send(
            f"No unban token found for {member.display_name}. Cannot unblacklist.",
            ephemeral=True
        )

    response = unblacklist_user(unban_token)

    if response.status_code == 200:
        status_text = "User successfully unblacklisted!"
        color = discord.Color.green()
    else:
        status_text = "Failed to unblacklist user."
        color = discord.Color.red()

    await interaction.followup.send(status_text, ephemeral=True)

    await send_action_log(
        interaction.guild,
        member,
        "Unblacklist Status",
        f"User: {member.mention}\nKey: ||{user_key}||\nStatus: {status_text}",
        color
    )

# ============================
# Ban
# ============================
@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(member="The member to ban", reason="Reason for banning")
@is_support_or_admin()
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(
            f"{member.mention} has been banned.\nReason: {reason}", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Failed to ban {member.mention}: {e}", ephemeral=True
        )

# ============================
# Kick
# ============================
@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="The member to kick", reason="Reason for kicking")
@is_support_or_admin()
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(
            f"{member.mention} has been kicked.\nReason: {reason}", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Failed to kick {member.mention}: {e}", ephemeral=True
        )

# ============================
# Timeout
# ============================
@bot.tree.command(
    name="timeout", description="Timeout a member for a specified duration in minutes"
)
@app_commands.describe(
    member="The member to timeout",
    duration_minutes="Duration in minutes",
    reason="Reason for timeout",
)
@is_support_or_admin()
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    duration_minutes: int,
    reason: str = "No reason provided",
):
    try:
        await member.timeout(timedelta(minutes=duration_minutes), reason=reason)
        await interaction.response.send_message(
            f"{member.mention} has been timed out for {duration_minutes} minute(s).\nReason: {reason}",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Failed to timeout {member.mention}: {e}", ephemeral=True
        )

# ============================
# Send Message
# ============================
@bot.tree.command(
    name="send", description="Send a message to a channel or to the current channel"
)
@app_commands.describe(
    text="The message to send",
    channel="Optional: channel ID or channel link to send the message",
)
@is_support_or_admin()
async def send(interaction: discord.Interaction, text: str, channel: str = None):
    target_channel = None

    if channel:
        try:
            if channel.startswith("<#") and channel.endswith(">"):
                channel_id = int(channel[2:-1])
            else:
                channel_id = int(channel)
            target_channel = interaction.guild.get_channel(channel_id)
        except:
            await interaction.response.send_message(
                "Invalid channel ID or mention!", ephemeral=True
            )
            return

        if not target_channel:
            await interaction.response.send_message(
                "Channel not found!", ephemeral=True
            )
            return
    else:
        target_channel = interaction.channel

    try:
        await target_channel.send(text)
        await interaction.response.send_message(
            f"Message sent to {target_channel.mention}!", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Failed to send message: {e}", ephemeral=True
        )

# ============================
# Send Website
# ============================
@bot.tree.command(
    name="website", description="Send a link to a specific page of the website"
)
@app_commands.describe(page="Select the page to send the link for")
@app_commands.choices(
    page=[
        app_commands.Choice(name="Home", value=""),
        app_commands.Choice(name="Games", value="games"),
        app_commands.Choice(name="Executors", value="executors"),
        app_commands.Choice(name="Purchase", value="pricing"),
        app_commands.Choice(name="Terms", value="tos"),
    ]
)
async def website(interaction: discord.Interaction, page: app_commands.Choice[str]):
    await interaction.response.send_message(website_link + page.value)

# message
@bot.event
async def on_message(message):
    lower_message = message.content.lower()
    # block bot message
    if message.author == bot.user:
        return
    # ping
    for user in message.mentions:
        if user.id in admin_ids:
            await message.reply(
                f"{message.author.mention} You mentioned the administrator"
            )
            await message.author.timeout(
                timedelta(seconds=timeout_duration),
                reason="Mentioned the administrator",
            )
            await message.delete()
    # ping everyone and here
    if "@everyone" in lower_message or "@here" in lower_message or "imgur" in lower_message or "i.ibb" in lower_message:
        await message.reply(
            f"{message.author.mention} You got hacked and received a softban for one day."
        )
        await message.author.timeout(
            timedelta(days=1), reason="Mentioning @everyone or @here"
        )
        await message.delete()
    await bot.process_commands(message)

server_on()
bot.run(bot_token)
