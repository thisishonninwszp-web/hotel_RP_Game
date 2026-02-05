# utils.py
#基础设施: 包含了所有 JSON 读写、数据验证、目录初始化函数。
#经营逻辑: 包含了 update_world_rating（评分计算）和 parse_stars。
#音频支持: 包含了 gTTS 语音播放功能。
#完整词库 (Database):
#World: 酒店名、类型、季节、入住率(Occupancy)、特殊状况(Condition)、天气。
#Guest: 名字、职业、性格、会员等级(VIP)、初始情绪(Mood)、预约渠道、日期背景、投诉类型。
#Staff: 男女名字、职位预设(Presets)。
#Context: 电话背景音、时间段。

# hotel_utils.py
# ==========================================
# 🏨 Hotel Tycoon Ultimate - Data & Utilities
# ==========================================
import json
import os
import re
import io
import random
import streamlit as st
from gtts import gTTS

# ==========================================
# ⚙️ 1. 全局配置与路径 (Configuration)
# ==========================================
# 1. 确定当前文件（hotel_utils.py）所在的绝对目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 锁定 data 文件夹的绝对路径
DATA_DIR = os.path.join(BASE_DIR, "data")

# 3. 基于 DATA_DIR 定义所有文件路径
CHARS_FILE = os.path.join(DATA_DIR, "characters.json")
STAFF_FILE = os.path.join(DATA_DIR, "staff.json")
WORLDS_FILE = os.path.join(DATA_DIR, "worlds.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

# 确保 data 目录一定存在（如果不存在则自动创建）
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


# ==========================================
# 🏨 2. 酒店与世界观参数 (World Params)
# ==========================================
HOTEL_NAMES = [
    "グランド・ミヤコ・京都", "ホテル・ルミナス東京", "旅館・山水", "ビジネス・イン・博多", 
    "リゾート・パラダイス沖縄", "スカイタワー大阪", "古都の宿・桜亭", "カプセルホテル・24",
    "ラブホテル・ピンクムーン", "民宿・おばあちゃん家", "星空グランピング・富士", "ホテル・ミラコスタ"
]

HOTEL_TYPES = [
    "高級旅館 (Ryokan)", "ビジネスホテル (Biz Hotel)", "リゾートホテル (Resort)", 
    "カプセルホテル (Capsule)", "民泊 (Airbnb)", "ラブホテル (Love Hotel)", "グランピング (Glamping)"
]

SEASONS = [
    "春の桜シーズン", "夏休み(繁忙期)", "紅葉シーズン", "冬の閑散期", "年末年始", "ゴールデンウィーク"
]

# [核心功能] 稼働率 (Occupancy)
OCCUPANCY_STATES = [
    "満室 (Fully Booked - No Room Change)", 
    "空室わずか (Almost Full - Hard to Change)", 
    "通常 (Normal)", 
    "ガラガラ (Empty - Upgrade Possible)"
]

# [核心功能] 特殊状况
SPECIAL_CONDITIONS = [
    "特になし (None)",
    "台風直撃 (Typhoon - Guests stuck inside)",
    "猛暑日 (Heatwave - AC complaints)",
    "大雪・交通麻痺 (Snowstorm - Staff late)",
    "近隣で花火大会 (Event - Noise/Crowd)",
    "館内停電トラブル (Blackout - Critical)",
    "インフルエンザ流行中 (Flu - Health risk)"
]

WEATHER_TYPES = [
    "晴天", "小雨", "土砂降り (Heavy Rain)", "強風", "大雪", "猛暑", "霧"
]

# ==========================================
# 👤 3. 顾客参数 (Guest Params)
# ==========================================
CHAR_NAMES = [
    "佐藤 健一", "鈴木 愛", "高橋 誠", "田中 美咲", "伊藤 翔太", "渡辺 裕子", "山本 大輔", "加藤 恵",
    "小林 剛", "松本 さくら", "井上 龍之介", "木村 拓也", "斎藤 飛鳥", "金子 賢", "John Smith", "李 偉"
]

CHAR_JOBS = [
    "弁護士", "医師", "経営者", "ITコンサルタント", "現場作業員", "教師", "YouTuber", "主婦", "公務員",
    "トラック運転手", "ホスト", "看護師", "退職者", "大学生", "投資家", "ヤクザ風の男", "芸能人"
]

PERSONALITY_TRAITS = [
    "威圧的 (Aggressive)", "神経質 (Nervous/Picky)", "優柔不断 (Indecisive)", 
    "早口 (Impatient)", "無気力 (Quiet/Low energy)", "論理的 (Logical/Cold)", 
    "感情的 (Emotional)", "丁寧すぎる (Passive Aggressive)", "フレンドリー (Too Friendly)"
]

# [核心] 初始情绪
INITIAL_MOODS = [
    "激怒 (Furious)", "イライラ (Irritated)", "泣きそう (Crying)", 
    "泥酔 (Drunk)", "冷淡 (Cold)", "困惑 (Confused)", "パニック (Panic)", "冷静 (Calm)"
]

# [核心] VIP等级
VIP_LEVELS = [
    "一般客 (Regular)", "常連客 (Regular)", "VIP会員 (Gold)", 
    "超VIP (Platinum)", "ブラックリスト (Blacklisted)"
]

BOOKING_CHANNELS = [
    "公式HP", "じゃらん", "楽天トラベル", "Booking.com", "Agoda", "電話予約", "飛び込み (Walk-in)", "招待客"
]

DATE_CONTEXTS = [
    "平日 (Weekday)", "土日祝 (Weekend)", 
    "クリスマス (Christmas)", "バレンタイン (Valentine)", 
    "年末年始 (New Year)", "お盆 (Obon)", "深夜 (Midnight)"
]

COMPLAINT_TYPES = [
    "客室の清掃不備 (髪の毛、シミ、虫)", "設備・備品の故障 (Wi-Fi、エアコン、お湯)", 
    "スタッフの態度 (タメ口、無視)", "騒音トラブル (隣人、工事音)", "会計・予約ミス (Overbooked)",
    "アメニティ不足", "食事の不満 (異物混入)", "怪奇現象 (Ghost?)", "他のお客様とのトラブル"
]

# ==========================================
# 🧑‍💼 4. 员工参数 (Staff Params)
# ==========================================
GENDERS = ["男性", "女性"]

STAFF_NAMES_MALE = [
    "佐藤 健", "鈴木 一郎", "高橋 龍", "田中 翔", "渡辺 裕太", 
    "伊藤 誠", "山本 大輔", "中村 賢", "小林 剛"
]
STAFF_NAMES_FEMALE = [
    "佐藤 花子", "鈴木 優子", "高橋 美咲", "田中 愛", "渡辺 奈々", 
    "伊藤 結衣", "山本 さくら", "中村 恵", "小林 葵"
]

STAFF_PRESETS = {
    "新人アルバイト": ["1週間", "1ヶ月", "3ヶ月"],
    "フロントスタッフ": ["1年", "3年", "5年"],
    "コンシェルジュ": ["5年", "10年", "15年"],
    "支配人": ["15年", "20年", "30年"],
    "清掃スタッフ": ["3日", "1年", "10年(ベテラン)"],
    "夜勤担当": ["半年", "2年"],
    "警備員": ["半年", "元警察官(20年)"]
}

# ==========================================
# 🌍 5. 环境噪音与时间 (Context Params)
# ==========================================
CALL_BACKGROUNDS = [
    "静かな部屋", "騒がしい居酒屋", "走行中の車内", "赤ちゃんの泣き声", "工事現場の近く", "駅のホーム", "暴風雨の音"
]

TIME_SETTINGS = [
    "早朝 (6:00)", "昼下がり (14:00)", "夕方 (18:00)", "深夜 (2:00)"
]

# ==========================================
# 📜 6. Prompt 基础设定
# ==========================================
REALISM_BLOCK = """
【PRIME DIRECTIVE: EXTREME REALISM】
1. You are NOT an AI. You are a human character in a roleplay.
2. DO NOT be polite unless your character is polite. If the character is angry, use aggressive language.
3. NEVER output action descriptions like (sigh) or *angry*. ONLY output the spoken dialogue.
4. Keep responses concise and conversational, like a real phone call.
5. LANGUAGE: ALL OUTPUT MUST BE IN JAPANESE (日本語).
"""

# ==========================================
# 🛠️ 7. 基础工具函数 (IO & Logic)
# ==========================================
def init_dirs():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

def clean_json_text(text):
    """清理 AI 输出的 JSON 文本，去除 Markdown 标记"""
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    text = text.strip()
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: return match.group(0)
    except: pass
    return text

def ensure_dict(data):
    """确保数据是字典格式"""
    if isinstance(data, list): return data[0] if len(data) > 0 else {}
    if isinstance(data, dict): return data
    return {}

def validate_data(data_list):
    """过滤无效数据"""
    valid_data = []
    for item in data_list:
        item = ensure_dict(item)
        if item.get("name"): valid_data.append(item)
    return valid_data

def load_json(filepath):
    """读取 JSON 文件"""
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            raw_list = [ensure_dict(item) for item in data] if isinstance(data, list) else []
            
            # ✨ 核心修复：如果是履历文件，跳过 validate_data 的 name 检查
            if "history.json" in filepath:
                return raw_list
            
            return validate_data(raw_list)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def save_json(filepath, data):
    """保存 JSON 文件"""
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path): os.makedirs(dir_path)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Save failed: {e}")

def add_to_library(filepath, new_item):
    """添加到库（去重）"""
    new_item = ensure_dict(new_item)
    if not new_item.get("name"): return
    data = load_json(filepath)
    data = [d for d in data if d.get("name") != new_item.get("name")]
    data.insert(0, new_item)
    save_json(filepath, data)

def delete_from_library(filepath, name_to_delete):
    """从库中删除"""
    data = load_json(filepath)
    new_data = [d for d in data if d.get("name") != name_to_delete]
    save_json(filepath, new_data)

def autoplay_audio(text):
    """TTS 播放"""
    try:
        clean_text = re.sub(r'^(客|スタッフ|店員|フロント|Guest|Staff)(:|：)', '', text).strip()
        clean_text = re.sub(r'（.*?）', '', clean_text)
        clean_text = re.sub(r'\(.*?\)', '', clean_text)
        if not clean_text: return
        
        tts = gTTS(text=clean_text, lang='ja')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        st.audio(fp, format='audio/mp3', autoplay=True)
    except Exception as e:
        print(f"TTS Error: {e}")

# ==========================================
# 📈 8. 经营核心算法 (Tycoon Rating)
# ==========================================
def parse_stars(star_text):
    """从 AI 文本中提取 1-5 星级"""
    if not star_text: return 3
    text_str = str(star_text)
    match = re.search(r'([1-5])\s*[/／stars★]', text_str, re.IGNORECASE)
    if match: return int(match.group(1))
    match_digit = re.search(r'\b([1-5])\b', text_str)
    if match_digit: return int(match_digit.group(1))
    star_count = text_str.count('★')
    if star_count > 0: return min(star_count, 5)
    return 3

def update_world_rating(world_name, new_guest_score):
    """更新酒店评分（加权平均）"""
    if not world_name: return 3.0, 3.0
    
    worlds = load_json(WORLDS_FILE)
    target_world = None
    target_index = -1
    
    for i, w in enumerate(worlds):
        if w['name'] == world_name:
            target_world = w
            target_index = i
            break
            
    if not target_world: return 3.0, 3.0
    
    if 'rating_count' not in target_world: target_world['rating_count'] = 10
    if 'current_rating' not in target_world:
        try:
            raw_stars = str(target_world.get('stars', '3.0'))
            clean_stars = re.search(r"(\d+(\.\d+)?)", raw_stars)
            val = float(clean_stars.group(1)) if clean_stars else 3.0
            target_world['current_rating'] = min(max(val, 1.0), 5.0)
        except:
            target_world['current_rating'] = 3.0

    old_rating = target_world['current_rating']
    count = target_world['rating_count']
    score = int(new_guest_score) if new_guest_score else 3
    
    new_rating = ((old_rating * count) + score) / (count + 1)
    new_rating = round(new_rating, 2)
    
    target_world['current_rating'] = new_rating
    target_world['rating_count'] += 1
    
    worlds[target_index] = target_world
    save_json(WORLDS_FILE, worlds)
    
    return old_rating, new_rating

# 9. 追加到play履历中

def add_to_history(entry):
    """
    将评估结果追加到历史记录文件中
    """
    try:
        # 1. 尝试读取现有记录
        data = load_json(HISTORY_FILE)
        if not isinstance(data, list):
            data = []
            
        # 2. 插入新记录到最前面 (最新的在最上面)
        data.insert(0, entry)
        
        # 3. 写入文件
        save_json(HISTORY_FILE, data)
        return True
    except Exception as e:
        print(f"Error saving history: {e}")
        return False
    
# 全局RP要求
def get_global_world_logic(world_name, world_type):
    """
    所有的 RP 行为都必须锚定在这个全局逻辑之上。
    """
    return f"""
【WORLD LOGIC & BOUNDARIES (MANDATORY)】
1. **Environment Grounding**: The current setting is "{world_name}" which is a "{world_type}".
2. **Economic Realism**: All character expectations and behaviors MUST align with the hotel's grade.
   - For Capsule/Biz Hotels: Focus on essential service, noise, and space. Luxury demands are strictly prohibited.
   - For Ryokan/Resort: High-end expectations for food and hospitality are standard.
3. **Common Sense**: Characters must not ignore the physical and social reality of the setting. 
4. **No AI Meta-talk**: Stay in character at all times. Do not mention you are an AI or a simulation.
"""