import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- Configuration ---
PERMIT_ID = "74466"
MONTH_API_URL = f"https://www.recreation.gov/api/permits/{PERMIT_ID}/availability/month"
CONTENT_API_URL = f"https://www.recreation.gov/api/permitcontent/{PERMIT_ID}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": f"https://www.recreation.gov/permits/{PERMIT_ID}/registration/detailed-availability"
}

@st.cache_data(ttl=86400)
def get_camp_metadata():
    """Fetches the master rulebook and preserves the downstream sorting order."""
    try:
        response = requests.get(CONTENT_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        
        camps = {}
        divisions = data.get("payload", {}).get("divisions", {})
        
        for div_id, div_info in divisions.items():
            name = (
                div_info.get("name") or 
                div_info.get("title") or 
                div_info.get("division_name") or 
                f"Camp {div_id}"
            )
            max_size = div_info.get("max_group_size") or div_info.get("max_capacity") or 30
            
            # Recreation.gov uses an 'order' integer to sequence camps downstream
            downstream_order = div_info.get("order") or div_info.get("display_order") or 999
            
            camps[div_id] = {
                "name": name, 
                "max_size": int(max_size),
                "order": int(downstream_order)
            }
            
        return camps
    except Exception as e:
        st.error(f"Failed to load camp metadata: {e}")
        return {}

def find_key_in_json(data, target_key):
    """Recursively digs to find a specific key (like a division ID)."""
    if isinstance(data, dict):
        if target_key in data:
            return data[target_key]
        for key, value in data.items():
            result = find_key_in_json(value, target_key)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_key_in_json(item, target_key)
            if result is not None:
                return result
    return None

def find_date_in_json(data, target):
    """Recursively digs through JSON to find the target date string."""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str) and target in key:
                return value
            result = find_date_in_json(value, target)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_date_in_json(item, target)
            if result is not None:
                return result
    return None

# --- Web Interface ---
st.set_page_config(page_title="River Permit Grid", page_icon="🛶", layout="wide")
st.title("🛶 River Permit Downstream Grid")

camps_metadata = get_camp_metadata()

# Sort the camps immediately by their downstream order value
sorted_camp_ids = sorted(camps_metadata.keys(), key=lambda x: camps_metadata[x]["order"])

# User Inputs
col1, col2, col3 = st.columns(3)
with col1:
    selected_date = st.date_input("Launch Date", value=datetime(2026, 7, 15))
with col2:
    group_size = st.number_input("Group Size", min_value=1, max_value=30, value=4)
with col3:
    trip_nights = st.number_input("Nights on River", min_value=1, max_value=7, value=3)

# Build out column headers
dates_to_check = [selected_date + timedelta(days=i) for i in range(trip_nights)]

if st.button("Generate Downstream Grid", type="primary"):
    with st.spinner("Building grid from live data..."):
        
        # Fetch required months
        months_needed = {d.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z") for d in dates_to_check}
        month_data = {}
        try:
            for m_str in months_needed:
                params_month = {"start_date": m_str, "commercial_acct": "false", "is_lottery": "false"}
                res = requests.get(MONTH_API_URL, params=params_month, headers=HEADERS)
                res.raise_for_status()
                month_data[m_str] = res.json()
        except Exception as e:
            st.error(f"API Error: {e}")
            st.stop()
            
        st.divider()
        
        # --- Launch Permit Check Banner ---
        launch_date_str = dates_to_check[0].strftime("%Y-%m-%d")
        launch_month_str = dates_to_check[0].replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z")
        availability_folder = month_data.get(launch_month_str, {}).get("payload", {}).get("availability", {})
        launch_info = find_date_in_json(availability_folder, launch_date_str)
        
        if launch_info and (launch_info.get("available", False) or launch_info.get("remaining", 0) > 0):
            st.success(f"✅ **{launch_info.get('remaining', 0)} Launch Permit(s)** available to start your trip on {launch_date_str}!")
        else:
            st.error(f"❌ **No Launch Permits** available to start a trip on {launch_date_str}.")

        # --- Build Table Matrix ---
        grid_data = []
        campsite_row_labels = []
        
        for div_id in sorted_camp_ids:
            camp_info = camps_metadata[div_id]
            
            # If group size is systematically too big for this camp, skip showing the row entirely
            if group_size > camp_info["max_size"]:
                continue
                
            campsite_row_labels.append(camp_info["name"])
            row_availabilities = []
            
            # Check availability across consecutive nights
            for i, current_date in enumerate(dates_to_check):
                date_str = current_date.strftime("%Y-%m-%d")
                month_str = current_date.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z")
                current_month_data = month_data.get(month_str, {})
                
                div_availability_data = find_key_in_json(current_month_data, div_id)
                is_open = False
                
                if div_availability_data:
                    target_date_info = find_date_in_json(div_availability_data, date_str)
                    if target_date_info and target_date_info.get("remaining", 0) > 0:
                        is_open = True
                        
                # Recreate the clean look of image_708aba.png using text cues
                row_availabilities.append("⛺ Available" if is_open else "—")
                
            grid_data.append(row_availabilities)
            
        # Structure columns beautifully as Night 1 (Date), Night 2 (Date)...
        column_headers = [f"Night {i+1} ({d.strftime('%b %d')})" for i, d in enumerate(dates_to_check)]
        
        if grid_data:
            df = pd.DataFrame(grid_data, columns=column_headers, index=campsite_row_labels)
            
            # Render out the complete grid on screen
            st.subheader("🗺️ Downstream Camp Grid")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No camps match your criteria or metadata failed to parse.")
