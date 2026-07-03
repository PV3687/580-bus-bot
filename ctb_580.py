import re
import requests
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime

# ==================== 【 自 訂 設 定 區 】 ====================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1522450077715529838/Rsrx4DKFRsCjZsMhI5Afa84UdBCG7ZWcFLubc-2td4rR2qZq4tjG2f8ZEJaHp50aUrOd"
URL = "https://1005.idv.hk/index.php?page=21&rt=580"
DATA_FILE = "last_ctb_580.txt"
# ============================================================

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def check_bus_number(bus_str):
    """檢查車隊編號是否符合特見範圍：5518-5582, 51155-51208, 8100-8319"""
    numbers = re.findall(r'\d+', bus_str)
    if not numbers:
        return False
    bus_num = int(numbers[0])
    if (5518 <= bus_num <= 5582) or (51155 <= bus_num <= 51208) or (8100 <= bus_num <= 8319):
        return True
    return False

def send_discord_message(msg):
    """發送 Discord 推播通知"""
    payload = {"content": msg}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("Discord 通知發送成功！")
        else:
            print(f"Discord 發送失敗: {response.status_code}")
    except Exception as e:
        print(f"發送失敗: {e}")

def check_once():
    """執行單次網頁抓取與比對邏輯"""
    try:
        res = requests.get(URL, headers=HEADERS)
        res.encoding = 'big5'
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
        current_today_buses = []            # 當前網頁上所有出現的車
        new_buses_to_notify = []            # 存放本次需要發通知的行蹤
        has_bold_bus = False                # 標記本次通知內是否包含特見
        
        if today_str in html_text:
            # 安全切片：防止被備註截斷
            after_today = html_text.split(today_str)[1]
            
            for line in after_today.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if len(line) == 10 and line.count('-') == 2 and line != today_str:
                    break
                
                tokens = line.split()
                if len(tokens) >= 3:
                    # 拿回 tokens[2]，直接作為網頁上顯示的路線
                    fleet_no, plates_no, route_no = tokens[0], tokens[1], tokens[2]
                    
                    if fleet_no.replace('.', '', 1).isdigit() or fleet_no.isdigit():
                        if fleet_no not in current_today_buses:
                            current_today_buses.append(fleet_no)
                        
                        is_special = check_bus_number(fleet_no)
                        
                        # 判定：特見加粗，普通車正常
                        if is_special:
                            formatted_output = f"**{fleet_no} ({plates_no}) @ {route_no} ({time_str})**"
                        else:
                            formatted_output = f"{fleet_no} ({plates_no}) @ 580 ({time_str})" # 修正：統一顯示 @ 580 
                            formatted_output = f"{fleet_no} ({plates_no}) @ {route_no} ({time_str})"
                        
                        # 定義是否需要將此行計入通知
                        should_add = False
                        if is_initial:
                            should_add = True
                        else:
                            if fleet_no not in last_buses:
                                should_add = True
                        
                        if should_add and formatted_output not in new_buses_to_notify:
                            new_buses_to_notify.append(formatted_output)
                            # 🎯 如果這部新車是特見，就把標記設為 True
                            if is_special:
                                has_bold_bus = True
        
        # 有新動態才發通知
        if new_buses_to_notify:
            current_matches_str = "\n".join(new_buses_to_notify)
            
            # 🎯 核心判定：只有含有加粗特見才觸發 @everyone
            if has_bold_bus:
                msg = f"@everyone\n\n{current_matches_str}"
            else:
                msg = f"\n\n{current_matches_str}"
                
            send_discord_message(msg)
            
        # 覆寫本地紀錄，供全天候下一分鐘比對
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            f.write(",".join(current_today_buses))
                
    except Exception as e:
        print(f"單次檢查出錯: {e}")

def main():
    # 每天 00:00 重新喚醒時，自動移除昨天的殘留檔案，重設初始化
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
        
    print("🚀 巴士路線 24H 全天候監控啟動...")
    # 連續執行 1440 次（24 小時，每 60 秒檢查一次）
    for i in range(1440):
        print(f"⏱️ 正在執行第 {i+1}/1440 次檢查...")
        check_once()
        if i < 1439:
            time.sleep(60)

if __name__ == "__main__":
    main()