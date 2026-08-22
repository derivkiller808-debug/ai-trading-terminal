import streamlit as st
from PIL import Image
from google import genai

# --- STYLING ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    h1, h2, h3 { color: #00ff88 !important; font-family: 'Courier New', monospace; }
    .stButton>button { background-color: #00ff88; color: #000; font-weight: bold; border-radius: 5px; }
    .stNumberInput>div>div>input { background-color: #1a1f2e; color: white; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 The Brilliant Trader's AI Terminal")
st.caption("Upload screenshots, and let the 'Top Trader' AI analyze the pattern and calculate your exact risk.")

# --- API KEY ---
API_KEY = st.secrets.get("GEMINI_API_KEY", "PASTE_YOUR_KEY_HERE")
client = genai.Client(api_key=API_KEY)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Risk Management Dashboard")
    account_balance = st.number_input("Account Balance ($)", min_value=100.0, value=10000.0, step=100.0)
    leverage = st.number_input("Leverage (e.g., 10, 50, 100)", min_value=1.0, value=10.0, step=1.0)
    risk_percent = st.slider("Risk Per Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
    
    st.divider()
    st.subheader("📈 Chart Upload")
    uploaded_files = st.file_uploader("Upload Chart Screenshots", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- AI ANALYSIS ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    
    if st.button("Run Top-Trader Analysis"):
        system_prompt = """
        You are a top-tier, brilliant technical analyst with 20 years of experience. 
        You analyze crypto charts using Multi-Timeframe Confluence.
        I am uploading several screenshots of BTC/USD charts (1m, 5m, 15m, and 4h). 
        Some have a horizontal red line (key pivot/support/resistance).
        Follow these steps exactly:
        1. Identify the primary trend on the 4H chart.
        2. Identify the pattern on the 15M/30M chart.
        3. Use the 1M/5M charts for the precise "Sniper Entry".
        4. State clearly whether I should BUY or SELL, and why.
        5. Provide a specific ENTRY price, STOP LOSS (SL) price, and two TAKE PROFIT (TP) targets. 
        6. Include the exact Risk-to-Reward ratio. 
        Respond as a professional Wall Street analyst would, concise and direct.
        """
        
        try:
            images = [Image.open(file) for file in uploaded_files]
            
            with st.spinner("Analyzing charts and calculating probabilities..."):
                # UPDATED: Use Chat.send_message to suppress the warning
                chat = client.chats.create(model="gemini-3.6-flash")
                response = chat.send_message([system_prompt, *images])
                
            st.success("Analysis Complete:")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Error running AI. Check your API Key or model limit. {e}")

st.divider()

# --- POSITION SIZING ---
st.subheader("🧮 Precision Position Sizing Calculator")
st.caption("Once the AI gives you your Entry and Stop Loss, plug them in below to see exactly how much to trade.")

col1, col2, col3 = st.columns(3)
with col1:
    entry_price = st.number_input("Entry Price", value=76969.00, step=10.0)
with col2:
    stop_loss = st.number_input("Stop Loss (SL)", value=77180.00, step=10.0)
with col3:
    take_profit = st.number_input("Take Profit (TP)", value=76570.00, step=10.0)

contract_size = st.number_input("Contract Size (1 for BTC, 100,000 for Forex)", value=1.0, step=1.0)

if st.button("Calculate Position Size"):
    risk_amount = account_balance * (risk_percent / 100)
    price_diff = abs(entry_price - stop_loss)
    position_size = risk_amount / price_diff
    margin_required = (position_size * entry_price) / leverage
    lot_size = position_size / contract_size
    potential_profit = abs(take_profit - entry_price) * position_size
    rr_ratio = (abs(take_profit - entry_price)) / (price_diff)
    
    st.success("--- CALCULATION RESULTS ---")
    st.write(f"💰 **Account Balance:** ${account_balance:,.2f}")
    st.write(f"⚠️ **Risk Amount (at {risk_percent}%):** ${risk_amount:,.2f}")
    st.write(f"📉 **Distance to SL:** {price_diff:,.2f} points")
    st.markdown(f"### 📊 You should trade: **{position_size:.4f} Units** (or **{lot_size:.2f} Lots**)")
    st.write(f"🏦 **Margin Required (with {leverage}x leverage):** ${margin_required:,.2f}")
    st.write(f"🎯 **Potential Profit at TP:** ${potential_profit:,.2f}")
    st.write(f"📈 **Risk-to-Reward Ratio:** 1 : {rr_ratio:.2f}")
    st.warning("Rule #1: Never risk more than 1-2% per trade. This tool helps you survive the losing streaks.")
else:
    st.info("Enter your trade parameters to calculate your exact lot size.")
