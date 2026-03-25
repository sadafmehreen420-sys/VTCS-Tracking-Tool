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
# Option 1: Tracking File (TCP)
tcp_file = st.sidebar.file_uploader("Option A: Upload TCP Tracking Report", type=['xlsx', 'csv'])
# Option 2: Waste Entry/Portal (WE)
we_file = st.sidebar.file_uploader("Option B: Upload WE Portal Report", type=['xlsx', 'csv'])

def process_audit(vtcs_df, tcp_df=None, we_df=None):
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

    # --- TRACKING CROSS-CHECK (TCP/WE) ---
    # Combine or choose tracking source
    track_df = tcp_df if tcp_df is not None else we_df
    
    if track_df is not None:
        track_df.columns = [c.strip() for c in track_df.columns]
        # Find time column (usually 2nd column or named 'Time')
        time_col = 'Time' if 'Time' in track_df.columns else track_df.columns[1]
        track_df['Time_Parsed'] = pd.to_datetime(track_df[time_col], errors='coerce')
        
        vtcs_df['Match_Time'] = vtcs_df['Time In'].dt.floor('min')
        track_df['Match_Time'] = track_df['Time_Parsed'].dt.floor('min')
        
        # Merge
        merged = pd.merge(
            vtcs_df, 
            track_df[['Vehicle', 'Match_Time', 'Status']] if 'Status' in track_df.columns else track_df[['Vehicle', 'Match_Time']], 
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
    # Load Main File
    df_vtcs = pd.read_excel(vtcs_file) if vtcs_file.name.endswith('xlsx') else pd.read_csv(vtcs_file)
    
    # Load TCP or WE
    df_tcp = None
    if tcp_file:
        df_tcp = pd.read_excel(tcp_file) if tcp_file.name.endswith('xlsx') else pd.read_csv(tcp_file)
    
    df_we = None
    if we_file:
        df_we = pd.read_excel(we_file) if we_file.name.endswith('xlsx') else pd.read_csv(we_file)
    
    # Run Audit
    results = process_audit(df_vtcs, df_tcp, df_we)

    # --- DASHBOARD UI ---
    st.header("📋 Audit Dashboard")
    
    # Source Indicator
    if tcp_file and we_file:
        st.warning("⚠️ Both TCP and WE uploaded. Defaulting to TCP for audit.")
    elif tcp_file:
        st.info("📊 Auditing using **TCP Tracking** data.")
    elif we_file:
        st.info("📊 Auditing using **WE Portal** data.")

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
