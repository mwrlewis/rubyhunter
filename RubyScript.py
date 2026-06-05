import requests
import streamlit as st
from datetime import datetime

# --- Configuration ---
PERMIT_ID = "74466"
MONTH_API_URL = f"https://www.recreation.gov/api/permits/{PERMIT_ID}/availability/month"
CONTENT_API_URL = f"https://www.recreation.gov/api/permitcontent/{PERMIT_ID}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": f"https://www.recreation.gov/permits/{PERMIT_ID}/registration/detailed-availability"
}

@st.cache_data(ttl=86400) # Caches the rulebook for 24 hours
def get_camp_metadata():
    """Fetches the master rulebook for the permit to get camp names and capacities."""
    try:
        response = requests.get(CONTENT_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        
        camps = {}
        divisions = data.get("payload", {}).get("divisions", {})
        
        for div_id, div_info in divisions.items():
            # --- THE AUTO-MAP FIX ---
            # Hunts through the dictionary for any key that might hold the name
            name = (
                div_info.get("name") or 
                div_info.get("title") or 
                div_info.get("division_name") or 
                div_info.get("facility_name") or 
                div_info.get("description") or
                f"Camp {div_id}"
            )
            
            # Grab max capacity (default to 30 if blank)
            max_size = div_info.get("max_group_size") or div_info.get("max_capacity") or 30
            camps[div_id] = {"name": name, "max_size": int(max_size)}
            
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
st.set_page_config(page_title="River Permit Tracker", page_icon="🛶")
st.title("🛶 River Permit Tracker")

# 1. Load the camp metadata invisibly in the background
camps_metadata = get_camp_metadata()

# User Inputs
col1, col2 = st.columns(2)
with col1:
    selected_date = st.date_input("Select Launch Date", value=datetime(2026, 7, 15))
with col2:
    group_size = st.number_input("Your Group Size", min_value=1, max_value=30, value=4)

target_date_str = selected_date.strftime("%Y-%m-%d")
launch_month_str = selected_date.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z")

if st.button("Check Availability Now", type="primary"):
    with st.spinner("Pinging Recreation.gov..."):
        launch_available = False
        remaining_launches = 0
        open_camps = []
        
        try:
            # 2. Fetch the giant availability data dump for the month
            params_month = {"start_date": launch_month_str, "commercial_acct": "false", "is_lottery": "false"}
            response_month = requests.get(MONTH_API_URL, params=params_month, headers=HEADERS)
            data_month = response_month.json()
            
            # --- A. Check Overall Launch Permits ---
            availability_folder = data_month.get("payload", {}).get("availability", {})
            date_data = find_date_in_json(availability_folder, target_date_str)
            
            if date_data:
                remaining_launches = date_data.get("remaining", 0)
                launch_available = date_data.get("available", False) or remaining_launches > 0
                
            # --- B. Check Specific Campsites ---
            # Loop through every camp we found in the rulebook
            for div_id, camp_info in camps_metadata.items():
                
                # LOCAL FILTERING: If your group is too big, ignore this camp entirely!
                if group_size > camp_info["max_size"]:
                    continue
                
                # Dig through the month data to find this specific camp's ID
                div_availability_data = find_key_in_json(data_month, div_id)
                
                if div_availability_data:
                    # Find our specific launch date inside that camp's data
                    target_date_info = find_date_in_json(div_availability_data, target_date_str)
                    
                    if target_date_info and target_date_info.get("remaining", 0) > 0:
                        open_camps.append(f"{camp_info['name']} (Max: {camp_info['max_size']})")
                        
        except Exception as e:
            st.error(f"API Error: {e}")

        # --- Display Results ---
        st.divider()
        st.subheader(f"Results for {target_date_str} (Group of {group_size})")
        
        # Display Launch Quotas
        if launch_available:
            st.success(f"✅ **{remaining_launches}** Launch Permit(s) Available to start a trip!")
        else:
            st.error("❌ No Launch Permits available to start a trip on this date.")
            
        # Display Campsites
        st.write("---")
        if open_camps:
            st.info(f"🏕️ **{len(open_camps)}** Campsites Available:")
            for camp in sorted(open_camps):
                st.write(f"- {camp}")
        else:
            if camps_metadata:
                st.warning("❌ No Camps available for your group size.")
            else:
                st.warning("⚠️ Could not load camp list. The API might have blocked the request.")
