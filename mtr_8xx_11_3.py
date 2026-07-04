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
URL = "https://1005.idv.hk/index.php?page=22&p=323"  # 請在此貼上 Across Bus 該車型的專屬網址
WEBHOOK_URL = "https://discord.com/api/webhooks/1522477172168720395/P3z6ctjZcRPGeKiy_wFrqCEHo95l3l2hQaXZJJHTpJJqV3GqDb0ODNaqs7KErT_oUB-v"  # 請在此貼上 Discord Webhook 網址

# 條件觸發設定
TARGET_ROUTES = []  # 路線編號的條件觸發空位，例如 ["980A", "796X"]，可為空 []
DB_NAME = "mtr_8xx_11_3"
# ==============================================

DB_FILE = f"db_fleet_{DB_NAME}.json"

def check_condition(route):
    """判斷該路線是否符合用家觸發條件"""
    if not TARGET_ROUTES:
        return False
    route_main = route.split()[0] if route else ""
    return (route_main in TARGET_ROUTES) or (route in TARGET_ROUTES)

def send_to_discord(content):
    """發送單條訊息到 Discord，自帶防頻率限制機制"""
    if not WEBHOOK_URL:
        return
    res = requests.post(WEBHOOK_URL, json={"content": content})
    
    # 如果不幸觸發了 Discord 頻率限制 (Rate Limit)，聽從 Discord 指示暫停
    if res.status_code == 429:
        retry_after = res.json().get("retry_after", 1)
        time.sleep(retry_after)
        requests.post(WEBHOOK_URL, json={"content": content})
        
    # 每發完一句，安全延時 1.2 秒，避開 Discord 每 5 秒 5 訊的限制
    time.sleep(1.2)

def main():
    start_time = time.time()
    max_duration = 3 * 3600 + 55 * 60  # 運作時間：3小時55分鐘
    
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
        
        if current_date_str != today_str:
            today_str = current_date_str
            seen_entries.clear()
            
        try:
            if URL:
                response = requests.get(URL, timeout=15)
                
                html_text = response.text.replace('</tr>', '\n').replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                soup = BeautifulSoup(html_text, 'html.parser')
                lines = soup.get_text().split('\n')
                
                is_today = False
                
                for line in lines:
                    line = line.strip()
                    if not line: 
                        continue
                        
                    # 已改回：原版嚴格日期判斷 (精準比對 YYYY-MM-DD 結尾)
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', line):
                        if line == today_str:
                            is_today = True
                            continue
                        elif is_today:
                            break 
                            
                    if is_today:
                        line_raw = line.replace('\xa0', '|').replace(' ', '|')
                        parts = line_raw.split('|')
                        parts = [p.strip() for p in parts if p.strip()]
                        
                        cleaned_parts = []
                        for p in parts:
                            # 核心邏輯：如果這個欄位包含開括號，說明已經到達時間備註區
                            if '(' in p:
                                # 只取括號前面的殘餘字串（如果有讀到路線的話）
                                before_paren = p.split('(')[0].strip()
                                if before_paren:
                                    cleaned_parts.append(before_paren)
                                # 直接中斷欄位迴圈，後面所有的時間、地點、目的地全部丟棄不讀取
                                break
                            
                            # 沒遇到括號，正常放入欄位
                            cleaned_parts.append(p)
                            
                        if len(cleaned_parts) >= 3:
                            fleet_no = cleaned_parts[0]
                            reg_no = cleaned_parts[1]
                            route = cleaned_parts[2]
                            
                            if len(cleaned_parts) >= 4 and cleaned_parts[2].isdigit():
                                reg_no = f"{cleaned_parts[1]} {cleaned_parts[2]}"
                                route = cleaned_parts[3]
                                
                            if fleet_no and reg_no and route:
                                entry = (fleet_no, reg_no, route)
                                
                                # 發現新數據，立刻進入單條發送流程
                                if entry not in seen_entries:
                                    seen_entries.add(entry)
                                    
                                    time_str = now.strftime("%H:%M")
                                    matched = check_condition(route)
                                    line_str = f"{fleet_no} ({reg_no}) @ {route} ({time_str})"
                                    
                                    if matched:
                                        line_str = f"@everyone\n\n**{line_str}**"
                                    
                                    # 呼叫獨立的發送函數，一條條發送
                                    send_to_discord(line_str)
                
                is_first_run = False
                
                # 每次迴圈結束後儲存當前已讀資料庫
                with open(DB_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"date": today_str, "entries": list(seen_entries)}, f, ensure_ascii=False)
                    
        except Exception as e:
            print(f"Fetch Error: {e}")
            
        # 檢查完一次網頁後，原地小憩 60 秒
        time.sleep(60)

if __name__ == "__main__":
    main()