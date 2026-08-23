import streamlit as st
import math
import re
import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from PIL import Image
from google import genai
from supabase import create_client, Client
import streamlit.components.v1 as components

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
    .analysis-box {{ border: 2px solid #c084fc; background: linear-gradient(145deg, #1a1f2e, #2d1b4e); border-radius: 15px; padding: 20px; margin-top: 10px; box-shadow: 0 0 20px rgba(192, 132, 252, 0.3); }}
    .analysis-text {{ color: #d8b4fe !important; line-height: 1.6; font-size: 15px; }}
    .gold-warning-box {{ border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4); text-align: center; }}
    .gold-warning-text {{ color: #f9e79f !important; font-weight: bold; font-size: 16px; line-height: 1.5; }}
    .spec-box {{ border: 2px solid #f1c40f; background: linear-gradient(145deg, #4e342e, #6d4c41); border-radius: 15px; padding: 20px; margin-top: 10px; box-shadow: 0 0 25px rgba(241, 196, 15, 0.4); }}
    .spec-header {{ font-size: 18px; font-weight: bold; color: #f9e79f !important; margin-bottom: 10px; font-family: 'Courier New', monospace; }}
    .spec-text {{ color: #f9e79f !important; line-height: 1.6; font-size: 15px; }}
    .info-box {{ border: 2px solid #c084fc; background: linear-gradient(145deg, #1a1f2e, #2d1b4e); border-radius: 15px; padding: 15px; margin-top: 10px; box-shadow: 0 0 20px rgba(192, 132, 252, 0.4); text-align: left; }}
    .info-text {{ color: #d8b4fe !important; line-height: 1.5; font-size: 14px; }}
    footer {{visibility: hidden;}}
    [data-testid="stMarkdownContainer"] {{ word-break: break-word; overflow-wrap: anywhere; }}
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown("<h1 style='color: #00E5A0; font-family: \"Courier New\", monospace; text-align: left;'>🧠 The Brilliant Trader's AI Terminal</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #c084fc; font-family: \"Courier New\", monospace;'>Upload 4H, 30M, 5M. Full AI Analysis, Auto-Calculated Risk.</p>", unsafe_allow_html=True)

# --- SETUP ---
try:
    KEYS_LIST = [k.strip() for k in st.secrets["GEMINI_API_KEYS"].split(",") if k.strip()]
    if len(KEYS_LIST) == 0:
        st.error("❌ No keys found! Please check Settings -> Secrets.")
        st.stop()
except Exception as e:
    st.error(f"❌ Missing GEMINI_API_KEYS in Settings -> Secrets. Error: {e}")
    st.stop()

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    supabase_connected = True
except:
    supabase_connected = False

# --- NEW: PERMANENT DEVICE TRACKING (LocalStorage) ---
# Inject JS to get or create a persistent Device ID in the browser
device_id_js = """
<script>
const existingID = localStorage.getItem('brilliant_trader_device_id');
const deviceID = existingID || 'device-' + Date.now() + '-' + Math.random().toString(16).substr(2, 8);
localStorage.setItem('brilliant_trader_device_id', deviceID);
window.parent.postMessage({type: "streamlit:setComponentValue", value: deviceID}, "*");
</script>
"""
device_id_component = components.html(device_id_js, height=0, width=0)

# Use the persistent ID. If the JS hasn't loaded yet (first millisecond), generate a temporary one.
if device_id_component:
    st.session_state.session_id = device_id_component
else:
    # Fallback for the very first load if JS hasn't returned yet
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

if 'total_users' not in st.session_state: st.session_state.total_users = 0
if 'active_users' not in st.session_state: st.session_state.active_users = 0

def track_visit():
    if supabase_connected:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            # Using the persistent Device ID
            supabase.table('app_visits').upsert({'session_id': st.session_state.session_id, 'last_seen': now_iso}).execute()
            total = supabase.table('app_visits').select('*', count='exact').execute()
            st.session_state.total_users = total.count
            active_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            active = supabase.table('app_visits').select('*', count='exact').gte('last_seen', active_cutoff).execute()
            st.session_state.active_users = active.count
        except:
            pass

# Run tracking
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
    with open(USAGE_FILE, "w") as f:
        f.write(str(count + 1))
    return count + 1

# --- TEXT CLEANER ---
def clean_analysis(text):
    text = re.sub(r'(?<=\d)\s+(?=\d)', '', text)
    text = re.sub(r'(?<=\w)\s+(?=\w)', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\.(?=[A-Z])', '. ', text)
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    text = text.replace("Pricehas", "Price has")
    text = text.replace("Priceis", "Price is")
    text = text.replace("Pricewill", "Price will")
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
    symbol_match = re.search(r"Symbol:\s*([A-Z]+)", text, re.IGNORECASE)
    direction_match = re.search(r"Direction:\s*(BUY|SELL|NEUTRAL)", text, re.IGNORECASE)
    entry_match = re.search(r"Entry:\s*([\d.]+)", text, re.IGNORECASE)
    sl_match = re.search(r"Stop Loss:\s*([\d.]+)", text, re.IGNORECASE)
    tp_match = re.search(r"Take Profit:\s*([\d.]+)", text, re.IGNORECASE)
    
    if entry_match and sl_match and tp_match:
        sym = symbol_match.group(1).upper() if symbol_match else "BTCUSD"
        if sym in ["XAUUSD", "GOLD"]: sym = "XAUUSD (Gold)"
        elif sym in ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"]: sym = "EURUSD (Forex)"
        else: sym = "BTCUSD (Bitcoin)"
        direction = direction_match.group(1).upper() if direction_match else "NEUTRAL"
        return {'symbol': sym, 'direction': direction, 'entry': float(entry_match.group(1)), 'sl': float(sl_match.group(1)), 'tp': float(tp_match.group(1))}
    return None

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
    st.subheader("📈 Upload Charts")
    uploaded_files = st.file_uploader("Upload Exactly 3 Charts (4H, 30M, 5M)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- AI ANALYSIS (3-VOTE CONSENSUS) ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    if st.button("Run Top-Trader Analysis"):
        if os.path.exists(USAGE_FILE): os.remove(USAGE_FILE)

        hasher = hashlib.sha256()
        for file in uploaded_files:
            hasher.update(file.getvalue())
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
            except:
                pass

        # THE UPDATED PROMPT (3 Individual Occurrences)
        system_prompt = """
        You are a legendary, mathematically precise, and exceptionally risk-averse trading strategist with 50 years of experience.

        You are provided with 3 charts: 4H, 30M, and 5M.

        **HARD RULES:**
        1. **TREND FILTER:** Do not trade counter-trend. If 4H is Bearish, only SELL. If 4H is Bullish, only BUY.
        2. **CONFLUENCE FILTER:** If 4H, 30M, and 5M do NOT agree on direction, output NEUTRAL.
        3. **RISK TO REWARD FILTER:** If TP distance is NOT at least 2x SL distance, output NEUTRAL.
        4. **QUALITY FILTER:** If chart is choppy or unclear, output NEUTRAL.

        **OUTPUT FORMAT:**
        **📊 4H Trend Analysis:** (Break down macro bias and S/R levels).
        **🧩 30M Pattern Analysis:** (Identify exact pattern or structure).
        **🎯 5M Sniper Entry:** (Point out exact liquidity grab or order block).
        **⚖️ Final Verdict:** (State BUY, SELL, or NEUTRAL).
        
        **IF YOU SAY NEUTRAL:**
        You MUST provide a **🚨 SPECULATIVE SETUP:** section immediately after the verdict.
        
        **CRITICAL REQUIREMENT:**
        List the **THREE (3) individual occurrences** that would support an entry. These should be listed as a numbered list (1, 2, 3). They do NOT have to happen all at the same time. Each is an independent trigger that supports the trade.
        - Example: (1) If price sweeps 77,300, (2) If a wick rejection forms on the 5M chart, (3) If the 30M trend begins to shift bullish.
        - **Important:** State clearly: "If all three occur simultaneously, it is a high-probability setup."

        **IMPORTANT:** Do NOT include the Entry, Stop Loss, or Take Profit labels at the end if your verdict is NEUTRAL. Only include the Symbol and Direction: NEUTRAL labels.

        **End your response with exactly these labels on new lines (no extra text after them):**
        Symbol:
        Direction: (BUY, SELL, or NEUTRAL)
        Entry: (Leave blank if NEUTRAL)
        Stop Loss: (Leave blank if NEUTRAL)
        Take Profit: (Leave blank if NEUTRAL)

        DO NOT calculate lot sizes, leverage, or margin.
        """

        success = False
        votes = []
        results = []
        raw_texts = []

        try:
            images = [Image.open(file) for file in uploaded_files]
            with st.spinner("Analyzing..."):
                for i in range(3):
                    try:
                        key = KEYS_LIST[i]
                        client = genai.Client(api_key=key)
                        chat = client.chats.create(model="gemini-3.6-flash")
                        response = chat.send_message(
                            message=[system_prompt, *images],
                            config=genai.types.GenerateContentConfig(temperature=0.0)
                        )
                        parsed = parse_ai_response(response.text)
                        raw_texts.append(response.text)
                        
                        if parsed:
                            results.append(parsed)
                            votes.append(parsed['direction'])
                            increment_usage()
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            continue
                        else:
                            continue

                # THE VOTING LOGIC
                buy_votes = votes.count("BUY")
                sell_votes = votes.count("SELL")
                final_direction = "NEUTRAL"
                if buy_votes >= 2: final_direction = "BUY"
                elif sell_votes >= 2: final_direction = "SELL"

                # CASE 1: CLEAR TRADE
                if final_direction != "NEUTRAL":
                    winning_results = [r for r in results if r['direction'] == final_direction]
                    avg_entry = sum(r['entry'] for r in winning_results) / len(winning_results)
                    avg_sl = sum(r['sl'] for r in winning_results) / len(winning_results)
                    avg_tp = sum(r['tp'] for r in winning_results) / len(winning_results)
                    sym = winning_results[0]['symbol']

                    st.session_state.analysis_result = f"**AI Consensus (3-Vote {final_direction})**\n\nSymbol: {sym}\nEntry: {avg_entry:.2f}\nStop Loss: {avg_sl:.2f}\nTake Profit: {avg_tp:.2f}"
                    st.session_state.auto_symbol = sym
                    st.session_state.entry_field = f"{avg_entry:.2f}"
                    st.session_state.sl_field = f"{avg_sl:.2f}"
                    st.session_state.tp_field = f"{avg_tp:.2f}"

                    if supabase_connected:
                        try:
                            cache_data = {'text': st.session_state.analysis_result, 'symbol': sym, 'entry': f"{avg_entry:.2f}", 'sl': f"{avg_sl:.2f}", 'tp': f"{avg_tp:.2f}"}
                            supabase.table('analysis_cache').upsert({'hash': image_hash, 'result': cache_data}).execute()
                        except:
                            pass

                    st.success(f"✅ High Accuracy Signal Locked! ({len(winning_results)} AIs agreed)")
                    st.rerun()
                    
                # CASE 2: NEUTRAL
                else:
                    if raw_texts:
                        full_text = clean_analysis(raw_texts[0])
                        split_marker = "🚨 SPECULATIVE SETUP:"
                        if split_marker in full_text:
                            main_analysis, spec_part = full_text.split(split_marker, 1)
                        else:
                            main_analysis, spec_part = full_text, "No speculative setup provided."
                            
                        st.markdown(f"""
                        <div class='gold-warning-box'>
                            <div class='gold-warning-text'>🛑 NO ACTIVE TRADE - Speculative Setup Only</div>
                            <div class='gold-warning-text'>The 3 AI models did not reach a clear consensus right now. However, they have provided a speculative setup below. Wait for these conditions to be met before considering a trade.</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div class='analysis-box'>
                            <div class='analysis-text'>{main_analysis.strip()}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div class='spec-box'>
                            <div class='spec-header'>🚨 LUXURY SPECULATIVE SETUP</div>
                            <div class='spec-text'>{spec_part.strip()}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div class='info-box'>
                            <div class='info-text'>These are NOT active trades. Only enter if the market reaches the exact conditions described in the analysis. You can manually type the levels into the calculator below once the trigger is confirmed.</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class='gold-warning-box'>
                            <div class='gold-warning-text'>🛑 NO TRADE - No Speculative Analysis Available</div>
                            <div class='gold-warning-text'>The AI could not even generate a speculative setup. It is safer to skip this chart entirely.</div>
                        </div>
                        """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ AI Error: {e}")

    if 'analysis_result' in st.session_state:
        st.success("AI Analysis Summary:")
        with st.container(border=True):
            st.markdown(st.session_state['analysis_result'])

st.divider()

# --- AUTO-FILLING MULTI-SYMBOL CALCULATOR ---
st.subheader("🧮 Auto-Calculating Precision Calculator")
st.caption("Values fill automatically after analysis. You can manually override them.")

col1, col2 = st.columns(2)
with col1:
    try:
        default_index = symbol_options.index(st.session_state.auto_symbol)
    except (ValueError, AttributeError):
        default_index = 0
    
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
    except:
        entry_price, stop_loss, take_profit = 0.0, 0.0, 0.0

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
        if lot_size < 0.01:
            st.error(f"⚠️ Risk amount (${risk_amount:.2f}) is too small for 0.01 lots.")
        else:
            st.markdown(f"### 📊 Trade **{lot_size:.2f} Lots** (Min 0.01)")
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
