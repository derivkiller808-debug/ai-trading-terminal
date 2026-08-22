import streamlit as st
import math
import re
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
st.caption("Triple AI Consensus & Permanent Cloud Memory (Supabase)")

# --- API & DATABASE SETUP ---
API_KEY = st.secrets.get("GEMINI_API_KEY", "PASTE_YOUR_KEY_HERE")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "your_anon_public_key")

client = genai.Client(api_key=API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

# --- AI ANALYSIS (Ensemble & Permanent Cloud Cache) ---
if uploaded_files:
    st.subheader("🤖 Multi-Timeframe Analysis")
    if st.button("Run Top-Trader Analysis"):
        # 1. Calculate Hash
        hasher = hashlib.sha256()
        for file in uploaded_files:
            hasher.update(file.getvalue())
        image_hash = hasher.hexdigest()

        # 2. Query Supabase First!
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
        except Exception as db_error:
            st.warning(f"Database connection issue: {db_error}, falling back to RAM.")

        # 3. Run Ensemble Analysis
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
            models = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
            votes = []
            valid_results = []
            
            with st.spinner("Running 3-AI Consensus & Saving to Database..."):
                for model_name in models:
                    try:
                        chat = client.chats.create(model=model_name)
                        response = chat.send_message(contents=[system_prompt, *images], config=genai.types.GenerateContentConfig(temperature=0.0))
                        parsed = parse_ai_response(response.text)
                        if parsed:
                            votes.append(parsed['direction'])
                            valid_results.append(parsed)
                    except:
                        continue

            buy_count = votes.count("BUY"); sell_count = votes.count("SELL"); neutral_count = votes.count("NEUTRAL")
            final_direction = "NEUTRAL"
            if buy_count > sell_count and buy_count >= 2: final_direction = "BUY"
            elif sell_count > buy_count and sell_count >= 2: final_direction = "SELL"
            
            winning_results = [r for r in valid_results if r['direction'] == final_direction]
            if final_direction == "NEUTRAL" or not winning_results:
                final_text = f"**AI Consensus:** {neutral_count} Neutral, {buy_count} Buy, {sell_count} Sell.\n**Action: NEUTRAL / NO TRADE.**"
                cache_data = {'text': final_text, 'symbol': placeholder, 'entry': "", 'sl': "", 'tp': ""}
            else:
                avg_entry = sum(r['entry'] for r in winning_results) / len(winning_results)
                avg_sl = sum(r['sl'] for r in winning_results) / len(winning_results)
                avg_tp = sum(r['tp'] for r in winning_results) / len(winning_results)
                sym = winning_results[0]['symbol']
                final_text = f"**AI Consensus (Majority Vote {final_direction})**\n\nSymbol: {sym}\nDirection: {final_direction}\nEntry: {avg_entry:.2f}\nStop Loss: {avg_sl:.2f}\nTake Profit: {avg_tp:.2f}"
                cache_data = {'text': final_text, 'symbol': sym, 'entry': f"{avg_entry:.2f}", 'sl': f"{avg_sl:.2f}", 'tp': f"{avg_tp:.2f}"}

            # 4. Save to Supabase (Permanent Memory)
            try:
                supabase.table('analysis_cache').upsert({'hash': image_hash, 'result': cache_data}).execute()
            except Exception as e:
                st.warning(f"Could not save to permanent database: {e}")

            # Apply to UI
            st.session_state.analysis_result = cache_data['text']
            st.session_state.auto_symbol = cache_data['symbol']
            st.session_state.entry_field = cache_data['entry']
            st.session_state.sl_field = cache_data['sl']
            st.session_state.tp_field = cache_data['tp']
            st.success("✅ Consensus Complete and Locked permanently.")
            st.rerun()
            
        except Exception as e:
            st.error(f"AI Error: {e}")

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
