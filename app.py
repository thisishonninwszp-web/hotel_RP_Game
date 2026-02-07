# app.py
"""
🏨 Hotel Sim: Ultimate Edition - Main Application
"""
import streamlit as st
# ✅ 关键：引用 hotel_utils
import hotel_utils as utils
import logic
import random
import json
import datetime
import uuid
import pandas as pd
import plotly.graph_objects as go

# ==========================================
# ⚙️ 1. 初始化与配置
# ==========================================
st.set_page_config(page_title="Hotel Sim: Tycoon Ultimate", page_icon="🏨", layout="wide")

# CSS 美化
st.markdown("""
<style>
    div.stButton > button { width: 100%; border-radius: 6px; font-weight: bold; height: 50px; }
    .main-header { font-size: 1.8em; font-weight: bold; color: #1565c0; margin-bottom: 20px; border-bottom: 2px solid #1565c0; padding-bottom: 10px; }
    .bio-box { font-size: 0.9em; color: #444; background: #f9f9f9; padding: 15px; border-radius: 8px; border-left: 4px solid #ddd; margin-top: 10px; line-height: 1.6; }
    .incident-box { background-color: #fff3e0; color: #d84315; padding: 10px; border-radius: 5px; font-weight: bold; border: 1px solid #ffcc80; }
    .score-card { background-color: #e8eaf6; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #c5cae9; }
    .pass-tag { background-color: #e8f5e9; color: #2e7d32; padding: 5px 10px; border-radius: 15px; font-weight: bold; font-size: 0.8em; }
    .fail-tag { background-color: #ffebee; color: #c62828; padding: 5px 10px; border-radius: 15px; font-weight: bold; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

utils.init_dirs()

# API Key 配置
api_key = None
try:
    if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
except: pass
if api_key: logic.configure_genai(api_key)
else:
    user_key = st.sidebar.text_input("Google API Key", type="password")
    if user_key: logic.configure_genai(user_key)

# ==========================================
# 🧠 2. 状态管理 (State Management)
# ==========================================
def init_state():
    defaults = {
        "nav_page": "dashboard",
        "messages": [],
        "evaluation_result": None,
        "rating_change": None,

        # --- [NEW!] 实验身份识别与计数 ---
        "user_id": str(uuid.uuid4())[:8],    # 自动生成的8位唯一随机码
        "user_nickname": "匿名研修生",        # 默认昵称
        "pre_test_data": {},                  # 存储 10 个前测问题的分数
        "pre_test_score": 0,                  # 前测 100 分制得分
        "pre_test_done": False,               # 标记前测是否完成

        # --- [NEW!] 实验与问卷相关数据 ---
        "total_play_count": 0,      # 累计练习次数
        "pre_test_data": {},        # 存储 10 个前测问题的 1-5 分
        "pre_test_score": 0,        # 前测的 100 分制得分
        "pre_test_done": False,     # 标记前测是否完成
        
        "active_world_name": None,
        "active_guest_name": None,
        "active_staff_name": None,
        "current_role": "staff",
        "last_audio_id": None,
        "last_audio_signature": None,
        # app.py 约 70 行左右
        "last_audio_data": None,  # 新增：用于存储二进制音频
        
        "temp_world": None,
        "temp_guest": None,
        "temp_staff": None,
        
        "w_rnd": {
            "name": "グランド・ホテル", "type": "高級旅館", "season": "繁忙期", 
            "stars": 3.5, "fac": "普通", "occ": "通常", "cond": "特になし"
        },
        "c_rnd": {
            "name": "田中 太郎", "job": "会社員", "age": "30代", "booking": "公式HP", 
            "date": "平日", "incident": "Wi-Fi故障", "urgency": "Medium",
            "vip": "一般客", "mood": "イライラ"
        },
        "s_rnd": {
            "name": "", "gender": "女性", "role": "フロントスタッフ", 
            "exp": "1年", "stress": "普通", "weak": "なし"
        }
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

init_state()

# ==========================================
# 🧭 3. 侧边栏导航 (Sidebar)
# ==========================================
with st.sidebar:
    st.title("🏨 Hotel Tycoon MBA")

    st.session_state.user_nickname = st.text_input(
        "👤 プレイヤー名", 
        value=st.session_state.user_nickname
    )
    st.caption(f"ID: {st.session_state.user_id}") # 顺便显示一下ID
    st.divider() # 加个分割线
    
    # --- 基础导航 ---
    if st.button("📊 ダッシュボード"): st.session_state.nav_page = "dashboard"; st.rerun()
    st.markdown("---")
    if st.button("🌍 世界観 (World)"): st.session_state.nav_page = "world"; st.rerun()
    if st.button("👤 顧客 (Guest)"): st.session_state.nav_page = "guest"; st.rerun()
    if st.button("🧑‍💼 スタッフ (Staff)"): st.session_state.nav_page = "staff"; st.rerun()
    
    st.markdown("---")
    # --- 核心入口 ---
    if st.button("🚀 出撃 (Mission Start)", type="primary"): 
        st.session_state.nav_page = "mode_select" 
        st.rerun()
        
    if st.button("📜 履歴 (History)"): st.session_state.nav_page = "history"; st.rerun()

    # --- ☁️ [NEW!] 云端共享库 ---
    st.markdown("---")
    st.markdown("### ☁️ クラウド共有 (Cloud Assets)")
    if st.button("🔄 クラウドから設定読込", use_container_width=True):
        with st.spinner("同期中..."):
            # 🔴 统一使用 utils
            cloud_data = utils.fetch_assets_from_cloud()
            if cloud_data:
                st.session_state.cloud_assets = cloud_data
                st.toast("✅ クラウドデータを同期しました！", icon="🌐")
            else:
                st.warning("クラウドデータはありません。")

    # --- 💾 数据管理 (本地备份) ---
    st.markdown("---")
    with st.expander("📂 ローカルデータ管理 (Save/Load)"):
        st.caption("※ PC環境でのバックアップ用")
        
        # 保存逻辑
        current_data = {
            "worlds": utils.load_json(utils.WORLDS_FILE),
            "guests": utils.load_json(utils.CHARS_FILE),
            "staffs": utils.load_json(utils.STAFF_FILE),
            "history": utils.load_json(utils.HISTORY_FILE)
        }
        json_str = json.dumps(current_data, ensure_ascii=False, indent=2)
        
        st.download_button(
            label="⬇️ セーブ (Download)",
            data=json_str,
            # 🔴 修正点在这里：改为 datetime.datetime.now()
            file_name=f"hotel_save_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True
        )
        
        uploaded_file = st.file_uploader("ロード (Upload)", type=["json"], label_visibility="collapsed")
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                if "worlds" in data: utils.save_json(utils.WORLDS_FILE, data["worlds"])
                if "guests" in data: utils.save_json(utils.CHARS_FILE, data["guests"])
                if "staffs" in data: utils.save_json(utils.STAFF_FILE, data["staffs"])
                if "history" in data: utils.save_json(utils.HISTORY_FILE, data["history"])
                st.toast("✅ データを復元しました！", icon="🎉")
                st.rerun()
            except Exception as e:
                st.error(f"読み込みエラー: {e}")

# ==========================================
# 📊 4. 仪表盘 (Dashboard)
# ==========================================
if st.session_state.nav_page == "dashboard":
    st.markdown("<div class='main-header'>📊 Dashboard</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Worlds", len(utils.load_json(utils.WORLDS_FILE)))
    c2.metric("Guests", len(utils.load_json(utils.CHARS_FILE)))
    c3.metric("Staff", len(utils.load_json(utils.STAFF_FILE)))
    
    st.divider()
    
    c_start, c_info = st.columns([1, 2])
    with c_start:
        st.subheader("⚡ クイックスタート")
        st.caption("全設定をランダム生成して即座に開始します")
        
        # 👇👇👇 从这里开始完全替换 👇👇👇
        if st.button("🎲 今すぐ始める (Quick Play)", type="primary", use_container_width=True):
            
            # 1. 定义随机池 (为了让每次生成的都不一样)
            POLICIES = ["お客様は神様 (CS重視)", "利益第一 (コストカット)", "事なかれ主義", "伝統と格式", "フレンドリー＆カジュアル", "完全なる放置"]
            DIFFICULTY_LEVELS = ["Easy (初級)", "Normal (中級)", "Hard (上級)", "Hell (理不尽)"]
            FACILITIES = ["雨漏りするボロ宿", "昭和レトロな設備", "一般的なビジネスホテル", "リノベーション済み", "最新鋭のスマート設備", "王宮のような豪華設備"]
            EXP_LEVELS = ["新人 (研修中)", "1年目", "3年 (一人前)", "10年のベテラン", "伝説のコンシェルジュ"]
            STRESS_LEVELS = ["やる気満々", "通常", "少し疲れている", "疲労困憊", "辞める寸前"]

            with st.spinner("運命のサイコロを振っています..."):
                # 2. 随机生成 World (注意：这里用了 random 生成星级和难度)
                rnd_stars = round(random.uniform(1.0, 5.0), 1)
                rnd_diff = random.choice(DIFFICULTY_LEVELS)
                
                w = logic.generate_world_setting(
                    random.choice(utils.HOTEL_NAMES), 
                    random.choice(utils.HOTEL_TYPES),
                    random.choice(utils.SEASONS), 
                    rnd_stars,                  # 随机星级
                    random.choice(FACILITIES),  # 随机设施
                    random.choice(POLICIES),    # ✅ 随机经营方针 (替代了原来的 occupancy)
                    random.choice(utils.SPECIAL_CONDITIONS),
                    rnd_diff                    # ✅ 必须加上这个 difficulty 参数！
                )
                
                # 3. 随机生成 Staff
                s = logic.generate_staff_profile(
                    "", 
                    "フロント", 
                    random.choice(EXP_LEVELS),    # 随机经验
                    random.choice(STRESS_LEVELS), # 随机压力
                    "特になし", 
                    random.choice(["男性", "女性"])
                )
                
                # 4. 随机生成 Guest
                c = logic.generate_guest_profile({
                    "name": random.choice(utils.CHAR_NAMES),
                    "job": random.choice(utils.CHAR_JOBS),
                    "booking_channel": random.choice(utils.BOOKING_CHANNELS),
                    "date_context": random.choice(utils.DATE_CONTEXTS),
                    "incident_type": random.choice(utils.COMPLAINT_TYPES),
                    "severity": random.randint(1, 5), # 随机严重度
                    "vip_level": random.choice(utils.VIP_LEVELS),
                    "initial_mood": random.choice(utils.INITIAL_MOODS)
                })
                
                # 5. 保存并跳转
                if "error" not in w and "error" not in s and "error" not in c:
                    # 保存到库
                    utils.add_to_library(utils.WORLDS_FILE, w)
                    utils.add_to_library(utils.STAFF_FILE, s)
                    utils.add_to_library(utils.CHARS_FILE, c)
                    
                    # 激活当前选择
                    st.session_state.active_world_name = w['name']
                    st.session_state.active_staff_name = s['name']
                    st.session_state.active_guest_name = c['name']
                    
                    # 存入临时状态 (Preview用，虽然直接跳转了但也存一下)
                    st.session_state.temp_world = w
                    st.session_state.temp_staff = s
                    st.session_state.temp_guest = c

                    # 重置对话
                    st.session_state.messages = []
                    st.session_state.evaluation_result = None
                    
                    # 跳转到模式选择
                    st.session_state.nav_page = "mode_select"
                    st.rerun()
                else:
                    st.error("生成エラーが発生しました。もう一度試してください。")
    
    with c_info:
        #以此替换原来的 User Manual 部分
        with st.expander("📖 ユーザーマニュアル (About this Simulator)", expanded=True):
            st.markdown("""
            ### 🎓 開発背景 (Background)
            本ソフトウェアは、**京都大学経営管理大学院 (Kyoto University MBA)** における**蓮行先生**の「コンサルテーションXX」に着想を得て開発されました。
            
            従来、対人で行われていた高負荷なロールプレイ演習を、**生成AI (Generative AI)** 技術を用いることで、いつでも・どこでも・何度でも反復練習できるようにした「和対 (Watai)」です。

            ### 🎭 ロールプレイの仕組み
            - **Player (あなた)**: ホテルの現場スタッフとして振る舞います。
            - **AI (相手)**: あなたの設定した「理不尽なクレーマー」や「訳ありのVIP」を、感情豊かに演じきります。
            
            単なるゲームではありません。相手の怒りを鎮め、信頼を勝ち取るための**「傾聴力」と「交渉力」**が試されるシリアスゲームです。

            ### 🕹️ 操作フロー (How to use)
            1.  **Setup (設定)**:
                - 左の **「⚡クイックスタート」** を押すと、ランダムなトラブル状況が生成されます。
                - 詳細に設定したい場合は、サイドバーの「World」「Guest」から編集可能です。
            2.  **Interaction (対話)**:
                - テキスト、または**音声入力**で接客を行います。難易度が高いほど、AIは簡単には許してくれません。
            3.  **Review (評価)**:
                - 対応終了後、「**評価レポート**」を確認してください。
                - 支配人AIが、あなたの対応を**LEARNモデル**（Listen, Empathize, Apologize, Resolve, Notify）に基づいて厳しく採点します。
            """)
            
            st.info("💡 **Tip**: 難易度「Hell」では、論理的な正論よりも、感情への寄り添いが重要になります。")

# ==========================================
# 🌍 5. World Editor
# ==========================================
elif st.session_state.nav_page == "world":
    st.markdown("<div class='main-header'>🌍 世界観設定</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📚 ライブラリ", "🛠️ 新規作成"])
    
    # --- Tab 1: 现有库 (详细阅览版) ---
    with tab1:
        worlds = utils.load_json(utils.WORLDS_FILE)
        if not worlds:
            st.info("データがありません。")
            
        for w in worlds:
            check = "✅ " if w['name'] == st.session_state.active_world_name else ""
            
            # 标题栏显示关键信息
            label = f"{check}{w['name']} (★{w.get('current_rating', w.get('stars', 3.0))} | {w.get('type')})"
            
            with st.expander(label):
                # 1. 关键参数栏
                c_info1, c_info2 = st.columns(2)
                c_info1.info(f"🔒 **制約**: {w.get('constraints')}")
                c_info2.write(f"**稼働率**: {w.get('occupancy', '不明')} | **難易度**: {w.get('difficulty', 'Normal')}")
                
                # 2. 完整背景故事 (带滚动条)
                st.caption("📜 背景ストーリー:")
                with st.container(height=200): # 固定高度，内容可滚动
                    st.markdown(w.get('background_story'))
                
                st.divider()
                
                # 3. 操作按钮
                c1, c2 = st.columns([1, 1])
                if c1.button("選択", key=f"sw_{w['name']}"): 
                    st.session_state.active_world_name = w['name']
                    st.rerun()
                if c2.button("🗑️ 削除", key=f"dw_{w['name']}"): 
                    utils.delete_from_library(utils.WORLDS_FILE, w['name'])
                    st.rerun()

    with tab2:
        # 定义新的选项列表
        DIFFICULTY_LEVELS = ["Easy (初級)", "Normal (中級)", "Hard (上級)", "Hell (理不尽)"]
        POLICIES = ["お客様は神様 (CS重視)", "利益第一 (コストカット)", "事なかれ主義 (隠蔽体質)", "伝統と格式 (ルール絶対)", "新興ベンチャー (混乱中)"]

        if st.button("🎲 ランダム入力"):
            st.session_state.w_rnd.update({
                "name": random.choice(utils.HOTEL_NAMES),
                "type": random.choice(utils.HOTEL_TYPES),
                "season": random.choice(utils.SEASONS),
                "policy": random.choice(POLICIES),     # ✅ 新参数
                "cond": random.choice(utils.SPECIAL_CONDITIONS),
                "diff": random.choice(DIFFICULTY_LEVELS)
            })
            st.rerun()
            
        with st.form("w_gen"):
            r = st.session_state.w_rnd
            # 兼容性处理：防止 key error
            if "policy" not in r: r["policy"] = POLICIES[0]
            if "diff" not in r: r["diff"] = "Normal (中級)"

            name = st.text_input("ホテル名", r["name"])
            
            c1, c2 = st.columns(2)
            htype = c1.selectbox("タイプ", utils.HOTEL_TYPES, index=utils.HOTEL_TYPES.index(r["type"]) if r["type"] in utils.HOTEL_TYPES else 0)
            season = c2.selectbox("シーズン", utils.SEASONS, index=utils.SEASONS.index(r["season"]) if r["season"] in utils.SEASONS else 0)
            
            c3, c4 = st.columns(2)
            # 👇 这里把原来的稼働率换成了 经营方针
            policy = c3.selectbox("経営方針", POLICIES, index=POLICIES.index(r["policy"]) if r["policy"] in POLICIES else 0)
            cond = c4.selectbox("特殊状況", utils.SPECIAL_CONDITIONS, index=utils.SPECIAL_CONDITIONS.index(r["cond"]) if r["cond"] in utils.SPECIAL_CONDITIONS else 0)
            
            diff = st.select_slider("🔥 難易度 (補償手段の制限)", options=DIFFICULTY_LEVELS, value=r["diff"])
            
            stars = st.slider("初期評価", 1.0, 5.0, 3.5)
            fac = st.text_input("設備", r["fac"])
            
            if st.form_submit_button("🚀 生成してプレビュー"):
                loading_texts = [
                    "😈 支配人が金庫の鍵を隠しています...", 
                    "📉 経費削減プランを作成中...", 
                    "📝 マニュアルを書き換えています...",
                    "🔨 ホテルを建設中..."
                ]
                with st.spinner(random.choice(loading_texts)):
                    # ✅ 传入 policy 而不是 occ
                    data = logic.generate_world_setting(name, htype, season, stars, fac, policy, cond, diff)
                    if "error" not in data:
                        st.session_state.temp_world = data
                        st.rerun()
                    else: st.error(data["error"])

        # 预览部分 (保持之前逻辑，增加显示 allowed_compensations)
        if st.session_state.temp_world:
            st.divider()
            st.subheader("👀 プレビュー")
            
            c_save, c_del = st.columns([1, 1])
            if c_save.button("💾 保存 (Save)", type="primary", use_container_width=True):
                utils.add_to_library(utils.WORLDS_FILE, st.session_state.temp_world)
                st.session_state.active_world_name = st.session_state.temp_world['name']
                st.session_state.temp_world = None
                st.success("保存しました！")
                st.rerun()
            
            if c_del.button("🗑️ 破棄", use_container_width=True):
                st.session_state.temp_world = None
                st.rerun()

            w = st.session_state.temp_world
            # 👇 显示 AI 生成的“可用手段”
            st.warning(f"🛠️ **使用可能な補償**: {w.get('allowed_compensations')}")
            st.info(f"📜 **経営方針**: {w.get('policy')} | **制約**: {w.get('constraints')}")
            
            with st.container(height=300):
                st.markdown(w['background_story'])

# ==========================================
# 👤 Guest Editor
# ==========================================
elif st.session_state.nav_page == "guest":
    st.markdown("<div class='main-header'>👤 顧客設定</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📚 ライブラリ", "🛠️ 新規作成"])
    
    # --- Tab 1: 现有库 (已修复：增加删除按钮) ---
    # --- Tab 1: 现有库 (详细阅览版) ---
    with tab1:
        guests = utils.load_json(utils.CHARS_FILE)
        if not guests:
            st.info("データがありません。")
            
        for g in guests:
            check = "✅ " if g['name'] == st.session_state.active_guest_name else ""
            label = f"{check}{g['name']} ({g.get('incident_type', 'Trouble')})"
            
            with st.expander(label):
                # 1. 醒目的麻烦内容
                st.error(f"🚨 **トラブル内容**: {g.get('specific_incident')}")
                
                # 2. 详细数据
                st.caption(f"😡 怒り: {g.get('initial_anger')}/100 | 💎 VIP: {g.get('vip_level')} | 🎭 気分: {g.get('initial_mood')}")
                
                # 3. 第一句台词 (很有趣的信息)
                if g.get('default_complaint'):
                    st.info(f"🗣️ **第一声**: 「{g.get('default_complaint')}」")
                
                # 4. 完整生平 (带滚动条)
                st.caption("📜 詳細プロフィール:")
                with st.container(height=200):
                    st.markdown(g.get('bio'))
                
                st.divider()
                
                # 5. 操作按钮
                c1, c2 = st.columns([1, 1])
                if c1.button("選択", key=f"sg_{g['name']}"): 
                    st.session_state.active_guest_name = g['name']
                    st.rerun()
                if c2.button("🗑️ 削除", key=f"dg_{g['name']}"):
                    utils.delete_from_library(utils.CHARS_FILE, g['name'])
                    if st.session_state.active_guest_name == g['name']: st.session_state.active_guest_name = None
                    st.rerun()

    # --- Tab 2: 新建表单 ---
    with tab2:
        # 1. 🎲 随机参数按钮
        if st.button("🎲 パラメータをランダムセット"):
            st.session_state.c_rnd.update({
                "name": random.choice(utils.CHAR_NAMES),
                "job": random.choice(utils.CHAR_JOBS),
                "booking": random.choice(utils.BOOKING_CHANNELS),
                "date": random.choice(utils.DATE_CONTEXTS),
                "incident": random.choice(utils.COMPLAINT_TYPES),
                "urgency": random.choice(["Low", "Medium", "High", "Critical"]),
                "vip": random.choice(utils.VIP_LEVELS),
                "mood": random.choice(utils.INITIAL_MOODS)
            })
            # 重置之前的预览，防止混淆
            st.session_state.temp_guest = None
            st.rerun()
            
        # 2. 📝 输入表单
        # ... (app.py 的 Guest Editor -> tab2 里面) ...

        with st.form("g_gen"):
            r = st.session_state.c_rnd
            
            # ✅ 修改点 1：调整布局，加入“性别”选择框
            c1, c2, c3 = st.columns([2, 1, 2]) 
            name = c1.text_input("名前", r['name'])
            # 👇 这里增加了性别选择，默认是 Random
            gender_input = c2.selectbox("性別", ["Random", "男性", "女性"], index=0) 
            job = c3.text_input("職業", r['job'])
            
            # 第二行
            c4, c5 = st.columns(2)
            booking = c4.selectbox("予約経路", utils.BOOKING_CHANNELS, index=utils.BOOKING_CHANNELS.index(r['booking']) if r['booking'] in utils.BOOKING_CHANNELS else 0)
            date_ctx = c5.selectbox("日付/イベント", utils.DATE_CONTEXTS, index=utils.DATE_CONTEXTS.index(r['date']) if r['date'] in utils.DATE_CONTEXTS else 0)
            
            # 第三行
            c6, c7 = st.columns(2)
            vip = c6.selectbox("会員ランク", utils.VIP_LEVELS, index=utils.VIP_LEVELS.index(r['vip']) if r['vip'] in utils.VIP_LEVELS else 0)
            mood = c7.selectbox("初期情緒", utils.INITIAL_MOODS, index=utils.INITIAL_MOODS.index(r['mood']) if r['mood'] in utils.INITIAL_MOODS else 0)

            # 第四行
            inc = st.selectbox("トラブル内容", utils.COMPLAINT_TYPES, index=utils.COMPLAINT_TYPES.index(r['incident']) if r['incident'] in utils.COMPLAINT_TYPES else 0)
            
            # 第五行
            c8, c9 = st.columns(2)
            sev = c8.slider("深刻度 (Severity)", 1, 5, 3)
            urg = c9.select_slider("緊急度 (Urgency)", options=["Low", "Medium", "High", "Critical"], value=r['urgency'])
            
            # 🚀 生成按钮
            submitted = st.form_submit_button("🚀 生成してプレビュー")
            
            if submitted:
                loading_texts = [
                    "😡 クレーマーを探しています...", 
                    "🔥 怒りゲージを充填中...", 
                    "🍷 VIPのためにレッドカーペットを準備中...", 
                    "📝 架空の悪い口コミを生成中..."
                ]
                with st.spinner(random.choice(loading_texts)):
                    params = {
                        "name": name, 
                        "gender": gender_input, # ✅ 修改点 2：把选好的性别传给 logic
                        "job": job, 
                        "booking_channel": booking, "date_context": date_ctx, 
                        "incident_type": inc, "severity": sev, "urgency": urg,
                        "vip_level": vip, "initial_mood": mood
                    }
                    # 调用 AI 生成
                    data = logic.generate_guest_profile(params)
                    
                    if "error" not in data:
                        st.session_state.temp_guest = data
                        st.rerun()
                    else: 
                        st.error(data["error"])

        # 3. 👀 预览与保存区域 (必须在 form 外面！)
        # 只要 temp_guest 有数据，这里就会显示
        if st.session_state.temp_guest:
            st.divider()
            st.subheader("👀 プレビュー (確認して保存)")
            
            # 按钮组 (保存 & 丢弃)
            c_save, c_del = st.columns([1, 1])
            
            # 保存按钮
            if c_save.button("💾 この設定で保存 (Save)", type="primary", use_container_width=True):
                utils.add_to_library(utils.CHARS_FILE, st.session_state.temp_guest)
                st.session_state.active_guest_name = st.session_state.temp_guest['name']
                st.session_state.temp_guest = None # 清空缓存
                st.success("保存しました！")
                st.rerun()
            
            # 丢弃按钮
            if c_del.button("🗑️ 破棄 (Discard)", use_container_width=True):
                st.session_state.temp_guest = None # 清空缓存
                st.rerun()

            # 内容展示卡片
            g = st.session_state.temp_guest
            st.info(f"怒りレベル: {g.get('initial_anger')}/100 | 第一声: 「{g.get('default_complaint')}」")
            st.markdown(f"<div class='incident-box'>🚨 {g.get('specific_incident')}</div>", unsafe_allow_html=True)
            st.caption(f"🆔 {g.get('gender', '不明')} | {g.get('age', '??')} | {g.get('job', '职业不明')}")
            st.info(f"怒りレベル: {g.get('initial_anger')}/100 | 第一声: 「{g.get('default_complaint')}」")

            # 滚动条容器
            with st.container(height=300):
                st.markdown(g.get('bio'))

# ==========================================
# 🧑‍💼 6. Staff Editor (已修复：增加预览与保存/丢弃)
# ==========================================
elif st.session_state.nav_page == "staff":
    st.markdown("<div class='main-header'>🧑‍💼 スタッフ設定</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📚 ライブラリ", "🛠️ 新規作成"])
    
    # --- Tab 1: 现有库 (已修复：增加删除按钮) ---
    # --- Tab 1: 现有库 (详细阅览版) ---
    with tab1:
        staffs = utils.load_json(utils.STAFF_FILE)
        if not staffs:
            st.info("データがありません。")

        for s in staffs:
            check = "✅ " if s['name'] == st.session_state.active_staff_name else ""
            label = f"{check}{s['name']} ({s.get('role')})"
            
            with st.expander(label):
                # 1. 基本信息
                st.info(f"📋 **役割**: {s.get('role')} | **経験**: {s.get('experience')} | **性格**: {s.get('personality')}")
                
                # 2. 完整简历 (带滚动条)
                st.caption("📜 履歴書 / バイオグラフィー:")
                with st.container(height=200):
                    st.markdown(s.get('bio'))
                
                # 3. AI演技指导 (如果有的话)
                if s.get('ai_prompt'):
                    st.caption("🤖 AIへの演技指導:")
                    st.code(s.get('ai_prompt'), language='text')

                st.divider()

                # 4. 操作按钮
                c1, c2 = st.columns([1, 1])
                if c1.button("選択", key=f"ss_{s['name']}"): 
                    st.session_state.active_staff_name = s['name']
                    st.rerun()
                if c2.button("🗑️ 削除", key=f"ds_{s['name']}"):
                    utils.delete_from_library(utils.STAFF_FILE, s['name'])
                    if st.session_state.active_staff_name == s['name']: st.session_state.active_staff_name = None
                    st.rerun()

    with tab2:
        # 1. 🎲 随机参数按钮
        if st.button("🎲 パラメータをランダムセット", key="rnd_staff"):
            rnd_gender = random.choice(utils.GENDERS)
            if rnd_gender == "男性":
                rnd_name = random.choice(utils.STAFF_NAMES_MALE)
            else:
                rnd_name = random.choice(utils.STAFF_NAMES_FEMALE)
            rnd_role = random.choice(list(utils.STAFF_PRESETS.keys()))
            rnd_exp = random.choice(utils.STAFF_PRESETS[rnd_role])
            
            st.session_state.s_rnd.update({
                "name": rnd_name, "gender": rnd_gender, "role": rnd_role, "exp": rnd_exp
            })
            st.session_state.temp_staff = None # 随机时清空预览
            st.rerun()

        # 2. 生成表单
        with st.form("s_gen"):
            r = st.session_state.s_rnd
            
            c1, c2 = st.columns(2)
            name = c1.text_input("名前 (空白ならランダム)", r['name'])
            # ✅ 性別を選択（これによって logic.py で声が割り当てられます）
            gender = c2.selectbox("性別", utils.GENDERS, index=utils.GENDERS.index(r['gender']) if r['gender'] in utils.GENDERS else 0)
            
            c3, c4 = st.columns(2)
            role = c3.selectbox("役割", list(utils.STAFF_PRESETS.keys()), index=list(utils.STAFF_PRESETS.keys()).index(r['role']) if r['role'] in utils.STAFF_PRESETS else 0)
            exp = c4.text_input("経験年数", r['exp'])
            
            # 🚀 生成ボタン
            if st.form_submit_button("🚀 生成してプレビュー"):
                loading_texts = [
                    "👔 面接を行っています...", 
                    "📑 履歴書をチェック中...", 
                    "☕ 休憩室でサボっているスタッフを呼び出し中...", 
                    "🧹 制服のサイズを調整中..."
                ]
                with st.spinner(random.choice(loading_texts)):
                    # ✅ logic.generate_staff_profile に gender を確実に渡す
                    # ここで logic.py は voice_id を自動的に割り当てて返してくれます
                    data = logic.generate_staff_profile(name, role, exp, "Normal", "None", gender)
                    if "error" not in data:
                        st.session_state.temp_staff = data
                        st.rerun()
                    else: 
                        st.error(data["error"])

        # 3. 预览与保存区域
        if st.session_state.temp_staff:
            st.divider()
            st.subheader("👀 プレビュー (面接結果)")
            
            # ✅ 性別と割り当てられた声の確認（デバッグ用キャプション）
            g_icon = "👨" if st.session_state.temp_staff.get('gender') == "男性" else "👩"
            v_id = st.session_state.temp_staff.get('voice_id', '未設定')
            st.caption(f"{g_icon} 性別: {st.session_state.temp_staff.get('gender')} | 🔊 割り当て声線: {v_id}")
            
            c_save, c_del = st.columns([1, 1])
            if c_save.button("💾 採用する (Save)", type="primary", use_container_width=True):
                # ここで保存される JSON に voice_id も含まれるようになります
                utils.add_to_library(utils.STAFF_FILE, st.session_state.temp_staff)
                st.session_state.active_staff_name = st.session_state.temp_staff['name']
                st.session_state.temp_staff = None
                st.success(f"{st.session_state.active_staff_name} さんを採用しました！")
                st.rerun()
            
            if c_del.button("🗑️ 不採用 (Discard)", use_container_width=True):
                st.session_state.temp_staff = None
                st.info("履歴書をシュレッダーにかけました。")
                st.rerun()

            st.info(f"性格: {st.session_state.temp_staff.get('personality')}")
            with st.container(height=300):
                st.markdown(st.session_state.temp_staff['bio'])

# ==========================================
# 🚀 7. Mode Select (模式选择)
# ==========================================
elif st.session_state.nav_page == "mode_select":
    st.markdown("<div class='main-header'>🚀 出撃準備</div>", unsafe_allow_html=True)

    # 加载数据用于显示验证
    w = next((x for x in utils.load_json(utils.WORLDS_FILE) if x["name"] == st.session_state.active_world_name), None)
    g = next((x for x in utils.load_json(utils.CHARS_FILE) if x["name"] == st.session_state.active_guest_name), None)
    s = next((x for x in utils.load_json(utils.STAFF_FILE) if x["name"] == st.session_state.active_staff_name), None)
    
    # 显示状态栏
    col1, col2, col3 = st.columns(3)
    if w: col1.success(f"World: {w['name']}")
    else: col1.error("未選択")
    if g: col2.success(f"Guest: {g['name']}")
    else: col2.error("未選択")
    if s: col3.success(f"Staff: {s['name']}")
    else: col3.error("未選択")
    
    # 只有当三个都选好时，才显示模式按钮
    if w and g and s:
        st.divider()
        st.subheader("🏁 プレイモードを選択してください")
        
        # 定义跳转逻辑：选完模式 -> 去中转门 (Pre-test Gate)
        def set_mode_and_go(role):
            st.session_state.current_role = role
            st.session_state.messages = []
            st.session_state.evaluation_result = None
            st.session_state.rating_change = None
            # 💡 关键路径：去中转门
            st.session_state.nav_page = "pre_test_gate"
            st.rerun()

        m1, m2, m3 = st.columns(3)
        if m1.button("🧑‍💼 Staff Mode\n(AI = 激怒客)", type="primary", use_container_width=True):
            set_mode_and_go("staff")
        if m2.button("😠 Guest Mode\n(AI = スタッフ)", use_container_width=True):
            set_mode_and_go("guest")
        if m3.button("👁️ Observer Mode\n(AI vs AI)", use_container_width=True):
            set_mode_and_go("observer")

# ==========================================
# 🚪 8. Pre-test Gate (中转决策页)
# ==========================================
elif st.session_state.nav_page == "pre_test_gate":
    st.markdown("<div class='main-header'>⚔️ ミッション開始確認</div>", unsafe_allow_html=True)
    
    # 再次确认配置，增加仪式感
    st.info(f"**🏨 舞台:** {st.session_state.active_world_name} | **👤 角色:** {st.session_state.current_role.upper()}")
    
    st.markdown("""
    ### 📊 接客戦闘力診断 (任意)
    実戦の前に、今のあなたの**「接客戦闘力」**を測定してみませんか？
    10個の質問に答えるだけで、AIが推定ランクを判定します。
    """)

    c1, c2 = st.columns(2)
    # 路径 A：去考试
    with c1:
        if st.button("✨ 診断を受けてから出撃 (推奨)", type="primary", use_container_width=True):
            st.session_state.nav_page = "pre_test"
            st.rerun()
    
    # 路径 B：直接打仗
    with c2:
        if st.button("🚀 診断せず直接実戦へ", use_container_width=True):
            st.session_state.pre_test_done = False
            st.session_state.pre_test_score = 0
            st.session_state.nav_page = "chat"
            st.rerun()

# ==========================================
# 📝 9. Pre-test Assessment (全100分制)
# ==========================================
elif st.session_state.nav_page == "pre_test":
    st.markdown("<div class='main-header'>⚖️ 接客スキル精密診断</div>", unsafe_allow_html=True)
    st.info("各項目を **0点(自信なし)** 〜 **100点(完璧)** で自己採点してください。")
    st.caption("※ 最後に平均点を算出し、あなたの「総合戦闘力」とします。")

    with st.form("fun_pre_test_form"):
        # 10个核心能力维度
        questions = [
            (3, "把握力: 顧客の困りごとを正確に一発で把握できる"),
            (4, "忍耐力: 激怒している相手の話も遮らずに聞ける"),
            (5, "表現力: 声のトーンや抑揚で「誠実さ」を演出できる"),
            (6, "共感力: 相手が「わかってくれた」と感じる雰囲気を作れる"),
            (7, "説明力: 複雑な事情やルールを簡潔に説明できる"),
            (8, "柔軟性: マニュアルに縛られず、納得感のある解決策を出せる"),
            (9, "完結力: 電話の最後を気持ちよく、ポジティブに終われる"),
            (10, "精神力: プレッシャーの中でも焦らず、頭が真っ白にならない"),
            (11, "臨場感: 本物のクレーム対応だと思って没入できる"),
            (12, "成長心: 失敗しても、そこから学び取る意欲がある")
        ]
        
        scores = {}
        c1, c2 = st.columns(2)
        
        for i, (idx, txt) in enumerate(questions):
            with c1 if i < 5 else c2:
                # 🔴 改动点：范围变成 0~100，步长设为 5 (方便拖动，如 75, 80, 85)
                # 如果你想要小数点，把 step 改为 0.1，但 100分制通常整数就够了
                scores[f"q{idx}"] = st.slider(
                    label=f"Q{i+1}. {txt}",
                    min_value=0,
                    max_value=100,
                    value=50,
                    step=1, # 👈 步长设为5，手感更好（50, 55, 60...）
                    help="直感で100点満点の評価をしてください"
                )

        st.markdown("---")
        
        if st.form_submit_button("💯 採点結果を確定して出撃", type="primary", use_container_width=True):
            # 💡 算分逻辑：(总分 / 10个题) = 平均分 (也就是最终的100分制得分)
            total_sum = sum(scores.values())
            final_score = int(total_sum / 10) # 取整数
            
            # 存入 Session
            st.session_state.pre_test_score = final_score
            st.session_state.pre_test_data = scores
            st.session_state.pre_test_done = True
            
            # 趣味评级判定
            if final_score >= 90:
                rank = "👑 Sランク: ホテル王の器"
                msg = "恐ろしいほどの自信...！その実力が本物か見せてもらいましょう。"
            elif final_score >= 75:
                rank = "🔷 Aランク: 頼れるエース"
                msg = "高い水準でまとまっています。即戦力として期待大です。"
            elif final_score >= 55:
                rank = "🟢 Bランク: 期待のホープ"
                msg = "平均的なスキルセットです。ここからの成長が楽しみです！"
            else:
                rank = "🔰 Cランク: 伸び代モンスター"
                msg = "今はまだ原石です。AIとの特訓で経験値を稼ぎましょう！"

            # 弹窗提示结果
            st.toast(f"診断完了！総合戦闘力: {final_score}点\n判定: {rank}", icon="🔥")
            
            # 缓冲跳转
            import time
            with st.spinner(f"戦闘力 {final_score} で出撃中..."):
                time.sleep(1.5) 
                st.session_state.nav_page = "chat"
                st.rerun()

# ==========================================
# 💬 10. Chat Interface
# ==========================================
elif st.session_state.nav_page == "chat":
    # 1. 基础变量初始化
    role = st.session_state.get('current_role', 'staff')
    date_ctx = "Weekday" 

    # 2. 关键：确保 g 和 s 在所有逻辑运行前都被定义
    # 首先加载世界观数据
    w_list = utils.load_json(utils.WORLDS_FILE)
    w = next((x for x in w_list if x["name"] == st.session_state.active_world_name), {})

    # --- 这里是重点：检查你的变量名 ---
    # 有的代码里叫 GUEST_FILE，有的叫 CHARS_FILE，我们统一尝试读取
    guest_path = getattr(utils, 'GUEST_FILE', getattr(utils, 'CHARS_FILE', 'data/guests.json'))
    g_list = utils.load_json(guest_path)
    # 根据当前激活的顾客姓名匹配数据
    g = next((x for x in g_list if x["name"] == st.session_state.active_guest_name), {})

    # 加载员工数据
    s_list = utils.load_json(utils.STAFF_FILE)
    s = next((x for x in s_list if x["name"] == st.session_state.active_staff_name), {})

    # 3. UI 头部渲染
    c1, c2 = st.columns([5, 1])
    c1.subheader(f"💬 {role.upper()} MODE")
    if c2.button("終了/評価"): 
        st.session_state.nav_page = "eval"
        st.rerun()
    
    # 4. 初始化对话逻辑
    if not st.session_state.messages:
        sys_prompt = ""
        first_msg = ""
        
        # 此时 g, s, w 已经在上方定义，不会再报 NameError
        if role == "staff": 
            sys_prompt = logic.get_staff_system_instruction(w, g, s, date_ctx)
            first_msg = g.get('default_complaint', 'すみません、ちょっといいですか！')
        elif role == "guest": 
            sys_prompt = logic.get_guest_system_instruction(w, g, s, date_ctx)
            first_msg = "お電話ありがとうございます。フロントでございます。いかがなさいましたか？"
        else: 
            # 1. 即使是观察者模式，也使用专门的“现场再现”指令
            sys_prompt = logic.get_observer_system_instruction(w, g, s, date_ctx)
            
            # 2. 获取实时变量
            h_name = w.get('name', '当ホテル')
            g_name = g.get('name', 'お客様')
            incident = g.get('specific_incident', 'ご指摘の事項')

            # 3. 采用“现场再现 / 记录档案”的口吻，增加真实感
            # 模拟监控录像或事故调查报告的开场
            first_msg = (
                f"【現場再現：{h_name} フロントデスク】\n"
                f"ロビーの喧騒の中、{g_name}様が険しい表情でカウンターに詰め寄っています。"
                f"現在、{incident}を巡って現場には張り詰めた空気が流れています。\n"
                "これより、当時の状況を記録に基づき詳細に再現します。"
            )

        # 启动聊天 session
        st.session_state.messages.append({"role": "assistant", "content": first_msg})
        st.session_state.chat_model = logic.get_model(sys_prompt)
        st.session_state.chat = st.session_state.chat_model.start_chat(history=[])

        # 处理第一句话的语音
        speaker_data = g if role == "staff" else s
        t_voice = speaker_data.get("voice_id")
        t_gender = speaker_data.get("gender", "女性")
        
        # --- 修改后 ---
        if first_msg: # 去掉 role != "observer" 的判断
            speaker_data = g if role == "staff" or role == "observer" else s # 观察者模式默认先选顾客声音或根据剧情定
            init_audio = logic.get_azure_speech(
                first_msg, 
                gender=speaker_data.get("gender", "女性"), 
                style="customer-service", 
                voice_name=speaker_data.get("voice_id")
            )
            if init_audio: 
                st.session_state.last_audio_data = init_audio

        st.rerun()

    # ✅ 2. 显示历史消息
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # ✅ 3. 核心：Azure 语音播放器 (替换了原来的 utils.autoplay_audio)
    if "last_audio_data" in st.session_state and st.session_state.last_audio_data:
        st.audio(st.session_state.last_audio_data, format="audio/wav", autoplay=True)
        # 播完即焚，防止刷新时复读
        del st.session_state.last_audio_data

    # ✅ 4. 输入区域
    if role == "observer":
        st.info("👁️ 観察者モード: 下のボタンを押してドラマを進めてください")
        # 观察者模式专用按钮
        if st.button("▶️ 続きを生成 (Action)", type="primary", use_container_width=True):
            with st.spinner("現場状況を再現中..."):
                try:
                    # 1. 向 AI 发送 Next 指令
                    resp = st.session_state.chat.send_message("Next")
                    
                    # 2. 解析 JSON (配合 logic.py 的新格式)
                    import json
                    try:
                        # 使用 logic 里的清洗工具处理返回的文本
                        raw_json = logic.clean_json_text(resp.text)
                        ai_data = json.loads(raw_json)
                        ai_role = ai_data.get("role", "Narrator")
                        ai_text = ai_data.get("content", "")
                    except:
                        # 如果 AI 没按格式出牌，回退到普通文本
                        ai_role = "Drama"
                        ai_text = resp.text

                    # 3. 存入聊天记录 (显示角色名)
                    st.session_state.messages.append({"role": "assistant", "content": f"**{ai_role}**: {ai_text}"})
                    
                    # 4. 触发语音 (根据 AI 返回的角色自动匹配声音)
                    # 如果返回的是 Guest 就用顾客声，否则用员工声
                    target_speaker = g if "Guest" in ai_role else s
                    
                    audio_bytes = logic.get_azure_speech(
                        ai_text, 
                        gender=target_speaker.get("gender", "女性"), 
                        style="empathetic", 
                        voice_name=target_speaker.get("voice_id")
                    )
                    
                    if audio_bytes:
                        st.session_state.last_audio_data = audio_bytes
                    
                    st.rerun()
                except Exception as e: 
                    st.error(f"脚本生成エラー: {e}")
                    
    else:
        audio_value = st.audio_input("🎤 按下录音 (Record)")
        text_input = st.chat_input("Type message...")
        final_input = None

        # 录音去重逻辑 (保留你原来的代码)
        if audio_value:
            current_audio_hash = hash(audio_value.getvalue())
            if st.session_state.last_audio_id != current_audio_hash:
                with st.spinner("🎧 音声をテキストに変換中..."):
                    transcript = logic.transcribe_audio(audio_value.read())
                    if "[Error" not in transcript:
                        final_input = transcript
                        st.session_state.last_audio_id = current_audio_hash
                    else: st.error(transcript)
        elif text_input:
            final_input = text_input

        # ✅ 5. 发送逻辑 + 动态语音生成
        if final_input:
            st.session_state.messages.append({"role": "user", "content": final_input})
            with st.spinner("Thinking..."):
                try:
                    resp = st.session_state.chat.send_message(final_input)
                    ai_text = resp.text
                    st.session_state.messages.append({"role": "assistant", "content": ai_text})
                    
                    # 🔴 检查这里！确保下面这些行前面没有多余的空格
                    current_style = "customer-service"
                    if any(w in ai_text for w in ["申し訳", "すみません", "お詫び"]):
                        current_style = "empathetic"

                    # 判定发声角色并获取 Voice ID
                    speaker_data = g if role == "staff" else s
                    audio_bytes = logic.get_azure_speech(
                        ai_text, 
                        gender=speaker_data.get("gender", "女性"), 
                        style=current_style, 
                        voice_name=speaker_data.get("voice_id")
                    )
                    
                    if audio_bytes:
                        st.session_state.last_audio_data = audio_bytes
                    
                    st.rerun()
                except Exception as e: 
                    st.error(str(e))

# ==========================================
# 📊 11. Evaluation & Post-test (评价与后测)
# ==========================================
elif st.session_state.nav_page == "eval":
    st.markdown("<div class='main-header'>📊 最終分析レポート</div>", unsafe_allow_html=True)
    
    # --- 1. 获取或生成评价结果 ---
    if not st.session_state.evaluation_result:
        with st.spinner("支配人が接客ログを分析中..."):
            # A. 整理对话文本
            log_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            
            # B. 准备环境锚定信息
            world_ctx = {
                "name": st.session_state.get('active_world_name'),
                "type": st.session_state.get('world_type', 'ホテル'),
                "constraints": st.session_state.get('active_world_constraints'),
                "context": st.session_state.get('active_world_context')
            }
            
            # C. 调用逻辑分析
            result = logic.evaluate_interaction(log_text, world_ctx)
            st.session_state.evaluation_result = result
            
            # D. [经营模拟] 更新酒店评分
            satisfaction_text = result.get('guest_inner_voice', {}).get('satisfaction', '★3')
            guest_stars = utils.parse_stars(satisfaction_text)
            old_r, new_r = utils.update_world_rating(world_ctx["name"], guest_stars)
            st.session_state.rating_change = (old_r, new_r)
            
            # E. [MBA数据] 增加练习次数计数
            st.session_state.total_play_count += 1 

            # F. 保存本地历史
            history_entry = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "world": world_ctx["name"],
                "guest": st.session_state.get('active_guest_name'),
                "score": result.get('manager_review', {}).get('score', 0),
                "status": result.get('manager_review', {}).get('overall_status', 'N/A'),
                "result": result
            }
            utils.add_to_history(history_entry)

    # --- 渲染详细结果 ---
    res = st.session_state.evaluation_result
    m = res.get('manager_review', {})
    g = res.get('guest_inner_voice', {})

    if "error" in res:
        st.error(f"評価エラー: {res['error']}")
    else:
        # === A. 核心得分与经营影响 ===
        st.subheader(f"👨‍💼 支配人の判定: {m.get('overall_status', '評価中')}")
        
        col_score, col_tycoon = st.columns(2)
        with col_score:
            final_score = m.get('score', 0)
            st.metric("総合得点 (AI Score)", f"{final_score} / 100")
            st.progress(final_score / 100)

        with col_tycoon: 
            if "rating_change" in st.session_state:
                old_r, new_r = st.session_state.rating_change
                diff = round(new_r - old_r, 2)
                st.metric(
                    label="🏨 ホテルの評判 (Tycoon Rating)",
                    value=f"{new_r} / 5.0",
                    delta=f"{diff}",
                    delta_color="normal"
                )

        st.divider()

        # === B. LEARN模型分析 ===
        st.subheader("📚 LEARNモデル適用チェック")
        l_analysis = res.get('learn_analysis', {})
        l_cols = st.columns(5)
        learn_steps = [("L", "Listen"), ("E", "Empathize"), ("A", "Apologize"), ("R", "Resolve"), ("N", "Notify")]
        for i, (letter, full) in enumerate(learn_steps):
            l_cols[i].markdown(f"### {letter}")
            l_cols[i].caption(full)
        st.info(f"**LEARN総評**: {l_analysis.get('summary', '分析中...')}")

        st.divider()

        # === C. 玩家行为分析 ===
        st.subheader("👤 プレイヤー分析")
        p_analysis = res.get('player_analysis', {})
        pa_c1, pa_c2 = st.columns([1, 2])
        with pa_c1:
            st.success(f"**タイプ**: {p_analysis.get('type', '標準')}")
        with pa_c2:
            st.write(f"**特徴**: {p_analysis.get('traits', '...')}")
            st.warning(f"🚀 **成長のヒント**: {p_analysis.get('growth_tip', '...')}")

        # === D. 强项弱项 ===
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.success("🌟 **良かった点**")
            for s in m.get('strengths', []): st.write(f"✅ {s}")
        with c2:
            st.error("⚠️ **改善すべき点**")
            for w in m.get('weaknesses', []): st.write(f"❌ {w}")

        # === E. 客人本音 ===
        st.divider()
        with st.expander("😠 お客様の生々しい本音 (Guest Voice)", expanded=False):
            st.write(f"**満足度**: {g.get('satisfaction')}")
            st.write(f"**感情推移**: {g.get('emotional_curve')}")
            st.write(g.get('detailed_comment'))

    st.markdown("---")

    # ==========================================
    # 🧠 Post-test & Gap Analysis (核心MBA模块)
    # ==========================================
    st.subheader("🧠 振り返り & 研究データ送信 (Post-test)")
    st.write("実際のプレイを終えて、**今の実感**として自己採点してください。（0〜100点）")
    st.caption("※ 送信後、事前の自己評価とのギャップ（過信/過小評価）がグラフで表示されます。")

    with st.form("post_test_form"):
        # 10个核心能力维度 (Post-test)
        questions = [
            (3, "把握力: 顧客の困りごとを正確に把握できた"),
            (4, "忍耐力: 怒っている話を最後まで聞けた"),
            (5, "表現力: 声のトーンで誠実さを伝えられた"),
            (6, "共感力: 話しやすい雰囲気をつくれた"),
            (7, "説明力: 事実関係をわかりやすく説明できた"),
            (8, "柔軟性: ルールの中で解決策を練れた"),
            (9, "完結力: 納得感のある締めで終えられた"),
            (10, "精神力: 焦らず自分の意志を伝えられた"),
            (11, "臨場感: 本物のクレームに近い緊張感を感じた"),
            (12, "成長心: 今回の経験は今後に役立つと感じた")
        ]
        
        post_scores = {}
        c1, c2 = st.columns(2)
        for i, (idx, txt) in enumerate(questions):
            with c1 if i < 5 else c2:
                post_scores[f"q{idx}"] = st.slider(f"Q{i+1}. {txt}", 0, 100, 50, step=1, key=f"post_{idx}")

        user_comment = st.text_area("✍️ 自由感想 (任意):", placeholder="例：AIの反応が予想以上に早くて焦った...")

        st.markdown("---")
        submit_cloud = st.form_submit_button("📊 レポート生成 & データ送信 (Submit)", type="primary", use_container_width=True)
        
    # ✅ 重点：这里缩进退回最左边（或者与 with st.form 对齐）
    if submit_cloud:
        st.success("分析レポートを生成しました！")
        
        # ---------------------------------------------------------
        # 1. 绘制 RPG 雷达图 (Gap Analysis)
        # ---------------------------------------------------------
        if st.session_state.get('pre_test_done', False):
            import plotly.graph_objects as go
            
            # 定义 10 个维度
            labels = ["把握", "忍耐", "表現", "共感", "説明", "柔軟", "完結", "精神", "臨場", "成長"]
            
            # 提取数据
            pre_values = []
            post_values = []
            
            for i in range(10): 
                q_key = f"q{i+3}"
                # Pre-test 数据处理
                raw_pre = st.session_state.pre_test_data.get(q_key, 0)
                if raw_pre <= 5 and raw_pre > 0: raw_pre *= 20
                elif raw_pre <= 10 and raw_pre > 0: raw_pre *= 10
                pre_values.append(raw_pre)
                # Post-test 数据
                post_values.append(post_scores.get(q_key, 0))
            
            # 闭环处理
            labels_closed = labels + [labels[0]]
            pre_closed = pre_values + [pre_values[0]]
            post_closed = post_values + [post_values[0]]

            # 绘图
            fig = go.Figure()
            # Before (蓝)
            fig.add_trace(go.Scatterpolar(
                r=pre_closed, theta=labels_closed, fill='toself', 
                name='Before (予想)', line_color='#A0C4FF', opacity=0.6
            ))
            # After (红)
            fig.add_trace(go.Scatterpolar(
                r=post_closed, theta=labels_closed, fill='toself', 
                name='After (実感)', line_color='#FFADAD', opacity=0.7
            ))
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10, color="gray")),
                    bgcolor='rgba(0,0,0,0)'
                ),
                title="📉 能力値ギャップ分析 (Before vs After)",
                margin=dict(l=40, r=40, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("※ Pre-test未実施のため、比較グラフは表示されません。")

        # ---------------------------------------------------------
        # 2. 打包并上传数据
        # ---------------------------------------------------------
        with st.spinner("クラウドに研究データを送信中..."):
            pre = st.session_state.get('pre_test_data', {})
            
            log_data = [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
                st.session_state.get('user_id', 'Guest'),           
                st.session_state.get('user_nickname', 'Unknown'),   
                st.session_state.get('current_role', 'Staff'),      
                st.session_state.get('total_play_count', 1),        
                st.session_state.get('active_world_name'),          
                st.session_state.get('active_guest_name'),          
                final_score,                                        
                
                # Pre-test (Q3-Q10)
                pre.get("q3",0), pre.get("q4",0), pre.get("q5",0), pre.get("q6",0),
                pre.get("q7",0), pre.get("q8",0), pre.get("q9",0), pre.get("q10",0),
                
                # Post-test (Q3-Q12)
                post_scores.get("q3",0), post_scores.get("q4",0), post_scores.get("q5",0), post_scores.get("q6",0), 
                post_scores.get("q7",0), post_scores.get("q8",0), post_scores.get("q9",0), post_scores.get("q10",0), 
                post_scores.get("q11",0), post_scores.get("q12",0),
                
                user_comment,                  
                str(st.session_state.messages) 
            ]
            
            if utils.upload_log_to_cloud(log_data):
                st.toast("✅ データ送信完了！分析ありがとうございました！", icon="🎓")
                st.balloons()
            else:
                st.error("送信失敗。Secrets設定を確認してください。")

    # 返回按钮
    if st.button("🏠 ダッシュボードに戻る", type="secondary", use_container_width=True):
        st.session_state.nav_page = "dashboard"
        st.session_state.messages = []
        st.session_state.evaluation_result = None
        st.rerun()

# ==========================================
# 📜 12. プレイ履歴 (History)
# ==========================================
elif st.session_state.nav_page == "history":
    st.title("📜 プレイ履歴")
    if st.button("⬅️ Dashboardに戻る"): 
        st.session_state.nav_page = "dashboard"
        st.rerun()
    
    # 重新加载数据
    hist = utils.load_json(utils.HISTORY_FILE)
    
    if not hist:
        st.info("履歴はまだありません。")
    else:
        # ✅ 修复点 1：使用 enumerate 获取序号 i
        for i, h in enumerate(hist):
            # 标题显示时间、酒店和得分
            label = f"📅 {h.get('timestamp')} | {h.get('world')} | 得点: {h.get('score')}点"
            with st.expander(label):
                col1, col2 = st.columns(2)
                col1.write(f"**👤 お客様**: {h.get('guest')}")
                col1.write(f"**🏆 ランク**: {h.get('status')}")
                
                detail = h.get('result', {})
                advice = detail.get('manager_review', {}).get('advice', 'アドバイスなし')
                col2.write(f"**💡 アドバイス**: {advice}")
                
                # ✅ 修复点 2：添加唯一的 key
                # 这样即使时间戳一模一样，Streamlit 也能分清这是第几个按钮
                if st.button(f"詳細データを確認 ({h.get('timestamp')})", key=f"hist_btn_{i}"):
                    st.json(detail)

