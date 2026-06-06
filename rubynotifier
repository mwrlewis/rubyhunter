import requests
import os
from datetime import datetime, timedelta

# --- Configuration ---
PERMIT_ID = "74466"  # Ruby Horsethief
LAUNCH_DATE_STR = "2026-07-15"  # Your target launch date
GROUP_SIZE = 4                  # Your party size
TRIP_NIGHTS = 3                 # Number of nights on the river

# NTFY Configuration - Replace 'your_secret_river_topic' with a unique name
NTFY_TOPIC = "your_secret_river_topic" 

MONTH_API_URL = f"https://www.recreation.gov/api/permits/{PERMIT_ID}/availability/month"
CONTENT_API_URL = f"https://www.recreation.gov/api/permitcontent/{PERMIT_ID}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": f"https://www.recreation.gov/permits/{PERMIT_ID}/registration/detailed-availability"
}

CAMPS_METADATA = {}

def send_ntfy_notification(message, title, priority="default"):
    """Sends a push notification to your phone via ntfy.sh"""
    try:
        url = f"https://ntfy.sh/{NTFY_TOPIC}"
        headers = {
            "Title": title,
            "Priority": priority,
            "Tags": "canoe,alarm_clock"
        }
        res = requests.post(url, data=message.encode('utf-8'), headers=headers)
        res.raise_for_status()
    except Exception as e:
        print(f"Failed to send ntfy notification: {e}")

def load_camp_metadata():
    global CAMPS_METADATA
    if CAMPS_METADATA: return CAMPS_METADATA
    try:
        response = requests.get(CONTENT_API_URL, headers=HEADERS)
        response.raise_for_status()
        divisions = response.json().get("payload", {}).get("divisions", {})
        
        for div_id, div_info in divisions.items():
            name = div_info.get("name") or div_info.get("title") or div_info.get("division_name") or f"Camp {div_id}"
            max_size = div_info.get("max_group_size") or div_info.get("max_capacity") or 30
            downstream_order = div_info.get("order") or div_info.get("display_order") or 999
            
            CAMPS_METADATA[div_id] = {
                "name": name, 
                "max_size": int(max_size),
                "order": int(downstream_order)
            }
        return CAMPS_METADATA
    except Exception as e:
        print(f"Error loading river metadata: {e}")
        return {}

def find_key_in_json(data, target_key):
    if isinstance(data, dict):
        if target_key in data: return data[target_key]
        for k, v in data.items():
            res = find_key_in_json(v, target_key)
            if res is not None: return res
    elif isinstance(data, list):
        for item in data:
            res = find_key_in_json(item, target_key)
            if res is not None: return res
    return None

def find_date_in_json(data, target):
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str) and target in k: return v
            res = find_date_in_json(v, target)
            if res is not None: return res
    elif isinstance(data, list):
        for item in data:
            res = find_date_in_json(item, target)
            if res is not None: return res
    return None

def check_river_itinerary():
    start_date = datetime.strptime(LAUNCH_DATE_STR, "%Y-%m-%d").date()
    dates_to_check = [start_date + timedelta(days=i) for i in range(TRIP_NIGHTS)]
    
    camps_rules = load_camp_metadata()
    if not camps_rules: return
    
    months_needed = {d.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z") for d in dates_to_check}
    month_data = {}
    try:
        for m_str in months_needed:
            params = {"start_date": m_str, "commercial_acct": "false", "is_lottery": "false"}
            res = requests.get(MONTH_API_URL, params=params, headers=HEADERS)
            res.raise_for_status()
            month_data[m_str] = res.json()
    except Exception as e:
        print(f"API Network Error: {e}")
        return

    # Evaluate Day 1 Launch Permit
    launch_month_str = start_date.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z")
    day1_payload = month_data.get(launch_month_str, {})
    availability_folder = day1_payload.get("payload", {}).get("availability", {})
    launch_info = find_date_in_json(availability_folder, LAUNCH_DATE_STR)
    
    launch_available = False
    if launch_info:
        launch_available = launch_info.get("available", False) or launch_info.get("remaining", 0) > 0

    # Evaluate Consecutive Campsites
    itinerary_camps = {}
    itinerary_valid = True
    
    for i, current_date in enumerate(dates_to_check):
        d_str = current_date.strftime("%Y-%m-%d")
        m_str = current_date.replace(day=1).strftime("%Y-%m-%dT00:00:00.000Z")
        current_month_payload = month_data.get(m_str, {})
        
        open_tonight = []
        for div_id, camp_info in camps_rules.items():
            if GROUP_SIZE > camp_info["max_size"]: continue
                
            div_data = find_key_in_json(current_month_payload, div_id)
            if div_data:
                date_info = find_date_in_json(div_data, d_str)
                if date_info and date_info.get("remaining", 0) > 0:
                    open_tonight.append(camp_info)
                    
        open_tonight = sorted(open_tonight, key=lambda x: x["order"])
        itinerary_camps[d_str] = [c["name"] for c in open_tonight]
        
        if not open_tonight:
            itinerary_valid = False

    # Status Logs and ntfy Push Alerts
    if launch_available and itinerary_valid:
        alert_body = f"Launch open on {LAUNCH_DATE_STR}!\n"
        for date_str, camps in itinerary_camps.items():
            alert_body += f"• {date_str}: {', '.join(camps[:3])}...\n"
            
        print("PERMIT ITINERARY FOUND! Sending notification.")
        send_ntfy_notification(alert_body, "🛶 Ruby Permit Found!", priority="high")
    else:
        print("Checked. Itinerary conditions not fully met.")

if __name__ == "__main__":
    check_river_itinerary()
