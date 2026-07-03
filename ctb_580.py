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
        
        # 🎯 改動 1：改用「換行讀取」完整的行蹤識別碼，避免新行蹤被吃掉
        last_records = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                last_records = [line.strip() for line in f.readlines() if line.strip()]
        
        is_initial = (len(last_records) == 0) # 00:00 剛啟動或檔案不存在時為初始化
        current_today_records = []          # 儲存當前網頁上所有合法的行蹤
        new_buses_to_notify = []            # 存放本次需要發通知的行蹤
        has_bold_bus = False                # 標記本次通知內是否包含特見
        
        if today_str in html_text:
            after_today = html_text.split(today_str)[1]
            
            for line in after_today.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 🎯 改動 2：精準判定！只有整行「剛好只有日期」才視為昨天的分隔線
                # 這樣 580 常見的 DEAD (2026-07-03 12:31:12) 這種長備註行就不會導致程式腰斬！
                if len(line) == 10 and line.count('-') == 2 and line != today_str:
                    break
                
                tokens = line.split()
                if len(tokens) >= 3:
                    fleet_no, plates_no, route_no = tokens[0], tokens[1], tokens[2]
                    
                    # 兼容所有車隊編號格式
                    if fleet_no.replace('.', '', 1).isdigit() or fleet_no.isalnum():
                        
                        # 🎯 改動 3：建立唯一的「車牌_路線」識別碼
                        # 這樣一來，即使同一台車換了新路線或進了 DEAD 廠，都能當作新動態抓出來！
                        record_key = f"{fleet_no}__{route_no}"
                        
                        if record_key not in current_today_records:
                            current_today_records.append(record_key)
                        
                        # 保留你原本判斷 580 特見號碼的函式
                        is_special = check_bus_number(fleet_no)
                        
                        # 判定：特見加粗，普通車正常
                        if is_special:
                            formatted_output = f"**{fleet_no} ({plates_no}) @ {route_no} ({time_str})**"
                        else:
                            formatted_output = f"{fleet_no} ({plates_no}) @ {route_no} ({time_str})"
                        
                        # 定義是否需要將此行計入通知
                        should_add = False
                        if is_initial:
                            should_add = True
                        else:
                            # 🎯 改動 4：改用 record_key 比對，只要這個車牌搭配此路線沒出現過，就通報
                            if record_key not in last_records:
                                should_add = True
                        
                        if should_add and formatted_output not in new_buses_to_notify:
                            new_buses_to_notify.append(formatted_output)
                            if is_special:
                                has_bold_bus = True
        
        # 有新動態才發通知
        if new_buses_to_notify:
            current_matches_str = "\n".join(new_buses_to_notify)
            
            # 🎯 精準排版：有特見觸發 @everyone，無特見則直接空行排版
            if has_bold_bus:
                msg = f"@everyone\n\n{current_matches_str}"
            else:
                msg = f"\n\n{current_matches_str}"
                
            send_discord_message(msg)
            
        # 🎯 改動 5：改用換行符號將所有最新的組合寫入存檔
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(current_today_records))
                
    except Exception as e:
        print(f"單次檢查出錯: {e}")

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
