# track_route.py
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
URL = "https://1005.idv.hk/index.php?page=21&rt=580"  # 請在此貼上 Across Bus 該路線的專屬網址，例如 https://1005.idv.hk/index.php?page=xx&route=580
WEBHOOK_URL = "https://discord.com/api/webhooks/1522450077715529838/Rsrx4DKFRsCjZsMhI5Afa84UdBCG7ZWcFLubc-2td4rR2qZq4tjG2f8ZEJaHp50aUrOd"  # 請在此貼上 Discord Webhook 網址

# 條件觸發設定 (皆可為空)
TARGET_PREFIX = ""  # 車隊編號英文字首，例如 "E" 或 "ATENU" (留空代表不限制字首)

# 車隊編號數字範圍，支援多組範圍並以逗號分隔，例如: "5518-5582, 8100-8319"
# 也可以單獨輸入某個數字，例如: "5518-5582, 5590, 8100-8319"
TARGET_RANGES = "5518-5582, 8100-8319, 51155-51208, 4020-4039, 41000-41019"  
DB_NAME = "ctb_580"
# ==============================================

DB_FILE = f"db_route_{DB_NAME}.json"

def parse_range_setting(range_str):
    """解析用家輸入的多組數字範圍"""
    if not range_str.strip():
        return []
    
    parsed_ranges = []
    # 依逗號分割多組設定
    groups = range_str.split(',')
    for group in groups:
        group = group.strip()
        if not group:
            continue
        if '-' in group:
            # 處理範圍型，如 "5518-5582"
            parts = group.split('-')
            if len(parts) == 2:
                try:
                    start = int(re.sub(r'\D', '', parts[0]))
                    end = int(re.sub(r'\D', '', parts[1]))
                    parsed_ranges.append((start, end))
                except ValueError:
                    pass
        else:
            # 處理單一數字型，如 "5590"
            try:
                num = int(re.sub(r'\D', '', group))
                parsed_ranges.append((num, num))
            except ValueError:
                pass
    return parsed_ranges

def check_condition(fleet_no, parsed_ranges):
    """判斷該車隊編號是否符合用家設定的字首及多組數字範圍條件"""
    # 如果完全沒有設定任何條件，預設不觸發強烈通知
    if not TARGET_PREFIX and not parsed_ranges:
        return False
        
    # 1. 檢查英文字首條件（若有設定）
    if TARGET_PREFIX and not fleet_no.startswith(TARGET_PREFIX):
        return False
        
    # 2. 檢查數字範圍條件（若有設定）
    if parsed_ranges:
        # 提取車隊編號中的所有純數字部分
        num_str = re.sub(r'\D', '', fleet_no)
        if not num_str:
            return False
        try:
            fleet_num = int(num_str)
            # 檢查是否落在任何一組範圍內
            matched_range = any(start <= fleet_num <= end for start, end in parsed_ranges)
            if not matched_range:
                return False
        except ValueError:
            return False
            
    return True

def main():
    start_time = time.time()
    # GitHub Actions 每個 job 上限為 6 小時，此處設定執行 3 小時 55 分鐘後自動正常結束
    max_duration = 3 * 3600 + 55 * 60 
    
    seen_entries = set()
    today_str = datetime.now(HKT).strftime("%Y-%m-%d")
    is_first_run = not os.path.exists(DB_FILE)
    
    # 事前解析好用家設定的數字範圍，增進比對效率
    parsed_ranges = parse_range_setting(TARGET_RANGES)
    
    # 讀取當天的數據庫檔案以延續記憶
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
        
        # 凌晨 12 點換日時自動清空記憶庫
        if current_date_str != today_str:
            today_str = current_date_str
            seen_entries.clear()
            
        try:
            if URL:
                response = requests.get(URL, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
                # 將所有文字撈出並按行切割
                lines = soup.get_text(separator='\n').split('\n')
                
                is_today = False
                new_buses = []
                
                for line in lines:
                    # 將網頁中常見的 \xa0 替換成標準空格，並移除頭尾空白
                    line = line.replace('\xa0', ' ').strip()
                    if not line: 
                        continue
                        
                    # 辨識日期標籤 (格式如 2026-07-03)
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', line):
                        if line == today_str:
                            is_today = True
                            continue
                        elif is_today:
                            # 如果已經讀完今天，碰到了昨天的日期，就立刻停止往下讀
                            break 
                            
                    if is_today:
                        # 💡 修改這裡：用最嚴格的正則表達式，只拿最前面兩個單字（車隊、車牌），以及第三個單字（路線主編號）
                        match = re.match(r'^\s*(\S+)\s+(\S+)\s+(\S+)', line)
        
                        if match:
                            fleet_no = match.group(1).strip()
                            reg_no = match.group(2).strip()
                            route = match.group(3).strip() # 💡 這裡會被強行限制只拿第一個單字（例如 18 或 DEAD），後面網頁自帶的舊時間地點通通會被丟棄
                            
                            entry = (fleet_no, reg_no, route)
                            
                            if entry not in seen_entries:
                                seen_entries.add(entry)
                                new_buses.append(entry)
                
                # 若發現新行蹤，則發送至 Discord
                if new_buses:
                    messages = []
                    has_trigger = False
                    time_str = now.strftime("%H:%M")
                    
                    for fleet_no, reg_no, route in new_buses:
                        matched = check_condition(fleet_no, parsed_ranges)
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
                            requests.post(WEBHOOK_URL, json={"content": final_msg}, timeout=10)
                
                is_first_run = False
                
                # 儲存目前的數據庫狀態
                with open(DB_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"date": today_str, "entries": list(seen_entries)}, f, ensure_ascii=False)
                    
        except Exception as e:
            print(f"網絡或解析錯誤: {e}")
            
        # 每 1 分鐘循環執行一次
        time.sleep(60)

if __name__ == "__main__":
    main()