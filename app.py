import streamlit as st
import math
import re  # NEW: Imported for parsing the AI's numbers
from PIL import Image
from google import genai

# --- STYLING ---
bg_url = "https://github.com/derivkiller808-debug/ai-trading-terminal/raw/main/download.png"

st.markdown(f"""
<style>
    .stApp {{
        background-image: url("{bg_url}");
        background-size: cover;
        background-color: #0e1117;
    }}
    h1, h2, h3, h4 {{ color: #00ff88 !important; font-family: 'Courier New', monospace; }}
    .stButton>button {{ background-color: #00ff88; color: #000; font-weight: bold; border-radius: 5px; }}
    .stNumberInput>div>div>input {{ background-color: #1a1f2e; color: white; }}
    .stFileUploader {{ background-color: rgba(20, 20, 20, 0.8); border: 1px solid #00ff88; border-radius: 10px; }}
    footer {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)

st.title("🧠 The Brilliant Trader's AI Terminal")
st.caption("Upload the 4H, 30M, and 5M charts. The AI analyzes price action; the app automatically populates the risk calculator.")

# --- API KEY ---
API_KEY = st.secrets.get("GEMINI_API_KEY", "PASTE_YOUR_KEY_HERE")
client = genai.Client(api_key=API_KEY)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Risk Management Dashboard")
    account_balance = st.number_input("Account Balance ($)", min_value=1.0, value=1000.0, step=10.0)
    leverage = st.number_input("Leverage (Default 400)", min_value=1.0, value=400.0, step=10.0)
    risk_percent = st.slider("Risk % of Account", min_value=0.1, max_value=100.0, value=1.0, step=0.1)
    
    st.divider()
    st.subheader("📈 Upload Charts")
    uploaded_files = st.file_uploader("Upload 3 Charts: 4H, 30M, and 5M", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- AI ANALYSIS (Persistent & Auto-Fill Logic) ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    
    if st.button("Run Top-Trader Analysis"):
        system_prompt = """
        You are a top-tier, brilliant technical analyst. I am uploading exactly three charts: 4H, 30M, and 5M.
        1. Identify the primary trend on the 4H chart.
        2. Identify the pattern on the 30M chart.
        3. Use the 5M chart for the precise "Sniper Entry".
        4. State clearly whether I should BUY or SELL.
        5. Provide the exact Entry and Stop Loss.
        
        **CRITICAL RULES:**
        - DO NOT calculate or suggest lot sizes, position sizes, contract sizes, margin, or leverage amounts.
        - You MUST end your response with exactly these three lines, with no other text after them, so my app can read the numbers:
        ENTRY: [number]
        SL: [number]
        TP: [number]
        """
        
        try:
            images = [Image.open(file) for file in uploaded_files]
            
            with st.spinner("Analyzing charts and auto-filling calculator..."):
                chat = client.chats.create(model="gemini-3.6-flash")
                response = chat.send_message([system_prompt, *images])
                
            # 1. Store the text analysis so it doesn't disappear
            st.session_state['analysis_result'] = response.text
            
            # 2. Parse the numbers using regex and store them in session state
            text = response.text
            entry_match = re.search(r'ENTRY:\s*([\d.]+)', text)
            sl_match = re.search(r'SL:\s*([\d.]+)', text)
            tp_match = re.search(r'TP:\s*([\d.]+)', text)
            
            if entry_match:
                st.session_state['parsed_entry'] = float(entry_match.group(1))
            if sl_match:
                st.session_state['parsed_sl'] = float(sl_match.group(1))
            if tp_match:
                st.session_state['parsed_tp'] = float(tp_match.group(1))
            
        except Exception as e:
            st.error(f"Error running AI: {e}")

    # Display stored result
    if 'analysis_result' in st.session_state:
        st.success("Analysis Complete:")
        st.markdown(st.session_state['analysis_result'])

st.divider()

# --- MULTI-SYMBOL AUTO-FILL CALCULATOR (Empty until Analysis) ---
st.subheader("🧮 Multi-Symbol Precision Calculator")
st.caption("Fields are empty until the AI analysis completes. Once complete, Entry/SL/TP will automatically fill.")

# Instrument selection
instrument = st.selectbox(
    "Select Instrument",
    ["BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD (Forex)"],
    index=0
)

# Auto-populate contract size based on symbol
contract_sizes = {"BTCUSD (Bitcoin)": 1.0, "XAUUSD (Gold)": 100.0, "EURUSD (Forex)": 100000.0}
contract_size = contract_sizes[instrument]

# Auto-fill fields using session state; default to None (empty)
col1, col2, col3 = st.columns(3)
with col1:
    entry_price = st.number_input(f"Entry ({instrument})", min_value=0.0, value=st.session_state.get('parsed_entry', None), step=1.0, format="%.2f")
with col2:
    stop_loss = st.number_input(f"Stop Loss ({instrument})", min_value=0.0, value=st.session_state.get('parsed_sl', None), step=1.0, format="%.2f")
with col3:
    take_profit = st.number_input(f"Take Profit ({instrument})", min_value=0.0, value=st.session_state.get('parsed_tp', None), step=1.0, format="%.2f")

if st.button("Calculate Position Size"):
    if entry_price is None or stop_loss is None or entry_price == 0.0 or stop_loss == 0.0:
        st.error("Please run the AI analysis first or manually enter an Entry and Stop Loss.")
    else:
        risk_amount = account_balance * (risk_percent / 100)
        price_diff = abs(entry_price - stop_loss)
        
        position_size = risk_amount / price_diff
        margin_required = (position_size * entry_price) / leverage
        
        raw_lot_size = position_size / contract_size
        lot_size = math.floor(raw_lot_size * 100) / 100
        
        if take_profit is None or take_profit == 0.0:
            rr_ratio = 0.0
            potential_profit = 0.0
        else:
            potential_profit = abs(take_profit - entry_price) * position_size
            rr_ratio = (abs(take_profit - entry_price)) / (price_diff)
        
        st.success(f"--- RESULTS FOR {instrument} ---")
        st.write(f"💰 **Account Balance:** ${account_balance:,.2f}")
        st.write(f"⚠️ **Risk Amount (at {risk_percent}%):** ${risk_amount:,.2f}")
        st.write(f"📉 **Distance to SL:** {price_diff:,.2f} points")
        
        if lot_size < 0.01:
            st.error(f"🚨 IMPORTANT: Your risk amount (${risk_amount:.2f}) is too small to trade the minimum 0.01 lots. Increase your risk % or increase the Stop Loss distance.")
        else:
            st.markdown(f"### 📊 You should trade exactly: **{lot_size:.2f} Lots** (Min 0.01, increments 0.01)")
        
        st.write(f"🏦 **Margin Required (at {leverage:.0f}x leverage):** ${margin_required:,.2f}")
        st.write(f"🎯 **Potential Profit at TP:** ${potential_profit:,.2f}")
        st.write(f"📈 **Risk-to-Reward Ratio:** 1 : {rr_ratio:.2f}")
        
        st.warning("Rule #1: Never risk money you can't afford to lose. This tool helps you survive the losing streaks.")

# --- FOOTER ---
st.divider()
st.markdown("### **Created by Alex Nderitu**")
