import streamlit as st
import os
from PIL import Image
import google.generativeai as genai

# --- STYLING: Professional Dark Trading Terminal ---
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

# --- STEP 1: API KEY (Google Gemini Free Tier) ---
# Instructions: Get a free key at https://aistudio.google.com/app/apikey
# Go to Streamlit Cloud -> Settings -> Secrets -> Add this:
# GEMINI_API_KEY = "your_api_key_here"
API_KEY = st.secrets.get("GEMINI_API_KEY", "PASTE_YOUR_KEY_HERE")
genai.configure(api_key=API_KEY)

# --- STEP 2: SIDEBAR (Account & Risk Settings) ---
with st.sidebar:
    st.header("⚙️ Risk Management Dashboard")
    account_balance = st.number_input("Account Balance ($)", min_value=100.0, value=10000.0, step=100.0)
    leverage = st.number_input("Leverage (e.g., 10, 50, 100)", min_value=1.0, value=10.0, step=1.0)
    risk_percent = st.slider("Risk Per Trade (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
    
    st.divider()
    st.subheader("📈 Chart Upload")
    uploaded_files = st.file_uploader("Upload Chart Screenshots (1m, 5m, 15m, 4h, etc.)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- STEP 3: AI ANALYSIS SECTION ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    
    if st.button("Run Top-Trader Analysis"):
        # The "Secret Sauce" Prompt
        system_prompt = """
        You are a top-tier, brilliant technical analyst with 20 years of experience. 
        You analyze crypto charts using Multi-Timeframe Confluence.
        
        I am uploading several screenshots of BTC/USD charts (1m, 5m, 15m, and 4h). 
        Some have a horizontal red line (key pivot/support/resistance).
        
        Please follow these steps exactly:
        1. Identify the primary trend on the 4H chart (Macro bias).
        2. Identify the pattern on the 15M/30M chart (e.g., double top, head and shoulders, bull flag).
        3. Use the 1M/5M charts for the precise "Sniper Entry" (look for order blocks, liquidity sweeps, and rejection wicks).
        4. State clearly whether I should BUY or SELL, and why.
        5. Provide a specific ENTRY price, STOP LOSS (SL) price, and two TAKE PROFIT (TP) targets. 
        6. Include the exact Risk-to-Reward ratio. 
        Respond as a professional Wall Street analyst would, concise and direct.
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            images = [Image.open(file) for file in uploaded_files]
            
            with st.spinner("Analyzing charts and calculating probabilities..."):
                response = model.generate_content([system_prompt, *images])
                
            st.success("Analysis Complete:")
            st.markdown(response.text)
            
        except Exception as e:
            st.error(f"Error running AI. Check your API Key. {e}")

st.divider()

# --- STEP 4: THE LOT SIZE CALCULATOR (THE MATH) ---
st.subheader("🧮 Precision Position Sizing Calculator")
st.caption("Once the AI gives you your Entry and Stop Loss, plug them in below to see exactly how much to trade.")

col1, col2, col3 = st.columns(3)
with col1:
    entry_price = st.number_input("Entry Price", value=76969.00, step=10.0)
with col2:
    stop_loss = st.number_input("Stop Loss (SL)", value=77180.00, step=10.0)
with col3:
    take_profit = st.number_input("Take Profit (TP)", value=76570.00, step=10.0)

# Forex/Crypto Contract size (Crypto = 1, Forex = 100,000)
contract_size = st.number_input("Contract Size (1 for BTC, 100,000 for Forex)", value=1.0, step=1.0)

if st.button("Calculate Position Size"):
    # 1. Calculate Risk Amount
    risk_amount = account_balance * (risk_percent / 100)
    
    # 2. Calculate Price Difference (Risk per unit)
    price_diff = abs(entry_price - stop_loss)
    
    # 3. Calculate Units (Position Size)
    position_size = risk_amount / price_diff
    
    # 4. Calculate Margin Required
    margin_required = (position_size * entry_price) / leverage
    
    # 5. Calculate Lots
    lot_size = position_size / contract_size
    
    # 6. Calculate Risk Reward Ratio
    potential_profit = abs(take_profit - entry_price) * position_size
    rr_ratio = (abs(take_profit - entry_price)) / (price_diff)
    
    # Display the results like a pro terminal
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