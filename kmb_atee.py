# track_fleet.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
import time
import json
import os
import re

# 設定為香港時間 (UTC+8)
HKT = timezone(timedelta(hours=8))

# ================= 用家設定區 =================
URL = "https://1005.idv.hk/index.php?page=22&p=295"  # 請在此貼上 Across Bus 該車型的專屬網址
WEBHOOK_URL = "https://discord.com/api/webhooks/1522474982930776084/HT3b9m8Ff-YdPA1EmHQvvRi3svVD2ec2cID6m49y2qIy0TEP90w2KQ65z2LwSMFJE77N"  # 請在此貼上 Discord Webhook 網址

# 條件觸發設定
TARGET_ROUTES = []  # 路線編號的條件觸發空位，例如 ["980A", "796X"]，可為空 []
DB_NAME = "kmb_atee"
# ==============================================

DB_FILE = f"db_fleet_{DB_NAME}.json"

def check_condition(route):
    """判斷該路線是否符合用家觸發條件"""
    if not TARGET_ROUTES:
        return False
    # 擷取首個單字作比對（防止 DEAD 或 CTB 等後方帶有括號時間的情況影響判斷）
    route_main = route.split()[0] if route else ""
    return (route_main in TARGET_ROUTES) or (route in TARGET_ROUTES)

def main():
    start_time = time.time()
    max_duration = 3 * 3600 + 55 * 60 
    
    seen_entries = set()
    today_str = datetime.now(HKT).strftime("%Y-%m-%d")
    is_first_run = not os.path.exists(DB_FILE)
    
    if not is_first_run:
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    for entry in data.get("entries", []):
                        seen_entries.add(tuple(entry))
        except:
            pass

    while time.time() - start_time < max_duration:
        now = datetime.now(HKT)
        current_date_str = now.strftime("%Y-%m-%d")
        
        # 凌晨12點換日清空
        if current_date_str != today_str:
            today_str = current_date_str
            seen_entries.clear()
            
        try:
            if URL:
                response = requests.get(URL, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
                lines = soup.get_text(separator='\n').split('\n')
                
                is_today = False
                new_buses = []
                
                for line in lines:
                    line = line.strip()
                    if not line: continue
                        
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', line):
                        if line == today_str:
                            is_today = True
                            continue
                        elif is_today:
                            break
                            
                    if is_today:
                        if '\xa0' in line:
                            parts = line.split('\xa0')
                        else:
                            parts = re.split(r'\s+', line, maxsplit=2)
                            
                        if len(parts) >= 3:
                            fleet_no = parts[0].strip()
                            reg_no = parts[1].strip()
                            route = " ".join(parts[2:]).strip()
                            entry = (fleet_no, reg_no, route)
                            
                            if entry not in seen_entries:
                                seen_entries.add(entry)
                                new_buses.append(entry)
                
                if new_buses:
                    messages = []
                    has_trigger = False
                    time_str = now.strftime("%H:%M")
                    
                    for fleet_no, reg_no, route in new_buses:
                        matched = check_condition(route)
                        line_str = f"{fleet_no} ({reg_no}) @ {route} ({time_str})"
                        if matched:
                            line_str = f"**{line_str}**"
                            has_trigger = True
                        messages.append(line_str)
                    
                    if messages:
                        final_msg = "\n".join(messages)
                        if has_trigger:
                            final_msg = "@everyone\n\n" + final_msg
                            
                        if WEBHOOK_URL:
                            requests.post(WEBHOOK_URL, json={"content": final_msg})
                
                is_first_run = False
                
                with open(DB_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"date": today_str, "entries": list(seen_entries)}, f, ensure_ascii=False)
                    
        except Exception as e:
            print(f"Fetch Error: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    main()