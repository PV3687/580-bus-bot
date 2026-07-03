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
URL = "https://1005.idv.hk/index.php?page=22&p=278"  # 請在此貼上 Across Bus 該車型的專屬網址
WEBHOOK_URL = "https://discord.com/api/webhooks/1522477099053744260/ZBHliZq-E8VuQvJNcAzMG06NyZQcq8_9fu9YWRgIJgmpDjmK7WIiRrTfVxyUwEUBxci0"  # 請在此貼上 Discord Webhook 網址

# 條件觸發設定
TARGET_ROUTES = []  # 路線編號的條件觸發空位，例如 ["980A", "796X"]，可為空 []
DB_NAME = "mtr_8xx_12"
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
                
                # 💡 修正 1：移除 separator='\n'，確保整條巴士紀錄維持在同一行，不被標籤拆散
                lines = soup.get_text().split('\n')
                
                is_today = False
                new_buses = []
                
                for line in lines:
                    line = line.strip()
                    if not line: 
                        continue
                        
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', line):
                        if line == today_str:
                            is_today = True
                            continue
                        elif is_today:
                            break 
                            
                    if is_today:
                        # 💡 核心修正 2：Across Bus 真正的欄位分隔符是 \xa0。
                        # 我們將所有的 \xa0 標記替換為專用切分符，這樣就能100%保留九巴車牌中間的普通空格！
                        line_raw = line.replace('\xa0', '[[SPLIT]]').replace(' ', '[[SPLIT]]')
                        parts = line_raw.split('[[SPLIT]]')
                        
                        # 清理因為網頁排版產生的多餘空欄位
                        parts = [p.strip() for p in parts if p.strip()]
                            
                        if len(parts) >= 3:
                            fleet_no = parts[0]
                            reg_no = parts[1]
                            raw_route = parts[2]
                            
                            # 💡 修正 3：車牌如果是「兩字母+空格+四位數」（例如 RA 4078），它會被分到 parts[1] 和 parts[2] 裡。
                            # 我們檢查 parts[2] 如果是純數字，就代表它是車牌後半部，必須幫它接回 parts[1]
                            if len(parts) >= 4 and parts[2].isdigit():
                                reg_no = f"{parts[1]} {parts[2]}"
                                raw_route = parts[3]
                            
                            # 丟棄主路線後面的詳細地點或網頁自帶的舊時間，只保留第一個單字
                            route = raw_route.split()[0] if raw_route else ""
                            
                            if fleet_no and reg_no and route:
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