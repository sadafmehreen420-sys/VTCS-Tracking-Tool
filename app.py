import pandas as pd
import numpy as np
import streamlit as st

# Haversine Distance Function
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    c = 2*np.arcsin(np.sqrt(a))
    
    return R * c

st.header("2. Tracking Module")

tracking_file = st.file_uploader("Upload Tracking Report", type=["xlsx","csv"])
coord_file = st.file_uploader("Upload TCP/WE Coordinates", type=["xlsx","csv"])

if tracking_file and coord_file:

    # Read files
    tracking = pd.read_excel(tracking_file) if tracking_file.name.endswith("xlsx") else pd.read_csv(tracking_file)
    coords = pd.read_excel(coord_file) if coord_file.name.endswith("xlsx") else pd.read_csv(coord_file)

    # Clean column names (important)
    tracking.columns = tracking.columns.str.strip().str.lower()
    coords.columns = coords.columns.str.strip().str.lower()

    # Rename columns to standard
    tracking = tracking.rename(columns={
        "vehicle": "vehicle",
        "lat": "lat",
        "long": "lon"
    })

    coords = coords.rename(columns={
        "name": "location",
        "lat": "lat",
        "long": "lon"
    })

    results = []

    # Matching Logic
    for _, t in tracking.iterrows():
        for _, c in coords.iterrows():

            dist = haversine(t['lat'], t['lon'], c['lat'], c['lon'])

            if dist <= 0.2:  # 200 meters threshold
                results.append({
                    "Vehicle": t['vehicle'],
                    "Location (TCP/WE)": c['location'],
                    "Distance (KM)": round(dist, 3)
                })

    result_df = pd.DataFrame(results)

    if not result_df.empty:
        # Remove duplicates
        result_df = result_df.drop_duplicates()

        st.success("✅ Matching Completed Successfully")

        st.dataframe(result_df)

        # Download option
        csv = result_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Result", csv, "vehicle_tracking_result.csv")

    else:
        st.warning("❌ No vehicle matched with any TCP/WE location")
