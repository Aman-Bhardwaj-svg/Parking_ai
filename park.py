import streamlit as st
try:
    import google.generativeai as genai
except ImportError:
    st.error("Gemini library not installed")
import json
import time
from datetime import datetime
import pandas as pd
from PIL import Image
import io
import os

# --- CONFIGURATION ---
CAPACITY = 50
DATA_FILE = "parked_vehicles.json"
HISTORY_FILE = "parking_history.json"

# Initialize Gemini (Ensure GEMINI_API_KEY is in your environment variables)
# Or replace with your actual key for local testing: genai.configure(api_key="YOUR_KEY")
api_key = st.secrets.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    st.warning("Gemini API key not found. AI detection disabled.")
    model = None

# --- DATA PERSISTENCE ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return []

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f)

# --- HELPERS ---
def format_duration(seconds):
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if mins > 0: parts.append(f"{mins}m")
    if secs > 0 or not parts: parts.append(f"{secs}s")
    return " ".join(parts)

def extract_plate(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        prompt = "Extract the license plate number from this image. Return ONLY the alphanumeric plate number, nothing else. If no plate is visible, return 'NONE'."
        response = model.generate_content([prompt, img])
        return response.text.strip().upper()
    except Exception as e:
        st.error(f"AI OCR Error: {e}")
        return None

# --- APP STATE ---
if 'parked' not in st.session_state:
    st.session_state.parked = load_json(DATA_FILE)
if 'history' not in st.session_state:
    st.session_state.history = load_json(HISTORY_FILE)

# --- UI LAYOUT ---
st.set_page_config(page_title="Smart Parking Manager", page_icon="🅿️", layout="centered")

st.title("🅿️ Smart Parking Manager")
st.markdown("AI-powered lot monitoring and plate detection.")

# Sidebar Stats
parked_count = len(st.session_state.parked)
available = CAPACITY - parked_count
st.sidebar.header("Lot Status")
st.sidebar.metric("Occupancy", f"{parked_count} / {CAPACITY}")
st.sidebar.metric("Available Spaces", available)

# Tabs
tab1, tab2, tab3 = st.tabs(["🚗 Entry/Exit", "📋 Active Vehicles", "📜 History"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Vehicle Entry")
        entry_plate = st.text_input("Manual Plate Entry", key="entry_manual").upper()
        if st.button("Park Vehicle", use_container_width=True):
            if entry_plate:
                if any(v['plate'] == entry_plate for v in st.session_state.parked):
                    st.warning(f"Vehicle {entry_plate} is already inside.")
                elif parked_count >= CAPACITY:
                    st.error("Parking lot is full!")
                else:
                    st.session_state.parked.append({"plate": entry_plate, "entry_time": time.time()})
                    save_json(DATA_FILE, st.session_state.parked)
                    st.success(f"Successfully parked: {entry_plate}")
                    st.rerun()

    with col2:
        st.subheader("Vehicle Exit")
        exit_plate = st.text_input("Manual Plate Exit", key="exit_manual").upper()
        if st.button("Process Exit", use_container_width=True):
            vehicle = next((v for v in st.session_state.parked if v['plate'] == exit_plate), None)
            if vehicle:
                exit_time = time.time()
                duration_sec = exit_time - vehicle['entry_time']
                
                summary = {
                    "plate": exit_plate,
                    "entry_time": vehicle['entry_time'],
                    "exit_time": exit_time,
                    "duration": format_duration(duration_sec)
                }
                
                st.session_state.parked = [v for v in st.session_state.parked if v['plate'] != exit_plate]
                st.session_state.history.insert(0, summary)
                
                save_json(DATA_FILE, st.session_state.parked)
                save_json(HISTORY_FILE, st.session_state.history)
                
                st.success(f"Exit processed for {exit_plate}")
                st.info(f"Total Duration: {summary['duration']}")
                st.rerun()
            else:
                st.error("Vehicle not found in lot.")

    st.divider()
    st.subheader("📸 AI Camera Scan")
    camera_img = st.camera_input("Scan License Plate")
    
    if camera_img:
        with st.spinner("AI Extracting Plate..."):
            detected = extract_plate(camera_img.getvalue())
            if detected and detected != "NONE":
                st.info(f"Detected Plate: **{detected}**")
                c1, c2 = st.columns(2)
                if c1.button(f"Park {detected}"):
                    # Logic for entry
                    pass 
                if c2.button(f"Exit {detected}"):
                    # Logic for exit
                    pass
            else:
                st.warning("Could not detect a plate. Please try again or enter manually.")

with tab2:
    st.subheader("Current Vehicles")
    if not st.session_state.parked:
        st.info("The parking lot is currently empty.")
    else:
        for v in st.session_state.parked:
            elapsed = time.time() - v['entry_time']
            with st.expander(f"🚗 {v['plate']}"):
                st.write(f"**Entry Time:** {datetime.fromtimestamp(v['entry_time']).strftime('%I:%M %p')}")
                st.write(f"**Duration:** {format_duration(elapsed)}")

with tab3:
    st.subheader("Parking History")
    if st.button("Clear All History"):
        st.session_state.history = []
        save_json(HISTORY_FILE, [])
        st.rerun()
        
    if not st.session_state.history:
        st.write("No history recorded yet.")
    else:
        # Convert to DataFrame for a nice table
        history_df = pd.DataFrame(st.session_state.history)
        history_df['entry_time'] = history_df['entry_time'].apply(lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M'))
        history_df['exit_time'] = history_df['exit_time'].apply(lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M'))
        st.dataframe(history_df[['plate', 'entry_time', 'exit_time', 'duration']], use_container_width=True)

st.divider()

st.caption("System Operational • AI Detection Enabled")







