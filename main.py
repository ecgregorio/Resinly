import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os

from storage import (
    load_subscriptions,
    save_subscriptions,
    build_genshin_client,
    encrypt_value,
    decrypt_value,
)

# load .env file
load_dotenv()
token = os.getenv('DISCORD_TOKEN')
default_genshin_uid = os.getenv('GENSHIN_UID')
check_interval_seconds = int(os.getenv('CHECK_INTERVAL_SECONDS', '300')) # 2nd param is default

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()

# specify manual intents
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

### --- constant/helper functions --- ###
# helper function to check one user
async def check_one_user(discord_user_id: str, state: dict):
    # return if notifications off
    if not state.get("enabled", True):
        return
    
    # return if uid is Null
    uid = state.get("uid") or default_genshin_uid
    if not uid:
        return
    
    try:
        user_ltuid = decrypt_value(state["ltuid_v2"]) if "ltuid_v2" in state else None
        user_ltoken = decrypt_value(state["ltoken_v2"]) if "ltoken_v2" in state else None
        client = build_genshin_client(user_ltuid, user_ltoken)
        notes = await client.get_genshin_notes(int(uid))
    except Exception:
        return
    
    # fetch resin full status (bool)
    is_full = notes.current_resin >= notes.max_resin
    
    # notify user if their resin is full AND not yet notified
    if is_full and not state.get("notified_full", False):
        user = bot.get_user(int(discord_user_id)) or await bot.fetch_user(int(discord_user_id))
        if user:
            try:
                await user.send(f"Your resin is full ({notes.current_resin}/{notes.max_resin}) for UID `{uid}`.")
                state["notified_full"] = True
            except Exception:
                pass
    
    # update state
    if not is_full and state.get("notified_full", False):
        state["notified_full"] = False
    
### ---- Events ---- ###
@bot.event
async def on_ready():
    if bot.user is None: # guard check
        return
    print(f"We are ready to go in, {bot.user.name}")

    await bot.change_presence(status=discord.Status.idle, activity=discord.CustomActivity(name="/setup | !resin"))
    
    # sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Slash sync failed: {type(e).__name__}")
    
    if not resin_loop.is_running():
        resin_loop.start()

### --- Modal Form --- ###
class SetupModal(discord.ui.Modal, title="Resinly Setup"):
    uid = discord.ui.TextInput(
        label="Genshin UID", 
        placeholder="Your 9-digit in-game UID",
        required=True, 
        max_length=9,
    )
    ltuid = discord.ui.TextInput(
        label="ltuid_v2", required=True,
        placeholder="Copy from your HoYoLab browser cookies",
    )
    ltoken = discord.ui.TextInput(
        label="ltoken_v2", required=True,
        placeholder="Copy from your HoYoLab browser cookies",
        style=discord.TextStyle.paragraph, # make it so the text doesn't cut off (too long cant see)
    )
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        uid_value = str(self.uid).strip()
        # check if parameter values invalid
        if not uid_value.isdigit() or len(uid_value) != 9:
            await interaction.response.send_message(
                "UID must be exactly 9 digits.", ephemeral=True
            )
            return

        data = load_subscriptions()
        user_id = str(interaction.user.id)
        state = data.get(user_id, {})
        
        state["uid"] = uid_value
        state["ltuid_v2"] = encrypt_value(str(self.ltuid).strip())
        state["ltoken_v2"] = encrypt_value(str(self.ltoken).strip())
        state.setdefault("enabled", True)
        state.setdefault("notified_full", False)
        
        data[user_id] = state
        save_subscriptions(data)
        
        await interaction.response.send_message(
            "Setup saved securely. Notifications are enabled.",
            ephemeral=True,
        )

# help embed builder helper
def build_cookie_help_embed() -> discord.Embed:
    # create embed field
    embed = discord.Embed(
        title="How to find your HoYoLab cookies",
        description=(
            "You need two cookie values from your signed-in HoYoLab browser session: "
            "`ltuid_v2` and `ltoken_v2`"
        ),
        color=discord.Color.gold(),
    )
    
    # Chrome
    embed.add_field(
        name="Chrome / Edge",
        value=(
            "1. Sign in to HoYoLab in your browser. \n"
            "2. Open the HoYoLab site. \n"
            "3. Press `F12`. \n"
            "4. Open the `Application` tab (press `>>` or `+` if not seen). \n"
            "5. Open `Cookies` in the left sidebar. \n"
            "6. Select the HoYoLab site. \n"
            "7. Find `ltuid_v2` and `ltoken_v2` \n"
            "8. Copy their values into the setup form."
        ),
        inline=False,
    )
    
    # Firefox
    embed.add_field(
        name="Firefox",
        value=(
            "1. Sign in to HoYoLab in your browser. \n"
            "2. Press `F12`. \n"
            "3. Open the `Storage` tab. \n"
            "4. Open `Cookies` in the left sidebar. \n"
            "5. Select the HoYoLab site. \n"
            "6. Find `ltuid_v2` and `ltoken_v2` \n"
            "7. Copy their values into the setup form."
        ),
        inline=False,
    )
    
    # Safety
    embed.add_field(
        name="Safety",
        value=(
            "Treat these like passwords. Only submit them through Resinly's private setup flow. "
            "If you think they were exposed, log out of HoYoLab and sign back in."
        ),
        inline=False,
    )
     
    return embed

class SetupView(discord.ui.View):
    @discord.ui.button(label="Open Secure Setup Form", style=discord.ButtonStyle.primary)
    async def open_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SetupModal())
        
    @discord.ui.button(label="How to Find Cookies", style=discord.ButtonStyle.secondary)
    async def cookie_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=build_cookie_help_embed(),
            ephemeral=True,
        )
        
@bot.tree.command(name="setup", description="Securely set UID and HoYoLab cookies.")
async def setup(interaction: discord.Interaction):
    await interaction.response.send_message(
        (
            "You'll need your 9-digit Genshin UID and two HoYoLab cookies: "
            "`ltuid_v2` and `ltoken_v2`.\n\n"
            "These are used only to read your Genshin notes and are stored encrypted. "
            "Use the help button if you don't know where to find them."
        ),
        view=SetupView(),
        ephemeral=True,
    )

### --- Commands --- ###
# ping
@bot.command()
async def ping(ctx):
    await ctx.send("Pong")
    
# resin - check current resin + remaining time until full 
@bot.command()
async def resin(ctx):
    # get user data
    data = load_subscriptions()
    user_id = str(ctx.author.id)
    state = data.get(user_id, {})
    
    uid = state.get("uid") or default_genshin_uid
    
    # send message if uid not found/null
    if not uid:
        await ctx.send("No UID found. Use `!setuid` <your_uid> or set GENSHIN_UID in .env bru")
        return

    try:
        user_ltuid = decrypt_value(state["ltuid_v2"]) if "ltuid_v2" in state else None
        user_ltoken = decrypt_value(state["ltoken_v2"]) if "ltoken_v2" in state else None
        client = build_genshin_client(user_ltuid, user_ltoken)
        notes = await client.get_genshin_notes(int(uid))
    except Exception as e:
        await ctx.send(f"Could not fetch resin: {type(e).__name__}")
        return
    
    # success
    await ctx.send(
        f"UID `{uid}` | Resin: {notes.current_resin}/{notes.max_resin} | "
        f"Recovery: {notes.remaining_resin_recovery_time}"
    )

# setuid <uid>
@bot.command()
async def setuid(ctx, uid: str):
    # validate (digits only, len == 9)
    if not uid.isdigit() or len(uid) != 9:
        await ctx.send("UID must be a 9-digit number. Example: `!setuid 800123456`")
        return
    
    # save under current discord user
    data = load_subscriptions()
    user_id = str(ctx.author.id)
    
    state = data.get(user_id, {})
    state["uid"] = uid
    
    # give user notification status
    state.setdefault("enabled", True)
    state.setdefault("notified_full", False)
    
    data[user_id] = state
    save_subscriptions(data)
    
    # reply w confirmation
    await ctx.send(f"Saved UID `{uid}` for {ctx.author.mention}")

# myuid
@bot.command()
async def myuid(ctx):
    # read current user's saved UID
    data = load_subscriptions()
    user_id = str(ctx.author.id)
    uid = data.get(user_id, {}).get("uid")
    
    # reply with UID or "not set"
    if not uid: 
        await ctx.send("No UID saved yet. Use `!setuid <your_uid>`.")
        return
    
    await ctx.send(f"Your saved UID is `{uid}`")

# notify user
@bot.command()
async def notify(ctx, value: str):
    # check if value is valid
    normalized = value.strip().lower()
    if normalized not in {"on", "off"}:
        await ctx.send("Use `!notify on` or `!notify off`.")
        return

    # set user notification state
    data = load_subscriptions()
    user_id = str(ctx.author.id)
    state = data.get(user_id, {})
    state.setdefault("uid", default_genshin_uid)
    state["enabled"] = normalized == "on"
    data[user_id] = state
    save_subscriptions(data)
    
    await ctx.send(f"Resin notifications are now {normalized}.")
    
# set cookies (privately of course)
@bot.command()
async def setcookies(ctx, ltuid_v2: str, ltoken_v2: str):
    # DM ONLY - never accept in a public channel
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("For your security, please use this command in a DM with me")
        return
    
    # fetch user data
    data = load_subscriptions()
    user_id = str(ctx.author.id)
    state = data.get(user_id, {})
    
    state["ltuid_v2"] = encrypt_value(ltuid_v2)
    state["ltoken_v2"] = encrypt_value(ltoken_v2)
    state.setdefault("enabled", True)
    state.setdefault("notified_full", False)
    
    # save data
    data[user_id] = state
    save_subscriptions(data)
    await ctx.send("Cookies saved securely. Use `!setuid <uid> if you haven't already`")

# clear cookies
@bot.command()
async def clearcookies(ctx):
    data = load_subscriptions()
    user_id = str(ctx.author.id)
    state = data.get(user_id, {})
    state.pop("ltuid_v2", None)
    state.pop("ltoken_v2", None)
    data[user_id] = state
    save_subscriptions(data)
    await ctx.send("Your cookies have been removed.")

### ---- Tasks ---- ###
# background loop
@tasks.loop(seconds=check_interval_seconds)
async def resin_loop():
    data = load_subscriptions()
    if not data:
        return
    
    for discord_user_id, state in data.items():
        await check_one_user(discord_user_id, state)
        
    save_subscriptions(data)

@resin_loop.before_loop
async def before_resin_loop():
    await bot.wait_until_ready()

# token guard
if token is None:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

# authenticate and start the bot
bot.run(token, log_handler=handler, log_level=logging.INFO)