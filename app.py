import streamlit as st
import math
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
st.caption("Upload the 4H, 30M, and 5M charts. The AI analyzes price action; the app calculates risk.")

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
    # Explicitly requests the correct timeframes
    uploaded_files = st.file_uploader("Upload 3 Charts: 4H, 30M, and 5M", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- AI ANALYSIS (Persistent & Chart-Only) ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    
    if st.button("Run Top-Trader Analysis"):
        system_prompt = """
        You are a top-tier, brilliant technical analyst. I am uploading exactly three charts: 4H, 30M, and 5M.
        1. Identify the primary trend on the 4H chart.
        2. Identify the pattern on the 30M chart.
        3. Use the 5M chart for the precise "Sniper Entry".
        4. State clearly whether I should BUY or SELL.
        5. Provide a specific ENTRY price, STOP LOSS (SL) price, and TAKE PROFIT (TP) target.
        
        **CRITICAL RULE: DO NOT calculate or suggest lot sizes, position sizes, contract sizes, margin, or leverage amounts.** 
        You are strictly an analyst of price charts. My risk and leverage math is calculated by a separate mathematical engine in the app.
        """
        
        try:
            images = [Image.open(file) for file in uploaded_files]
            
            with st.spinner("Analyzing charts..."):
                chat = client.chats.create(model="gemini-3.6-flash")
                response = chat.send_message([system_prompt, *images])
                
            st.session_state['analysis_result'] = response.text
            
        except Exception as e:
            st.error(f"Error running AI: {e}")

    if 'analysis_result' in st.session_state:
        st.success("Analysis Complete (Price Levels Only):")
        st.markdown(st.session_state['analysis_result'])

st.divider()

# --- MULTI-SYMBOL POSITION SIZING CALCULATOR ---
st.subheader("🧮 Multi-Symbol Precision Calculator")
st.caption("Select your symbol, input the AI's exact Entry/SL. The app will calculate the exact safe lot size.")

# Instrument selection
instrument = st.selectbox(
    "Select Instrument",
    ["BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD (Forex)"],
    index=0
)

# Auto-populate contract size based on symbol
# Gold = 100 oz per lot, Forex = 100,000 units per lot, BTC = 1
contract_sizes = {"BTCUSD (Bitcoin)": 1.0, "XAUUSD (Gold)": 100.0, "EURUSD (Forex)": 100000.0}
contract_size = contract_sizes[instrument]

# Generic defaults (0.00) so users don't accidentally use BTC numbers on Gold
col1, col2, col3 = st.columns(3)
with col1:
    entry_price = st.number_input(f"Entry Price ({instrument})", value=0.00, step=1.0)
with col2:
    stop_loss = st.number_input(f"Stop Loss ({instrument})", value=0.00, step=1.0)
with col3:
    take_profit = st.number_input(f"Take Profit ({instrument})", value=0.00, step=1.0)

if st.button("Calculate Position Size"):
    if entry_price == 0.00 or stop_loss == 0.00:
        st.error("Please enter a valid Entry Price and Stop Loss from the AI analysis.")
    else:
        risk_amount = account_balance * (risk_percent / 100)
        price_diff = abs(entry_price - stop_loss)
        
        # Calculate Units and Lots
        position_size = risk_amount / price_diff
        margin_required = (position_size * entry_price) / leverage
        
        raw_lot_size = position_size / contract_size
        # Floor to nearest 0.01
        lot_size = math.floor(raw_lot_size * 100) / 100
        
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
        
        # Important explanation for Gold
        if instrument == "XAUUSD (Gold)":
            st.info("Note: 1 Standard Lot of Gold = 100 oz. Because Gold has a high monetary value per unit, the lot size is usually much smaller than Forex.")
        elif instrument == "EURUSD (Forex)":
            st.info("Note: 1 Standard Lot of Forex = 100,000 units. Lot sizes are usually in whole numbers or halves for Forex.")
        
        st.warning("The AI only gives you the price levels. The app strictly manages the mathematics to protect your account.")

# --- FOOTER ---
st.divider()
st.markdown("### **Created by Alex Nderitu**")
