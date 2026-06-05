import requests
import streamlit as st
from datetime import datetime

# --- Configuration ---
PERMIT_ID = "74466"
MONTH_API_URL = f"https://www.recreation.gov/api/permits/{PERMIT_ID}/availability/month"
# We removed the hardcoded DIVISIONS URL because we will generate it dynamically!

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": f"https://www.recreation.gov/permits/{PERMIT_ID}/registration/detailed-availability"
}

def find_date_in_json(data, target):
    """Recursively digs through JSON to find the target date."""
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

# User Inputs
col1, col2 = st.columns(2)
with col1:
    selected_date = st.date_input("Select Launch Date")
with col2:
    group_size = st.number_input("Group Size", min_value=1, max_value=30, value=4)

target_date_str = selected_date.strftime("%Y-%m-%d")
launch_month_str = selected_date.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z")

if st.button("Check Availability Now", type="primary"):
    with st.spinner("Pinging Recreation.gov..."):
        launch_available = False
        remaining_launches = 0
        open_camps = []
        
        # 1. Check Overall Launch Permits
        try:
            params_month = {
                "start_date": launch_month_str, 
                "commercial_acct": "false", 
                "is_lottery": "false"
            }
            response_month = requests.get(MONTH_API_URL, params=params_month, headers=HEADERS)
            data_month = response_month.json()
            availability_folder = data_month.get("payload", {}).get("availability", {})
            date_data = find_date_in_json(availability_folder, target_date_str)
            
            if date_data:
                remaining_launches = date_data.get("remaining", 0)
                launch_available = date_data.get("available", False) or remaining_launches > 0
        except Exception as e:
            st.error(f"Failed to check launch permits: {e}")
            
        # 2. Check Specific Campsites (Divisions)
        try:
            # Dynamically build the divisions URL based on the user's inputs
            divisions_url = f"https://www.recreation.gov/api/permits/{PERMIT_ID}/divisions/availability"
            params_divisions = {
                "start_date": f"{target_date_str}T00:00:00Z",
                "end_date": f"{target_date_str}T00:00:00Z",
                "commercial_acct": "false",
                "is_lottery": "false",
                "group_size": group_size
            }
            
            response_camps = requests.get(divisions_url, params=params_divisions, headers=HEADERS)
            
            if response_camps.status_code == 200:
                camp_data = response_camps.json()
                for division_id, division_data in camp_data.get("payload", {}).items():
                    date_info = division_data.get("date_availability", {})
                    target_date_info = find_date_in_json(date_info, target_date_str)
                    
                    if target_date_info and target_date_info.get("remaining", 0) > 0:
                        open_camps.append(division_data.get("division_name", division_id))
            else:
                st.warning(f"Campsite API returned status {response_camps.status_code}. They may have updated the endpoint.")
        except Exception as e:
            st.error(f"Failed to check campsites: {e}")

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
            st.info(f"🏕️ **{len(open_camps)}** Campsites Available for a group of {group_size}:")
            for camp in sorted(open_camps):
                st.write(f"- {camp}")
        else:
            st.warning("❌ No Camps available for this group size.")
