import streamlit as st
import pandas as pd
import numpy as np
from image_module import process_images

# Page Configuration
st.set_page_config(page_title="VTCS & GPS Auditor", layout="wide")
st.title("🚛 VTCS & GPS Tracking Auditor")

# --- SIDEBAR: FILE UPLOADS ---
st.sidebar.title("Navigation")

module = st.sidebar.radio(
    "Select Module",
    ["VTCS & GPS Audit", "Image Verification"]
)
if module == "VTCS & GPS Audit":
    else if module == "Image Verification":

    st.title("🖼️ VTCS Image Verification")

    before_file = st.file_uploader("Upload BEFORE Image", type=["jpg", "png"])
    after_file = st.file_uploader("Upload AFTER Image", type=["jpg", "png"])

    activity_time = st.datetime_input("Select Activity Time")

    if st.button("Verify Images"):

        if before_file and after_file:

            result = process_images(before_file, after_file, activity_time)

            st.success(f"Status: {result['status']}")
            st.write(f"Image Difference Score: {result['difference']}")
            st.write(f"Time Difference (minutes): {result['time_diff']}")

        else:
            st.warning("Please upload both images")

def process_audit(vtcs_df, track_df=None):
    # --- 1. VTCS PROCESSING ---
    # Weight Conversion
    cols_to_fix = ['Waste Collected (Kg)', 'Before Weight', 'After Weight (Kg)']
    for col in cols_to_fix:
        if col in vtcs_df.columns:
            vtcs_df[col] = pd.to_numeric(vtcs_df[col].astype(str).str.replace(',', ''), errors='coerce')
    
    vtcs_df['Tonnage'] = vtcs_df['Waste Collected (Kg)'] / 1000
    
    # Time Conversion (Portal format: Mar 17, 2026, 2:01:12 PM)
    vtcs_df['Time In'] = pd.to_datetime(vtcs_df['Time In'], errors='coerce')
    vtcs_df['Time Out'] = pd.to_datetime(vtcs_df['Time Out'], errors='coerce')
    
    # 30-Minute Logic (Above 30 is Suspicious)
    vtcs_df['Duration_Mins'] = (vtcs_df['Time Out'] - vtcs_df['Time In']).dt.total_seconds() / 60
    vtcs_df['Time_Status'] = vtcs_df['Duration_Mins'].apply(lambda x: "🚨 Suspicious (>30m)" if x > 30 else "✅ Normal")

    # --- 2. GPS TRACKING CROSS-CHECK ---
    if track_df is not None:
        # Standardize Tracking Columns
        # We assume tracking has 'Vehicle', 'Time', and 'Status'
        track_df['Time'] = pd.to_datetime(track_df.iloc[:, 1], errors='coerce') # Assuming 2nd column is time
        track_df.columns = [c.strip() for c in track_df.columns]
        
        # Merge Logic: Find GPS status at VTCS 'Time In'
        # To handle seconds difference, we round to nearest minute
        vtcs_df['Match_Time'] = vtcs_df['Time In'].dt.floor('min')
        track_df['Match_Time'] = track_df['Time'].dt.floor('min')
        
        # Merge VTCS with Tracking on Vehicle and Time
        merged = pd.merge(
            vtcs_df, 
            track_df[['Vehicle', 'Match_Time', 'Status']], 
            on=['Vehicle', 'Match_Time'], 
            how='left'
        )
        
        # IDLE Logic: Check if GPS status matches "Idle" at Portal entry time
        def check_idle(row):
            gps_status = str(row['Status']).lower()
            if 'idle' in gps_status:
                return "✅ Verified (Idle)"
            elif 'moving' in gps_status or 'active' in gps_status:
                return "❌ Conflict (Moving)"
            else:
                return "❓ No GPS Data"

        merged['GPS_Audit'] = merged.apply(check_idle, axis=1)
        return merged
    
    return vtcs_df

if vtcs_file:
    df_vtcs = pd.read_excel(vtcs_file) if vtcs_file.name.endswith('xlsx') else pd.read_csv(vtcs_file)
    
    df_track = None
    if tracking_file:
        df_track = pd.read_excel(tracking_file) if tracking_file.name.endswith('xlsx') else pd.read_csv(tracking_file)
    
    # Run the Audit
    results = process_audit(df_vtcs, df_track)

    # --- DASHBOARD UI ---
    st.header("📋 Audit Dashboard")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Tonnage (Day)", f"{results['Tonnage'].sum():.2f} Tons")
    m2.metric("Delayed Trips (>30m)", len(results[results['Time_Status'].str.contains("🚨")]))
    
    if 'GPS_Audit' in results.columns:
        conflicts = len(results[results['GPS_Audit'] == "❌ Conflict (Moving)"])
        m3.metric("GPS Conflicts", conflicts)

    # Vehicle Table
    st.subheader("Vehicle Summary")
    summary = results.groupby('Vehicle').agg({'Tonnage': 'sum', 'Data ID': 'count'}).rename(columns={'Data ID': 'Trips'})
    st.table(summary)

    # Main Data Table
    st.subheader("Detailed Logs")
    
    # Column selection for cleaner view
    display_cols = ['Vehicle', 'Time In', 'Time Out', 'Duration_Mins', 'Tonnage', 'Time_Status']
    if 'GPS_Audit' in results.columns:
        display_cols.append('GPS_Audit')

    # Color highlighting
    def color_rows(val):
        if '🚨' in str(val) or '❌' in str(val): return 'background-color: #ffcccc'
        if '✅' in str(val): return 'background-color: #ccffcc'
        return ''

    st.dataframe(results[display_cols].style.applymap(color_rows), use_container_width=True)

else:
    st.info("Please upload your VTCS file from the sidebar to start.")







import streamlit as st
import cv2
import numpy as np
from PIL import Image
import imagehash
import io
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ---------------- DB SETUP ----------------
engine = create_engine("sqlite:///vtcs.db")
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Record(Base):
    __tablename__ = "records"
    id = Column(Integer, primary_key=True)
    before_hash = Column(String)
    after_hash = Column(String)
    difference = Column(Float)
    time_diff = Column(Float)
    status = Column(String)

Base.metadata.create_all(engine)

# ---------------- FUNCTIONS ----------------

def get_hash(img_bytes):
    img = Image.open(io.BytesIO(img_bytes))
    return str(imagehash.phash(img))

def compare_images(img1_bytes, img2_bytes):
    img1 = cv2.imdecode(np.frombuffer(img1_bytes, np.uint8), 1)
    img2 = cv2.imdecode(np.frombuffer(img2_bytes, np.uint8), 1)

    img1 = cv2.resize(img1, (400, 400))
    img2 = cv2.resize(img2, (400, 400))

    diff = cv2.absdiff(img1, img2)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    return float(np.mean(gray))

# ---------------- UI ----------------

st.title("🚛 VTCS Image Verification Dashboard")

st.subheader("Upload Before & After Images")

before_file = st.file_uploader("Upload BEFORE Image", type=["jpg", "png"])
after_file = st.file_uploader("Upload AFTER Image", type=["jpg", "png"])

activity_time = st.datetime_input("Select Activity Time")

if st.button("Submit"):

    if before_file and after_file:

        db = Session()

        before_bytes = before_file.read()
        after_bytes = after_file.read()

        # HASH
        before_hash = get_hash(before_bytes)
        after_hash = get_hash(after_bytes)

        duplicate = db.query(Record).filter(
            (Record.before_hash == before_hash) |
            (Record.after_hash == after_hash)
        ).first()

        # IMAGE DIFFERENCE
        diff_score = compare_images(before_bytes, after_bytes)

        # TIME DIFFERENCE
        now = datetime.now()
        time_diff = abs((now - activity_time).total_seconds() / 60)

        # STATUS LOGIC
        status = "VALID"
        if duplicate or diff_score < 10 or time_diff > 60:
            status = "INVALID"

        # SAVE RECORD
        record = Record(
            before_hash=before_hash,
            after_hash=after_hash,
            difference=diff_score,
            time_diff=time_diff,
            status=status
        )

        db.add(record)
        db.commit()

        # OUTPUT
        st.success(f"Status: {status}")
        st.write(f"Image Difference Score: {diff_score}")
        st.write(f"Time Difference (minutes): {time_diff}")
        st.write(f"Duplicate: {'Yes' if duplicate else 'No'}")

# ---------------- DASHBOARD ----------------

st.subheader("📊 Records Dashboard")

db = Session()
records = db.query(Record).all()

data = []
for r in records:
    data.append({
        "ID": r.id,
        "Status": r.status,
        "Difference": r.difference,
        "Time Diff": r.time_diff
    })

if data:
    st.dataframe(data)

    # Simple chart
    st.bar_chart([d["Difference"] for d in data])
else:
    st.info("No records yet")
