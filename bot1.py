# bot.py - نظام الفيديوهات الذكي المطور
# التحديث: نظام التعرف التلقائي على الفيديوهات المضافة للمجلد

try:
    import telethonpatch
except Exception:
    pass

import os
import json
import asyncio
import logging
import random
import time
import tempfile
import requests
from io import BytesIO
from datetime import datetime
import pytz
from typing import List, Optional, Dict, Union, Any, Tuple
from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import HideAllChatJoinRequestsRequest
from telethon.tl.types import UpdatePendingJoinRequests

# ---------------- logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

# ---------------- قراءة الإعدادات من البيئة ----------------
try:
    from config import API_ID, API_HASH, PHONE, PASSWORD, BOT_TOKEN, CHANNEL_IDENTIFIER, ADMIN_ID
except ImportError:
    API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "")
    PHONE = os.getenv("TELEGRAM_PHONE", "")
    PASSWORD = os.getenv("TELEGRAM_PASSWORD", "")
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHANNEL_IDENTIFIER = os.getenv("TELEGRAM_CHANNEL", "")
    ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0")) if os.getenv("TELEGRAM_ADMIN_ID") else 0

TIMEZONE = pytz.timezone('Africa/Cairo')

if not API_ID or not API_HASH:
    log.critical("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in environment.")
    raise SystemExit("Set TELEGRAM_API_ID and TELEGRAM_API_HASH first.")

if not PHONE:
    log.critical("Missing TELEGRAM_PHONE in environment.")
    raise SystemExit("Set TELEGRAM_PHONE first.")

# ---------------- resources & state ----------------
APPLE_GAME_PHOTOS = ["apple1.jpg", "apple2.jpg", "apple3.jpg"]

# ============ إعدادات نظام الفيديوهات الجديد ============
VIDEOS_DIR = "VIDEO"
VIDEO_EVERY_N_SIGNALS = 3  # فيديو كل 3 إشارات
VIDEO_CAPTION = None 

# ربط الأنماط بالفيديوهات (تلقائياً من أسماء الملفات)
def get_pattern_to_video_map() -> Dict[str, str]:
    mapping = {}
    if not os.path.exists(VIDEOS_DIR):
        try:
            os.makedirs(VIDEOS_DIR)
        except:
            return mapping
    for filename in os.listdir(VIDEOS_DIR):
        if filename.endswith(".mp4") and filename.startswith("{") and filename.endswith("}.mp4"):
            # {9-0-8-2}.mp4 -> 9:0_8:2
            pattern_str = filename[1:-5] 
            parts = pattern_str.split('-')
            formatted_parts = []
            for i in range(0, len(parts), 2):
                if i+1 < len(parts):
                    formatted_parts.append(f"{parts[i]}:{parts[i+1]}")
            pattern_id = "_".join(formatted_parts)
            mapping[pattern_id] = filename
    return mapping

STATE_FILE = "state.json"
last_used_patterns = []
video_counter = 0
last_apple_info = None

REGISTRATION_LINK = "https://redirspinner.com/2CFD?p=%2Fregistration%2F"
CONTACT_USERNAME = "@elharam110"
TUTORIAL_LINK = "https://t.me/c/3296506024/4287"

# ---------------- الرسائل ----------------
GAME_INTRO_TEXT = "🚨🚨 انتظر إشارة جديدة..."
GAME_CONGRATS_TEXT = "🎉 مبروك لكل من شارك وفاز معنا! انتظرونا في الإشارة القادمة..."

# ---------------- clients and state ----------------
SESSION_USER = f"session_user_{PHONE.replace('+','').replace(' ','')}" if PHONE else "session_user"
user_client = TelegramClient(SESSION_USER, API_ID, API_HASH)
bot_client = TelegramClient("session_bot", API_ID, API_HASH) if BOT_TOKEN else None
bot_started = False
user_target_channel = None

users_welcomed = set()
users_sent = set()
users_final_replied = set()
users_join_time: Dict[int, float] = {}
users_registered = set()
_user_locks: Dict[int, asyncio.Lock] = {}
_join_handler_lock = asyncio.Lock()
_is_processing_join_event = False

# ============ دوال نظام الفيديوهات الجديدة ============

def create_pattern_id(pattern: Dict[int, int]) -> str:
    sorted_rows = sorted(pattern.keys(), reverse=True)
    parts = [f"{row}:{pattern[row]}" for row in sorted_rows]
    return "_".join(parts)

def select_smart_pattern() -> Dict[int, int]:
    global last_used_patterns
    # يتم تحديث الخريطة في كل مرة لاكتشاف الملفات الجديدة فوراً
    mapping = get_pattern_to_video_map()
    all_p = []
    for pattern_id in mapping.keys():
        p_dict = {}
        parts = pattern_id.split('_')
        for part in parts:
            row_col = part.split(':')
            if len(row_col) == 2:
                p_dict[int(row_col[0])] = int(row_col[1])
        all_p.append(p_dict)
    
    if not all_p:
        log.warning("⚠️ No patterns with videos found in VIDEO folder!")
        return {9: random.randint(0, 4)}
    
    unused = [p for p in all_p if create_pattern_id(p) not in last_used_patterns[-5:]]
    selected = random.choice(unused if unused else all_p)
    
    pattern_id = create_pattern_id(selected)
    last_used_patterns.append(pattern_id)
    if len(last_used_patterns) > 10:
        last_used_patterns.pop(0)
    
    return selected

async def generate_apple_game_with_video_support() -> Tuple[str, Dict]:
    global last_apple_info
    rows, columns = 10, 5
    base_grid = [["🟫" for _ in range(columns)] for _ in range(rows)]
    
    selected_pattern = select_smart_pattern()
    for row, col in selected_pattern.items():
        base_grid[row][col] = "🍎"
    
    pattern_id = create_pattern_id(selected_pattern)
    last_apple_info = {
        "pattern": selected_pattern,
        "pattern_id": pattern_id
    }
    
    grid_text = "\n".join("".join(row) for row in base_grid)
    game_text = f"✅ اشاره جديده ✅\nالاشاره لمده ٥ دقائق ⏰\n🍏 Apple oF Fortune 🍏\n\n{grid_text}\n\n‼️الاشاره تعمل فقط لمن استعمل الرمز الترويجي BB33 عن التسجيل بحساب جديد\n‼️اقل ايداع عشان الإشارات تشتغل معاك هو  195 جنيه و في حاله الايداع بمبلغ اقل من 195 هتخسر للاسف\nرابط التسجيل : 🔥🔥 {REGISTRATION_LINK}\n\nلو عندك مشكلة او استفسارات تواصل مع : {CONTACT_USERNAME}"
    
    return game_text, last_apple_info

async def send_video_if_needed(apple_info: Dict):
    global video_counter
    video_counter += 1
    save_state()
    
    if video_counter % VIDEO_EVERY_N_SIGNALS == 0:
        # تحديث الخريطة لاكتشاف أي فيديوهات مضافة حديثاً
        mapping = get_pattern_to_video_map()
        pattern_id = apple_info["pattern_id"]
        if pattern_id in mapping:
            video_file = mapping[pattern_id]
            video_path = os.path.join(VIDEOS_DIR, video_file)
            if os.path.exists(video_path):
                log.info(f"📹 Processing video note for pattern: {pattern_id}")
                output_path = f"temp_round_{pattern_id}.mp4"
                try:
                    process = await asyncio.create_subprocess_exec(
                        'ffmpeg', '-y', '-i', video_path,
                        '-vf', "crop='min(iw,ih):min(iw,ih)',scale=400:400",
                        '-an', 
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                        output_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await process.communicate()
                    
                    if os.path.exists(output_path):
                        log.info(f"✅ Video converted and sent: {output_path}")
                        await user_client.send_file(
                            user_target_channel,
                            output_path,
                            video_note=True,
                            caption=None
                        )
                        os.remove(output_path)
                except Exception as e:
                    log.error(f"❌ Error in ffmpeg/sending: {e}")

def load_state():
    global users_welcomed, users_sent, users_final_replied, users_join_time, users_registered
    global video_counter, last_used_patterns
    try:
        if os.path.isfile(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            users_welcomed = set(state.get("users_welcomed", []))
            users_sent = set(state.get("users_sent", []))
            users_final_replied = set(state.get("users_final_replied", []))
            users_join_time = {int(k): float(v) for k, v in state.get("users_join_time", {}).items()}
            users_registered = set(state.get("users_registered", []))
            video_counter = state.get("video_counter", 0)
            last_used_patterns = state.get("last_used_patterns", [])
    except:
        pass

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "users_welcomed": list(users_welcomed), 
                "users_sent": list(users_sent),
                "users_final_replied": list(users_final_replied),
                "users_join_time": {str(k): v for k, v in users_join_time.items()},
                "users_registered": list(users_registered),
                "video_counter": video_counter,
                "last_used_patterns": last_used_patterns
            }, f, ensure_ascii=False, indent=2)
    except:
        pass

def create_action_buttons():
    return [
        [Button.url("📝 التسجيل على البرنامج", REGISTRATION_LINK)],
        [Button.url("🎮 شرح طريقة المكسب", TUTORIAL_LINK)],
        [Button.url("💬 التواصل معي", f"https://t.me/{CONTACT_USERNAME.replace('@', '')}")]
    ]

async def send_text_safe(sender, peer, text):
    try:
        await sender.send_message(peer, text)
        return True
    except:
        return False

# ---------------- Channel Posting Logic ----------------
async def apple_game_loop():
    log.info("🚀 Apple game loop started!")
    while True:
        try:
            await send_text_safe(user_client, user_target_channel, GAME_INTRO_TEXT)
            await asyncio.sleep(300)

            game_text, apple_info = await generate_apple_game_with_video_support()
            await user_client.send_message(user_target_channel, game_text, buttons=create_action_buttons())
            
            await send_video_if_needed(apple_info)
            await asyncio.sleep(300)

            await send_text_safe(user_client, user_target_channel, GAME_CONGRATS_TEXT)
            await asyncio.sleep(300)
        except Exception as e:
            log.error(f"Error in loop: {e}")
            await asyncio.sleep(30)

@user_client.on(events.Raw(UpdatePendingJoinRequests))
async def handler_join_requests(update):
    global _is_processing_join_event
    if _is_processing_join_event: return
    async with _join_handler_lock:
        _is_processing_join_event = True
        try:
            await user_client(HideAllChatJoinRequestsRequest(peer=update.peer, approved=True))
        finally:
            _is_processing_join_event = False

async def main():
    global user_target_channel
    load_state()
    await user_client.start(phone=PHONE, password=PASSWORD)
    user_target_channel = await user_client.get_entity(int(CHANNEL_IDENTIFIER) if CHANNEL_IDENTIFIER.replace('-','').isdigit() else CHANNEL_IDENTIFIER)
    asyncio.create_task(apple_game_loop())
    await user_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
