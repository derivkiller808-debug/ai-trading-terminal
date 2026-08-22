import streamlit as st
import math
import re
import os
import hashlib
from PIL import Image
from google import genai
from supabase import create_client, Client

# --- STYLING ---
bg_url = "https://github.com/derivkiller808-debug/ai-trading-terminal/raw/main/download.png"
st.markdown(f"""
<style>
    .stApp {{ background-image: url("{bg_url}"); background-size: cover; background-color: #0e1117; }}
    h1, h2, h3, h4 {{ color: #00ff88 !important; font-family: 'Courier New', monospace; }}
    .stButton>button {{ background-color: #00ff88; color: #000; font-weight: bold; border-radius: 5px; }}
    footer {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)

st.title("🧠 The Brilliant Trader's AI Terminal")
st.caption("Upload 4H, 30M, 5M. Full AI Analysis, Auto-Calculated Risk.")

# --- SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"❌ Missing GEMINI_API_KEY in Settings -> Secrets. Error: {e}")
    st.stop()

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    supabase_connected = True
except:
    supabase_connected = False

# --- USAGE COUNTER LOGIC ---
USAGE_FILE = "usage_count.txt"
DAILY_LIMIT = 20

if 'limit_reached' not in st.session_state:
    st.session_state.limit_reached = False

def get_usage_count():
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except:
                return 0
    return 0

def increment_usage():
    count = get_usage_count()
    with open(USAGE_FILE, "w") as f:
        f.write(str(count + 1))
    return count + 1

# --- IMPROVED CLEANING FUNCTION (Fixes all the weird AI spacing) ---
def clean_analysis(text):
    # 1. Remove spaces between numbers (e.g., 7 9 , 6 0 0 -> 79,600)
    text = re.sub(r'(?<=\d)\s+(?=\d)', '', text)
    # 2. Remove spaces between letters (e.g., p r i c e -> price)
    text = re.sub(r'(?<=\w)\s+(?=\w)', ' ', text)
    # 3. Collapse multiple newlines and spaces into one
    text = re.sub(r'\s+', ' ', text).strip()
    # 4. Add a newline before specific headings to make it neat
    text = text.replace("4H Trend Analysis:", "\n\n**4H Trend Analysis:**")
    text = text.replace("30M Pattern Analysis:", "\n\n**30M Pattern Analysis:**")
    text = text.replace("5M Sniper Entry:", "\n\n**5M Sniper Entry:**")
    text = text.replace("Final Verdict:", "\n\n**Final Verdict:**")
    return text

# --- SYMBOLS ---
placeholder = "Select Instrument..."
symbol_options = [placeholder, "BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD (Forex)"]

# --- SESSION STATE ---
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
    account_balance = st.number_input("Account Balance ($)", min_value=1.0, value=1000.0, step=10.0)
    leverage = st.number_input("Leverage (Default 400)", min_value=1.0, value=400.0, step=10.0)
    risk_percent = st.slider("Risk % of Account", min_value=0.1, max_value=100.0, value=1.0, step=0.1)
    
    st.divider()
    
    current_usage = get_usage_count()
    if st.session_state.limit_reached:
        current_usage = DAILY_LIMIT
    remaining = max(0, DAILY_LIMIT - current_usage)
    
    st.markdown("### 📊 Daily Scan Limit")
    
    if st.session_state.limit_reached or remaining == 0:
        st.error("🚫 **LIMIT REACHED**")
        st.progress(1.0)
    else:
        st.progress(current_usage / DAILY_LIMIT)
        
    st.markdown(f"**Used:** {current_usage} / {DAILY_LIMIT}")
    st.markdown(f"**Remaining:** {remaining} scans")
    
    if st.session_state.limit_reached:
        st.caption("Contact Authdev for License Activation")
    
    st.divider()
    
    st.subheader("📈 Upload Charts")
    uploaded_files = st.file_uploader("Upload Exactly 3 Charts (4H, 30M, 5M)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- AI ANALYSIS ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    if st.button("Run Top-Trader Analysis"):
        
        if get_usage_count() >= DAILY_LIMIT or st.session_state.limit_reached:
            st.session_state.limit_reached = True
            st.warning("""
            ### 🚫 Daily Limit Reached
            You have reached your daily scan limit of 20 charts. 
            
            Contact authdev Alex Nderitu via Whatsapp **+254759914001** for License Activation.
            """)
            st.stop()
        
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

        system_prompt = """
        You are a legendary, highly profitable and exceptionally skilled trader with over 50 years of experience. You are a master of every trading strategy, concept, and psychological principle known to mankind.

        I am uploading exactly three screenshots: 4H, 30M, and 5M.

        **📊 4H Trend Analysis:**
        Break down the macro bias, structure, and major support or resistance levels (like the red line).

        **🧩 30M Pattern Analysis:**
        Identify the specific price action pattern (e.g., double top, bull flag, break of structure) and explain what it means.

        **🎯 5M Sniper Entry:**
        Pinpoint the exact liquidity grab, order block, or rejection wick that confirms the entry.

        **⚖️ Final Verdict:**
        Conclude clearly with a BUY, SELL, or NEUTRAL recommendation, backed by your expert reasoning.

        **End your response with exactly these labels on new lines (no extra text after them), so my calculator can parse them:**

        Symbol:
        Direction:
        Entry:
        Stop Loss:
        Take Profit:

        DO NOT calculate lot sizes, leverage, or margin.
        """
        
        try:
            images = [Image.open(file) for file in uploaded_files]
            with st.spinner("Analyzing charts..."):
                chat = client.chats.create(model="gemini-3.6-flash")
                response = chat.send_message(
                    message=[system_prompt, *images],
                    config=genai.types.GenerateContentConfig(temperature=0.0)
                )
                
                parsed_data = parse_ai_response(response.text)
                
                if parsed_data:
                    increment_usage()
                    
                    # Apply the cleaner here!
                    st.session_state.analysis_result = clean_analysis(response.text)
                    st.session_state.auto_symbol = parsed_data['symbol']
                    st.session_state.entry_field = f"{parsed_data['entry']:.2f}"
                    st.session_state.sl_field = f"{parsed_data['sl']:.2f}"
                    st.session_state.tp_field = f"{parsed_data['tp']:.2f}"

                    if supabase_connected:
                        try:
                            cache_data = {'text': response.text, 'symbol': parsed_data['symbol'], 'entry': f"{parsed_data['entry']:.2f}", 'sl': f"{parsed_data['sl']:.2f}", 'tp': f"{parsed_data['tp']:.2f}"}
                            supabase.table('analysis_cache').upsert({'hash': image_hash, 'result': cache_data}).execute()
                        except:
                            pass

                    st.success("✅ Analysis Complete! (Locked to this image)")
                    st.rerun()
                else:
                    st.error("❌ AI did not return the exact numbers. Check the output format.")
                
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                st.session_state.limit_reached = True
                st.warning("""
                ### 🚫 Daily Limit Reached
                You have reached your daily scan limit of 20 charts. 
                
                Contact authdev Alex Nderitu via Whatsapp **+254759914001** for License Activation.
                """)
                st.rerun()
            else:
                st.error(f"❌ AI Error: {e}")

    if 'analysis_result' in st.session_state:
        st.success("AI Analysis Summary:")
        # THIS IS THE FIX: Native Streamlit Container (No custom HTML Divs!)
        # It automatically keeps the text inside the box and wraps it perfectly.
        with st.container(border=True):
            st.markdown(st.session_state['analysis_result'])

st.divider()

# --- AUTO-FILLING MULTI-SYMBOL CALCULATOR ---
st.subheader("🧮 Auto-Calculating Precision Calculator")
st.caption("Values fill automatically. You can manually override them.")

col1, col2 = st.columns(2)
with col1:
    try:
        default_index = symbol_options.index(st.session_state.auto_symbol)
    except ValueError:
        default_index = 0
    
    instrument = st.selectbox("Select Instrument", symbol_options, index=default_index)
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
st.markdown("### **Created by Alex Nderitu**")
