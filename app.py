import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="VTCS & GPS Auditor", layout="wide")
st.title("🚛 VTCS & GPS Tracking Auditor")

# --- SIDEBAR: FILE UPLOADS ---
st.sidebar.header("Upload Data")
vtcs_file = st.sidebar.file_uploader("1. Upload VTCS Data (Excel/CSV)", type=['xlsx', 'csv'])
tracking_file = st.sidebar.file_uploader("2. Upload Tracking Report (Excel/CSV)", type=['xlsx', 'csv'])

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
