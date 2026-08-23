import streamlit as st
import math
import re
import os
import uuid
import hashlib
import pandas as pd
from datetime import datetime, timezone, timedelta
from PIL import Image
from google import genai
from supabase import create_client, Client
from streamlit_cookies_controller import CookieController

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
st.markdown("<p style='color: #c084fc; font-family: \"Courier New\", monospace;'>Upload 4H, 30M, 5M. Full AI Analysis, Auto-Calculated Risk. Batch Scanner with Validation.</p>", unsafe_allow_html=True)

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

# --- USER TRACKING ---
cookies = CookieController()
device_id = cookies.get("brilliant_trader_device_id")
if not device_id:
    device_id = "device-" + str(uuid.uuid4())
    cookies.set("brilliant_trader_device_id", device_id, max_age=31536000)

st.session_state.session_id = device_id

if 'total_users' not in st.session_state: st.session_state.total_users = 0
if 'active_users' not in st.session_state: st.session_state.active_users = 0

def track_visit():
    if supabase_connected:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            supabase.table('app_visits').upsert({'session_id': st.session_state.session_id, 'last_seen': now_iso}).execute()
            total = supabase.table('app_visits').select('*', count='exact').execute()
            st.session_state.total_users = total.count
            active_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            active = supabase.table('app_visits').select('*', count='exact').gte('last_seen', active_cutoff).execute()
            st.session_state.active_users = active.count
        except:
            pass
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

# --- NEW FUNCTION: PRE-SCAN (Detect Symbol & Validate Timeframes) ---
def pre_scan_image_set(images, keys, usage_index):
    """
    Sends 3 images to AI to detect symbol and timeframes.
    Returns (symbol, timeframes) or (None, None) if error.
    """
    # Build prompt for pre-scan
    pre_scan_prompt = """
    You are given 3 charts for the same trading symbol. Identify:
    1. The **trading symbol** (e.g., BTCUSD, XAUUSD, EURUSD) – look at the top-left corner of any chart.
    2. The **timeframe** of each chart (e.g., 4H, 30M, 5M) – usually shown in the top-left corner or on the chart itself.

    Return your answer in **exact** format:
    Symbol: [SYMBOL]
    Timeframes: [TF1], [TF2], [TF3]

    Do not include any other text.
    """
    try:
        # Use a key from the pool (rotate through keys)
        key = keys[usage_index % len(keys)]
        client = genai.Client(api_key=key)
        chat = client.chats.create(model="gemini-3.6-flash")
        response = chat.send_message(
            message=[pre_scan_prompt, *images],
            config=genai.types.GenerateContentConfig(temperature=0.0)
        )
        text = response.text.strip()
        # Extract symbol
        sym_match = re.search(r"Symbol:\s*([A-Z]+)", text, re.IGNORECASE)
        symbol = sym_match.group(1).upper() if sym_match else None
        # Extract timeframes
        tf_match = re.search(r"Timeframes:\s*(.+)", text, re.IGNORECASE)
        timeframes = []
        if tf_match:
            tfs = re.findall(r"\d+[HhMmDdWw]", tf_match.group(1))
            # Normalize to upper
            timeframes = [tf.upper() for tf in tfs]
        return symbol, timeframes
    except Exception as e:
        st.warning(f"Pre-scan error: {e}")
        return None, None

# --- SYMBOLS & SESSION ---
placeholder = "Select Instrument..."
symbol_options = [placeholder, "BTCUSD (Bitcoin)", "XAUUSD (Gold)", "EURUSD (Forex)"]

if 'batch_results' not in st.session_state: st.session_state.batch_results = []
if 'known_symbols' not in st.session_state: st.session_state.known_symbols = []
if 'detected_groups' not in st.session_state: st.session_state.detected_groups = []  # list of dicts

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

    # --- SYMBOL INVENTORY ---
    st.divider()
    st.markdown("### 📦 Auto-Saved Inventory")
    
    if supabase_connected:
        try:
            inv_response = supabase.table('symbol_inventory').select('symbol_name').execute()
            st.session_state.known_symbols = [x['symbol_name'] for x in inv_response.data]
        except:
            pass
    
    if st.session_state.known_symbols:
        for sym in st.session_state.known_symbols:
            st.markdown(f"- {sym}")
    else:
        st.caption("No symbols saved yet.")

    st.divider()
    st.subheader("📈 Upload Charts")
    uploaded_files = st.file_uploader("Upload all charts (4H, 30M, 5M per symbol)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

st.divider()

# --- BATCH DETECTION & VALIDATION ---
if uploaded_files:
    # Ensure count is multiple of 3
    num_groups = len(uploaded_files) // 3
    remainder = len(uploaded_files) % 3
    if remainder != 0:
        st.warning(f"⚠️ You uploaded {len(uploaded_files)} images, not divisible by 3. Ignoring last {remainder} image(s).")
        uploaded_files = uploaded_files[:num_groups * 3]
    
    if num_groups == 0:
        st.error("Please upload at least 3 images (1 symbol).")
    else:
        # Pre-scan each group
        with st.spinner("Pre-scanning images for symbols and timeframes..."):
            detected = []
            for i in range(num_groups):
                group_files = uploaded_files[i*3 : (i+1)*3]
                images = [Image.open(f) for f in group_files]
                # Use the first key for pre-scan (usage_index = i)
                symbol, tfs = pre_scan_image_set(images, KEYS_LIST, i)
                detected.append({
                    'index': i,
                    'symbol': symbol,
                    'timeframes': tfs,
                    'valid': False,
                    'files': group_files
                })
            
            # Validate
            required_tfs = ['4H', '30M', '5M']
            for group in detected:
                if group['timeframes'] == required_tfs:
                    group['valid'] = True
                    # Save symbol if new
                    if supabase_connected and group['symbol']:
                        try:
                            supabase.table('symbol_inventory').upsert({'symbol_name': group['symbol']}).execute()
                            st.session_state.known_symbols.append(group['symbol'])
                        except:
                            pass
                else:
                    group['valid'] = False
            
            st.session_state.detected_groups = detected
        
        # Display detection results
        st.subheader("Detection & Validation Results")
        for group in st.session_state.detected_groups:
            sym = group['symbol'] if group['symbol'] else "Unknown"
            tfs = ", ".join(group['timeframes']) if group['timeframes'] else "Not readable"
            status = "✅ Valid" if group['valid'] else "❌ Rejected (wrong timeframes)"
            st.markdown(f"**Group {group['index']+1}:** {sym} – {tfs} → {status}")
        
        # If any invalid, stop and ask re-upload
        invalid_groups = [g for g in st.session_state.detected_groups if not g['valid']]
        if invalid_groups:
            st.error("❌ Some groups have incorrect timeframes. Please re-upload the correct 4H, 30M, 5M charts for those symbols.")
            st.stop()
        
        # If all valid, show "Run Full Analysis" button
        if st.button("🚀 Run Full Analysis on All Valid Groups"):
            st.session_state.batch_results = []
            with st.spinner("Running AI Consensus on all symbols..."):
                results = []
                for group in st.session_state.detected_groups:
                    symbol = group['symbol'].upper() if group['symbol'] else "UNKNOWN"
                    group_files = group['files']
                    
                    # Calculate hash
                    hasher = hashlib.sha256()
                    for file in group_files:
                        hasher.update(file.getvalue())
                    image_hash = hasher.hexdigest()
                    
                    # Check supabase cache
                    cached = False
                    if supabase_connected:
                        try:
                            response = supabase.table('analysis_cache').select('*').eq('hash', image_hash).execute()
                            if response.data:
                                cached_data = response.data[0]['result']
                                results.append({
                                    'symbol': symbol,
                                    'direction': cached_data['direction'],
                                    'entry': cached_data['entry'],
                                    'sl': cached_data['sl'],
                                    'tp': cached_data['tp'],
                                    'status': 'Cached'
                                })
                                cached = True
                        except:
                            pass
                    
                    if not cached:
                        votes = []
                        parsed_results = []
                        images = [Image.open(f) for f in group_files]
                        for j in range(3):
                            key_index = (get_usage_count() + j) % len(KEYS_LIST)
                            key = KEYS_LIST[key_index]
                            client = genai.Client(api_key=key)
                            chat = client.chats.create(model="gemini-3.6-flash")
                            
                            system_prompt = """
                            You are a legendary, mathematically precise, and exceptionally risk-averse trading strategist with 50 years of experience.
                            
                            You are provided with 3 charts: 4H, 30M, and 5M for this specific symbol.
                            
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
                            You MUST provide a **🚨 SPECULATIVE SETUP:** section immediately after the verdict. List the **THREE (3) individual occurrences** that would support an entry. These should be listed as a numbered list (1, 2, 3). They do NOT have to happen all at the same time. Each is an independent trigger that supports the trade.
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
                            
                            response = chat.send_message(
                                message=[system_prompt, *images],
                                config=genai.types.GenerateContentConfig(temperature=0.0)
                            )
                            parsed = parse_ai_response(response.text)
                            if parsed:
                                parsed_results.append(parsed)
                                votes.append(parsed['direction'])
                                increment_usage()
                        
                        buy_votes = votes.count("BUY")
                        sell_votes = votes.count("SELL")
                        final_direction = "NEUTRAL"
                        if buy_votes >= 2: final_direction = "BUY"
                        elif sell_votes >= 2: final_direction = "SELL"
                        
                        if final_direction != "NEUTRAL" and parsed_results:
                            winning = [r for r in parsed_results if r['direction'] == final_direction]
                            avg_entry = sum(r['entry'] for r in winning) / len(winning)
                            avg_sl = sum(r['sl'] for r in winning) / len(winning)
                            avg_tp = sum(r['tp'] for r in winning) / len(winning)
                            result = {
                                'symbol': symbol,
                                'direction': final_direction,
                                'entry': f"{avg_entry:.2f}",
                                'sl': f"{avg_sl:.2f}",
                                'tp': f"{avg_tp:.2f}",
                                'status': 'Active'
                            }
                            if supabase_connected:
                                try:
                                    cache_data = {'text': f"{final_direction} signal for {symbol}", 'symbol': symbol, 'direction': final_direction, 'entry': f"{avg_entry:.2f}", 'sl': f"{avg_sl:.2f}", 'tp': f"{avg_tp:.2f}"}
                                    supabase.table('analysis_cache').upsert({'hash': image_hash, 'result': cache_data}).execute()
                                except:
                                    pass
                        else:
                            result = {
                                'symbol': symbol,
                                'direction': 'NEUTRAL',
                                'entry': '',
                                'sl': '',
                                'tp': '',
                                'status': 'Speculative'
                            }
                        results.append(result)
                
                st.session_state.batch_results = results
            st.rerun()

if st.session_state.batch_results:
    st.subheader("📊 Batch Scan Results")
    df = pd.DataFrame(st.session_state.batch_results)
    st.dataframe(df, use_container_width=True)
    
    selected = st.selectbox("Select a result to load into the calculator:", options=[f"{r['symbol']} - {r['direction']}" for r in st.session_state.batch_results])
    
    if selected:
        selected_index = [f"{r['symbol']} - {r['direction']}" for r in st.session_state.batch_results].index(selected)
        selected_result = st.session_state.batch_results[selected_index]
        if selected_result['status'] == 'Active':
            st.session_state.auto_symbol = selected_result['symbol']
            st.session_state.entry_field = selected_result['entry']
            st.session_state.sl_field = selected_result['sl']
            st.session_state.tp_field = selected_result['tp']
            st.success(f"Loaded {selected_result['symbol']} into calculator!")
        else:
            st.info("This is a speculative setup. Wait for triggers before entering.")
    
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
