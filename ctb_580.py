import re
import requests
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime, timedelta

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
    """執行單次網頁抓取與比對邏輯（純路線監控版本 - 支援 580 及所有指定路線）"""
    try:
        res = requests.get(URL, headers=HEADERS)
        res.encoding = 'big5'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 解決特殊空白問題
        html_text = soup.text.replace('\xa0', ' ')
        
        # 將時間強制轉換為香港本地時間（UTC + 8 小時）
        hkt_now = datetime.utcnow() + timedelta(hours=8)
        today_str = hkt_now.strftime('%Y-%m-%d')
        time_str = hkt_now.strftime('%H:%M')
        
        # 讀取上一次記錄的完整行蹤識別碼 (車牌__路線)
        last_records = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                last_records = [line.strip() for line in f.readlines() if line.strip()]
        
        is_initial = (len(last_records) == 0) # 如果是空檔，代表是這 4 小時內第一次開機
        current_today_records = []            # 儲存當前網頁上所有合法的行蹤
        new_buses_to_notify = []              # 本次需要發通知的行蹤
        has_bold_trigger = False              # 標記本次通知內是否包含特見路線
        
        if today_str in html_text:
            after_today = html_text.split(today_str)[1]
            
            for line in after_today.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 單行局部防護罩，防止 DEAD 長備註字元爆炸
                try:
                    tokens = line.split()
                    if len(tokens) >= 3:
                        fleet_no, plates_no, route_no = tokens[0], tokens[1], tokens[2]
                        
                        # 放寬判定，只要前兩欄合法就抓取
                        if fleet_no.isdigit() or fleet_no.replace('.', '', 1).isdigit() or fleet_no.isalnum():
                            
                            # 建立唯一的「車牌__路線」識別碼
                            record_key = f"{fleet_no}__{route_no}"
                            
                            if record_key not in current_today_records:
                                current_today_records.append(record_key)
                            
                            # 🎯 路線版特見判定：檢查這條路線有沒有在你的 BOLD_ROUTES 裡面
                            # (如果是 580 檔案，且你想改用車牌判定，可以把這裡改成 is_special = check_bus_number(fleet_no))
                            is_special = route_no in BOLD_ROUTES
                            
                            # 判定排版格式
                            if is_special:
                                formatted_line = f"**{fleet_no} ({plates_no}) @ {route_no} ({time_str})**"
                            else:
                                formatted_line = f"{fleet_no} ({plates_no}) @ {route_no} ({time_str})"
                            
                            # 比對去重邏輯
                            should_add = False
                            if is_initial:
                                # 🎯 優化：首輪開機，把當下網頁上的所有車都噴出來，方便你立刻確認程式有在跑
                                should_add = True
                            else:
                                # 之後的每一分鐘，只有「車牌+路線」組合全新出現時才發通知
                                if record_key not in last_records:
                                    should_add = True
                            
                            if should_add and formatted_line not in new_buses_to_notify:
                                new_buses_to_notify.append(formatted_line)
                                if is_special:
                                    has_bold_trigger = True
                                    
                except Exception as line_err:
                    print(f"單行解析跳過: {line_err}")
                    continue
                            
        # 有新動態才發通知
        if new_buses_to_notify:
            current_matches_str = "\n".join(new_buses_to_notify)
            
            if has_bold_trigger:
                final_msg = f"@everyone\n\n{current_matches_str}"
            else:
                final_msg = f"\n\n{current_matches_str}"
                
            send_discord_message(final_msg)
            
        # 將當前所有的識別碼寫入本地存檔
        with open(DATA_FILE, 'w', encoding='utf-8') as f: 
            f.write("\n".join(current_today_records))
            
    except Exception as e: 
        print(f"總體檢查出錯: {e}")

def main():
    # 香港時間午夜 00:00 這一輪剛醒來時，立即清除昨天的舊紀錄，重設初始化
    hkt_hour = (datetime.utcnow() + timedelta(hours=8)).hour
    if hkt_hour == 0:
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
            print(" Midnight HKT！已自動清空昨日存檔。")
            
    print("🚀 巴士路線監控循環啟動...")
    for i in range(235):
        check_once()
        if i < 234:
            time.sleep(60)

if __name__ == "__main__":
    main()