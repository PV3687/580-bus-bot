import requests
import os
import time
from datetime import datetime

# ==================== 【 自 訂 設 定 區 】 ====================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1522477172168720395/P3z6ctjZcRPGeKiy_wFrqCEHo95l3l2hQaXZJJHTpJJqV3GqDb0ODNaqs7KErT_oUB-v"
URL = "https://1005.idv.hk/index.php?page=22&p=323" 
DATA_FILE = "last_mtr_8xx_11_3.txt"
# ============================================================

BOLD_ROUTES = [] 
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def send_discord_message(msg):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    except:
        pass

def check_once():
    try:
        res = requests.get(URL, headers=HEADERS)
        res.encoding = 'big5'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 解決特殊空白問題
        html_text = soup.text.replace('\xa0', ' ')
        
        today_str = datetime.today().strftime('%Y-%m-%d')
        time_str = datetime.now().strftime('%H:%M')
        
        # 讀取這 24 小時生命週期內上一次記錄的車隊清單
        last_buses = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                last_buses = [b.strip() for b in f.read().split(',') if b.strip()]
        
        is_initial = (len(last_buses) == 0) # 00:00 剛啟動時為空，視為初始化
        current_today_buses = []            # 當前網頁上所有出現的車隊
        new_buses_to_notify = []            # 存放本次需要發通知的行蹤
        has_bold_route = False              # 標記本次通知內是否包含特見路線
        
        if today_str in html_text:
            after_today = html_text.split(today_str)[1]
            
            for line in after_today.split('\n'):
                line = line.strip()
                if not line: 
                    continue
                
                if len(line) == 10 and line.count('-') == 2 and line != today_str:
                    break
                
                tokens = line.split()
                if len(tokens) >= 3:
                    fleet_no, plates_no, route_no = tokens[0], tokens[1], tokens[2]
                    
                    if fleet_no.isdigit():
                        if fleet_no not in current_today_buses:
                            current_today_buses.append(fleet_no)
                        
                        is_special = route_no in BOLD_ROUTES
                        
                        # 判定：特見路線加粗，普通路線正常
                        if is_special:
                            formatted_line = f"**{fleet_no} ({plates_no}) @ {route_no} ({time_str})**"
                        else:
                            formatted_line = f"{fleet_no} ({plates_no}) @ {route_no} ({time_str})"
                        
                        # 定義是否需要將此行計入通知
                        should_add = False
                        if is_initial:
                            should_add = True
                        else:
                            if fleet_no not in last_buses:
                                should_add = True
                        
                        if should_add and formatted_line not in new_buses_to_notify:
                            new_buses_to_notify.append(formatted_line)
                            if is_special:
                                has_bold_route = True
                            
        # 有新動態才發通知
        if new_buses_to_notify:
            current_matches_str = "\n".join(new_buses_to_notify)
            
            # 🎯 核心判定：只有含有加粗特見才觸發 @everyone，其餘直接空行排版
            if has_bold_route:
                final_msg = f"@everyone\n\n{current_matches_str}"
            else:
                final_msg = f"\n\n{current_matches_str}"
                
            send_discord_message(final_msg)
            
        # 覆寫本地紀錄，供全天候下一分鐘比對
        with open(DATA_FILE, 'w', encoding='utf-8') as f: 
            f.write(",".join(current_today_buses))
    except: 
        pass

def main():
    # 🎯 核心判定：如果是在香港時間 00:00（即 UTC 16:00）這一輪剛醒來
    # 立即清除昨天的舊紀錄，確保新的一天開始時會執行「初始化全出」
    current_utc_hour = datetime.utcnow().hour
    if current_utc_hour == 16:
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
            print(" Midnight！新的一天開始，已自動清空昨日特見存檔。")
            
    print("🚀 巴士監控循環啟動...")
    # 🎯 每次喚醒連續執行 235 次（共 3 小時 55 分鐘，每 60 秒檢查一次）
    # 提早 5 分鐘正常關機，留給系統收尾，等下一個 4 小時準時被定時任務喚醒
    for i in range(235):
        check_once()
        if i < 234:
            time.sleep(60)

if __name__ == "__main__":
    main()
