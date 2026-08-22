import streamlit as st
import math
import re
from PIL import Image
from google import genai

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
st.caption("Upload 4H, 30M, 5M. AI analyzes price; Engine auto-calculates risk.")

# --- API SETUP ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"❌ CRITICAL ERROR: Missing or incorrect GEMINI_API_KEY in Settings -> Secrets. Error: {e}")
    st.stop()

# --- SYMBOLS LIST ---
placeholder = "Select Instrument..."
symbol_options = [placeholder, "BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD (Forex)"]

# --- SESSION STATE ---
if 'entry_field' not in st.session_state: st.session_state.entry_field = ""
if 'sl_field' not in st.session_state: st.session_state.sl_field = ""
if 'tp_field' not in st.session_state: st.session_state.tp_field = ""
if 'auto_symbol' not in st.session_state: st.session_state.auto_symbol = placeholder
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None

# --- PARSING FUNCTION ---
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
    uploaded_files = st.file_uploader("Upload 3 Charts (4H, 30M, 5M)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- AI ANALYSIS (SINGLE MODEL - BULLETPROOF) ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    if st.button("Run Top-Trader Analysis"):
        system_prompt = """
        You are a top-tier, brilliant technical analyst. I am uploading exactly three charts: 4H, 30M, and 5M.
        Analyze the MACRO TREND on 4H. Find the PRICE ACTION PATTERN on 30M. THEN declare BUY or SELL.
        If neutral, say NEUTRAL.
        STRICTLY output in this format:
        Symbol: XAUUSD (or BTCUSD or EURUSD)
        Direction: SELL
        Entry: 2450.50
        Stop Loss: 2460.00
        Take Profit: 2400.00
        DO NOT calculate lot sizes, leverage, or margin.
        """
        
        try:
            images = [Image.open(file) for file in uploaded_files]
            
            with st.spinner("Analyzing charts..."):
                # Using the guaranteed available model
                chat = client.chats.create(model="gemini-3.6-flash")
                response = chat.send_message(
                    message=[system_prompt, *images],
                    config=genai.types.GenerateContentConfig(temperature=0.0)
                )
                
                parsed_data = parse_ai_response(response.text)
                
                if parsed_data:
                    # Auto-Fill
                    st.session_state.analysis_result = response.text
                    st.session_state.auto_symbol = parsed_data['symbol']
                    st.session_state.entry_field = f"{parsed_data['entry']:.2f}"
                    st.session_state.sl_field = f"{parsed_data['sl']:.2f}"
                    st.session_state.tp_field = f"{parsed_data['tp']:.2f}"
                    st.success("✅ Analysis Complete!")
                else:
                    st.session_state.analysis_result = f"AI did not return numbers in the required format. Raw text: {response.text}"
                    st.warning("Could not parse exact numbers. Check AI output format.")
                
                st.rerun()
                
        except Exception as e:
            # This will print the EXACT error to the screen
            st.error(f"❌ AI Error: {e}")
            st.error("If this says '404' or 'Model not found', change 'gemini-2.5-flash' to another model in the code.")

    if 'analysis_result' in st.session_state:
        st.success("AI Analysis Summary:")
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
