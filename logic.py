# logic.py

#✅ 功能与修复核对
#Bug 修复：
#✅ 参数缺失修复：generate_staff_profile 接收完整的 6 个参数。
#✅ KeyError 修复：evaluate_interaction 增加容错逻辑，防止评价系统崩溃。
#✅ AttributeError 修复：补全 get_staff_system_instruction 和 get_guest_system_instruction 函数。
#✅ JSON 解析增强：generate_guest_profile 使用 .get() 安全获取所有新参数（VIP、Mood等）。
#核心逻辑增强：
#✅ 愤怒系统 (Anger Meter)：AI 扮演客人时，根据愤怒值（0-100）动态切换敬语/粗口。
#✅ 规章预检查 (Rule Pre-check)：AI 扮演员工时，强制检查“稼働率”和“天气”，绝不答应违规要求（如台风天外出、满室换房）。
#✅ 观察者模式 (Observer)：新增 get_observer_system_instruction，让 AI 扮演“剧本导演”，自动推动剧情。
#内容增强：
#✅ 500字限制：所有生成函数（World/Guest/Staff）都强制要求 500 字以上的详细背景。
#✅ 新参数集成：VIP 等级、初始情绪、天气、入住率全部融入 Prompt。


# logic.py
import streamlit as st
import google.generativeai as genai
import json
import random
import os
import azure.cognitiveservices.speech as speechsdk
from hotel_utils import (
    clean_json_text, ensure_dict, REALISM_BLOCK, 
    STAFF_NAMES_MALE, STAFF_NAMES_FEMALE
)

# Default Model Configuration
MODEL_NAME = "gemini-2.0-flash"

def configure_genai(api_key):
    if api_key:
        genai.configure(api_key=api_key)

def get_model(system_instruction=None):
    if system_instruction:
        return genai.GenerativeModel(MODEL_NAME, system_instruction=system_instruction)
    return genai.GenerativeModel(MODEL_NAME)

# ==========================================
# 🎵 Azure 日本语声优库 (纯净版)
# ==========================================
# 建议放在 logic.py 文件的最顶部 (import 之后)
VOICE_OPTIONS = {
    "男性": [
        "ja-JP-KeitaNeural",   # 充满活力的青年 (适合暴躁/年轻客人)
        "ja-JP-DaichiNeural",  # 低沉稳重 (适合严肃VIP/大叔)
        "ja-JP-NaokiNeural"    # 温和中性 (适合普通客人)
    ],
    "女性": [
        "ja-JP-NanamiNeural",  # 清澈 (适合年轻女性)
        "ja-JP-AoiNeural",     # 知性 (适合成熟女性)
        "ja-JP-ShioriNeural"   # 可爱 (适合有点小脾气的)
    ]
}

# ==========================================
# 🌍 1. World Generation (世界观生成：难易度决定可用手段)
# ==========================================
# 👇 参数变化：occupancy -> policy
def generate_world_setting(name, htype, season, stars, fac, policy, condition, difficulty):
    prompt = f"""
    あなたは「高難易度ホテルのシミュレーションゲーム」のシナリオライターです。
    以下のパラメータに基づいて、ホテルの世界観と「プレイヤーが使える武器（補償手段）」を定義してください。
    
    【重要：JSONの値はすべて「日本語」で出力してください】

    【入力パラメータ】
    ホテル名: {name}
    タイプ: {htype}
    季節: {season}
    評価: {stars}
    設備: {fac}
    **経営方針**: {policy} (例：お客様第一、利益至上主義、老舗の伝統など)
    特殊状況: {condition}
    
    🔥 **難易度設定**: {difficulty}
    この難易度は「トラブル解決のために、スタッフがどこまでリソースを使っていいか」を決定します。
    
    - **Easy**: 予算潤沢。クーポン配布、部屋のアップグレード、無料ドリンク提供など、金銭的解決が可能。
    - **Normal**: 常識の範囲内。上司の許可があればクーポン等は出せる。
    - **Hard**: 予算削減中。金銭的解決（クーポン・返金）は原則禁止。誠意ある謝罪のみで解決しなければならない。
    - **Hell**: 理不尽な経営。返金不可なのはもちろん、「客に損害賠償を請求しろ」等、火に油を注ぐ対応を強要される。
    
    【出力要件】
    1. **allowed_compensations**: この難易度で使用可能な具体的な解決手段リスト（日本語）。
       (例: ["ドリンク券配布", "部屋交換"] または ["ひたすら謝罪", "警察を呼ぶ"] )
    2. **constraints**: 経営方針と難易度に基づいた、接客ルール。
    3. **background_story**: 上記の状況を反映したドラマチックな背景ストーリー (500文字以上)。
    
    出力JSON形式:
    {{
        "name": "{name}",
        "type": "{htype}",
        "policy": "{policy}",  // 旧 occupancy の代わり
        "allowed_compensations": "使用可能な手段リスト (日本語)",
        "constraints": "接客ルール (日本語)",
        "background_story": "詳細なストーリー (日本語 500文字以上)..."
    }}
    """
    try:
        model = get_model()
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return ensure_dict(json.loads(clean_json_text(resp.text)))
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 👤 2. Guest Generation (顾客生成 - 含声线分配)
# ==========================================
def generate_guest_profile(params):
    # 1. 安全地提取 app.py 传来的参数
    name = params.get('name', 'Unknown')
    target_gender = params.get('gender', 'Random') # ✅ 提取性别参数
    
    job = params.get('job', 'Unknown')
    age = params.get('age', '30s')
    personality = params.get('personality', 'Normal')
    
    booking = params.get('booking_channel', 'Unknown')
    date_ctx = params.get('date_context', 'Weekday')
    urgency = params.get('urgency', 'Medium')
    vip_level = params.get('vip_level', 'Regular')
    initial_mood = params.get('initial_mood', 'Irritated')
    incident_type = params.get('incident_type', 'Complaint')
    
    # 2. 核心逻辑：计算怒气值 (Anger Calculation)
    severity = params.get('severity', 3)
    base_anger = severity * 20
    
    if "激怒" in initial_mood or "Furious" in initial_mood: base_anger += 30
    elif "冷静" in initial_mood: base_anger -= 20
    elif "泥酔" in initial_mood: base_anger += 10
    
    initial_anger = min(100, max(10, base_anger + random.randint(-10, 10)))

    # 3. 提示词 (全日语，强制 AI 输出日语)
    prompt = f"""
    あなたはドラマの脚本家です。ホテルスタッフを困らせる、非常に「厄介なクレーマー客」のプロフィールを作成してください。
    
    【重要：JSONの値はすべて「日本語」で出力してください】

    【客のスペック】
    名前: {name}
    性別: {target_gender} 
    職業: {job}, 年齢: {age}
    性格: {personality}
    VIPランク: {vip_level}
    初期気分: {initial_mood}
    予約経路: {booking}, 日付: {date_ctx}
    トラブル: {incident_type}
    怒りレベル: {initial_anger}/100
    
    【出力要件】
    1. **bio**: **500文字以上**の日本語で詳細な背景を書いてください。
    2. **default_complaint**: スタッフに投げかける「最初の一言」。
    3. **gender**: 必ず「男性」または「女性」と明記すること。
    
    出力JSON形式:
    {{
        "name": "{name}",
        "gender": "男性" または "女性",
        "job": "{job}",
        "age": "{age}",
        "personality": "{personality}",
        "vip_level": "{vip_level}",
        "initial_mood": "{initial_mood}",
        "initial_anger": {initial_anger},
        "bio": "詳細な背景ストーリー...",
        "specific_incident": "トラブルの詳細...",
        "default_complaint": "最初の一言...",
        "ai_prompt": "AIへの演技指導..."
    }}
    """
    
    # 4. 调用 AI 并处理结果
    try:
        model = get_model()
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        data = ensure_dict(json.loads(clean_json_text(resp.text)))

        # ---------------------------------------------------------
        # ✅ 新增核心逻辑：分配 Voice ID (身份与声音绑定)
        # ---------------------------------------------------------
        # 1. 确认最终性别 (以 AI 生成的为准，防止 Prompt 虽然要男但 AI 发疯生成了女)
        final_gender = data.get("gender", target_gender)
        
        # 2. 清洗性别文本 (防止 AI 返回 "男" 或 "Male" 等非标准词)
        if "男" in final_gender: final_gender = "男性"
        elif "女" in final_gender: final_gender = "女性"
        else: final_gender = "女性" # 默认兜底

        # 3. 随机抽取对应的声优 ID 并存入数据
        if final_gender in VOICE_OPTIONS:
            data['voice_id'] = random.choice(VOICE_OPTIONS[final_gender])
        else:
            data['voice_id'] = "ja-JP-NanamiNeural" # 终极兜底

        return data
        # ---------------------------------------------------------

    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 🧑‍💼 3. Staff Generation (员工生成 - 含声线分配)
# ==========================================
def generate_staff_profile(name, role, exp, stress, weak, gender):
    # 1. 如果没填名字，随机生成一个
    if not name:
        # 注意：这里假设你已经定义或导入了 STAFF_NAMES_MALE/FEMALE
        # 如果报错，可以在这里直接写个简单的列表兜底
        if gender == "男性":
            name = random.choice(["佐藤 健", "鈴木 大輔", "高桥 翔ta", "田中 裕也"])
        else:
            name = random.choice(["佐藤 美咲", "鈴木 陽子", "高桥 愛", "田中 結衣"])
    
    prompt = f"""
    あなたはホテルの人事担当、あるいはドラマの脚本家です。
    シミュレーションゲームに登場する、リアルな「ホテルスタッフ」のプロフィールを作成してください。
    
    【重要：JSONの値はすべて「日本語」で出力してください】
    
    【スタッフのパラメータ】
    名前: {name} ({gender})
    役割: {role}
    経験年数: {exp}
    現在の状態: {stress}
    弱点・苦手なこと: {weak}
    
    【出力要件】
    1. **bio**: **500文字以上**の日本語で、詳細な履歴書風の経歴を書いてください。
       - なぜホテル業界に入ったのか？（志望動機）
       - 過去の職歴や失敗談。
       - 現在の生活状況（例：奨学金返済中、子育て中、夢を追っている等）を含め、人間味あふれる内容にしてください。
    2. **personality**: 性格の特徴（例：真面目すぎる、おっちょこちょい、冷徹など）。
    3. **ai_prompt**: このキャラを演じるAIへの演技指導（例：自信なさげに話す、テキパキと早口で話す）。
    
    出力JSON形式:
    {{
        "name": "{name}",
        "gender": "{gender}",
        "role": "{role}",
        "experience": "{exp}",
        "personality": "性格の特徴 (日本語)",
        "bio": "詳細な経歴ストーリー (日本語 500文字以上)...",
        "ai_prompt": "AIへの演技指導 (日本語)"
    }}
    """
    try:
        model = get_model()
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        data = ensure_dict(json.loads(clean_json_text(resp.text)))

        # ---------------------------------------------------------
        # ✅ 新增核心逻辑：分配 Voice ID (给员工分配声音)
        # ---------------------------------------------------------
        # 1. 确认最终性别 (使用传入的 gender 参数)
        final_gender = gender
        
        # 2. 清洗性别文本 (防止传入 "Male" 等英文)
        if "男" in final_gender: final_gender = "男性"
        elif "女" in final_gender: final_gender = "女性"
        else: final_gender = "女性" # 默认兜底

        # 3. 随机抽取对应的声优 ID 并存入数据
        # (确保 VOICE_OPTIONS 已在文件顶部定义)
        if final_gender in VOICE_OPTIONS:
            data['voice_id'] = random.choice(VOICE_OPTIONS[final_gender])
        else:
            data['voice_id'] = "ja-JP-NanamiNeural" # 终极兜底
            
        # 4. 强制把 voice_id 也写进 data 里返回
        return data
        # ---------------------------------------------------------

    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 🧠 4. Memory & Transcription
# ==========================================
def update_memory_bank(current_mem, user_input, last_ai_reply, constraints):
    # 这个函数保持不变，照抄即可
    prompt = f"""
    Analyze the dialogue state.
    [Rules]: {constraints}
    [Last Turn]: AI="{last_ai_reply}" / User="{user_input}"
    [Current Memory]: {json.dumps(current_mem, ensure_ascii=False)}
    
    OUTPUT JSON: 
    - summary: Short summary of what happened.
    - mood_score: int 0-100 (0=Furious, 100=Happy).
    - facts: list of new facts established.
    - pending_issues: what needs to be solved.
    """
    try:
        model = get_model()
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return ensure_dict(json.loads(clean_json_text(resp.text)))
    except:
        return current_mem

def transcribe_audio(audio_bytes):
    """
    🎤 听力功能：复用全局默认模型 (Gemini 2.0 Flash)
    """
    try:
        # ✅ 修改点：直接调用全局工具函数，不再硬编码模型名
        model = get_model() 
        
        response = model.generate_content([
            "Transcribe this audio to Japanese text strictly. Output ONLY the text.",
            {"mime_type": "audio/wav", "data": audio_bytes}
        ])
        return response.text.strip()
    except Exception as e:
        return f"[Error: {e}]"

def get_azure_speech(text, gender="女性", style="customer-service", voice_name=None):
    """
    🔊 终极版：优先使用指定的声优 ID (voice_name)，保留 SSML 语气功能
    """
    try:
        # 1. 读取密钥 (注意：确保你的 secrets.toml 里是 [azure] 还是 [AZURE_SPEECH_KEY] 格式，这里假设是 st.secrets["azure"]["speech_key"])
        # 如果你的 secrets 格式是 AZURE_SPEECH_KEY，请改为 st.secrets["AZURE_SPEECH_KEY"]
        try:
            api_key = st.secrets["azure"]["speech_key"]
            region = st.secrets["azure"]["region"]
        except:
            # 兼容另一种写法
            api_key = st.secrets["AZURE_SPEECH_KEY"]
            region = st.secrets["AZURE_SPEECH_REGION"]

        speech_config = speechsdk.SpeechConfig(subscription=api_key, region=region)
        
        # 2. ✅ 核心逻辑：确定使用哪个声优 ID
        target_voice = "ja-JP-NanamiNeural" # 默认值
        
        if voice_name:
            # 如果传了具体的 ID (比如 'ja-JP-DaichiNeural')，直接用它
            target_voice = voice_name
        else:
            # 没传 ID，就按性别兜底
            if gender == "男性":
                target_voice = "ja-JP-KeitaNeural"
            else:
                target_voice = "ja-JP-NanamiNeural"
            
        speech_config.speech_synthesis_voice_name = target_voice
        
        # 3. 构建 SSML (为了让 style 语气生效，必须用 SSML)
        # 注意：有些男声优可能不支持 style，但 Azure 会自动忽略，不会报错
        ssml = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='ja-JP'>
            <voice name='{target_voice}'>
                <mstts:express-as style='{style}' styledegree='1.2'>
                    {text}
                </mstts:express-as>
            </voice>
        </speak>
        """
        
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        result = synthesizer.speak_ssml_async(ssml).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            st.error(f"TTS Canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                st.error(f"Error details: {cancellation_details.error_details}")
        return None
        
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

# ==========================================
# 📊 5. Evaluation System (評価システム)
# ==========================================
def evaluate_interaction(log_text, world_context):
    """
    强化版评价系统：引入环境锚定与多维度反馈
    world_context: 包含酒店名称、类型、稼动率、特殊状况等
    """
    
    # 获取全局底层协议（环境锚定）
    global_logic = f"""
    【WORLD CONTEXT & BOUNDARIES】
    - Hotel: {world_context.get('name')} (Type: {world_context.get('type')})
    - Constraints: {world_context.get('constraints')}
    - Current Condition: {world_context.get('context')}
    - Logic: Evaluation must be realistic. For Capsule/Biz Hotels, do NOT penalize for lacking luxury service. 
      Penalize heavily if the staff promises something impossible (e.g., room change when 'Full').
    """

    prompt = f"""
    あなたはホテルの支配人兼最高評価責任者です。
    以下の対話ログと世界観設定に基づき、プロフェッショナルなフィードバックを生成してください。
    
    {global_logic}

    【対話ログ】
    {log_text}

    【評価の指示】
    1. **総合スコア**: 0-100で直感的に採点（加算方式は不要）。
    2. **多角的分析**: 
       - 「良かった点（Strengths）」と「改善点（Weaknesses）」を具体的かつ論理的に。
       - 「決定的な瞬間（Critical Moment）」：対応の成否を分けた一言を特定。
    3. **アクションプラン**: 次回のシフトから即実践できる具体的なアドバイス。

    【重要：出力は必ず以下のJSON形式で行い、すべて日本語で回答してください】
    {{
        "manager_review": {{ 
            "score": 0,
            "overall_status": "接客レベルの格付け（例：プロフェッショナル / 見習い / 要再トレーニング）",
            "strengths": ["...", "..."],
            "weaknesses": ["...", "..."],
            "critical_moment": "対話のターニングポイントとなった発言とその理由",
            "compliance_check": "世界観（ホテルタイプや満室状況）に沿った対応だったか？",
            "advice": "次に同じ状況が起きた時のための具体的な改善案"
        }},
        "learn_analysis": {{
            "summary": "LEARNモデル（Listen, Empathize, Apologize, Resolve, Notify）の適用状況の総評"
        }},
        "player_analysis": {{ # 👈 必须加这个，app.py 正在找它
            "type": "接客タイプ",
            "traits": "特徴分析",
            "growth_tip": "アドバイス"
        }},
        "guest_inner_voice": {{
            "satisfaction": "★1〜★5",
            "emotional_curve": "感情の変化（例：激怒 → 呆れ → 納得）",
            "detailed_comment": "250文字以上の生々しい本音。スタッフのどの言葉に救われ、どの言葉に絶望したか。"
        }}
    }}
    """
    try:
        model = get_model()
        # 确保生成配置强制使用 JSON 模式
        resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        data = ensure_dict(json.loads(clean_json_text(resp.text)))
        return data
    except Exception as e:
        return {
            "error": str(e),
            "manager_review": {"score": 0, "overall_status": "エラー", "advice": "APIの接続を確認してください。"}
        }

# ==========================================
# 🤖 6. System Instructions (Core Logic)
# ==========================================

def get_staff_system_instruction(world, guest, staff, date_ctx):
    """
    [User = Staff], [AI = Guest]c
    ✨ Feature: Anger Meter & Dynamic Language Switching
    """
    initial_anger = guest.get('initial_anger', 50)
    vip_status = guest.get('vip_level', 'Regular')
    
    return f"""
    {REALISM_BLOCK}
    
    【ROLE】
    You are {guest.get('name')}. Job: {guest.get('job')}.
    Personality: {guest.get('personality')}.
    **VIP Status**: {vip_status} (If VIP, be more arrogant and demanding).
    
    【SITUATION】
    Hotel: {world.get('name')}
    Occupancy: {world.get('constraints')}
    Date/Event: {date_ctx}
    
    【YOUR PROBLEM】
    {guest.get('specific_incident')}
    
    【🔥 DYNAMIC ANGER SYSTEM (CRITICAL)】
    Your internal Anger Meter starts at: {initial_anger}/100.
    
    [LANGUAGE RULES BASED ON ANGER]
    - **Anger 0-40 (Polite)**: Use formal Japanese (Desu/Masu). "すみませんが..."
    - **Anger 41-70 (Annoyed)**: Mix of polite and direct (Tameguchi). "ねえ、どうなってるの？"
    - **Anger 71-100 (Furious)**: Rude, aggressive, shouting. NO polite forms. "ふざけるな！責任者出せ！金返せ！"
    
    [BEHAVIOR LOGIC]
    1. If the User apologizes sincerely AND offers a solution -> Lower anger (-10).
    2. If the User makes excuses, asks you to wait, or is silent -> Increase anger (+20).
    3. If the User solves the problem -> Anger drops to 0 (Happy).

    """

def get_guest_system_instruction(world, guest, staff, date_ctx):
    """
    [User = Guest], [AI = Staff]
    ✨ Feature: Rule Pre-check (Constraints & Safety)
    """
    constraints = world.get('constraints', 'None')
    condition = world.get('context', 'None') # Get Special Condition/Weather
    
    return f"""
    {REALISM_BLOCK}
    
    【ROLE】
    You are {staff.get('name')}, a Staff at {world.get('name')}.
    Role: {staff.get('role')}.
    Experience: {staff.get('experience')}.
    
    【ENVIRONMENT (Context)】
    Constraint: {constraints}
    Condition: {condition}
    Date: {date_ctx}
    
    【⚠️ MANDATORY PRE-CHECK BEFORE REPLYING ⚠️】
    Before generating your dialogue, you MUST strictly check the following rules:
    
    1. **CHECK OCCUPANCY**: 
       - If the Constraint says "Full" or "満室", you **CANNOT** offer a room change. You must politely REFUSE and offer alternatives (free drink, cleaning, voucher).
    
    2. **CHECK SAFETY**:
       - If the Condition says "Typhoon", "Storm", or "Safety Issue", you **CANNOT** let the guest go outside. Safety is priority #1.
    
    3. **CHECK AUTHORITY**:
       - If the guest asks for a CASH refund (返金) or to fire a staff member, you MUST say "I need to check with my manager" (支配人に確認します). You do not have the authority.
       
    【GOAL】
    Provide professional Omotenashi (Hospitality), but maintain the hotel's rules and dignity.
    """

def get_observer_system_instruction(world, guest, staff, date_ctx):
    """
    [User = Watcher], [AI = Scriptwriter]
    ✨ Feature: Observer Mode (Auto Drama)
    """
    return f"""
    {REALISM_BLOCK}
    あなたはホテルのプロの脚本家です。リアリティのある緊張感漂うドラマを執筆してください。
    
    【CAST】
    Guest: {guest.get('name')} (性格: {guest.get('personality')}, 怒りの原因: {guest.get('specific_incident')})
    Staff: {staff.get('name')} (役職: {staff.get('role', 'スタッフ')}, 性格: {staff.get('personality')})
    
    【SCENE】
    Hotel: {world.get('name')} ({world.get('type')})
    Context: {world.get('constraints')}
    
    【TASK】
    1. ユーザーが「Next」と言うたびに、ストーリーを一歩進める **「次の1発言のみ」** を生成してください。
    2. GuestとStaffのどちらが話すかは、文脈に合わせて判断してください。
    3. 一度の出力で複数の発言（やり取り全部など）を出すことは **厳禁** です。
    
    【重要：出力形式】
    必ず以下のJSON形式で出力してください。他の説明文は一切不要です。
    {{
        "role": "Guest または Staff",
        "content": "セリフの内容のみ（カッコなどのト書きは不要）"
    }}
    """
