import streamlit as st
import math
import re
import os
import uuid
import random
import hashlib
from datetime import datetime, timezone, timedelta
from PIL import Image
from google import genai
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController

# --- STYLING ---
bg_url = "https://github.com/derivkiller808-debug/ai-trading-terminal/raw/main/download.png"
st.markdown(f"""
<style>
    .stApp {{ background-image: url("{bg_url}"); background-size: cover; background-color: #0e1117 !important; }}
    [data-testid="stSidebar"] {{ background-color: #0e1117 !important; border-right: 1px solid #2d313e; }}
    h1, h2, h3, h4, h5, h6 {{ color: #00E5A0 !important; font-family: 'Courier New', monospace; }}
    p, li, span, label, div {{ color: #c084fc !important; }}
    input, textarea, [data-baseweb="select"] > div {{ background-color: #1a1f2e !important; color: #ffffff !important; border-color: #c084fc !important; }}
    .stButton>button {{ background-color: rgba(0, 200, 83, 0.5) !important; color: #000 !important; font-weight: bold; border: 1px solid rgba(0, 200, 83, 0.8) !important; border-radius: 5px; transition: all 0.2s ease; }}
    .stButton>button:hover {{ background-color: rgba(0, 200, 83, 0.7) !important; }}
    [data-testid="stFileUploader"] {{ background-color: #1a1f2e !important; border: 1px solid #c084fc !important; border-radius: 10px; padding: 10px; }}
    .stProgress > div > div > div > div {{ background-color: #c084fc !important; }}
    .stSpinner > div {{ box-shadow: 0 0 25px rgba(0, 200, 83, 0.8); border: 2px solid #00C853; border-radius: 50%; animation: pulseGlow 1.5s infinite ease-in-out; }}
    @keyframes pulseGlow {{ 0% {{ box-shadow: 0 0 10px rgba(0, 200, 83, 0.4); }} 50% {{ box-shadow: 0 0 30px rgba(0, 200, 83, 0.9); }} 100% {{ box-shadow: 0 0 10px rgba(0, 200, 83, 0.4); }} }}
    footer {{visibility: hidden;}}
    [data-testid="stMarkdownContainer"] {{ word-break: break-word; overflow-wrap: anywhere; }}
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown("<h1 style='color: #00E5A0; font-family: \"Courier New\", monospace; text-align: left;'>🧠 The Brilliant Trader's AI Terminal</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #c084fc; font-family: \"Courier New\", monospace;'>Upload 3 Charts. Full AI Analysis, Auto-Calculated Risk.</p>", unsafe_allow_html=True)

# --- SETUP ---
try:
    KEYS_LIST = [k.strip() for k in st.secrets["GEMINI_API_KEYS"].split(",") if k.strip()]
    if len(KEYS_LIST) == 0: st.error("❌ No keys found! Please check Settings -> Secrets."); st.stop()
except Exception as e: st.error(f"❌ Missing GEMINI_API_KEYS in Settings -> Secrets. Error: {e}"); st.stop()

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    supabase_connected = True
except: supabase_connected = False

# --- COOKIE DEVICE TRACKING ---
cookies = CookieController()
device_id = cookies.get("brilliant_trader_device_id")
if not device_id:
    device_id = "device-" + str(uuid.uuid4())
    cookies.set("brilliant_trader_device_id", device_id, max_age=31536000)

st.session_state.session_id = device_id
if 'total_users' not in st.session_state: st.session_state.total_users = 0
if 'active_users' not in st.session_state: st.session_state.active_users = 0

def track_visit():
    if supabase_connected:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            supabase.table('app_visits').upsert({'session_id': st.session_state.session_id, 'last_seen': now_iso}).execute()
            total = supabase.table('app_visits').select('*', count='exact').execute()
            st.session_state.total_users = total.count
            active_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            active = supabase.table('app_visits').select('*', count='exact').gte('last_seen', active_cutoff).execute()
            st.session_state.active_users = active.count
        except: pass
track_visit()

# --- USAGE COUNTER LOGIC ---
USAGE_FILE = "usage_count.txt"
DAILY_LIMIT = 20
TOTAL_LIMIT = len(KEYS_LIST) * DAILY_LIMIT
def get_usage_count():
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            try: return int(f.read().strip())
            except: return 0
    return 0
def increment_usage():
    count = get_usage_count()
    with open(USAGE_FILE, "w") as f: f.write(str(count + 1))
    return count + 1

# --- SAFE FLOAT ---
def safe_float(s):
    if not s: return None
    s = s.replace(',', '').strip()
    if s.upper() == 'N/A' or s == '': return None
    try: return float(s)
    except: return None

# --- HELPERS TO KEEP HTML CLEAN ---
def clean_text(text):
    if not text: return ""
    text = text.replace('`', '')
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return text

def clean_analysis(text):
    text = re.sub(r'(?<=\d)\s+(?=\d)', '', text)
    text = re.sub(r'(?<=\w)\s+(?=\w)', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\.(?=[A-Z])', '. ', text)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    text = text.replace("Pricehas", "Price has")
    text = text.replace("Priceis", "Price is")
    text = text.replace("4H Trend Analysis:", "\n\n**4H Trend Analysis:**")
    text = text.replace("30M Pattern Analysis:", "\n\n**30M Pattern Analysis:**")
    text = text.replace("5M Sniper Entry:", "\n\n**5M Sniper Entry:**")
    text = text.replace("Final Verdict:", "\n\n**Final Verdict:**")
    text = text.replace("Speculative Setup:", "\n\n**🚨 SPECULATIVE SETUP:**")
    return text

# --- SYMBOLS & SESSION ---
placeholder = "Select Instrument..."
symbol_options = [placeholder, "BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD (Forex)"]
if 'entry_field' not in st.session_state: st.session_state.entry_field = ""
if 'sl_field' not in st.session_state: st.session_state.sl_field = ""
if 'tp_field' not in st.session_state: st.session_state.tp_field = ""
if 'auto_symbol' not in st.session_state: st.session_state.auto_symbol = placeholder
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None

# --- PARSING ---
def parse_ai_response(text):
    symbol_match = re.search(r"Symbol\s*[::=]\s*([A-Z]+)", text, re.IGNORECASE)
    direction_match = re.search(r"Direction\s*[::=]\s*(BUY|SELL|NEUTRAL)", text, re.IGNORECASE)
    entry_match = re.search(r"Entry(?:\s*Price)?\s*[::=]\s*([\d,]+(?:\.\d+)?|N/A)", text, re.IGNORECASE)
    sl_match = re.search(r"Stop\s*Loss\s*[::=]\s*([\d,]+(?:\.\d+)?|N/A)", text, re.IGNORECASE)
    tp_match = re.search(r"Take\s*Profit\s*[::=]\s*([\d,]+(?:\.\d+)?|N/A)", text, re.IGNORECASE)
    
    if entry_match and sl_match and tp_match:
        sym = symbol_match.group(1).upper() if symbol_match else "BTCUSD"
        if sym in ["XAUUSD", "GOLD"]: sym = "XAUUSD (Gold)"
        elif sym in ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"]: sym = "EURUSD (Forex)"
        else: sym = "BTCUSD (Bitcoin)"
        direction = direction_match.group(1).upper() if direction_match else "NEUTRAL"
        entry = safe_float(entry_match.group(1))
        sl = safe_float(sl_match.group(1))
        tp = safe_float(tp_match.group(1))
        if entry is None or sl is None or tp is None:
            return {'symbol': sym, 'direction': direction, 'entry': None, 'sl': None, 'tp': None}
        return {'symbol': sym, 'direction': direction, 'entry': entry, 'sl': sl, 'tp': tp}
    return None

def parse_top3_all(text):
    top3_block = re.search(r"TOP 3 SPECULATIVE SETUPS.*", text, re.IGNORECASE | re.DOTALL)
    if not top3_block:
        return []
    block = top3_block.group(0)
    items = re.split(r'\n(?=\d\.)', block)
    setups = []
    for item in items:
        if not re.search(r'Entry\s*[:=]?\s*[\d,]+', item):
            continue
        entry_match = re.search(r"Entry\s*[:=]?\s*([\d,]+(?:\.\d+)?)", item, re.IGNORECASE)
        sl_match = re.search(r"Stop\s*Loss\s*[:=]?\s*([\d,]+(?:\.\d+)?)", item, re.IGNORECASE)
        tp_match = re.search(r"Take\s*Profit\s*[:=]?\s*([\d,]+(?:\.\d+)?)", item, re.IGNORECASE)
        if entry_match and sl_match and tp_match:
            e = safe_float(entry_match.group(1))
            s = safe_float(sl_match.group(1))
            t = safe_float(tp_match.group(1))
            if e and s and t:
                desc = item.strip()
                # Determine direction from the description (Buy when / Sell when)
                if "Buy when" in desc or "buy" in desc.lower():
                    spec_direction = "BUY"
                elif "Sell when" in desc or "sell" in desc.lower():
                    spec_direction = "SELL"
                else:
                    spec_direction = "NEUTRAL"
                setups.append({'desc': clean_text(desc), 'entry': e, 'sl': s, 'tp': t, 'spec_direction': spec_direction})
    return setups[:3]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Risk Dashboard")
    account_balance = st.number_input("Account Balance ($)", min_value=1.0, value=80.0, step=10.0)
    leverage = st.number_input("Leverage (Default 400)", min_value=1.0, value=400.0, step=10.0)
    risk_percent = st.slider("Risk % of Account", min_value=0.1, max_value=100.0, value=1.0, step=0.1)
    st.divider()
    st.markdown("### 👥 Community Stats")
    st.markdown(f"🟢 **Active (24h):** {st.session_state.active_users}")
    st.markdown(f"👤 **Total Users:** {st.session_state.total_users}")
    st.divider()
    st.markdown(f"⚙️ **Keys Loaded:** {len(KEYS_LIST)}")
    st.divider()

    st.subheader("📈 Upload 3 Charts : 4HR , 30MIN , 5MIN")
    col1, col2, col3 = st.columns(3)
    with col1: chart1 = st.file_uploader("Chart 1", type=["png", "jpg", "jpeg"], key="chart_1")
    with col2: chart2 = st.file_uploader("Chart 2", type=["png", "jpg", "jpeg"], key="chart_2")
    with col3: chart3 = st.file_uploader("Chart 3", type=["png", "jpg", "jpeg"], key="chart_3")
    
    uploaded_files = [x for x in [chart1, chart2, chart3] if x is not None]

st.divider()

# --- AI ANALYSIS ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    if st.button("Run Top-Trader Analysis"):

        if len(uploaded_files) != 3:
            st.markdown(f"""
            <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4); text-align: center;">
                <p style="color: #f9e79f; font-weight: bold; font-size: 16px; margin: 0;">⚠️ ERROR: Invalid Image Count</p>
                <p style="color: #f9e79f; font-size: 16px; margin: 5px 0;">You must fill exactly 3 upload spaces (Chart 1, Chart 2, and Chart 3) to proceed.</p>
                <p style="color: #f9e79f; font-size: 16px; margin: 0;">Please re-upload the correct number of images.</p>
            </div>
            """, unsafe_allow_html=True)
            st.stop()

        if os.path.exists(USAGE_FILE): os.remove(USAGE_FILE)
        hasher = hashlib.sha256()
        for file in uploaded_files: hasher.update(file.getvalue())
        image_hash = hasher.hexdigest()
        
        if supabase_connected:
            try:
                response = supabase.table('analysis_cache').select('*').eq('hash', image_hash).execute()
                if response.data:
                    cached = response.data[0]['result']
                    st.session_state.analysis_result = cached['text']
                    st.session_state.auto_symbol = cached['symbol']
                    st.session_state.entry_field = cached['entry']
                    st.session_state.sl_field = cached['sl']
                    st.session_state.tp_field = cached['tp']
                    st.success("🔒 Permanent Cloud Memory hit! Returning identical result.")
                    st.rerun()
            except: pass

        # --- UPDATED PROMPT: OB/BB Priority ---
        system_prompt = """
        You are a legendary, mathematically precise, and exceptionally risk-averse trading strategist with 50 years of experience.

        You are provided with 3 charts.

        **CRITICAL VALIDATION RULES:**
        Before analyzing, validate the 3 images. Do all images have the matching symbol? Are the timeframes clearly 4H, 30M, and 5M? Are they zoomed out well?
        **Output Validation Status at the very top:**
        Validation: PASS  OR  Validation: FAIL
        Validation Error(s): (List reasons if FAIL, otherwise state "None")

        **HARD RULES:**
        Do not trade counter-trend. If 4H is Bearish, only SELL. If 4H is Bullish, only BUY.
        If 4H, 30M, and 5M do NOT agree, output NEUTRAL.
        If TP distance is NOT at least 2x SL distance, output NEUTRAL.
        If chart is choppy or unclear, output NEUTRAL.

        **OUTPUT FORMAT:**
        **📊 4H Trend Analysis:** (Break down macro bias and S/R levels).
        **🧩 30M Pattern Analysis:** (Identify exact pattern or structure).
        **🎯 5M Sniper Entry:** (Point out exact liquidity grab or order block).
        **⚖️ Final Verdict:** (State BUY, SELL, or NEUTRAL).

        **IF YOU SAY NEUTRAL (SPECULATIVE SETUP SECTION):**
        You MUST provide a **🚨 SPECULATIVE SETUP:** section immediately after the verdict.
        - First, brainstorm **EXACTLY TEN (10) individual speculative setups** that could support an entry. Use "Buy when..." or "Sell when..." for each. Number them 1 to 10. They do NOT have to happen all at the same time.
        - Then, evaluate those 10 setups based on **highest probability** and **best risk-to-reward ratio**.
        - Finally, write the **BEST THREE** setups in a new section starting with: **🔥 TOP 3 SPECULATIVE SETUPS:**
        
        **CRITICAL RANKING RULE:**
        When you rank the setups to pick the TOP 3, you MUST ensure that the **#1 setup** is the one that involves **Order Blocks (OB)** or **Breaker Blocks (BB)**. If there is a setup that uses OB/BB, it must be placed at number 1. If no OB/BB setup exists, use the highest probability setup.
        
        **For EACH of the TOP 3 setups, you MUST provide:**
        - A brief trigger description (e.g., "Buy when price sweeps 77,300 at the Order Block")
        - An explicit "Entry:", "Stop Loss:", and "Take Profit:" with numeric values.

        **CRITICAL FORMAT INSTRUCTION (for the entire response):**
        Regardless of your Final Verdict (BUY, SELL, or NEUTRAL), you MUST finish your ENTIRE response with exactly these 5 lines, in this order, using the exact labels below. If your verdict is NEUTRAL, write N/A for Entry, Stop Loss, and Take Profit.
        Symbol:
        Direction: (BUY, SELL, or NEUTRAL)
        Entry: (Value or N/A)
        Stop Loss: (Value or N/A)
        Take Profit: (Value or N/A)

        DO NOT calculate lot sizes, leverage, or margin.
        """

        try:
            images = [Image.open(file) for file in uploaded_files]
            with st.spinner("Analyzing..."):
                st.markdown("""
                <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 20px; margin-top: 10px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4);">
                    <h4 style="color: #f9e79f; margin: 0;">📊 AI Analysis Summary</h4>
                    <p style="color: #f9e79f; margin: 5px 0;">Loading... Please wait a few seconds while the AI scans the charts.</p>
                </div>
                """, unsafe_allow_html=True)

                random.shuffle(KEYS_LIST)
                ai_text = None

                for key in KEYS_LIST:
                    try:
                        client = genai.Client(api_key=key)
                        chat = client.chats.create(model="gemini-3.6-flash")
                        response = chat.send_message(message=[system_prompt, *images], config=genai.types.GenerateContentConfig(temperature=0.0))
                        ai_text = response.text
                        increment_usage()
                        break
                    except Exception:
                        continue

                if ai_text is None:
                    st.markdown(f"""
                    <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4); text-align: center;">
                        <p style="color: #f9e79f; font-weight: bold; font-size: 16px; margin: 0;">🛑 AI CONNECTION ERROR</p>
                        <p style="color: #f9e79f; font-size: 16px; margin: 5px 0;">All keys are exhausted right now. Please wait 30 seconds and try again.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.stop()

                if re.search(r"Validation:\s*FAIL", ai_text, re.IGNORECASE):
                    error_match = re.search(r"Validation Error\(s\):(.*)", ai_text, re.IGNORECASE)
                    errors = error_match.group(1).strip() if error_match else "The uploaded charts do not meet the requirements."
                    st.markdown(f"""
                    <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4); text-align: center;">
                        <p style="color: #f9e79f; font-weight: bold; font-size: 16px; margin: 0;">⚠️ ERROR: Image Validation Failed</p>
                        <p style="color: #f9e79f; font-size: 16px; margin: 5px 0;">{clean_text(errors)}</p>
                        <p style="color: #f9e79f; font-size: 16px; margin: 0;">Please re-upload the correct charts with matching symbols and try again.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.stop()

                parsed_data = parse_ai_response(ai_text)

                direction = "NEUTRAL"
                symbol = "BTCUSD (Bitcoin)"
                entry = sl = tp = None
                reasoning = ""
                top3_list = []

                if parsed_data and parsed_data['direction'] != "NEUTRAL":
                    direction = parsed_data['direction']
                    symbol = parsed_data['symbol']
                    entry = parsed_data['entry']
                    sl = parsed_data['sl']
                    tp = parsed_data['tp']
                    reasoning = ai_text.split("Symbol:")[0] if "Symbol:" in ai_text else ai_text
                else:
                    top3_list = parse_top3_all(ai_text)
                    if parsed_data and parsed_data['symbol']:
                        symbol = parsed_data['symbol']
                    reasoning = ai_text
                    
                    # #1 setup should be the OB/BB one (automatically ensured by prompt, but let's verify)
                    if top3_list and top3_list[0].get('spec_direction'):
                        direction = top3_list[0]['spec_direction']  # This will be "BUY" or "SELL"

                st.session_state.summary_data = {
                    'direction': direction,
                    'symbol': symbol,
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'reasoning': reasoning,
                    'top3_list': top3_list
                }

                # Auto-fill calculator with first setup if NEUTRAL
                if direction in ["BUY", "SELL"] and top3_list:
                    st.session_state.auto_symbol = symbol
                    st.session_state.entry_field = f"{top3_list[0]['entry']:.2f}"
                    st.session_state.sl_field = f"{top3_list[0]['sl']:.2f}"
                    st.session_state.tp_field = f"{top3_list[0]['tp']:.2f}"

                # Save to Supabase if entry exists
                if entry and sl and tp:
                    if supabase_connected:
                        try:
                            cache_data = {'text': reasoning, 'symbol': symbol, 'entry': f"{entry:.2f}", 'sl': f"{sl:.2f}", 'tp': f"{tp:.2f}"}
                            supabase.table('analysis_cache').upsert({'hash': image_hash, 'result': cache_data}).execute()
                        except: pass
                elif top3_list:
                    if supabase_connected:
                        try:
                            cache_data = {'text': reasoning, 'symbol': symbol, 'entry': f"{top3_list[0]['entry']:.2f}", 'sl': f"{top3_list[0]['sl']:.2f}", 'tp': f"{top3_list[0]['tp']:.2f}"}
                            supabase.table('analysis_cache').upsert({'hash': image_hash, 'result': cache_data}).execute()
                        except: pass

                # Show speculative setup details (if any)
                full_text = clean_analysis(ai_text)
                split_marker = "🚨 SPECULATIVE SETUP:"
                if split_marker in full_text:
                    main_analysis, spec_part = full_text.split(split_marker, 1)
                else:
                    main_analysis, spec_part = full_text, ""

                if spec_part:
                    top3_text = spec_part
                    full_list_text = spec_part
                    if "🔥 TOP 3 SPECULATIVE SETUPS:" in spec_part:
                        full_list_text, top3_text = spec_part.split("🔥 TOP 3 SPECULATIVE SETUPS:", 1)
                        top3_text = "🔥 TOP 3 SPECULATIVE SETUPS:" + top3_text

                    st.markdown(f"""
                    <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4); text-align: center;">
                        <p style="color: #f9e79f; font-weight: bold; font-size: 16px; margin: 0;">Scanned '{clean_text(symbol.split()[0])}' Successfully. AI speculations and high probability entries are below</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                    <div style="border: 2px solid #c084fc; background: linear-gradient(145deg, #1a1f2e, #2d1b4e); border-radius: 15px; padding: 20px; margin-top: 10px; box-shadow: 0 0 20px rgba(192, 132, 252, 0.3);">
                        <div style="color: #d8b4fe !important; line-height: 1.6; font-size: 15px;">{clean_text(main_analysis.strip())}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 20px; margin-top: 10px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4);">
                        <div style="font-size: 18px; font-weight: bold; color: #f9e79f !important; margin-bottom: 10px;">🏆 TOP 3 HIGHEST PROBABILITY SETUPS</div>
                        <div style="color: #f9e79f !important; line-height: 1.6; font-size: 15px;">{clean_text(top3_text.strip())}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown(f"""
                    <div style="border: 2px solid #c084fc; background: linear-gradient(145deg, #1a1f2e, #2d1b4e); border-radius: 15px; padding: 15px; margin-top: 10px; box-shadow: 0 0 20px rgba(192, 132, 252, 0.4); text-align: left;">
                        <div style="color: #d8b4fe !important; line-height: 1.5; font-size: 14px;"><strong>Full List of 10 Setups for Reference:</strong><br>{clean_text(full_list_text.strip())}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.info("These are NOT active trades. Only enter if the market reaches the exact conditions described in the Top 3. You can manually type the levels into the calculator below once the trigger is confirmed.")

                st.rerun()

        except Exception as e:
            st.error(f"❌ AI Error: {e}")

# --- FINAL SUMMARY BOX (ONLY ONE, GUARANTEED CLEAN) ---
if 'summary_data' in st.session_state:
    data = st.session_state.summary_data
    direction = data['direction']
    symbol = data['symbol']
    entry = data['entry']
    sl = data['sl']
    tp = data['tp']
    reasoning = clean_text(data['reasoning'])
    top3_list = data.get('top3_list', [])

    # CHANGE LABEL: "SPECULATIVE BUY" or "SPECULATIVE SELL" for neutral
    if direction == "BUY":
        # If it came from top3, it's speculative; if from direct, it's real.
        if top3_list:
            dir_label = "SPECULATIVE BUY"
        else:
            dir_label = "BUY"
        dir_color = "#00FF00"
    elif direction == "SELL":
        if top3_list:
            dir_label = "SPECULATIVE SELL"
        else:
            dir_label = "SELL"
        dir_color = "#FF0000"
    else:
        dir_label = "SPECULATIVE"
        dir_color = "#FFD700"
    
    sl_color = "#FF0000"; tp_color = "#00FF00"

    if top3_list:
        setups_html = ""
        for i, setup in enumerate(top3_list, 1):
            desc = clean_text(setup['desc'])
            setups_html += f"""
            <div style="border: 1px solid #f1c40f; border-radius: 8px; padding: 10px; margin-top: 10px;">
                <p style="color: #f9e79f; font-weight: bold; margin: 0;">Setup {i}: {desc}</p>
                <p style="color: white; margin: 5px 0;">Entry: {setup['entry']:.2f}</p>
                <p style="color: {sl_color}; margin: 5px 0;">Stop Loss: {setup['sl']:.2f}</p>
                <p style="color: {tp_color}; margin: 5px 0;">Take Profit: {setup['tp']:.2f}</p>
            </div>
            """
        html = f"""
        <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 20px; margin-top: 10px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4);">
            <div style="font-size: 18px; font-weight: bold; color: #f9e79f !important; margin-bottom: 10px;">📊 AI Analysis Summary</div>
            <p><b style="color: {dir_color}; margin: 0;">Direction: {dir_label}</b></p>
            <p><b style="color: #c084fc; margin: 0;">Symbol: {symbol}</b></p>
            {setups_html}
            <div style="margin-top: 15px; border-top: 1px solid #f1c40f; padding-top: 10px;">
                <b style="color: #f9e79f;">Reasoning / Speculative Analysis:</b>
                <p style="color: #f9e79f;">{reasoning}</p>
            </div>
        </div>
        """
    else:
        entry_str = f"{entry:.2f}" if entry else "N/A"
        sl_str = f"{sl:.2f}" if sl else "N/A"
        tp_str = f"{tp:.2f}" if tp else "N/A"
        html = f"""
        <div style="border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 20px; margin-top: 10px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4);">
            <div style="font-size: 18px; font-weight: bold; color: #f9e79f !important; margin-bottom: 10px;">📊 AI Analysis Summary</div>
            <p><b style="color: {dir_color}; margin: 0;">Direction: {dir_label}</b></p>
            <p><b style="color: #c084fc; margin: 0;">Symbol: {symbol}</b></p>
            <p><b style="color: white; margin: 0;">Entry: {entry_str}</b></p>
            <p><b style="color: {sl_color}; margin: 0;">Stop Loss: {sl_str}</b></p>
            <p><b style="color: {tp_color}; margin: 0;">Take Profit: {tp_str}</b></p>
            <div style="margin-top: 15px; border-top: 1px solid #f1c40f; padding-top: 10px;">
                <b style="color: #f9e79f;">Reasoning / Speculative Analysis:</b>
                <p style="color: #f9e79f;">{reasoning}</p>
            </div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)
    
    # Clear the data so it doesn't show again on refresh
    del st.session_state.summary_data

st.divider()

# --- AUTO-FILLING MULTI-SYMBOL CALCULATOR ---
st.subheader("🧮 Auto-Calculating Precision Calculator")
st.caption("Values fill automatically after analysis. You can manually override them.")

col1, col2 = st.columns(2)
with col1:
    try: default_index = symbol_options.index(st.session_state.auto_symbol)
    except (ValueError, AttributeError): default_index = 0
    
    instrument = st.selectbox("Select Instrument (Auto-filled by AI)", symbol_options, index=default_index)
    entry_input = st.text_input("Entry Price", key="entry_field")
    stop_loss_input = st.text_input("Stop Loss", key="sl_field")
    take_profit_input = st.text_input("Take Profit", key="tp_field")

if instrument == placeholder:
    st.info("Select an instrument to start calculating after analysis.")
else:
    try:
        entry_price = float(entry_input) if entry_input else 0.0
        stop_loss = float(stop_loss_input) if stop_loss_input else 0.0
        take_profit = float(take_profit_input) if take_profit_input else 0.0
    except: entry_price, stop_loss, take_profit = 0.0, 0.0, 0.0

    contract_sizes = {"BTCUSD (Bitcoin)": 1.0, "XAUUSD (Gold)": 100.0, "EURUSD (Forex)": 100000.0}
    contract_size = contract_sizes[instrument]

    if entry_price > 0 and stop_loss > 0 and take_profit > 0:
        risk_amount = account_balance * (risk_percent / 100)
        price_diff = abs(entry_price - stop_loss)
        position_size = risk_amount / price_diff
        margin_required = (position_size * entry_price) / leverage
        lot_size = math.floor((position_size / contract_size) * 100) / 100
        potential_profit = abs(take_profit - entry_price) * position_size
        rr_ratio = (abs(take_profit - entry_price)) / price_diff

        st.success("--- LIVE RESULTS ---")
        st.write(f"💼 **Account:** ${account_balance:,.2f} | **Lev:** {leverage:.0f}x | **Risk:** {risk_percent}% (${risk_amount:.2f})")
        if lot_size < 0.01: st.error(f"⚠️ Risk amount (${risk_amount:.2f}) is too small for 0.01 lots.")
        else: st.markdown(f"### 📊 Trade **{lot_size:.2f} Lots** (Min 0.01)")
        st.write(f"🏦 **Margin Required:** ${margin_required:,.2f}")
        st.write(f"🎯 **Potential Profit:** ${potential_profit:,.2f}")
        st.write(f"📈 **Risk-Reward Ratio:** 1 : {rr_ratio:.2f}")

# --- FOOTER ---
st.divider()
st.markdown("""
<div style="color: #00E5A0; text-align: center; font-family: 'Courier New', monospace;">
    <h3 style="color: #00E5A0;">Created by Alex Nderitu</h3>
    <p style="color: #c084fc;">Whatsapp +254759914001 for Further Assistance.</p>
</div>
""", unsafe_allow_html=True)
