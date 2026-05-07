import os
import asyncio
import sqlite3
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ImportChatInviteRequest, SendReactionRequest
from telethon.tl.types import ReactionEmoji
from telethon.errors import FloodWaitError, InviteHashInvalidError, UserAlreadyParticipantError, SessionPasswordNeededError
import logging

# ================= CONFIGURATION =================
BOT_TOKEN = "8769298679:AAHo6uH38eUHn2qPuaZTnTvL6aq0ZDcQNGU"
API_ID = 33418562
API_HASH = "316b85e7eef2e2f1615dee2cdee68be5"
OWNER_ID = 5286579067
OWNER_USERNAME = "Villaiinnn"
BOT_NAME = "𝗠𝟮𝗠 𝗥𝗘𝗤𝗨𝗘𝗦𝗧 𝗕𝗢𝗧"
START_IMG = "https://files.catbox.moe/xhv0n1.jpg"

# Second owner
SECOND_OWNER_ID = 8154938365  # @ShurTiip ka user ID daal
SECOND_OWNER_USERNAME = "ShurTiip"
# =================================================

# Database
conn = sqlite3.connect("m2m_bot.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    session_string TEXT,
    first_name TEXT,
    is_active BOOLEAN DEFAULT 1
)''')

c.execute('''CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
)''')

c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
if SECOND_OWNER_ID:
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SECOND_OWNER_ID,))
conn.commit()

# Globals
is_processing = False
user_steps = {}
BOT_START_TIME = time.time()
bot = None

REACTION_EMOJIS = ["❤️", "👍", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🎉", "🤩", "😎", "💯", "⚡", "🏆"]

# ========== STYLISH FUNCTIONS ==========
def blockquote(text):
    return f"<blockquote>{text}</blockquote>"

def create_progress_bar(current, total, length=20):
    if total == 0:
        return "█░░░░░░░░░░░░░░░░░░░ 0%"
    percentage = current / total
    filled = int(length * percentage)
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {int(percentage * 100)}%"

# ========== DATABASE FUNCTIONS ==========
def is_admin(user_id):
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def is_owner(user_id):
    return user_id == OWNER_ID or (SECOND_OWNER_ID and user_id == SECOND_OWNER_ID)

def get_all_sessions():
    c.execute("SELECT id, phone, first_name, session_string FROM sessions WHERE is_active = 1")
    return c.fetchall()

def get_session_count():
    c.execute("SELECT COUNT(*) FROM sessions WHERE is_active = 1")
    return c.fetchone()[0]

# ========== TELEGRAM FUNCTIONS ==========
async def join_channel(client, channel_link):
    try:
        link = channel_link.strip()
        if '/+' in link:
            invite_hash = link.split('/+')[-1].split('?')[0]
            await client(ImportChatInviteRequest(invite_hash))
        elif '/joinchat/' in link:
            invite_hash = link.split('/joinchat/')[-1].split('?')[0]
            await client(ImportChatInviteRequest(invite_hash))
        else:
            username = link.split('/')[-1].split('?')[0]
            if username.startswith('@'):
                username = username[1:]
            await client.join_channel(username)
        return True, "✅ 𝗝𝗼𝗶𝗻𝗲𝗱"
    except FloodWaitError as e:
        return False, f"⏳ 𝗙𝗹𝗼𝗼𝗱 {e.seconds}s"
    except InviteHashInvalidError:
        return False, "❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗹𝗶𝗻𝗸"
    except UserAlreadyParticipantError:
        return False, "⚠️ 𝗔𝗹𝗿𝗲𝗮𝗱𝘆 𝗺𝗲𝗺𝗯𝗲𝗿"
    except Exception as e:
        return False, f"❌ {str(e)[:30]}"

async def leave_channel(client, channel_link):
    try:
        link = channel_link.strip()
        
        # First try to get entity
        if '/+' in link:
            invite_hash = link.split('/+')[-1].split('?')[0]
            # Try to get channel by invite hash
            try:
                # First join to get entity (temporary)
                await client(ImportChatInviteRequest(invite_hash))
                await asyncio.sleep(1)
            except:
                pass
            # Now get entity
            entity = await client.get_entity(link)
        elif '/joinchat/' in link:
            invite_hash = link.split('/joinchat/')[-1].split('?')[0]
            try:
                await client(ImportChatInviteRequest(invite_hash))
                await asyncio.sleep(1)
            except:
                pass
            entity = await client.get_entity(link)
        else:
            username = link.split('/')[-1].split('?')[0]
            if username.startswith('@'):
                username = username[1:]
            entity = await client.get_entity(username)
        
        await client.leave_chat(entity)
        return True, "👋 𝗟𝗲𝗳𝘁"
    except Exception as e:
        error_msg = str(e)
        if "Chat not found" in error_msg or "USERNAME_NOT_OCCUPIED" in error_msg:
            return False, "⚠️ 𝗖𝗵𝗮𝗻𝗻𝗲𝗹 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱"
        elif "not a member" in error_msg.lower():
            return True, "⚠️ 𝗔𝗹𝗿𝗲𝗮𝗱𝘆 𝗻𝗼𝘁 𝗮 𝗺𝗲𝗺𝗯𝗲𝗿"
        return False, f"❌ {error_msg[:30]}"

async def send_view(client, post_link):
    try:
        if '/c/' in post_link:
            parts = post_link.split('/c/')[1].split('/')
            channel_id = int(f"-100{parts[0]}")
            msg_id = int(parts[1])
        else:
            parts = post_link.split('/')
            msg_id = int(parts[-1])
            username = parts[-2]
            entity = await client.get_entity(username)
            channel_id = entity.id
        
        await client.send_read_acknowledge(channel_id, max_id=msg_id)
        return True, "👁️ 𝗩𝗶𝗲𝘄 𝘀𝗲𝗻𝘁"
    except Exception as e:
        return False, f"❌ {str(e)[:30]}"

async def send_reaction(client, post_link, emoji=None):
    try:
        if emoji is None:
            emoji = random.choice(REACTION_EMOJIS)
        
        if '/c/' in post_link:
            parts = post_link.split('/c/')[1].split('/')
            channel_id = int(f"-100{parts[0]}")
            msg_id = int(parts[1])
        else:
            parts = post_link.split('/')
            msg_id = int(parts[-1])
            username = parts[-2]
            entity = await client.get_entity(username)
            channel_id = entity.id
        
        await client(SendReactionRequest(
            peer=channel_id,
            msg_id=msg_id,
            reaction=[ReactionEmoji(emoticon=emoji)]
        ))
        return True, f"😊 {emoji}"
    except Exception as e:
        return False, f"❌ {str(e)[:30]}"

# ========== START COMMAND ==========
async def start_command(event):
    user = await event.get_sender()
    user_name = user.first_name if user.first_name else str(user.id)
    
    caption = f"""
<b>𝗣𝗢𝗪𝗘𝗥 𝗢𝗙 𝗩𝗜𝗟𝗟𝗔𝗜𝗡 𝗕𝗢𝗧</b>

<b>𝗠𝟮𝗠 𝗥𝗘𝗤𝗨𝗘𝗦𝗧 𝗕𝗢𝗧</b>
"""
    
    if is_owner(user.id):
        buttons = [
            [Button.inline("𝗔𝗗𝗠𝗜𝗡", data="admin_panel", style="primary"),
             Button.inline("𝗢𝗪𝗡𝗘𝗥", data="owner_panel", style="danger")],
            [Button.inline("𝗔𝗗𝗗 𝗜𝗗", data="add_session", style="success"),
             Button.inline("𝗧𝗔𝗥𝗚𝗘𝗧", data="target_menu", style="primary")]
        ]
    elif is_admin(user.id):
        buttons = [
            [Button.inline("𝗔𝗗𝗠𝗜𝗡", data="admin_panel", style="primary")],
            [Button.inline("𝗔𝗗𝗗 𝗜𝗗", data="add_session", style="success"),
             Button.inline("𝗧𝗔𝗥𝗚𝗘𝗧", data="target_menu", style="primary")]
        ]
    else:
        caption += f"\n<b>⚠️ 𝗧𝗵𝗶𝘀 𝗯𝗼𝘁 𝗶𝘀 𝗼𝗻𝗹𝘆 𝗳𝗼𝗿 𝗮𝗱𝗺𝗶𝗻𝘀</b>"
        buttons = [[Button.url("👑 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿", f"https://t.me/{OWNER_USERNAME}", style="primary")]]
    
    caption += f"\n\n<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>"
    
    await event.reply(file=START_IMG, message=caption, buttons=buttons, parse_mode='html')

# ========== TARGET MENU ==========
async def target_menu(event):
    if not is_admin(event.sender_id) and not is_owner(event.sender_id):
        await event.answer("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", alert=True)
        return
    
    msg = f"""
<b>🎯 𝗧𝗔𝗥𝗚𝗘𝗧 𝗠𝗘𝗡𝗨</b>

<b>𝗖𝗵𝗼𝗼𝘀𝗲 𝗮𝗻 𝗼𝗽𝘁𝗶𝗼𝗻:</b>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗔𝗗𝗗", data="target_join", style="success"),
         Button.inline("📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗥𝗘𝗠𝗢𝗩𝗘", data="target_leave", style="danger")],
        [Button.inline("😊 𝗥𝗘𝗔𝗖𝗧𝗜𝗢𝗡𝗦", data="target_reaction", style="primary"),
         Button.inline("👁️ 𝗩𝗜𝗘𝗪𝗦", data="target_views", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="back_to_start", style="primary")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

# ========== MEMBER ADDING (JOIN) ==========
async def target_join(event):
    if not is_admin(event.sender_id) and not is_owner(event.sender_id):
        await event.answer("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", alert=True)
        return
    
    user_id = event.sender_id
    user_steps[user_id] = {"step": "join_channel", "type": "join"}
    
    buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]]
    
    msg = f"""
<b>📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗔𝗗𝗗𝗜𝗡𝗚</b>

<b>𝗦𝘁𝗲𝗽 1:</b> 𝗦𝗲𝗻𝗱 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 𝗹𝗶𝗻𝗸

<code>https://t.me/username</code>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_join_channel(event, user_id, channel_link):
    if not (channel_link.startswith("https://t.me/") or channel_link.startswith("t.me/")):
        await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗹𝗶𝗻𝗸!", parse_mode='html')
        return
    
    user_steps[user_id]["channel"] = channel_link
    user_steps[user_id]["step"] = "join_count"
    
    total = get_session_count()
    
    msg = f"""
<b>📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗔𝗗𝗗𝗜𝗡𝗚</b>

<b>𝗦𝘁𝗲𝗽 2:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗻𝘂𝗺𝗯𝗲𝗿 𝗼𝗳 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀

📌 {channel_link}
👥 𝗧𝗼𝘁𝗮𝗹 𝗜𝗗𝘀: {total}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1", data="join_count_1", style="primary"), Button.inline("5", data="join_count_5", style="primary"), Button.inline("10", data="join_count_10", style="primary")],
        [Button.inline(f"𝗔𝗟𝗟 ({total})", data="join_count_all", style="success"), Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="join_count_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_join_count(event, user_id, count_str):
    if count_str == "all":
        count = get_session_count()
    else:
        try:
            count = int(count_str)
        except:
            await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗻𝘂𝗺𝗯𝗲𝗿!", parse_mode='html')
            return
    
    user_steps[user_id]["count"] = count
    user_steps[user_id]["step"] = "join_delay"
    
    msg = f"""
<b>📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗔𝗗𝗗𝗜𝗡𝗚</b>

<b>𝗦𝘁𝗲𝗽 3:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗱𝗲𝗹𝗮𝘆 𝗯𝗲𝘁𝘄𝗲𝗲𝗻 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {user_steps[user_id]['channel']}
🔢 𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝘀: {count}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1𝘀", data="join_delay_1", style="primary"), Button.inline("5𝘀", data="join_delay_5", style="primary"), Button.inline("10𝘀", data="join_delay_10", style="primary")],
        [Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="join_delay_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def start_join_requests(event, user_id, delay):
    global is_processing
    
    channel = user_steps[user_id]["channel"]
    count = user_steps[user_id]["count"]
    
    sessions = get_all_sessions()
    if not sessions:
        await event.reply("❌ 𝗡𝗼 𝗮𝗰𝘁𝗶𝘃𝗲 𝗜𝗗𝘀!", parse_mode='html')
        user_steps.pop(user_id, None)
        return
    
    is_processing = True
    del user_steps[user_id]
    
    sessions_to_use = sessions[:min(count, len(sessions))]
    
    msg = await event.reply(
        f"<b>🚀 𝗦𝗲𝗻𝗱𝗶𝗻𝗴 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀</b>\n📎 {channel}\n🎯 𝗧𝗮𝗿𝗴𝗲𝘁: {len(sessions_to_use)} 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀\n⏱ 𝗗𝗲𝗹𝗮𝘆: {delay}s\n\n{create_progress_bar(0, len(sessions_to_use))}",
        parse_mode='html'
    )
    
    total_sent = 0
    total_failed = 0
    
    for i, (sid, phone, name, session_string) in enumerate(sessions_to_use):
        if not is_processing:
            break
        
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                continue
            
            success, result = await join_channel(client, channel)
            if success:
                total_sent += 1
            else:
                total_failed += 1
            
            await client.disconnect()
            
            progress = create_progress_bar(i + 1, len(sessions_to_use))
            await msg.edit(
                f"<b>🚀 𝗦𝗲𝗻𝗱𝗶𝗻𝗴 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀</b>\n📎 {channel}\n\n{progress}\n\n✅ 𝗦𝗲𝗻𝘁: {total_sent} | ❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}",
                parse_mode='html'
            )
            
            if i + 1 < len(sessions_to_use):
                await asyncio.sleep(delay)
            
        except Exception as e:
            total_failed += 1
    
    await msg.edit(
        f"<b>🏁 𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝘀 𝗳𝗶𝗻𝗶𝘀𝗵𝗲𝗱!</b>\n\n✅ 𝗦𝗲𝗻𝘁: {total_sent}\n❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}\n📊 𝗧𝗼𝘁𝗮𝗹: {len(sessions_to_use)}",
        parse_mode='html'
    )
    
    buttons = [[Button.inline("🔙 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", data="target_menu", style="primary")]]
    await event.reply("✅ 𝗧𝗮𝘀𝗸 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱!", buttons=buttons, parse_mode='html')
    
    is_processing = False

# ========== MEMBER REMOVE (LEAVE) - FIXED ==========
async def target_leave(event):
    if not is_admin(event.sender_id) and not is_owner(event.sender_id):
        await event.answer("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", alert=True)
        return
    
    user_id = event.sender_id
    user_steps[user_id] = {"step": "leave_channel", "type": "leave"}
    
    buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]]
    
    msg = f"""
<b>📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗥𝗘𝗠𝗢𝗩𝗘</b>

<b>𝗦𝘁𝗲𝗽 1:</b> 𝗦𝗲𝗻𝗱 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 𝗹𝗶𝗻𝗸

<code>https://t.me/username</code>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_leave_channel(event, user_id, channel_link):
    if not (channel_link.startswith("https://t.me/") or channel_link.startswith("t.me/")):
        await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗹𝗶𝗻𝗸!", parse_mode='html')
        return
    
    user_steps[user_id]["channel"] = channel_link
    user_steps[user_id]["step"] = "leave_count"
    
    total = get_session_count()
    
    msg = f"""
<b>📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗥𝗘𝗠𝗢𝗩𝗘</b>

<b>𝗦𝘁𝗲𝗽 2:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗻𝘂𝗺𝗯𝗲𝗿 𝗼𝗳 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀

📌 {channel_link}
👥 𝗧𝗼𝘁𝗮𝗹 𝗜𝗗𝘀: {total}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1", data="leave_count_1", style="primary"), Button.inline("5", data="leave_count_5", style="primary"), Button.inline("10", data="leave_count_10", style="primary")],
        [Button.inline(f"𝗔𝗟𝗟 ({total})", data="leave_count_all", style="success"), Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="leave_count_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_leave_count(event, user_id, count_str):
    if count_str == "all":
        count = get_session_count()
    else:
        try:
            count = int(count_str)
        except:
            await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗻𝘂𝗺𝗯𝗲𝗿!", parse_mode='html')
            return
    
    user_steps[user_id]["count"] = count
    user_steps[user_id]["step"] = "leave_delay"
    
    msg = f"""
<b>📎 𝗠𝗘𝗠𝗕𝗘𝗥 𝗥𝗘𝗠𝗢𝗩𝗘</b>

<b>𝗦𝘁𝗲𝗽 3:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗱𝗲𝗹𝗮𝘆 𝗯𝗲𝘁𝘄𝗲𝗲𝗻 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {user_steps[user_id]['channel']}
🔢 𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝘀: {count}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1𝘀", data="leave_delay_1", style="primary"), Button.inline("5𝘀", data="leave_delay_5", style="primary"), Button.inline("10𝘀", data="leave_delay_10", style="primary")],
        [Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="leave_delay_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def start_leave_requests(event, user_id, delay):
    global is_processing
    
    channel = user_steps[user_id]["channel"]
    count = user_steps[user_id]["count"]
    
    sessions = get_all_sessions()
    if not sessions:
        await event.reply("❌ 𝗡𝗼 𝗮𝗰𝘁𝗶𝘃𝗲 𝗜𝗗𝘀!", parse_mode='html')
        user_steps.pop(user_id, None)
        return
    
    is_processing = True
    del user_steps[user_id]
    
    sessions_to_use = sessions[:min(count, len(sessions))]
    
    msg = await event.reply(
        f"<b>👋 𝗥𝗲𝗺𝗼𝘃𝗶𝗻𝗴 𝗺𝗲𝗺𝗯𝗲𝗿𝘀</b>\n📎 {channel}\n🎯 𝗧𝗮𝗿𝗴𝗲𝘁: {len(sessions_to_use)} 𝗿𝗲𝗾𝘂𝗲𝘀𝘁𝘀\n⏱ 𝗗𝗲𝗹𝗮𝘆: {delay}s\n\n{create_progress_bar(0, len(sessions_to_use))}",
        parse_mode='html'
    )
    
    total_left = 0
    total_failed = 0
    
    for i, (sid, phone, name, session_string) in enumerate(sessions_to_use):
        if not is_processing:
            break
        
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                continue
            
            success, result = await leave_channel(client, channel)
            if success:
                total_left += 1
            else:
                total_failed += 1
            
            await client.disconnect()
            
            progress = create_progress_bar(i + 1, len(sessions_to_use))
            await msg.edit(
                f"<b>👋 𝗥𝗲𝗺𝗼𝘃𝗶𝗻𝗴 𝗺𝗲𝗺𝗯𝗲𝗿𝘀</b>\n📎 {channel}\n\n{progress}\n\n✅ 𝗥𝗲𝗺𝗼𝘃𝗲𝗱: {total_left} | ❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}",
                parse_mode='html'
            )
            
            if i + 1 < len(sessions_to_use):
                await asyncio.sleep(delay)
            
        except Exception as e:
            total_failed += 1
    
    await msg.edit(
        f"<b>🏁 𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝘀 𝗳𝗶𝗻𝗶𝘀𝗵𝗲𝗱!</b>\n\n✅ 𝗥𝗲𝗺𝗼𝘃𝗲𝗱: {total_left}\n❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}\n📊 𝗧𝗼𝘁𝗮𝗹: {len(sessions_to_use)}",
        parse_mode='html'
    )
    
    buttons = [[Button.inline("🔙 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", data="target_menu", style="primary")]]
    await event.reply("✅ 𝗧𝗮𝘀𝗸 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱!", buttons=buttons, parse_mode='html')
    
    is_processing = False

# ========== REACTIONS ==========
async def target_reaction(event):
    if not is_admin(event.sender_id) and not is_owner(event.sender_id):
        await event.answer("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", alert=True)
        return
    
    user_id = event.sender_id
    user_steps[user_id] = {"step": "reaction_channel", "type": "reaction"}
    
    buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]]
    
    msg = f"""
<b>😊 𝗥𝗘𝗔𝗖𝗧𝗜𝗢𝗡𝗦</b>

<b>𝗦𝘁𝗲𝗽 1:</b> 𝗦𝗲𝗻𝗱 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 𝗹𝗶𝗻𝗸

<code>https://t.me/username</code>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_reaction_channel(event, user_id, channel_link):
    if not (channel_link.startswith("https://t.me/") or channel_link.startswith("t.me/")):
        await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗹𝗶𝗻𝗸!", parse_mode='html')
        return
    
    user_steps[user_id]["channel"] = channel_link
    user_steps[user_id]["step"] = "reaction_post"
    
    msg = f"""
<b>😊 𝗥𝗘𝗔𝗖𝗧𝗜𝗢𝗡𝗦</b>

<b>𝗦𝘁𝗲𝗽 2:</b> 𝗦𝗲𝗻𝗱 𝗽𝗼𝘀𝘁 𝗹𝗶𝗻𝗸

<code>https://t.me/username/123</code>

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {channel_link}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, parse_mode='html')

async def process_reaction_post(event, user_id, post_link):
    user_steps[user_id]["post"] = post_link
    user_steps[user_id]["step"] = "reaction_count"
    
    total = get_session_count()
    
    msg = f"""
<b>😊 𝗥𝗘𝗔𝗖𝗧𝗜𝗢𝗡𝗦</b>

<b>𝗦𝘁𝗲𝗽 3:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗻𝘂𝗺𝗯𝗲𝗿 𝗼𝗳 𝗿𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {user_steps[user_id]['channel']}
📌 𝗣𝗼𝘀𝘁: {post_link}
👥 𝗧𝗼𝘁𝗮𝗹 𝗜𝗗𝘀: {total}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1", data="reaction_count_1", style="primary"), Button.inline("5", data="reaction_count_5", style="primary"), Button.inline("10", data="reaction_count_10", style="primary")],
        [Button.inline(f"𝗔𝗟𝗟 ({total})", data="reaction_count_all", style="success"), Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="reaction_count_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_reaction_count(event, user_id, count_str):
    if count_str == "all":
        count = get_session_count()
    else:
        try:
            count = int(count_str)
        except:
            await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗻𝘂𝗺𝗯𝗲𝗿!", parse_mode='html')
            return
    
    user_steps[user_id]["count"] = count
    user_steps[user_id]["step"] = "reaction_delay"
    
    msg = f"""
<b>😊 𝗥𝗘𝗔𝗖𝗧𝗜𝗢𝗡𝗦</b>

<b>𝗦𝘁𝗲𝗽 4:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗱𝗲𝗹𝗮𝘆 𝗯𝗲𝘁𝘄𝗲𝗲𝗻 𝗿𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {user_steps[user_id]['channel']}
📌 𝗣𝗼𝘀𝘁: {user_steps[user_id]['post']}
🔢 𝗥𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀: {count}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1𝘀", data="reaction_delay_1", style="primary"), Button.inline("5𝘀", data="reaction_delay_5", style="primary"), Button.inline("10𝘀", data="reaction_delay_10", style="primary")],
        [Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="reaction_delay_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def start_reaction_sending(event, user_id, delay):
    global is_processing
    
    channel = user_steps[user_id]["channel"]
    post = user_steps[user_id]["post"]
    count = user_steps[user_id]["count"]
    
    sessions = get_all_sessions()
    if not sessions:
        await event.reply("❌ 𝗡𝗼 𝗮𝗰𝘁𝗶𝘃𝗲 𝗜𝗗𝘀!", parse_mode='html')
        user_steps.pop(user_id, None)
        return
    
    is_processing = True
    del user_steps[user_id]
    
    sessions_to_use = sessions[:min(count, len(sessions))]
    
    msg = await event.reply(
        f"<b>😊 𝗦𝗲𝗻𝗱𝗶𝗻𝗴 𝗿𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀</b>\n📎 {post}\n🎯 𝗧𝗮𝗿𝗴𝗲𝘁: {len(sessions_to_use)} 𝗿𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀\n⏱ 𝗗𝗲𝗹𝗮𝘆: {delay}s\n\n{create_progress_bar(0, len(sessions_to_use))}",
        parse_mode='html'
    )
    
    total_sent = 0
    total_failed = 0
    emoji_counts = {}
    
    for i, (sid, phone, name, session_string) in enumerate(sessions_to_use):
        if not is_processing:
            break
        
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                continue
            
            emoji = random.choice(REACTION_EMOJIS)
            success, result = await send_reaction(client, post, emoji)
            
            if success:
                total_sent += 1
                emoji_counts[emoji] = emoji_counts.get(emoji, 0) + 1
            else:
                total_failed += 1
            
            await client.disconnect()
            
            progress = create_progress_bar(i + 1, len(sessions_to_use))
            await msg.edit(
                f"<b>😊 𝗦𝗲𝗻𝗱𝗶𝗻𝗴 𝗿𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀</b>\n📎 {post}\n\n{progress}\n\n✅ 𝗦𝗲𝗻𝘁: {total_sent} | ❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}",
                parse_mode='html'
            )
            
            if i + 1 < len(sessions_to_use):
                await asyncio.sleep(delay)
            
        except Exception as e:
            total_failed += 1
    
    emoji_stats = "\n".join([f"• {e}: {c}" for e, c in sorted(emoji_counts.items(), key=lambda x: -x[1])[:5]])
    
    await msg.edit(
        f"<b>🏁 𝗥𝗲𝗮𝗰𝘁𝗶𝗼𝗻𝘀 𝗳𝗶𝗻𝗶𝘀𝗵𝗲𝗱!</b>\n\n✅ 𝗦𝗲𝗻𝘁: {total_sent}\n❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}\n📊 𝗧𝗼𝘁𝗮𝗹: {len(sessions_to_use)}\n\n<b>📊 𝗘𝗺𝗼𝗷𝗶 𝘀𝘁𝗮𝘁𝘀:</b>\n{emoji_stats}",
        parse_mode='html'
    )
    
    buttons = [[Button.inline("🔙 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", data="target_menu", style="primary")]]
    await event.reply("✅ 𝗧𝗮𝘀𝗸 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱!", buttons=buttons, parse_mode='html')
    
    is_processing = False

# ========== VIEWS ==========
async def target_views(event):
    if not is_admin(event.sender_id) and not is_owner(event.sender_id):
        await event.answer("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", alert=True)
        return
    
    user_id = event.sender_id
    user_steps[user_id] = {"step": "views_channel", "type": "views"}
    
    buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]]
    
    msg = f"""
<b>👁️ 𝗩𝗜𝗘𝗪𝗦</b>

<b>𝗦𝘁𝗲𝗽 1:</b> 𝗦𝗲𝗻𝗱 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 𝗹𝗶𝗻𝗸

<code>https://t.me/username</code>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_views_channel(event, user_id, channel_link):
    if not (channel_link.startswith("https://t.me/") or channel_link.startswith("t.me/")):
        await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗹𝗶𝗻𝗸!", parse_mode='html')
        return
    
    user_steps[user_id]["channel"] = channel_link
    user_steps[user_id]["step"] = "views_post"
    
    msg = f"""
<b>👁️ 𝗩𝗜𝗘𝗪𝗦</b>

<b>𝗦𝘁𝗲𝗽 2:</b> 𝗦𝗲𝗻𝗱 𝗽𝗼𝘀𝘁 𝗹𝗶𝗻𝗸

<code>https://t.me/username/123</code>

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {channel_link}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, parse_mode='html')

async def process_views_post(event, user_id, post_link):
    user_steps[user_id]["post"] = post_link
    user_steps[user_id]["step"] = "views_count"
    
    total = get_session_count()
    
    msg = f"""
<b>👁️ 𝗩𝗜𝗘𝗪𝗦</b>

<b>𝗦𝘁𝗲𝗽 3:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗻𝘂𝗺𝗯𝗲𝗿 𝗼𝗳 𝘃𝗶𝗲𝘄𝘀

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {user_steps[user_id]['channel']}
📌 𝗣𝗼𝘀𝘁: {post_link}
👥 𝗧𝗼𝘁𝗮𝗹 𝗜𝗗𝘀: {total}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1", data="views_count_1", style="primary"), Button.inline("5", data="views_count_5", style="primary"), Button.inline("10", data="views_count_10", style="primary")],
        [Button.inline(f"𝗔𝗟𝗟 ({total})", data="views_count_all", style="success"), Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="views_count_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def process_views_count(event, user_id, count_str):
    if count_str == "all":
        count = get_session_count()
    else:
        try:
            count = int(count_str)
        except:
            await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗻𝘂𝗺𝗯𝗲𝗿!", parse_mode='html')
            return
    
    user_steps[user_id]["count"] = count
    user_steps[user_id]["step"] = "views_delay"
    
    msg = f"""
<b>👁️ 𝗩𝗜𝗘𝗪𝗦</b>

<b>𝗦𝘁𝗲𝗽 4:</b> 𝗖𝗵𝗼𝗼𝘀𝗲 𝗱𝗲𝗹𝗮𝘆 𝗯𝗲𝘁𝘄𝗲𝗲𝗻 𝘃𝗶𝗲𝘄𝘀

📌 𝗖𝗵𝗮𝗻𝗻𝗲𝗹: {user_steps[user_id]['channel']}
📌 𝗣𝗼𝘀𝘁: {user_steps[user_id]['post']}
🔢 𝗩𝗶𝗲𝘄𝘀: {count}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    buttons = [
        [Button.inline("1𝘀", data="views_delay_1", style="primary"), Button.inline("5𝘀", data="views_delay_5", style="primary"), Button.inline("10𝘀", data="views_delay_10", style="primary")],
        [Button.inline("𝗖𝗨𝗦𝗧𝗢𝗠", data="views_delay_custom", style="primary")],
        [Button.inline("🔙 𝗕𝗔𝗖𝗞", data="target_menu", style="primary"), Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_target", style="danger")]
    ]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def start_views_sending(event, user_id, delay):
    global is_processing
    
    channel = user_steps[user_id]["channel"]
    post = user_steps[user_id]["post"]
    count = user_steps[user_id]["count"]
    
    sessions = get_all_sessions()
    if not sessions:
        await event.reply("❌ 𝗡𝗼 𝗮𝗰𝘁𝗶𝘃𝗲 𝗜𝗗𝘀!", parse_mode='html')
        user_steps.pop(user_id, None)
        return
    
    is_processing = True
    del user_steps[user_id]
    
    sessions_to_use = sessions[:min(count, len(sessions))]
    
    msg = await event.reply(
        f"<b>👁️ 𝗦𝗲𝗻𝗱𝗶𝗻𝗴 𝘃𝗶𝗲𝘄𝘀</b>\n📎 {post}\n🎯 𝗧𝗮𝗿𝗴𝗲𝘁: {len(sessions_to_use)} 𝘃𝗶𝗲𝘄𝘀\n⏱ 𝗗𝗲𝗹𝗮𝘆: {delay}s\n\n{create_progress_bar(0, len(sessions_to_use))}",
        parse_mode='html'
    )
    
    total_sent = 0
    total_failed = 0
    
    for i, (sid, phone, name, session_string) in enumerate(sessions_to_use):
        if not is_processing:
            break
        
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            if not await client.is_user_authorized():
                continue
            
            success, result = await send_view(client, post)
            if success:
                total_sent += 1
            else:
                total_failed += 1
            
            await client.disconnect()
            
            progress = create_progress_bar(i + 1, len(sessions_to_use))
            await msg.edit(
                f"<b>👁️ 𝗦𝗲𝗻𝗱𝗶𝗻𝗴 𝘃𝗶𝗲𝘄𝘀</b>\n📎 {post}\n\n{progress}\n\n✅ 𝗦𝗲𝗻𝘁: {total_sent} | ❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}",
                parse_mode='html'
            )
            
            if i + 1 < len(sessions_to_use):
                await asyncio.sleep(delay)
            
        except Exception as e:
            total_failed += 1
    
    await msg.edit(
        f"<b>🏁 𝗩𝗶𝗲𝘄𝘀 𝗳𝗶𝗻𝗶𝘀𝗵𝗲𝗱!</b>\n\n✅ 𝗦𝗲𝗻𝘁: {total_sent}\n❌ 𝗙𝗮𝗶𝗹𝗲𝗱: {total_failed}\n📊 𝗧𝗼𝘁𝗮𝗹: {len(sessions_to_use)}",
        parse_mode='html'
    )
    
    buttons = [[Button.inline("🔙 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", data="target_menu", style="primary")]]
    await event.reply("✅ 𝗧𝗮𝘀𝗸 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱!", buttons=buttons, parse_mode='html')
    
    is_processing = False

# ========== ADD SESSION ==========
async def add_session(event):
    if not is_admin(event.sender_id) and not is_owner(event.sender_id):
        await event.answer("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", alert=True)
        return
    
    user_id = event.sender_id
    user_steps[user_id] = {"step": "awaiting_phone"}
    
    buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_add", style="danger")]]
    
    msg = f"""
<b>📱 𝗔𝗗𝗗 𝗜𝗗</b>

<b>𝗘𝗻𝘁𝗲𝗿 𝗽𝗵𝗼𝗻𝗲 𝗻𝘂𝗺𝗯𝗲𝗿:</b>

<code>+1234567890</code>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def cancel_add(event):
    user_id = event.sender_id
    user_steps.pop(user_id, None)
    await event.reply("❌ 𝗖𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱!", parse_mode='html')
    await start_command(event)

async def process_phone(event, user_id, phone):
    user_steps[user_id] = {"step": "awaiting_otp", "temp_phone": phone}
    
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        user_steps[user_id]["temp_client"] = client
        
        buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_add", style="danger")]]
        
        msg = f"""
<b>📱 𝗢𝗧𝗣 𝘀𝗲𝗻𝘁 𝘁𝗼 {phone}</b>

𝗘𝗻𝘁𝗲𝗿 𝗰𝗼𝗱𝗲:
<code>1 2 3 4 5</code>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
        
        await event.reply(msg, buttons=buttons, parse_mode='html')
    except Exception as e:
        await event.reply(f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}", parse_mode='html')
        user_steps.pop(user_id, None)

async def process_otp(event, user_id, otp_input):
    otp = otp_input.replace(" ", "")
    if not otp.isdigit() or len(otp) not in [5, 6]:
        await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗰𝗼𝗱𝗲!", parse_mode='html')
        return
    
    client = user_steps[user_id].get("temp_client")
    phone = user_steps[user_id].get("temp_phone")
    
    try:
        await client.sign_in(phone, otp)
        session_string = client.session.save()
        me = await client.get_me()
        
        c.execute("INSERT OR REPLACE INTO sessions (phone, session_string, first_name, is_active) VALUES (?, ?, ?, 1)",
                  (phone, session_string, me.first_name))
        conn.commit()
        
        await client.disconnect()
        user_steps.pop(user_id, None)
        
        await event.reply(
            f"✅ 𝗜𝗗 𝗮𝗱𝗱𝗲𝗱!\n\n📱 <code>{phone}</code>\n👤 {me.first_name}",
            parse_mode='html'
        )
        await start_command(event)
        
    except SessionPasswordNeededError:
        user_steps[user_id]["step"] = "awaiting_2fa"
        buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_add", style="danger")]]
        
        msg = f"""
<b>🔐 𝟮𝗙𝗔 𝗲𝗻𝗮𝗯𝗹𝗲𝗱</b>

𝗘𝗻𝘁𝗲𝗿 𝗽𝗮𝘀𝘀𝘄𝗼𝗿𝗱:

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
        await event.reply(msg, buttons=buttons, parse_mode='html')
    except Exception as e:
        await event.reply(f"❌ 𝗘𝗿𝗿𝗼𝗿: {str(e)}", parse_mode='html')
        user_steps.pop(user_id, None)

async def process_2fa(event, user_id, password):
    client = user_steps[user_id].get("temp_client")
    phone = user_steps[user_id].get("temp_phone")
    
    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        me = await client.get_me()
        
        c.execute("INSERT OR REPLACE INTO sessions (phone, session_string, first_name, is_active) VALUES (?, ?, ?, 1)",
                  (phone, session_string, me.first_name))
        conn.commit()
        
        await client.disconnect()
        user_steps.pop(user_id, None)
        
        await event.reply(
            f"✅ 𝗜𝗗 𝗮𝗱𝗱𝗲𝗱!\n\n📱 <code>{phone}</code>\n👤 {me.first_name}",
            parse_mode='html'
        )
        await start_command(event)
    except Exception as e:
        await event.reply("❌ 𝗪𝗿𝗼𝗻𝗴 𝗽𝗮𝘀𝘀𝘄𝗼𝗿𝗱!", parse_mode='html')
        user_steps.pop(user_id, None)

# ========== ADMIN PANEL ==========
async def admin_panel(event):
    if not is_owner(event.sender_id) and not is_admin(event.sender_id):
        await event.answer("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", alert=True)
        return
    
    user_id = event.sender_id
    user_steps[user_id] = {"step": "awaiting_admin_id"}
    
    buttons = [[Button.inline("❌ 𝗖𝗔𝗡𝗖𝗘𝗟", data="cancel_admin", style="danger")]]
    
    msg = f"""
<b>👑 𝗔𝗗𝗠𝗜𝗡 𝗣𝗔𝗡𝗘𝗟</b>

<b>𝗘𝗻𝘁𝗲𝗿 𝘂𝘀𝗲𝗿 𝗶𝗱 𝘁𝗼 𝗮𝗱𝗱 𝗮𝘀 𝗮𝗱𝗺𝗶𝗻:</b>

<code>123456789</code>

<i>⚠️ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗮𝗱𝗱 𝗮𝗱𝗺𝗶𝗻𝘀</i>

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

async def cancel_admin(event):
    user_id = event.sender_id
    user_steps.pop(user_id, None)
    await event.reply("❌ 𝗖𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱!", parse_mode='html')
    await start_command(event)

async def process_admin_add(event, user_id, admin_id_str):
    if not is_owner(event.sender_id):
        await event.reply("❌ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿 𝗰𝗮𝗻 𝗮𝗱𝗱 𝗮𝗱𝗺𝗶𝗻𝘀!", parse_mode='html')
        return
    
    try:
        admin_id = int(admin_id_str)
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
        conn.commit()
        user_steps.pop(user_id, None)
        await event.reply(f"✅ 𝗔𝗱𝗺𝗶𝗻 {admin_id} 𝗮𝗱𝗱𝗲𝗱!", parse_mode='html')
        await start_command(event)
    except ValueError:
        await event.reply("❌ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗶𝗱!", parse_mode='html')

# ========== OWNER PANEL ==========
async def owner_panel(event):
    if not is_owner(event.sender_id):
        await event.answer("❌ 𝗢𝗻𝗹𝘆 𝗼𝘄𝗻𝗲𝗿!", alert=True)
        return
    
    c.execute("SELECT user_id FROM admins")
    admins = [row[0] for row in c.fetchall()]
    
    msg = f"""
<b>⚡ 𝗢𝗪𝗡𝗘𝗥 𝗣𝗔𝗡𝗘𝗟</b>

<b>👑 𝗢𝘄𝗻𝗲𝗿𝘀:</b>
• @{OWNER_USERNAME}
• @{SECOND_OWNER_USERNAME}

<b>👥 𝗔𝗱𝗺𝗶𝗻𝘀:</b> {len(admins)}

<b>𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗢𝘄𝗻𝗲𝗿:- @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}</b>
"""
    buttons = [[Button.inline("🔙 𝗕𝗔𝗖𝗞", data="back_to_start", style="primary")]]
    
    await event.reply(msg, buttons=buttons, parse_mode='html')

# ========== CANCEL TARGET ==========
async def cancel_target(event):
    user_id = event.sender_id
    user_steps.pop(user_id, None)
    await event.reply("❌ 𝗖𝗮𝗻𝗰𝗲𝗹𝗹𝗲𝗱!", parse_mode='html')
    await start_command(event)

# ========== BACK TO START ==========
async def back_to_start(event):
    await start_command(event)

# ========== CUSTOM DELAY/CALLBACK HANDLERS ==========
async def custom_count_callback(event, task_type, count_type):
    user_id = event.sender_id
    if user_id not in user_steps:
        return
    
    step_map = {
        "join_count": "join_count",
        "leave_count": "leave_count",
        "reaction_count": "reaction_count",
        "views_count": "views_count"
    }
    
    user_steps[user_id]["step"] = step_map.get(count_type, "join_count")
    await event.reply("🔢 𝗘𝗻𝘁𝗲𝗿 𝗰𝘂𝘀𝘁𝗼𝗺 𝗻𝘂𝗺𝗯𝗲𝗿:\n\n<code>25</code>", parse_mode='html')

async def custom_delay_callback(event, task_type):
    user_id = event.sender_id
    if user_id not in user_steps:
        return
    
    user_steps[user_id]["step"] = f"{task_type}_delay"
    await event.reply("⏱ 𝗘𝗻𝘁𝗲𝗿 𝗰𝘂𝘀𝘁𝗼𝗺 𝗱𝗲𝗹𝗮𝘆 (𝘀𝗲𝗰𝗼𝗻𝗱𝘀):\n\n<code>3</code>", parse_mode='html')

# ========== MESSAGE HANDLER ==========
@events.register(events.NewMessage)
async def message_handler(event):
    if not event.message.text:
        return
    
    text = event.message.text.strip()
    user_id = event.sender_id
    
    if not is_admin(user_id) and not text.startswith('/start'):
        await event.reply("❌ 𝗨𝗻𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱!", parse_mode='html')
        return
    
    if user_id in user_steps:
        step = user_steps[user_id].get("step")
        
        if step == "awaiting_phone":
            await process_phone(event, user_id, text)
        elif step == "awaiting_otp":
            await process_otp(event, user_id, text)
        elif step == "awaiting_2fa":
            await process_2fa(event, user_id, text)
        elif step == "awaiting_admin_id":
            await process_admin_add(event, user_id, text)
        elif step == "join_channel":
            await process_join_channel(event, user_id, text)
        elif step == "join_count":
            await process_join_count(event, user_id, text)
        elif step == "join_delay":
            await start_join_requests(event, user_id, int(text))
        elif step == "leave_channel":
            await process_leave_channel(event, user_id, text)
        elif step == "leave_count":
            await process_leave_count(event, user_id, text)
        elif step == "leave_delay":
            await start_leave_requests(event, user_id, int(text))
        elif step == "reaction_channel":
            await process_reaction_channel(event, user_id, text)
        elif step == "reaction_post":
            await process_reaction_post(event, user_id, text)
        elif step == "reaction_count":
            await process_reaction_count(event, user_id, text)
        elif step == "reaction_delay":
            await start_reaction_sending(event, user_id, int(text))
        elif step == "views_channel":
            await process_views_channel(event, user_id, text)
        elif step == "views_post":
            await process_views_post(event, user_id, text)
        elif step == "views_count":
            await process_views_count(event, user_id, text)
        elif step == "views_delay":
            await start_views_sending(event, user_id, int(text))
        return
    
    if text.startswith('/start'):
        await start_command(event)

# ========== CALLBACK HANDLER ==========
@events.register(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode()
    user_id = event.sender_id
    
    # Main buttons
    if data == "admin_panel":
        await admin_panel(event)
    elif data == "cancel_admin":
        await cancel_admin(event)
    elif data == "owner_panel":
        await owner_panel(event)
    elif data == "add_session":
        await add_session(event)
    elif data == "cancel_add":
        await cancel_add(event)
    elif data == "target_menu":
        await target_menu(event)
    elif data == "cancel_target":
        await cancel_target(event)
    elif data == "back_to_start":
        await back_to_start(event)
    
    # Target options
    elif data == "target_join":
        await target_join(event)
    elif data == "target_leave":
        await target_leave(event)
    elif data == "target_reaction":
        await target_reaction(event)
    elif data == "target_views":
        await target_views(event)
    
    # Join count buttons
    elif data == "join_count_1":
        await process_join_count(event, user_id, "1")
    elif data == "join_count_5":
        await process_join_count(event, user_id, "5")
    elif data == "join_count_10":
        await process_join_count(event, user_id, "10")
    elif data == "join_count_all":
        await process_join_count(event, user_id, "all")
    elif data == "join_count_custom":
        await custom_count_callback(event, "join", "join_count")
    
    # Join delay buttons
    elif data == "join_delay_1":
        await start_join_requests(event, user_id, 1)
    elif data == "join_delay_5":
        await start_join_requests(event, user_id, 5)
    elif data == "join_delay_10":
        await start_join_requests(event, user_id, 10)
    elif data == "join_delay_custom":
        await custom_delay_callback(event, "join")
    
    # Leave count buttons
    elif data == "leave_count_1":
        await process_leave_count(event, user_id, "1")
    elif data == "leave_count_5":
        await process_leave_count(event, user_id, "5")
    elif data == "leave_count_10":
        await process_leave_count(event, user_id, "10")
    elif data == "leave_count_all":
        await process_leave_count(event, user_id, "all")
    elif data == "leave_count_custom":
        await custom_count_callback(event, "leave", "leave_count")
    
    # Leave delay buttons
    elif data == "leave_delay_1":
        await start_leave_requests(event, user_id, 1)
    elif data == "leave_delay_5":
        await start_leave_requests(event, user_id, 5)
    elif data == "leave_delay_10":
        await start_leave_requests(event, user_id, 10)
    elif data == "leave_delay_custom":
        await custom_delay_callback(event, "leave")
    
    # Reaction count buttons
    elif data == "reaction_count_1":
        await process_reaction_count(event, user_id, "1")
    elif data == "reaction_count_5":
        await process_reaction_count(event, user_id, "5")
    elif data == "reaction_count_10":
        await process_reaction_count(event, user_id, "10")
    elif data == "reaction_count_all":
        await process_reaction_count(event, user_id, "all")
    elif data == "reaction_count_custom":
        await custom_count_callback(event, "reaction", "reaction_count")
    
    # Reaction delay buttons
    elif data == "reaction_delay_1":
        await start_reaction_sending(event, user_id, 1)
    elif data == "reaction_delay_5":
        await start_reaction_sending(event, user_id, 5)
    elif data == "reaction_delay_10":
        await start_reaction_sending(event, user_id, 10)
    elif data == "reaction_delay_custom":
        await custom_delay_callback(event, "reaction")
    
    # Views count buttons
    elif data == "views_count_1":
        await process_views_count(event, user_id, "1")
    elif data == "views_count_5":
        await process_views_count(event, user_id, "5")
    elif data == "views_count_10":
        await process_views_count(event, user_id, "10")
    elif data == "views_count_all":
        await process_views_count(event, user_id, "all")
    elif data == "views_count_custom":
        await custom_count_callback(event, "views", "views_count")
    
    # Views delay buttons
    elif data == "views_delay_1":
        await start_views_sending(event, user_id, 1)
    elif data == "views_delay_5":
        await start_views_sending(event, user_id, 5)
    elif data == "views_delay_10":
        await start_views_sending(event, user_id, 10)
    elif data == "views_delay_custom":
        await custom_delay_callback(event, "views")

# ========== MAIN ==========
async def main():
    global bot
    bot = TelegramClient('M2MBot', API_ID, API_HASH)
    
    print(f"Starting {BOT_NAME}...")
    await bot.start(bot_token=BOT_TOKEN)
    print(f"✅ {BOT_NAME} Started!")
    
    bot.add_event_handler(message_handler)
    bot.add_event_handler(callback_handler)
    
    print(f"🤖 {BOT_NAME} IS READY!")
    print(f"👑 Owner: @{OWNER_USERNAME} | @{SECOND_OWNER_USERNAME}")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
