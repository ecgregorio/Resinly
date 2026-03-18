import discord
import os
import genshin

import re
import html

from storage.storage import (
    load_subscriptions,
    save_subscriptions,
    decrypt_value,
    encrypt_value,
    build_genshin_client,
)

from app.bot_core import (
    bot
)

# prefix/slash commands

# consts
default_genshin_uid = os.getenv('GENSHIN_UID')

### --- Helpers --- ###
# parses tags sent by get_banner_details
def clean_banner_content(raw: str, limit: int = 1000) -> str:
    # decode escaped entities
    text = html.unescape(raw or "")
     # convert line-break tags into real newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # convert paragraph end tags into newlines
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    # convert color tags into bold text using capture group 1
    text = re.sub(r"<color.*?>(.*?)</color>", r"**\1**", text, flags=re.IGNORECASE | re.DOTALL)
    # strip any remaining tags
    text = re.sub(r"<[^>]+>","",text)
    # collapse excessive blank lines
    text = re.sub(r"\n{3,}","\n\n", text).strip()
    
    if len(text) > limit:
        text = text[:limit - 1].rstrip() + "..."
        
    return text or "No banner description available."

def pick_preferred_banner(banners):
    # prefer event banner
    for b in banners:
        if str(getattr(b, "date_range", "")).lower() != "permanent":
            return b
    
    # return standard if not available for some reason
    return banners[0]

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
    
    uid = state.get("uid")
    
    # require per-user setup for UID to avoid falling back to default credentials
    if not uid:
        await ctx.send("Invalid credentials. No UID found for your account. Use `/setup` to configure your UID and HoYoLab cookies.")
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
    
# show current banner in genshin
@bot.command()
async def banner(ctx):
    # use per-user credential flow just like in !resin
    data = load_subscriptions()
    user_id = str(ctx.author.id)
    state = data.get(user_id, {})
    
    if "ltuid_v2" not in state or "ltoken_v2" not in state:
        await ctx.send("No HoYoLab cookies found for your account. Use /setup first.")
        return
    
    try:
        # build genshin client
        user_ltuid = decrypt_value(state["ltuid_v2"])
        user_ltoken = decrypt_value(state["ltoken_v2"])
        client = build_genshin_client(user_ltuid, user_ltoken)
        
        # call await client.get_banner_details()
        banners = await client.get_banner_details(game=genshin.Game.GENSHIN)
        if not banners:
            await ctx.send("No banners found.")
            return
        
        # get banner info (1 for now)
        selected = pick_preferred_banner(banners)
        selected_title = getattr(selected, "title", "Unknown Banner")
        selected_type_name = getattr(selected, "banner_type_name", "Unknown Type")
        selected_content = clean_banner_content(getattr(selected, "content", ""))
        selected_date_range = getattr(selected, "date_range", "Unknown")
        r5_items = list(getattr(selected, "r5_up_items", []) or [])
        r4_items = list(getattr(selected, "r4_up_items", []) or [])
        
        main_embed = discord.Embed(
            title=f"{selected_title} ({selected_type_name})",
            description=selected_content,
            color=discord.Color.blue()
        )
        
        # send a discord embed with banner details (+ graphics)
        main_embed.add_field(name="Banner Duration", value=selected_date_range, inline=False)
        
        # feature 5s and 4s items
        if r5_items:
            r5_names = ", ".join([getattr(item, "name", "Unknown") for item in r5_items])
            main_embed.add_field(name="5★ Featured", value=r5_names, inline=False)
            first_r5_icon = getattr(r5_items[0], "icon", None)
            
            if first_r5_icon:
                main_embed.set_thumbnail(url=first_r5_icon)
            
        if r4_items:
            r4_names = ", ".join([getattr(item, "name", "Unknown") for item in r4_items])
            main_embed.add_field(name="4★ Featured", value=r4_names, inline=False)
        
        preview_embeds = []
        preview_items = [(item, True) for item in r5_items[:2]] + [(item, False) for item in r4_items[:2]]
        for item, is_r5 in preview_items:
            icon_url = getattr(item, "icon", None)
            if not icon_url:
                continue
            
            item_embed = discord.Embed(
                title=getattr(item, "name", "Unknown"),
                description=f"{getattr(item, 'type', 'Unknown')} • {getattr(item, 'element', 'N/A')}",
                color=discord.Color.gold() if is_r5 else discord.Color.blurple(),
            )
            item_embed.set_thumbnail(url=icon_url)
            preview_embeds.append(item_embed)
            
        await ctx.send(embeds=[main_embed] + preview_embeds[:4])
    except Exception as e:
        await ctx.send(f"Error fetching banner: {type(e).__name__}: {e}")