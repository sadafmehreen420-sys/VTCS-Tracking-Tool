import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="VTCS & GPS Auditor", layout="wide")
st.title("🚛 VTCS & GPS Tracking Auditor") 

# --- SIDEBAR: FILE UPLOADS ---
st.sidebar.header("1. Primary Data")
vtcs_file = st.sidebar.file_uploader("Upload VTCS Main Data", type=['xlsx', 'csv'])

st.sidebar.header("2. Tracking Module Options")

# Dropdown to select tracking source
tracking_source = st.sidebar.selectbox(
    "Select Tracking Source",
    ["None", "Tracking Report", "TCP/WE Report"]
)

# Initialize variables for the processing function
df_track = None
df_tcp = None
df_we = None

# Show specific uploader based on dropdown choice
if tracking_source == "Tracking Report":
    tracking_file = st.sidebar.file_uploader("Upload Tracking Report", type=['xlsx', 'csv'])
    if tracking_file:
        df_track = pd.read_excel(tracking_file) if tracking_file.name.endswith('xlsx') else pd.read_csv(tracking_file)

elif tracking_source == "TCP/WE Report":
    # Sub-options if needed, or just a single uploader for the chosen report type
    report_type = st.sidebar.radio("Report Type", ["TCP", "WE"])
    we_tcp_file = st.sidebar.file_uploader(f"Upload {report_type} Report", type=['xlsx', 'csv'])
    if we_tcp_file:
        if report_type == "TCP":
            df_tcp = pd.read_excel(we_tcp_file) if we_tcp_file.name.endswith('xlsx') else pd.read_csv(we_tcp_file)
        else:
            df_we = pd.read_excel(we_tcp_file) if we_tcp_file.name.endswith('xlsx') else pd.read_csv(we_tcp_file)

def process_audit(vtcs_df, track_df=None, tcp_df=None, we_df=None):
    # --- VTCS PROCESSING ---
    cols_to_fix = ['Waste Collected (Kg)', 'Before Weight', 'After Weight (Kg)']
    for col in cols_to_fix:
        if col in vtcs_df.columns:
            vtcs_df[col] = pd.to_numeric(vtcs_df[col].astype(str).str.replace(',', ''), errors='coerce')
    
    vtcs_df['Tonnage'] = vtcs_df.get('Waste Collected (Kg)', 0) / 1000
    vtcs_df['Time In'] = pd.to_datetime(vtcs_df['Time In'], errors='coerce')
    vtcs_df['Time Out'] = pd.to_datetime(vtcs_df['Time Out'], errors='coerce')
    
    vtcs_df['Duration_Mins'] = (vtcs_df['Time Out'] - vtcs_df['Time In']).dt.total_seconds() / 60
    vtcs_df['Time_Status'] = vtcs_df['Duration_Mins'].apply(lambda x: "🚨 Suspicious (>30m)" if x > 30 else "✅ Normal")

    # Determine which tracking data to use
    active_track = track_df if track_df is not None else (tcp_df if tcp_df is not None else we_df)
    
    if active_track is not None:
        active_track.columns = [c.strip() for c in active_track.columns]
        # Auto-detect time column
        time_col = 'Time' if 'Time' in active_track.columns else active_track.columns[1]
        active_track['Time_Parsed'] = pd.to_datetime(active_track[time_col], errors='coerce')
        
        vtcs_df['Match_Time'] = vtcs_df['Time In'].dt.floor('min')
        active_track['Match_Time'] = active_track['Time_Parsed'].dt.floor('min')
        
        merged = pd.merge(
            vtcs_df, 
            active_track[['Vehicle', 'Match_Time', 'Status']] if 'Status' in active_track.columns else active_track[['Vehicle', 'Match_Time']], 
            on=['Vehicle', 'Match_Time'], 
            how='left'
        )
        
        def check_status(row):
            if 'Status' not in row or pd.isna(row['Status']):
                return "❓ No GPS Match"
            status = str(row['Status']).lower()
            return "✅ Verified" if 'idle' in status else "❌ Conflict"

        merged['GPS_Audit'] = merged.apply(check_status, axis=1)
        return merged
    
    return vtcs_df

if vtcs_file:
    df_vtcs = pd.read_excel(vtcs_file) if vtcs_file.name.endswith('xlsx') else pd.read_csv(vtcs_file)
    
    # Run Audit with whichever file was uploaded
    results = process_audit(df_vtcs, track_df=df_track, tcp_df=df_tcp, we_df=df_we)

    # --- DASHBOARD UI ---
    st.header("📋 Audit Dashboard")
    if tracking_source != "None":
        st.info(f"📊 Auditing using **{tracking_source}** data.")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Tonnage", f"{results['Tonnage'].sum():.2f} Tons")
    m2.metric("Delayed Trips", len(results[results['Time_Status'].str.contains("🚨")]))
    
    if 'GPS_Audit' in results.columns:
        conflicts = len(results[results['GPS_Audit'].str.contains("❌")])
        m3.metric("GPS Conflicts", conflicts)

    # Main Table
    display_cols = ['Vehicle', 'Time In', 'Time Out', 'Duration_Mins', 'Tonnage', 'Time_Status']
    if 'GPS_Audit' in results.columns:
        display_cols.append('GPS_Audit')

    def color_rows(val):
        if '🚨' in str(val) or '❌' in str(val): return 'background-color: #ffcccc'
        if '✅' in str(val): return 'background-color: #ccffcc'
        return ''

    st.dataframe(results[display_cols].style.applymap(color_rows), use_container_width=True)
else:
    st.info("Please upload your VTCS file from the sidebar to start.")
