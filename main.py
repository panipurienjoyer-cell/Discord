import discord
from discord.ext import tasks, commands
from discord import app_commands, Interaction, Embed, ui
from dotenv import load_dotenv
import feedparser
import asyncio
import re
import requests
import os
import json
import io
import string
import aiohttp
import time
from datetime import datetime, timedelta
import random

try:
    from ping_server import server_on
except ImportError:

    def server_on():
        pass

load_dotenv()

event_entries = {}
event_winners = {}
event_configs = {}
event_active = {}

hwid_reset_timestamps = {}
hwid_reset_cooldown = timedelta(days=1)

admin_ids = [1300017174886350899, 1209783415759704085]
timeout_duration = 5

feed_url_youtube = {
    "English": "https://www.youtube.com/feeds/videos.xml?channel_id=UC5abJGhz74y-cw88wFqX0Jw",
    "Thailand": "https://www.youtube.com/feeds/videos.xml?channel_id=UCoLxgTtHYNA8AjOJB1rU-2g",
}
howtobuy_channel = (
    "https://discord.com/channels/1328392700294070313/1426171154707775569"
)
channel_id_purchase = 1430745830716870827
panel_channel_id = 1430611712679350333
showcase_channel_id = 1328406450489393253
showcase_role = 1383766143939903528
TICKET_CATEGORY_ID = 1348103529436549250
TRANSCRIPT_CHANNEL_ID = 1347789044133793903
SUPPORT_ROLE_ID = 1395727901361704960

bot_token=os.getenv('BOT_TOKEN')
api_key=os.getenv('API_KEY')
project_id=os.getenv('PROJECT_ID')
keys_json=os.getenv('KEYS_JSON')
loader_json=os.getenv('LOADER_JSON')

headers_master_key = {
    'X-Master-Key':os.getenv('MASTER_KEY')
}

url_project_users = f"https://api.luarmor.net/v3/projects/{project_id}/users"
url_resethwid_users = (
    f"https://api.luarmor.net/v3/projects/{project_id}/users/resethwid"
)

headers = {"Authorization": api_key, "Content-Type": "application/json"}

buyer_role_id = 1328393648957558955

youtube_xecret_hub_channel = "https://www.youtube.com/@XecretHub"

gif_information = (
    "https://i.pinimg.com/originals/cd/0c/3f/cd0c3f12008404cae0a8cbc20e880d21.gif"
)

banner_gif = (
    "https://i.pinimg.com/originals/e6/da/c1/e6dac1038095d76596e8b1bd9653f569.gif"
)

discord_link = "https://discord.com/invite/xecrethub"
website_link = "https://xecrethub.com/"
thumbnail_logo = 'https://ibb.co/pvWJGhKs'
image_logo = 'https://ibb.co/67fj9vfr'
support_ticket = "https://discord.com/channels/1328392700294070313/1348578938024104006"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)
sent_video_ids = set()

# profile
@bot.event
async def on_ready():
    preload_latest_video_ids()
    check_youtube_feeds.start()
    await bot.tree.sync()
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="https://xecrethub.com/"
        ),
    )
    print(bot.user)


# end

# is_support_or_admin
def is_support_or_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True

        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
        if support_role and support_role in interaction.user.roles:
            return True

        raise app_commands.CheckFailure("You don't have permission to use this command.")
    return app_commands.check(predicate)

# end

# showcase
class VideoButtons(discord.ui.View):
    def __init__(self, video_url: str, channel_url: str):
        super().__init__()
        self.add_item(discord.ui.Button(label="Watch Video", url=video_url))
        self.add_item(discord.ui.Button(label="Visit Channel", url=channel_url))


def preload_latest_video_ids():
    for url in feed_url_youtube.values():
        feed = feedparser.parse(url)
        if feed.entries:
            latest = feed.entries[0]
            video_id = latest.yt_videoid
            sent_video_ids.add(video_id)


@tasks.loop(minutes=5)
async def check_youtube_feeds():
    for lang, url in feed_url_youtube.items():
        feed = feedparser.parse(url)
        if not feed.entries:
            continue

        latest = feed.entries[0]
        video_id = latest.yt_videoid
        if video_id in sent_video_ids:
            continue

        sent_video_ids.add(video_id)

        title = latest.title
        link = latest.link
        published = latest.published
        author = latest.author
        thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        updated = getattr(latest, "updated", published)
        raw_description = getattr(latest, "summary", "")

        short_title = title[:50] + "..." if len(title) > 50 else title
        description = (
            raw_description[:70] + "..."
            if len(raw_description) > 70
            else raw_description
        )

        embed = discord.Embed(
            title=short_title,
            url=link,
            description=description,
            color=discord.Color.from_rgb(200, 0, 0),
        )

        embed.set_author(
            name="Xecret Hub has posted a new video",
            url=youtube_xecret_hub_channel,
            icon_url=thumbnail_logo,
        )

        embed.set_thumbnail(url=thumbnail_logo)
        embed.set_image(url=thumbnail)
        embed.set_footer(
            text=f"@Posted by Xecret Hub | Published ({published}) and Updated ({updated})",
            icon_url=thumbnail_logo,
        )

        channel = bot.get_channel(showcase_channel_id)
        if channel:
            view = VideoButtons(link, youtube_xecret_hub_channel)
            await channel.send(f"<@&{showcase_role}>", embed=embed, view=view)


# end

# event
def resolve_role(guild, allowed_role_str):
    match = re.match(r"<@&(\d+)>", allowed_role_str)
    if match:
        role_id = int(match.group(1))
        return guild.get_role(role_id)

    role_name = allowed_role_str.replace("@", "").strip()
    return discord.utils.get(guild.roles, name=role_name)


async def update_event_timer(message, message_id, duration_minutes):
    total_seconds = duration_minutes * 60

    for remaining in range(total_seconds, 0, -1):
        if not event_active.get(message_id, False):
            break

        embed = message.embeds[0]
        entries = len(event_entries.get(message_id, []))
        minutes_left = remaining // 60
        seconds_left = remaining % 60

        embed.description = (
            f"After you win, please go to the {support_ticket} and submit photo proof of your win. "
            "This will help us verify you and ensure you receive your prize as quickly as possible.\n\n"
            f"Ends: {minutes_left:02d}:{seconds_left:02d}\n"
            f"Entries: {entries}\n"
            f"Winners: {event_configs.get(message_id, {}).get('max_winners', 0)}"
        )

        await message.edit(embed=embed)
        await asyncio.sleep(1)


class JoinEventButton(discord.ui.Button):
    def __init__(self, message_id):
        super().__init__(label="🤝 Join Event", style=discord.ButtonStyle.success)
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        msg_id = self.message_id

        if not event_active.get(msg_id, False):
            await interaction.response.send_message(
                "This event has already ended.", ephemeral=True
            )
            return

        allowed_role = event_configs.get(msg_id, {}).get("allowed_role", "Skip")
        if allowed_role.lower() != "skip":
            role_obj = resolve_role(interaction.guild, allowed_role)

            if allowed_role.lower() != "skip":
                if not role_obj or role_obj not in interaction.user.roles:
                    await interaction.response.send_message(
                        "Your role doesn't allow you to join this event.",
                        ephemeral=True,
                    )
                    return

        if msg_id not in event_entries:
            event_entries[msg_id] = []

        if user.id in event_entries[msg_id]:
            await interaction.response.send_message(
                "You've already joined this event!", ephemeral=True
            )
            return

        event_entries[msg_id].append(user.id)

        message = await interaction.channel.fetch_message(msg_id)
        if not message.embeds:
            await interaction.response.send_message(
                "Event embed not found.", ephemeral=True
            )
            return

        embed = message.embeds[0]
        entries = len(event_entries[msg_id])
        duration_minutes = event_configs.get(msg_id, {}).get("duration_minutes", 0)

        embed.description = (
            f"After you win, please go to the {support_ticket} and submit photo proof of your win. "
            "This will help us verify you and ensure you receive your prize as quickly as possible.\n\n"
            f"Ends: {duration_minutes}\n"
            f"Entries: {entries}\n"
            f"Winners: None"
        )

        embed.set_author(
            name=f"{user.display_name} has created a giveaway activity",
            url=f"https://discord.com/users/{user.id}",
            icon_url=user.display_avatar.url,
        )

        embed.add_field(
            name="🤝 Join Event",
            value="Join the event to receive rewards.",
            inline=True,
        )

        embed.add_field(
            name="👋 Leave Event",
            value="Leave Event to cancel receiving the prize",
            inline=True,
        )

        await message.edit(embed=embed)
        await interaction.response.send_message(
            "You've joined the event!", ephemeral=True
        )


class LeaveEventButton(discord.ui.Button):
    def __init__(self, message_id):
        super().__init__(label="👋 Leave Event", style=discord.ButtonStyle.danger)
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        msg_id = self.message_id

        if not event_active.get(msg_id, False):
            await interaction.response.send_message(
                "This event has already ended.", ephemeral=True
            )
            return

        allowed_role = event_configs.get(msg_id, {}).get("allowed_role", "Skip")
        if allowed_role.lower() != "skip":
            role_obj = resolve_role(interaction.guild, allowed_role)

            if allowed_role.lower() != "skip":
                if not role_obj or role_obj not in interaction.user.roles:
                    await interaction.response.send_message(
                        "Your role doesn't allow you to join this event.",
                        ephemeral=True,
                    )
                    return

        if msg_id not in event_entries or user.id not in event_entries[msg_id]:
            await interaction.response.send_message(
                "You haven't joined this event yet.", ephemeral=True
            )
            return

        event_entries[msg_id].remove(user.id)

        message = await interaction.channel.fetch_message(msg_id)
        if not message.embeds:
            await interaction.response.send_message(
                "Event embed not found.", ephemeral=True
            )
            return

        embed = message.embeds[0]
        entries = len(event_entries[msg_id])
        duration_minutes = event_configs.get(msg_id, {}).get("duration_minutes", 0)

        embed.description = (
            f"After you win, please go to the {support_ticket} and submit photo proof of your win. "
            "This will help us verify you and ensure you receive your prize as quickly as possible.\n\n"
            f"Ends: {duration_minutes}\n"
            f"Entries: {entries}\n"
            f"Winners: None"
        )

        embed.set_author(
            name=f"{user.display_name} has created a giveaway activity",
            url=f"https://discord.com/users/{user.id}",
            icon_url=user.display_avatar.url,
        )

        embed.add_field(
            name="🤝 Join Event",
            value="Join the event to receive rewards.",
            inline=True,
        )

        embed.add_field(
            name="👋 Leave Event",
            value="Leave Event to cancel receiving the prize",
            inline=True,
        )

        await message.edit(embed=embed)
        await interaction.response.send_message(
            "You've left the event.", ephemeral=True
        )


class EventView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.add_item(JoinEventButton(message_id))
        self.add_item(LeaveEventButton(message_id))


# setup
@bot.tree.command(
    name="set-event", description="Create a new Xecret Hub giveaway event"
)
@app_commands.describe(
    text="Event title",
    max_winners="Maximum number of winners",
    duration_minutes="Duration of event in minutes",
    allowed_role="Role allowed to participate or 'skip'",
)
@is_support_or_admin()
async def set_event(
    interaction: discord.Interaction,
    text: str,
    max_winners: int,
    duration_minutes: int,
    allowed_role: str,
):
    allowed_role_clean = allowed_role.strip()
    user = interaction.user

    if allowed_role_clean.lower() == "skip":
        role_event = discord.utils.get(interaction.guild.roles, name="Events Ping")
        ping_text = f"@here {role_event.mention}" if role_event else "@here"
    else:
        match = re.match(r"<@&(\d+)>", allowed_role_clean)
        if match:
            role_id = int(match.group(1))
            role_obj = interaction.guild.get_role(role_id)
        else:
            role_name = allowed_role_clean.replace("@", "")
            role_obj = discord.utils.get(interaction.guild.roles, name=role_name)

        ping_text = role_obj.mention if role_obj else "@here"

    msg = await interaction.channel.send(content=ping_text)
    await msg.delete()

    embed = discord.Embed(
        title=f"🎁 Xecret Hub - Event | {text} Giveaway!",
        url=discord_link,
        description=(
            f"After you win, please go to the {support_ticket} and submit photo proof of your win. "
            f"This will help us verify you and ensure you receive your prize as quickly as possible.\n\n"
            f"Ends: {duration_minutes} minutes\n"
            f"Entries: 0\n"
            f"Winners: {max_winners}"
        ),
        color=discord.Color.red(),
    )

    embed.set_author(
        name=f"{user.display_name} has created a giveaway activity",
        url=f"https://discord.com/users/{user.id}",
        icon_url=user.display_avatar.url,
    )
    embed.add_field(
        name="🤝 Join Event", value="Join the event to receive rewards.", inline=True
    )
    embed.add_field(
        name="👋 Leave Event",
        value="Leave Event to cancel receiving the prize",
        inline=True,
    )
    embed.set_thumbnail(url=thumbnail_logo)
    embed.set_image(url=image_logo)
    datatime_now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Hosted by {user.display_name} • {datatime_now}",
        icon_url=user.display_avatar.url,
    )

    message = await interaction.channel.send(embed=embed)
    view = EventView(message.id)
    await message.edit(view=view)
    asyncio.create_task(update_event_timer(message, message.id, duration_minutes))

    event_configs[message.id] = {
        "max_winners": max_winners,
        "duration_minutes": duration_minutes,
        "allowed_role": allowed_role.strip(),
    }
    event_entries[message.id] = []
    event_active[message.id] = True

    await interaction.response.send_message("Event has been created!", ephemeral=True)

    await asyncio.sleep(duration_minutes * 60)
    event_active[message.id] = False

    if not event_entries[message.id]:
        await interaction.channel.send("The event has ended, but no one joined.")
        return

    winners = random.sample(
        event_entries[message.id], min(max_winners, len(event_entries[message.id]))
    )
    event_winners[message.id] = winners
    winner_mentions = ", ".join(f"<@{uid}>" for uid in winners)

    updated_embed = message.embeds[0]
    datatime_now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    updated_embed.description = (
        f"After you win, please go to the {support_ticket} and submit photo proof of your win. "
        "This will help us verify you and ensure you receive your prize as quickly as possible.\n\n"
        f"Ended: {datatime_now}\n"
        f"Entries: {len(event_entries[message.id])}\n"
        f"Winners: {winner_mentions}"
    )

    updated_embed.set_author(
        name=f"{user.display_name} has created a giveaway activity",
        url=f"https://discord.com/users/{user.id}",
        icon_url=user.display_avatar.url,
    )

    await message.edit(embed=updated_embed)

    for uid in winners:
        await interaction.channel.send(
            f"Congratulations <@{uid}>! You won the giveaway **{embed.title}**"
        )


# end

# panel
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
        response = requests.get(loader_json, headers=headers_master_key)
        if response.status_code == 200:
            scripts_data = response.json()["record"]
        else:
            scripts_data = {}

        options = []
        for key, script in scripts_data.items():
            options.append(
                discord.SelectOption(
                    label=f"{script.get('name', key)} Script",
                    description=f"Xecret Hub {script.get('name', key)} Loader",
                    value=key
                )
            )

        super().__init__(
            placeholder="Choose your script",
            min_values=1,
            max_values=1,
            options=options,
        )

        self.scripts_data = scripts_data

    async def callback(self, interaction: discord.Interaction):
        params = {"discord_id": interaction.user.id}
        response = requests.get(url_project_users, headers=headers, params=params)
        if response.status_code == 200:
            user_key = response.json()["users"][0]["user_key"]
        else:
            return

        selected_value = self.values[0]
        script_info = self.scripts_data.get(selected_value, {})

        script_name_embed = script_info.get("name", "Unknown Script")
        loader_embed = script_info.get("url", "")

        value_embed = (
            "```lua\n"
            f'script_key = "{user_key}"\n'
            f'loadstring(game:HttpGet("{loader_embed}"))()\n'
            "```"
        )

        embed = discord.Embed(
            title="Xecret Hub | Script Loader",
            url=loader_embed,
            color=discord.Color.blurple(),
        )
        embed.set_author(
            name=f"{interaction.user.display_name} has got the script",
            url=f"https://discord.com/users/{interaction.user.id}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(
            name=f"{script_name_embed} Script",
            value= value_embed,
            inline=False,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_image(url=banner_gif)
        datatime_now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
        embed.set_footer(
            text=f"@Xecret Hub • {datatime_now}",
            icon_url=thumbnail_logo,
        )

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
        discord_id = str(interaction.user.id)
        params = {"discord_id": discord_id}

        response = requests.get(url_project_users, headers=headers, params=params)
        if response.status_code != 200:
            await interaction.response.send_message(
                "Failed to verify your access.", ephemeral=True
            )
            return

        data = response.json()
        user_data = data.get("users")

        if user_data:
            await interaction.response.send_message(
                "Please choose your script below:",
                view=ScriptDropdownView(),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "You are not whitelisted.", ephemeral=True
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

        res = requests.get(keys_json, headers=headers_master_key)
        if res.status_code != 200:
            status_text = "Failed to load key database."
            await interaction.followup.send(status_text, ephemeral=True)
            await self.send_status_embed(interaction, status_text, key)
            return

        data = res.json()
        record = data.get("record", {})
        matched_key = None

        for key_id, info in record.items():
            if info["key"] == key:
                matched_key = info
                break

        if not matched_key:
            status_text = "Invalid or already used key."
            await interaction.followup.send(status_text, ephemeral=True)
            await self.send_status_embed(interaction, status_text, key)
            return

        body = {
            "discord_id": str(interaction.user.id),
            "note": "Redeem Key Via Xecret Hub",
            "key_days": matched_key["day"][0] if matched_key["day"] else 0,
        }

        response = requests.post(url_project_users, headers=headers, json=body)
        result = response.json()

        if not result.get("success"):
            status_text = f"Failed to redeem key: {result.get('message')}"
            await interaction.followup.send(status_text, ephemeral=True)
            await self.send_status_embed(interaction, status_text, key)
            return

        role = interaction.guild.get_role(buyer_role_id)
        if role:
            await interaction.user.add_roles(role, reason="Key redeemed successfully")
            status_text = "Key redeemed successfully!"
            await interaction.followup.send(status_text, ephemeral=True)

        await self.send_status_embed(interaction, status_text, key)

    async def send_status_embed(
        self, interaction: discord.Interaction, status_text: str, key: str
    ):
        channel_purchase = interaction.guild.get_channel(channel_id_purchase)
        if not channel_purchase:
            return

        embed = discord.Embed(
            title="Key Redeem Status",
            description=f"User: {interaction.user.mention}\nKey: ||{key}||\nStatus: {status_text}",
            color=discord.Color.green()
            if "success" in status_text.lower()
            else discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        await channel_purchase.send(embed=embed)


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
        discord_id = str(interaction.user.id)
        params = {"discord_id": discord_id}
        response = requests.get(url_project_users, headers=headers, params=params)

        if response.status_code != 200:
            await interaction.response.send_message(
                "Access check failed. Please try again later.", ephemeral=True
            )
            return

        data = response.json()
        user_data = data.get("users")

        if not user_data:
            await interaction.response.send_message(
                "You are not whitelisted.", ephemeral=True
            )
            return

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        buyer_role = guild.get_role(buyer_role_id)

        if buyer_role in member.roles:
            await interaction.response.send_message(
                "You already have the buyer role.", ephemeral=True
            )
            return

        try:
            await member.add_roles(buyer_role, reason="Verified buyer via Luarmor")
            await interaction.response.send_message(
                "Buyer role successfully!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to get role: {e}", ephemeral=True
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
            "Processing your HWID reset...", ephemeral=True
        )

        last_reset = hwid_reset_timestamps.get(user_id)
        if last_reset and now - last_reset < hwid_reset_cooldown:
            remaining = hwid_reset_cooldown - (now - last_reset)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            await interaction.followup.send(
                f"You can reset HWID again in {remaining.days}d {hours}h {minutes}m {seconds}s.",
                ephemeral=True,
            )
            return

        hwid_reset_timestamps[user_id] = now

        params = {"discord_id": str(user_id), "force": True}

        response = await asyncio.to_thread(
            requests.get, url_project_users, headers=headers, params=params
        )

        if response.status_code != 200:
            await interaction.followup.send("Failed to verify your access.", ephemeral=True)
            return

        data = response.json()
        user_data = data.get("users")
        if not user_data:
            await interaction.followup.send("You are not whitelisted.", ephemeral=True)
            return

        user_key = user_data[0]["user_key"]
        body = {"user_key": user_key, "force": True}

        post_response = await asyncio.to_thread(
            requests.post, url_resethwid_users, headers=headers, json=body
        )
        post_data = post_response.json()

        if post_data.get("success"):
            await interaction.followup.send("Successfully reset your HWID.", ephemeral=True)
        else:
            await interaction.followup.send("HWID reset failed.", ephemeral=True)


class InfosButton(discord.ui.Button):
    def __init__(self, row: int = 0):
        super().__init__(
            label="📊 Infos", style=discord.ButtonStyle.red, custom_id="info", row=row
        )

    async def callback(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        params = {"discord_id": discord_id}

        response = requests.get(url_project_users, headers=headers, params=params)

        if response.status_code != 200:
            await interaction.response.send_message(
                "Failed to verify your access.", ephemeral=True
            )
            return

        data = response.json()
        user_data = data.get("users")

        if not user_data:
            await interaction.response.send_message(
                "You are not whitelisted.", ephemeral=True
            )
            return

        def format_expire(auth_expire):
            if auth_expire == -1:
                return "Never"
            expire_date = datetime.fromtimestamp(auth_expire)
            remaining = expire_date - datetime.now()
            if remaining.total_seconds() <= 0:
                return "Expired"
            days = remaining.days
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            if days >= 365:
                return f"{days // 365} year(s) left"
            elif days >= 30:
                return f"{days // 30} month(s) left"
            else:
                return f"{days} day(s) {hours}h {minutes}m left"

        if response.status_code != 200:
            await interaction.response.send_message("Failed to verify your access.", ephemeral=True)
            return

        data = response.json()
        user_data = data.get("users")
        if not user_data:
            await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
            return

        user = user_data[0]

        user_key = user.get("user_key", "Unknown")
        identifier = user.get("identifier", "Unknown")
        identifier_type = user.get("identifier_type", "Unknown")
        status = user.get("status", "Unknown")
        status = status.capitalize()
        last_reset_ts = user.get("last_reset")
        total_resets = user.get("total_resets", "Unknown")
        total_executions = user.get("total_executions", "Unknown")
        auth_expire = int(user.get("auth_expire", -1))
        banned = user.get("banned", 0)
        ban_reason = user.get("ban_reason", "Unknown")
        note = user.get("note", "None")
        ban_ip = user.get("ban_ip", "Unknown")
        key_days = user.get("key_days", -1)
        key_days_display = "Lifetime" if key_days == -1 else str(key_days)
        expire_display = format_expire(auth_expire)
        ban_expire_ts = user.get("ban_expire", "Unknown")
        banned_status = "Yes" if banned == 1 else "No"
        if last_reset_ts not in (None, 0, -1):
            last_reset = datetime.fromtimestamp(int(last_reset_ts)).strftime("%d/%m/%Y %H:%M:%S")
        else:
            last_reset = "Unknown"

        ban_expire = datetime.fromtimestamp(int(ban_expire_ts)).strftime("%d/%m/%Y %H:%M:%S") or "Unknown"

        embed = discord.Embed(
            title=f"Information | {interaction.user.display_name} ({interaction.user.name})",
            url=f"https://discord.com/users/{interaction.user.id}",
            description=(
                f"**User Key:** ||{user_key or 'Not Found'}||\n"
                f"**Key Status:** {status  or 'Unknown'}\n"
                f"**Key Days:** {key_days_display or 'Unknown'}\n"
                f"**Key Expires at:** {expire_display or 'Unknown'}\n"
                "\n"
                f"**Hwid Key:** ||{identifier or 'Not Found'}||\n"
                f"**Hwid Type:** {identifier_type or 'Unknown'}\n"
                f"**Last HWID Reset:** {last_reset or 'Unknown'}\n"
                "\n"
                f"**Total Executions:** {total_executions or 'Unknown'}\n"
                f"**Total HWID Resets:** {total_resets or 'Unknown'}\n"
                "\n"
                f"**Banned:** {banned_status or 'Unknown'}\n"
                f"**Ban Expires At:** {ban_expire or 'Unknown'}\n"
                f"**Ban IP:** ||{ban_ip or 'Unknown'}||\n"
                f"**Ban Reason:** {ban_reason or 'None'}\n"
                "\n"
                f"**Note:** {note or 'None'}\n"
            ),
            color=discord.Color.blurple(),
        )

        embed.set_author(
            name=f"📊 {interaction.user.display_name}’s Information",
            url=f"https://discord.com/users/{interaction.user.id}",
            icon_url=interaction.user.display_avatar.url,
        )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_image(url=gif_information)
        current_time = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
        embed.set_footer(
            text=f"@Infos by {interaction.user.display_name} • {current_time}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# setup
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


# end

# whitelist-infos
@bot.tree.command(name="whitelist-infos", description="Check whitelist info of a user")
@app_commands.describe(member="The member to check whitelist information")
@is_support_or_admin()
async def whitelist_infos(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True) 

    params = {"discord_id": str(member.id)}

    response = await asyncio.to_thread(requests.get, url_project_users, headers=headers, params=params)
    if response.status_code != 200:
        await interaction.followup.send("Failed to verify access.", ephemeral=True)
        return

    data = response.json()
    user_data = data.get("users")
    if not user_data:
        await interaction.followup.send("This user is not whitelisted.", ephemeral=True)
        return

    user = user_data[0]

    def format_expire(auth_expire):
        if auth_expire == -1:
            return "Never"
        expire_date = datetime.fromtimestamp(auth_expire)
        remaining = expire_date - datetime.now()
        if remaining.total_seconds() <= 0:
            return "Expired"
        days = remaining.days
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if days >= 365:
            return f"{days // 365} year(s) left"
        elif days >= 30:
            return f"{days // 30} month(s) left"
        else:
            return f"{days} day(s) {hours}h {minutes}m left"

    user_key = user.get("user_key", "Unknown")
    identifier = user.get("identifier", "Unknown")
    identifier_type = user.get("identifier_type", "Unknown")
    status = user.get("status", "Unknown").capitalize()
    last_reset_ts = user.get("last_reset")
    total_resets = user.get("total_resets", "Unknown")
    total_executions = user.get("total_executions", "Unknown")
    auth_expire = int(user.get("auth_expire", -1))
    banned = user.get("banned", 0)
    ban_reason = user.get("ban_reason", "Unknown")
    note = user.get("note", "None")
    ban_ip = user.get("ban_ip", "Unknown")
    key_days = user.get("key_days", -1)
    key_days_display = "Lifetime" if key_days == -1 else str(key_days)
    expire_display = format_expire(auth_expire)
    ban_expire_ts = user.get("ban_expire", 0)
    banned_status = "Yes" if banned == 1 else "No"

    if last_reset_ts not in (None, 0, -1):
        last_reset = datetime.fromtimestamp(int(last_reset_ts)).strftime("%d/%m/%Y %H:%M:%S")
    else:
        last_reset = "Unknown"

    if ban_expire_ts not in (None, 0, -1):
        ban_expire = datetime.fromtimestamp(int(ban_expire_ts)).strftime("%d/%m/%Y %H:%M:%S")
    else:
        ban_expire = "Unknown"

    embed = discord.Embed(
        title=f"Information | {member.display_name} ({member.name})",
        url=f"https://discord.com/users/{member.id}",
        description=(
            f"**User Key:** ||{user_key or 'Not Found'}||\n"
            f"**Key Status:** {status or 'Unknown'}\n"
            f"**Key Days:** {key_days_display or 'Unknown'}\n"
            f"**Key Expires at:** {expire_display or 'Unknown'}\n"
            "\n"
            f"**HWID Key:** ||{identifier or 'Not Found'}||\n"
            f"**HWID Type:** {identifier_type or 'Unknown'}\n"
            f"**Last HWID Reset:** {last_reset or 'Unknown'}\n"
            "\n"
            f"**Total Executions:** {total_executions or 'Unknown'}\n"
            f"**Total HWID Resets:** {total_resets or 'Unknown'}\n"
            "\n"
            f"**Banned:** {banned_status or 'Unknown'}\n"
            f"**Ban Expires At:** {ban_expire or 'Unknown'}\n"
            f"**Ban IP:** ||{ban_ip or 'Unknown'}||\n"
            f"**Ban Reason:** {ban_reason or 'None'}\n"
            "\n"
            f"**Note:** {note or 'None'}\n"
        ),
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )

    embed.set_author(
        name=f"📊 {member.display_name}’s Information",
        url=f"https://discord.com/users/{member.id}",
        icon_url=member.display_avatar.url,
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    if 'gif_information' in globals():
        embed.set_image(url=gif_information)

    current_time = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Infos requested by {interaction.user.display_name} • {current_time}",
        icon_url=interaction.user.display_avatar.url,
    )

    await interaction.followup.send(embed=embed, ephemeral=True)

# end

# generate key
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


# end

# set-ticket    
class TicketTypeDropdown(ui.Select):
    cooldowns = {}  

    def __init__(self):
        options = [
            discord.SelectOption(label="Purchase", description="Help with buying or payment"),
            discord.SelectOption(label="Bug Report", description="Report a bug or any issues"),
            discord.SelectOption(label="Question", description="Ask a question or get help"),
        ]
        super().__init__(placeholder="Choose your ticket type", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        ticket_type = self.values[0]
        username = interaction.user.name.lower().replace(" ", "-")
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        now = time.time()
        last_used = self.cooldowns.get(interaction.user.id)
        if last_used and now - last_used < 3600:
            remaining = int((3600 - (now - last_used)) // 60)
            return await interaction.response.send_message(
                f"You can create another ticket in {remaining} minute(s).", ephemeral=True
            )

        existing = discord.utils.get(category.text_channels, name=f"ticket-{username}")
        if existing:
            return await interaction.response.send_message(
                f"You already have an open ticket: {existing.mention}", ephemeral=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,      
                embed_links=True       
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                manage_channels=True
            ),
        }
        support_role = guild.get_role(SUPPORT_ROLE_ID)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
            )

        channel = await guild.create_text_channel(
            name=f"ticket-{username}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}",
        )

        embed = Embed(
            title=f"{ticket_type} Ticket",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        msg = await channel.send(interaction.user.mention)
        await msg.delete()
        await channel.send(embed=embed, view=TicketControlView(interaction.user, ticket_type, channel))

        self.cooldowns[interaction.user.id] = now

        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}", ephemeral=True
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

# setup
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

# end
async def script_autocomplete(interaction: discord.Interaction, current: str):
    try:
        response = requests.get(loader_json, headers=headers_master_key)
        if response.status_code != 200:
            return []
        scripts_data = response.json().get("record", {})
        choices = []
        for key, script in scripts_data.items():
            label = script.get("name", key)
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=key))
        return choices[:25]
    except Exception:
        return []

@bot.tree.command(name="get-script", description="Get your Xecret Hub script")
@app_commands.describe(script="Choose your script")
@app_commands.autocomplete(script=script_autocomplete)  
async def get_script(interaction: discord.Interaction, script: str):
    params = {"discord_id": interaction.user.id}
    response = requests.get(url_project_users, headers=headers, params=params)
    if response.status_code != 200:
        await interaction.response.send_message("Failed to fetch your key.", ephemeral=True)
        return

    user_data = response.json().get("users", [])
    if not user_data:
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return

    user_key = user_data[0]["user_key"]

    script_response = requests.get(loader_json, headers=headers_master_key)
    scripts_data = script_response.json().get("record", {})
    script_info = scripts_data.get(script, {})

    script_name_embed = script_info.get("name", "Unknown Script")
    loader_embed = script_info.get("url", "")

    value_embed = (
        "```lua\n"
        f'script_key = "{user_key}"\n'
        f'loadstring(game:HttpGet("{loader_embed}"))()\n'
        "```"
    )

    embed = discord.Embed(
        title="Xecret Hub | Script Loader",
        url=loader_embed,
        color=discord.Color.blurple(),
    )
    embed.set_author(
        name=f"{interaction.user.display_name} has got the script",
        url=f"https://discord.com/users/{interaction.user.id}",
        icon_url=interaction.user.display_avatar.url,
    )
    embed.add_field(
        name=f"{script_name_embed} Script",
        value=value_embed,
        inline=False,
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_image(url=banner_gif)
    datatime_now = datetime.now().strftime("%d/%m/%Y at %I:%M %p")
    embed.set_footer(
        text=f"@Xecret Hub • {datatime_now}",
        icon_url=thumbnail_logo,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)



# end

# resethwid-cooldown
@bot.tree.command(name="resethwid-cooldown", description="Set HWID reset cooldown (e.g. 2d or 12h)")
@app_commands.describe(duration="Cooldown duration like '2d' or '12h'")
@is_support_or_admin()
async def resethwid_cooldown(interaction: discord.Interaction, duration: str):
    global hwid_reset_cooldown

    duration = duration.lower().strip()
    if duration.endswith("d"):
        try:
            days = int(duration[:-1])
            hwid_reset_cooldown = timedelta(days=days)
        except ValueError:
            await interaction.response.send_message("Invalid format. Use like '2d' or '12h'.", ephemeral=True)
            return
    elif duration.endswith("h"):
        try:
            hours = int(duration[:-1])
            hwid_reset_cooldown = timedelta(hours=hours)
        except ValueError:
            await interaction.response.send_message("Invalid format. Use like '2d' or '12h'.", ephemeral=True)
            return
    else:
        await interaction.response.send_message("Invalid format. Use like '2d' or '12h'.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"Cooldown updated to {hwid_reset_cooldown}.", ephemeral=True
    )

# end

# whitelist
@bot.tree.command(name="whitelist", description="Whitelist a user or adjust their days")
@app_commands.describe(
    member="The member to whitelist",
    days="Number of days to add/subtract (0 = lifetime)",
    note="Optional note for the whitelist (leave blank for none)"
)
@is_support_or_admin()
async def whitelist(interaction: discord.Interaction, member: discord.Member, days: int, note: str = ""):
    await interaction.response.defer(ephemeral=True)

    try:
        params = {"discord_id": str(member.id)}
        check_response = requests.get(url_project_users, headers=headers, params=params)

        if check_response.status_code != 200:
            return await interaction.followup.send(
                f"Failed to fetch user data for {member.display_name}.", ephemeral=True
            )

        data = check_response.json()
        users = data.get("users", [])

        if users:
            user_key = users[0].get("user_key")
            current_days = users[0].get("key_days", 0)
            new_days = current_days + days

            if new_days <= 0:
                delete_url = f"{url_project_users}?user_key={user_key}"
                del_response = requests.delete(delete_url, headers=headers)
                del_data = del_response.json()

                if not del_data.get("success"):
                    return await interaction.followup.send(
                        f"Failed to unwhitelist {member.display_name}: {del_data.get('message')}",
                        ephemeral=True
                    )

                buyer_role = interaction.guild.get_role(buyer_role_id)
                if buyer_role and buyer_role in member.roles:
                    await member.remove_roles(buyer_role, reason="Unwhitelisted")

                embed = discord.Embed(
                    title="Whitelist Status",
                    description=f"User: {member.mention}\nKey: ||{user_key}||\nReason: Days reduced to 0 → Unwhitelisted.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(text=f"User ID: {member.id}")
                target_channel = interaction.guild.get_channel(panel_channel_id)
                if target_channel:
                    await target_channel.send(embed=embed)

                return await interaction.followup.send(
                    f"{member.display_name} has been unwhitelisted due to 0 days remaining.",
                    ephemeral=True
                )

            delete_url = f"{url_project_users}?user_key={user_key}"
            del_response = requests.delete(delete_url, headers=headers)
            del_data = del_response.json()

            if not del_data.get("success"):
                return await interaction.followup.send(
                    f"Failed to update whitelist: could not delete old key for {member.display_name}.",
                    ephemeral=True
                )

            body = {"discord_id": str(member.id), "key_days": new_days, "note": note or 'None'}
            create_response = requests.post(url_project_users, headers=headers, json=body)
            create_data = create_response.json()

            if create_data.get("success"):
                user_key = create_data.get("user_key")
                buyer_role = interaction.guild.get_role(buyer_role_id)
                if buyer_role and buyer_role not in member.roles:
                    await member.add_roles(buyer_role, reason="Whitelisted user")

                embed = discord.Embed(
                    title="Whitelist Status",
                    description=f"User: {member.mention}\nKey: ||{user_key}||\nReason: Adjusted to {new_days} day(s).",
                    color=discord.Color.blurple(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(text=f"User ID: {member.id}")
                target_channel = interaction.guild.get_channel(panel_channel_id)
                if target_channel:
                    await target_channel.send(embed=embed)

                return await interaction.followup.send("Whitelist updated.", ephemeral=True)
            else:
                return await interaction.followup.send(
                    f"Failed to re-whitelist {member.display_name}: {create_data.get('message')}",
                    ephemeral=True
                )

        else:
            key_days = max(days, 0)
            body = {"discord_id": str(member.id), "key_days": key_days, "note": note or 'None'}
            create_response = requests.post(url_project_users, headers=headers, json=body)
            create_data = create_response.json()

            if create_data.get("success"):
                user_key = create_data.get("user_key")
                buyer_role = interaction.guild.get_role(buyer_role_id)
                if buyer_role and buyer_role not in member.roles:
                    await member.add_roles(buyer_role, reason="Whitelisted user")

                status_text = (
                    f"{member.display_name} is whitelisted **lifetime**!"
                    if days == 0 else
                    f"{member.display_name} is whitelisted for {days} day(s)!"
                )

                embed = discord.Embed(
                    title="Whitelist Status",
                    description=f"User: {member.mention}\nKey: ||{user_key}||\nReason: {status_text}",
                    color=discord.Color.blurple(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(text=f"User ID: {member.id}")
                target_channel = interaction.guild.get_channel(panel_channel_id)
                if target_channel:
                    await target_channel.send(embed=embed)

                return await interaction.followup.send("Whitelist created.", ephemeral=True)
            else:
                return await interaction.followup.send(
                    f"Failed to whitelist {member.display_name}: {create_data.get('message')}",
                    ephemeral=True
                )

    except Exception as e:
        return await interaction.followup.send(f"Unexpected error: {e}", ephemeral=True)

# end

# unwhitelist
@bot.tree.command(name="unwhitelist", description="Remove a user's whitelist key")
@app_commands.describe(member="The member to remove from whitelist")
@is_support_or_admin()
async def unwhitelist(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    try:
        params = {"discord_id": str(member.id)}
        response = requests.get(url_project_users, headers=headers, params=params)

        if response.status_code != 200:
            return await interaction.followup.send(
                f"Failed to fetch user data for {member.display_name}.", ephemeral=True
            )

        data = response.json()
        users = data.get("users")
        if not users:
            return await interaction.followup.send(
                f"No key found for {member.display_name}.", ephemeral=True
            )

        user_key = users[0].get("user_key")
        if not user_key:
            return await interaction.followup.send(
                f"No key found for {member.display_name}.", ephemeral=True
            )

        delete_url = f"{url_project_users}?user_key={user_key}"
        del_response = requests.delete(delete_url, headers=headers)
        del_data = del_response.json()

        if not del_data.get("success"):
            return await interaction.followup.send(
                f"Failed to unwhitelist {member.display_name}: {del_data.get('message')}",
                ephemeral=True
            )

        buyer_role = interaction.guild.get_role(buyer_role_id)
        if buyer_role and buyer_role in member.roles:
            await member.remove_roles(buyer_role, reason="Unwhitelisted")

        target_channel = interaction.guild.get_channel(panel_channel_id)
        if target_channel:
            embed = discord.Embed(
                title="Unwhitelist Status",
                description=f"User: {member.mention}\nKey: ||{user_key}||\nStatus: Key removed successfully.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"User ID: {member.id}")
            await target_channel.send(embed=embed)

        return await interaction.followup.send(
            f"{member.display_name} has been unwhitelisted.", ephemeral=True
        )

    except Exception as e:
        return await interaction.followup.send(f"Unexpected error: {e}", ephemeral=True)


# end

# resethwid
@bot.tree.command(name="resethwid", description="Reset a user's HWID")
@app_commands.describe(member="The member whose HWID will be reset")
@is_support_or_admin()
async def resethwid(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    params = {"discord_id": str(member.id)}
    response = await asyncio.to_thread(requests.get, url_project_users, headers=headers, params=params)

    if response.status_code != 200:
        await interaction.followup.send(f"Failed to fetch user data for {member.display_name}.", ephemeral=True)
        return

    data = response.json()
    users = data.get("users")
    if not users:
        await interaction.followup.send(f"No key found for {member.display_name}.", ephemeral=True)
        return

    user_key = users[0].get("user_key")
    if not user_key:
        await interaction.followup.send(f"No key found for {member.display_name}.", ephemeral=True)
        return

    body = {"user_key": user_key, "force": True}
    resethwid_response = await asyncio.to_thread(
        requests.post, url_resethwid_users, headers=headers, json=body
    )
    resethwid_data = resethwid_response.json()

    if not resethwid_data.get("success"):
        status_text = f"Failed to reset HWID: {resethwid_data.get('message')}"
    else:
        status_text = "HWID reset successfully!"

    await interaction.followup.send(
        f"{status_text} for {member.display_name}.", ephemeral=True
    )

    target_channel = interaction.guild.get_channel(panel_channel_id)
    if target_channel:
        embed = discord.Embed(
            title="HWID Reset Status",
            description=f"User: {member.mention}\nKey: ||{user_key}||\nStatus: {status_text}",
            color=discord.Color.green()
            if "successfully" in status_text.lower()
            else discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"User ID: {member.id}")
        await target_channel.send(embed=embed)


# end

# blacklist
@bot.tree.command(name="blacklist", description="Blacklist a user's key permanently or temporarily")
@app_commands.describe(
    member="The member to blacklist",
    reason="Reason for blacklisting",
    duration="Duration like '2d' or '12h'. Leave blank for permanent"
)
@is_support_or_admin()
async def blacklist(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
    duration: str = None
):
    await interaction.response.defer(ephemeral=True)

    try:
        params = {"discord_id": str(member.id)}
        response = requests.get(url_project_users, headers=headers, params=params)

        if response.status_code != 200:
            return await interaction.followup.send(
                f"Failed to fetch user data for {member.display_name}.", ephemeral=True
            )

        data = response.json()
        users = data.get("users")
        if not users:
            return await interaction.followup.send(
                f"No key found for {member.display_name}.", ephemeral=True
            )

        user_key = users[0].get("user_key")
        if not user_key:
            return await interaction.followup.send(
                f"No key found for {member.display_name}.", ephemeral=True
            )

        ban_expire = -1
        expire_text = "Permanent"

        if duration:
            duration = duration.lower().strip()
            now = datetime.now()

            if duration.endswith("d"):
                try:
                    days = int(duration[:-1])
                    expire_time = now + timedelta(days=days)
                    ban_expire = int(expire_time.timestamp())
                    expire_text = f"{days} day(s)"
                except ValueError:
                    return await interaction.followup.send(
                        "Invalid duration format. Use like '2d' or '12h'.", ephemeral=True
                    )

            elif duration.endswith("h"):
                try:
                    hours = int(duration[:-1])
                    expire_time = now + timedelta(hours=hours)
                    ban_expire = int(expire_time.timestamp())
                    expire_text = f"{hours} hour(s)"
                except ValueError:
                    return await interaction.followup.send(
                        "Invalid duration format. Use like '2d' or '12h'.", ephemeral=True
                    )
            else:
                return await interaction.followup.send(
                    "Invalid duration format. Use like '2d' or '12h'.", ephemeral=True
                )

        body = {"user_key": user_key, "ban_reason": reason, "ban_expire": ban_expire}
        blacklist_response = requests.post(
            f"https://api.luarmor.net/v3/projects/{project_id}/users/blacklist",
            headers=headers,
            json=body,
        )
        blacklist_data = blacklist_response.json()

        if not blacklist_data.get("success"):
            status_text = f"Failed to blacklist: {blacklist_data.get('message')}"
            await interaction.followup.send(status_text, ephemeral=True)
        else:
            status_text = "User successfully blacklisted!"
            await interaction.followup.send(
                f"{member.display_name} has been blacklisted {expire_text}.", ephemeral=True
            )

        target_channel = interaction.guild.get_channel(panel_channel_id)
        if target_channel:
            embed = discord.Embed(
                title="Blacklist Status",
                description=(
                    f"User: {member.mention}\n"
                    f"Key: ||{user_key}||\n"
                    f"Status: {status_text}\n"
                    f"Reason: {reason}\n"
                    f"Expire: {expire_text}"
                ),
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"User ID: {member.id}")
            await target_channel.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"Unexpected error: {e}", ephemeral=True)


# end

# unblacklist
@bot.tree.command(name="unblacklist", description="Remove a user from blacklist")
@app_commands.describe(member="The member to unblacklist")
@is_support_or_admin()
async def unblacklist(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)  

    params = {"discord_id": str(member.id)}
    response = await asyncio.to_thread(requests.get, url_project_users, headers=headers, params=params)

    if response.status_code != 200:
        await interaction.followup.send(
            f"Failed to fetch user data for {member.display_name}.", ephemeral=True
        )
        return

    data = response.json()
    users = data.get("users")
    if not users:
        await interaction.followup.send(
            f"No key found for {member.display_name}.", ephemeral=True
        )
        return

    user_info = users[0]
    user_key = user_info.get("user_key")
    unban_token = user_info.get("unban_token")

    if not unban_token:
        await interaction.followup.send(
            f"No unban token found for {member.display_name}. Cannot unblacklist.",
            ephemeral=True,
        )
        return

    unban_url = f"https://api.luarmor.net/v3/projects/{project_id}/users/unban?unban_token={unban_token}"

    unban_response = await asyncio.to_thread(requests.get, unban_url)
    if unban_response.status_code != 200:
        status_text = "Failed to unblacklist user via API."
        await interaction.followup.send(status_text, ephemeral=True)
    else:
        status_text = "User successfully unblacklisted!"
        await interaction.followup.send(
            f"{member.display_name} has been unblacklisted.", ephemeral=True
        )

    target_channel = interaction.guild.get_channel(panel_channel_id)
    if target_channel:
        embed = discord.Embed(
            title="Unblacklist Status",
            description=f"User: {member.mention}\nKey: ||{user_key}||\nStatus: {status_text}",
            color=discord.Color.green()
            if "successfully" in status_text.lower()
            else discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"User ID: {member.id}")
        await target_channel.send(embed=embed)


# end

# ban
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


# kick
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


# timeout
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


# send text
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


# end

# website
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


# end

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
    #
    await bot.process_commands(message)


# end

server_on()
bot.run(bot_token)
