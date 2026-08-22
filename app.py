import streamlit as st
import math
from PIL import Image
from google import genai

# --- STYLING: Custom Background (Change URL if you want a new one) ---
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

st.title("🧠 Brilliant Trader's Terminal")
st.caption("Built for Multi-Symbol Trading. Created by Alex Nderitu")

# --- API KEY ---
API_KEY = st.secrets.get("GEMINI_API_KEY", "PASTE_YOUR_KEY_HERE")
client = genai.Client(api_key=API_KEY)

# --- SIDEBAR (Global Settings) ---
with st.sidebar:
    st.header("⚙️ Account Settings")
    account_balance = st.number_input("Account Balance ($)", min_value=1.0, value=1000.0, step=10.0)
    leverage = st.number_input("Leverage (Default 400)", min_value=1.0, value=400.0, step=10.0)
    risk_percent = st.slider("Risk % of Account", min_value=0.1, max_value=100.0, value=1.0, step=0.1)

# --- 3 COLUMN LAYOUT (No Scrolling) ---
col_upload, col_ai, col_calc = st.columns([1, 2, 2])

# --- COLUMN 1: UPLOAD & RUN ---
with col_upload:
    st.subheader("1. Upload Charts")
    st.caption("Demand: 4H, 30M, and 5M")
    uploaded_files = st.file_uploader(
        "Upload multiple charts", 
        type=["png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    
    if st.button("Run Top-Trader Analysis", use_container_width=True):
        if not uploaded_files:
            st.error("Please upload at least one chart.")
        else:
            # SPECIFIC PROMPT FOR 4H, 30M, 5M AND NO LOT CALCULATION
            system_prompt = """
            You are a top-tier, brilliant technical analyst with 20 years of experience. 
            You analyze crypto/Forex/Gold charts using Multi-Timeframe Confluence.
            I am uploading screenshots of BTC/USD charts (Specifically the 4H, 30M, and 5M timeframes).
            Some have a horizontal red line (key pivot/support/resistance).
            Follow these steps exactly:
            1. Identify the primary trend on the 4H chart.
            2. Identify the pattern on the 30M chart.
            3. Use the 5M chart for the precise "Sniper Entry".
            4. State clearly whether I should BUY or SELL, and why.
            5. Provide a specific ENTRY price, STOP LOSS (SL) price, and two TAKE PROFIT (TP) targets. 
            6. Include the exact Risk-to-Reward ratio. 
            **CRITICAL: Do NOT calculate lot size, margin, or leverage in your response. The app calculates this automatically based on the user's specific account size.**
            Respond as a professional Wall Street analyst would, concise and direct.
            """
            
            try:
                images = [Image.open(file) for file in uploaded_files]
                with st.spinner("Scanning... analyzing... calculating..."):
                    chat = client.chats.create(model="gemini-3.6-flash")
                    response = chat.send_message([system_prompt, *images])
                # Save to state so it doesn't disappear
                st.session_state['analysis_result'] = response.text
            except Exception as e:
                st.error(f"AI Error: {e}")

# --- COLUMN 2: AI ANALYSIS OUTPUT ---
with col_ai:
    st.subheader("2. AI Analysis")
    if 'analysis_result' in st.session_state:
        st.success("Analysis Complete:")
        st.markdown(st.session_state['analysis_result'])
    else:
        st.info("Upload charts on the left and click Run to see the analysis here.")

# --- COLUMN 3: POSITION CALCULATOR ---
with col_calc:
    st.subheader("3. Position Sizing")
    st.caption("The app calculates lots based on real Margin, Leverage & Contract Size.")
    
    # Multi-Symbol Selector
    symbol = st.selectbox(
        "Select Symbol", 
        ["BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD", "GBPUSD", "USDJPY"]
    )
    
    # Set Contract Size based on symbol
    if symbol == "BTCUSD (Bitcoin)": contract_size = 1.0
    elif symbol == "XAUUSD (Gold)": contract_size = 100.0
    else: contract_size = 100000.0 # FX Standard
    
    st.write(f"**Contract Size:** {contract_size:.0f} units per lot")
    
    col_a, col_b = st.columns(2)
    with col_a:
        entry_price = st.number_input("Entry Price", value=76969.00, step=10.0)
    with col_b:
        stop_loss = st.number_input("Stop Loss (SL)", value=77180.00, step=10.0)
    
    take_profit = st.number_input("Take Profit (TP)", value=76570.00, step=10.0)
    
    if st.button("Calculate Safe Lot Size", use_container_width=True):
        # 1. Calculate Risk Amount
        risk_amount = account_balance * (risk_percent / 100)
        # 2. Calculate Price Difference
        price_diff = abs(entry_price - stop_loss)
        
        # 3. Calculate Raw Units and Margin
        raw_units = risk_amount / price_diff
        raw_lot = raw_units / contract_size
        # Floor to nearest 0.01
        lot_size = math.floor(raw_lot * 100) / 100
        
        # 4. Calculate Margin Required for that lot
        margin_required = (lot_size * contract_size * entry_price) / leverage
        
        # 5. Check if it's impossible
        st.divider()
        st.write(f"**Risk Amount:** ${risk_amount:,.2f}")
        st.write(f"**Margin Required (for {lot_size:.2f} lots):** ${margin_required:,.2f}")
        st.write(f"**Leverage Used:** {leverage:.0f}x")
        
        if lot_size < 0.01:
            st.error(f"🚨 {risk_amount} risk is too small for the min 0.01 lot at this leverage. Increase risk% or tighten SL.")
        elif margin_required > account_balance:
            st.error(f"🚨 IMPOSSIBLE: {lot_size:.2f} lots requires ${margin_required:,.2f} margin, but your balance is ${account_balance:,.2f}. Lower lots or increase leverage.")
        else:
            st.success(f"✅ SAFE TRADE: **{lot_size:.2f} Lots**")
            # Calculate Potential Profit
            potential_profit = abs(take_profit - entry_price) * (lot_size * contract_size)
            rr_ratio = (abs(take_profit - entry_price)) / price_diff
            st.write(f"🎯 Potential Profit: **${potential_profit:,.2f}**")
            st.write(f"📈 Risk-to-Reward: **1 : {rr_ratio:.2f}**")
            st.warning("Rule #1: Never risk more than 1-2% per trade.")

st.divider()
st.markdown("### **Created by Alex Nderitu**")
