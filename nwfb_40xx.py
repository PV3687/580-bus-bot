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
URL = "https://1005.idv.hk/index.php?page=22&p=299"  # 請在此貼上 Across Bus 該車型的專屬網址
WEBHOOK_URL = "https://discord.com/api/webhooks/1522473464680812674/8OKlFiToOaa_OqythpPsmosDpCowF41dlym8vT3wS8RtQJasiMkFxNNGoUB3nstviqCV"  # 請在此貼上 Discord Webhook 網址

# 條件觸發設定
TARGET_ROUTES = ["3A", "5X", "6", "6A", "7", "8H", "20", "20A", "22", "22D", "22M", "22X", "50", "50M", "50R", "55", "56", "56A", "63", "66", "71", "73", "73X", "76", "78P", "79P", "81", "98", 
               "101R", "102R", "104R", "111P", "115", "260", "302", "302A", "347", "382", "388", "389", "580", "581", "582", "586", "587", "589", 
               "601P", "608P", "621", "629", "629M", "641", "690S", "694S", "701A", "702A", "702B", "790", "792M", "795", "796R", "905P", "933", "950", "979", "985", "986", "989", 
               "A10", "A11", "A12", "A17", "A20", "A21", "A22", "A23", "A25", "A25S", "A26", "A28", "A28X", "A29", "B3", "B3A", "B3M", "B3X", "B5", 
               "E11", "E11A", "E11B", "E11S", "E18", "E21", "E21A", "E21B", "E21C", "E21D", "E21X", "E22", "E22A", "E22C", "E22P", "E22S", "E22X", "E23", "E23A", "E28", 
               "N8", "N8P", "N8X", "N11", "N20", "N21", "N21A", "N23", "N26", "N29", "N50", "N72", "N90", "N118", "N121", "N122", "N170", "N171", "N182", "N307", "N619", "N680", "N691", "N930", "N952", "N962", "N969", 
               "NA10", "NA11", "NA12", "NA20", "NA21", "NA29", "NB3", "R8", "R11", "R22", "S1", "S52", "S52A", "S52P", "S56", "SP2", "SP2A", "SP9", "SP11", "X1", "X8", "X797", "X970"]  # 路線編號的條件觸發空位，例如 ["980A", "796X"]，可為空 []
DB_NAME = "nwfb_40xx"
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
                # 💡 修正：移除 separator='\n'，確保整條巴士紀錄維持在同一行，不被標籤拆散
                lines = soup.get_text().split('\n')
                
                is_today = False
                new_buses = []
                
                for line in lines:
                    line = line.strip()
                    if not line: 
                        continue
                        
                    # 辨識日期標籤
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', line):
                        if line == today_str:
                            is_today = True
                            continue
                        elif is_today:
                            break 
                            
                    if is_today:
                        # 💡 終極修正：利用特殊標記替換 \xa0，精確切分欄位
                        # 這樣做能100%保留車牌中間的空格（如 PT 195），同時徹底杜絕後面地點和舊時間的干擾
                        line_raw = line.replace('\xa0', '[[SPLIT]]').replace(' ', '[[SPLIT]]')
                        parts = line_raw.split('[[SPLIT]]')
                        
                        # 過濾掉因為網頁排版產生的空欄位
                        parts = [p.strip() for p in parts if p.strip()]
                            
                        if len(parts) >= 3:
                            fleet_no = parts[0]
                            reg_no = parts[1]
                            raw_route = parts[2]
                            
                            # 只拿取第三個欄位的第一個單字（即 580、18 或 DEAD），後面其餘雜訊直接丟棄
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