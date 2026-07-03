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
                
                # 💡 終極修正 1：利用 \xa0 完美把整個網頁的所有欄位一次過切開，不再依賴 \n 換行！
                full_text = soup.get_text()
                full_text_marked = full_text.replace('\xa0', '|||').replace(' ', '|||')
                tokens = full_text_marked.split('|||')
                
                # 過濾並清理所有空白的標籤物件
                tokens = [t.strip() for t in tokens if t.strip()]
                
                is_today = False
                new_buses = []
                
                # 💡 終極修正 2：用迴圈線性掃描所有切開的欄位
                i = 0
                while i < len(tokens):
                    token = tokens[i]
                    
                    # 檢查是否讀到了日期標籤
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', token):
                        if token == today_str:
                            is_today = True
                            i += 1
                            continue
                        elif is_today:
                            # 讀到昨天的日期，代表今天的部分已全部讀完，立刻安全跳出
                            break 
                    
                    # 💡 終極修正 3：在今天的區域內，每三樣東西就是一輛巴士的完整記錄（車隊、車牌、路線與狀態）
                    if is_today:
                        if i + 2 < len(tokens):
                            fleet_no = tokens[i]
                            reg_no = tokens[i+1]
                            raw_route = tokens[i+2]
                            
                            # 防錯機制：如果因為格式錯位導致拿到另一個日期，就交給外層迴圈去處理日期
                            if re.match(r'^\d{4}-\d{2}-\d{2}$', fleet_no):
                                continue
                                
                            # 💡 完美防錯：如果車牌中間帶有空格（如數字只有3個位），parts[i+2] 剛好會是純數字（例如 221）
                            # 我們自動判定並將其組裝回完整車牌，並把下一個位置的資料當成真正的路線
                            if raw_route.isdigit() and i + 3 < len(tokens):
                                reg_no = f"{tokens[i+1]} {tokens[i+2]}"
                                raw_route = tokens[i+3]
                                i += 1 # 指標向後修正
                            
                            # 丟棄主路線後面的詳細地點與網頁自帶的舊時間，只留第一個單字
                            route = raw_route.split()[0] if raw_route else ""
                            
                            if fleet_no and reg_no and route:
                                entry = (fleet_no, reg_no, route)
                                if entry not in seen_entries:
                                    seen_entries.add(entry)
                                    new_buses.append(entry)
                            
                            i += 3 # 成功讀取一輛巴士的欄位，跳至下一筆
                            continue
                    
                    i += 1
                
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