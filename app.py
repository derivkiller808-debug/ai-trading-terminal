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
    [data-testid="stMarkdownContainer"] {{ word-break: break-word; overflow-wrap: anywhere; }}
</style>
""", unsafe_allow_html=True)

st.title("🧠 The Brilliant Trader's AI Terminal")
st.caption("Upload 4H, 30M, 5M. Full AI Analysis, Auto-Calculated Risk.")

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

# --- USAGE COUNTER LOGIC ---
USAGE_FILE = "usage_count.txt"
DAILY_LIMIT = 20
TOTAL_LIMIT = len(KEYS_LIST) * DAILY_LIMIT

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
    text = text.replace("formingalowerhighwick", "forming a lower high wick")
    text = text.replace("4H Trend Analysis:", "\n\n**4H Trend Analysis:**")
    text = text.replace("30M Pattern Analysis:", "\n\n**30M Pattern Analysis:**")
    text = text.replace("5M Sniper Entry:", "\n\n**5M Sniper Entry:**")
    text = text.replace("Final Verdict:", "\n\n**Final Verdict:**")
    return text

# --- SYMBOLS & SESSION ---
placeholder = "Select Instrument..."
symbol_options = [placeholder, "BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD (Forex)"]
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
    
    st.markdown(f"⚙️ **Active Keys Loaded:** {len(KEYS_LIST)}")
    
    current_usage = get_usage_count()
    remaining = max(0, TOTAL_LIMIT - current_usage)
    
    st.markdown("### 📊 Daily Scan Limit")
    st.progress(current_usage / TOTAL_LIMIT)
    st.markdown(f"**Used:** {current_usage} / {TOTAL_LIMIT}")
    st.markdown(f"**Remaining:** {remaining} scans")
    
    # Master Reset Button
    if st.button("🧹 Reset Usage Counter"):
        if os.path.exists(USAGE_FILE):
            os.remove(USAGE_FILE)
        st.rerun()
    
    st.divider()
    
    st.subheader("📈 Upload Charts")
    uploaded_files = st.file_uploader("Upload Exactly 3 Charts (4H, 30M, 5M)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- AI ANALYSIS ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    if st.button("Run Top-Trader Analysis"):
        
        # 1. Calculate Hash
        hasher = hashlib.sha256()
        for file in uploaded_files:
            hasher.update(file.getvalue())
        image_hash = hasher.hexdigest()

        # 2. Check Supabase Cache
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

        # 3. The "Legendary 50-Year Master Trader" Prompt
        system_prompt = """
        You are a legendary, highly profitable and exceptionally skilled trader with over 50 years of experience. You are a master of every trading strategy, concept, and psychological principle known to mankind.

        I am uploading exactly three screenshots: 4H, 30M, and 5M.

        CRITICAL RULE: Use standard spacing. Ensure there is a space after every word and every period. Never output solid strings of text like "Priceisnow". Always format it as "Price is now".

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
        
        # 4. The Master Key Loop (Automatically finds the first working key)
        success = False
        last_error = ""
        
        try:
            images = [Image.open(file) for file in uploaded_files]
            with st.spinner("Analyzing charts..."):
                # Iterate through keys WITHOUT getting stuck on index
                for i, key in enumerate(KEYS_LIST):
                    try:
                        client = genai.Client(api_key=key)
                        chat = client.chats.create(model="gemini-3.6-flash")
                        response = chat.send_message(
                            message=[system_prompt, *images],
                            config=genai.types.GenerateContentConfig(temperature=0.0)
                        )
                        
                        parsed_data = parse_ai_response(response.text)
                        
                        if parsed_data:
                            increment_usage()
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

                            st.success(f"✅ Analysis Complete! (Used Key {i + 1})")
                            success = True
                            st.rerun()
                            break
                        else:
                            last_error = "AI did not return the exact numbers."
                            break
                            
                    except Exception as e:
                        # If 429, move to the next key!
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            continue
                        else:
                            last_error = str(e)
                            break
                            
                if not success:
                    st.warning("""
                    ### 🚫 ALL KEYS LIMIT REACHED
                    All 10 keys have been exhausted. 
                    
                    Contact authdev Alex Nderitu via Whatsapp **+254759914001** for License Activation.
                    """)
                    st.info(f"Debug Info (For your eyes only): {last_error}")
                
        except Exception as e:
            st.error(f"❌ AI Error: {e}")

    if 'analysis_result' in st.session_state:
        st.success("AI Analysis Summary:")
        with st.container(border=True):
            st.markdown(st.session_state['analysis_result'])

st.divider()

# --- AUTO-FILLING MULTI-SYMBOL CALCULATOR ---
st.subheader("🧮 Auto-Calculating Precision Calculator")
st.caption("Values fill automatically. You can manually override them.")

col1, col2 = st.columns(2)
with col1:
    instrument = st.selectbox("Select Instrument", symbol_options, index=0)
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
