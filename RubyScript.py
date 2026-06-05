import requests
import streamlit as st
from datetime import datetime

# --- Configuration ---
MONTH_API_URL = "https://www.recreation.gov/api/permits/74466/availability/month"
# Optional: Paste your divisions URL here if you have it!
DIVISIONS_API_URL = "PASTE_DIVISIONS_URL_HERE" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.recreation.gov/permits/74466/registration/detailed-availability"
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
st.set_page_config(page_title="Ruby Tracker", page_icon="🛶")
st.title("🛶 Ruby Horsethief Tracker")

# Interactive Calendar Input
selected_date = st.date_input("Select Launch Date")
target_date_str = selected_date.strftime("%Y-%m-%d")
launch_month_str = selected_date.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z")

if st.button("Check Availability Now"):
    with st.spinner("Pinging Recreation.gov..."):
        launch_available = False
        remaining_launches = 0
        open_camps = []
        
        # 1. Check Launches
        try:
            response = requests.get(MONTH_API_URL, params={"start_date": launch_month_str, "commercial_acct": "false", "is_lottery": "false"}, headers=HEADERS)
            data = response.json()
            availability_folder = data.get("payload", {}).get("availability", {})
            date_data = find_date_in_json(availability_folder, target_date_str)
            
            if date_data:
                remaining_launches = date_data.get("remaining", 0)
                launch_available = date_data.get("available", False) or remaining_launches > 0
        except Exception as e:
            st.error(f"Launch API Error: {e}")
            
        # 2. Check Campsites
        if DIVISIONS_API_URL != "PASTE_DIVISIONS_URL_HERE":
            try:
                response_camps = requests.get(DIVISIONS_API_URL, headers=HEADERS)
                camp_data = response_camps.json()
                for division_id, division_data in camp_data.get("payload", {}).items():
                    target_date_info = find_date_in_json(division_data.get("date_availability", {}), target_date_str)
                    if target_date_info and target_date_info.get("remaining", 0) > 0:
                        open_camps.append(division_data.get("division_name", division_id))
            except Exception as e:
                st.error(f"Campsite API Error: {e}")

        # --- Display Results ---
        st.divider()
        if launch_available:
            st.success(f"✅ {remaining_launches} Launch Permit(s) Available!")
        else:
            st.error("❌ No Launch Permits available.")
            
        if DIVISIONS_API_URL != "PASTE_DIVISIONS_URL_HERE":
            if open_camps:
                st.info(f"🏕️ {len(open_camps)} Camps Available:")
                for camp in open_camps:
                    st.write(f"- {camp}")
            else:
                st.warning("❌ No Camps available.")