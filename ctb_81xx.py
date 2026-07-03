import requests
import os
import time
from datetime import datetime, timedelta

# ==================== 【 自 訂 設 定 區 】 ====================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1522473956584587406/uLV9vNIKJcLHbuVbUgJuJ7KmullwDyvU07QoxoVJriyX-mzOUf6qvNolJ67jgai96bb9"
URL = "https://1005.idv.hk/index.php?page=22&p=277" 
DATA_FILE = "last_ctb_81xx.txt"
# ============================================================

BOLD_ROUTES = ["3A", "5X", "6", "6A", "7", "8H", "20", "20A", "22", "22D", "22M", "22X", "50", "50M", "50R", "55", "56", "56A", "63", "66", "71", "73", "73X", "76", "78P", "79P", "81", "98", 
               "101R", "102R", "104R", "111P", "115", "260", "302", "302A", "347", "382", "388", "389", "580", "581", "582", "586", "587", "589", 
               "601P", "608P", "621", "629", "629M", "641", "690S", "694S", "701A", "702A", "702B", "790", "792M", "795", "796R", "905P", "933", "950", "979", "985", "986", "989", 
               "A10", "A11", "A12", "A17", "A20", "A21", "A22", "A23", "A25", "A25S", "A26", "A28", "A28X", "A29", "B3", "B3A", "B3M", "B3X", "B5", 
               "E11", "E11A", "E11B", "E11S", "E18", "E21", "E21A", "E21B", "E21C", "E21D", "E21X", "E22", "E22A", "E22C", "E22P", "E22S", "E22X", "E23", "E23A", "E28", 
               "N8", "N8P", "N8X", "N11", "N20", "N21", "N21A", "N23", "N26", "N29", "N50", "N72", "N90", "N118", "N121", "N122", "N170", "N171", "N182", "N307", "N619", "N680", "N691", "N930", "N952", "N962", "N969", 
               "NA10", "NA11", "NA12", "NA20", "NA21", "NA29", "NB3", "R8", "R11", "R22", "S1", "S52", "S52A", "S52P", "S56", "SP2", "SP2A", "SP9", "SP11", "X1", "X8", "X797", "X970"] 
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def send_discord_message(msg):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    except:
        pass

def check_once():
    """執行單次網頁抓取與比對邏輯（580 與所有指定車型通用終極版）"""
    try:
        res = requests.get(URL, headers=HEADERS)
        res.encoding = 'big5'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 解決特殊空白問題
        html_text = soup.text.replace('\xa0', ' ')
        
        # 🎯 核心修正：將時間強制轉換為香港本地時間（UTC + 8 小時）
        hkt_now = datetime.utcnow() + timedelta(hours=8)
        today_str = hkt_now.strftime('%Y-%m-%d')
        time_str = hkt_now.strftime('%H:%M')
        
        # 採用換行讀取「完整行蹤識別碼 (車牌+路線)」，防止新動態被舊車牌吃掉
        last_records = []
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                last_records = [line.strip() for line in f.readlines() if line.strip()]
        
        is_initial = (len(last_records) == 0) # 初始化判定
        current_today_records = []            # 儲存當前網頁上所有合法的行蹤組合
        new_buses_to_notify = []              # 本次需要發通知的行蹤
        has_bold_trigger = False              # 標記本次通知內是否包含任何特見（加粗）
        
        if today_str in html_text:
            after_today = html_text.split(today_str)[1]
            
            for line in after_today.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 🎯 核心修正：移除所有 break 中斷！防範 DEAD 備註內的日期腰斬程式
                
                # 單行局部防護罩，萬一某行格式爆炸或有亂碼，絕對不影響後面所有車輛的抓取
                try:
                    tokens = line.split()
                    if len(tokens) >= 3:
                        fleet_no, plates_no, route_no = tokens[0], tokens[1], tokens[2]
                        
                        # 通用車隊編號判定！支援純數字、含小數點數字、以及所有英文開頭車型
                        if fleet_no.isdigit() or fleet_no.replace('.', '', 1).isdigit() or fleet_no.isalnum():
                            
                            # 建立唯一的「車牌__路線」識別碼
                            record_key = f"{fleet_no}__{route_no}"
                            
                            if record_key not in current_today_records:
                                current_today_records.append(record_key)
                            
                            # 智慧判斷特見邏輯（同時相容 580 專屬函式 與 其他車型的 BOLD_ROUTES 列表）
                            is_special = False
                            if 'check_bus_number' in globals() and '580' in DATA_FILE: # 簡單區分是否啟用 580 函數
                                is_special = check_bus_number(fleet_no)
                            elif 'BOLD_ROUTES' in globals():
                                is_special = route_no in BOLD_ROUTES
                            
                            # 判定排版：特見加粗，普通路線正常
                            if is_special:
                                formatted_line = f"**{fleet_no} ({plates_no}) @ {route_no} ({time_str})**"
                            else:
                                formatted_line = f"{fleet_no} ({plates_no}) @ {route_no} ({time_str})"
                            
                            # 比對去重
                            should_add = False
                            if is_initial:
                                should_add = True
                            else:
                                # 只要「車牌+路線」的組合之前沒出現過，就是新行蹤，必須通報
                                if record_key not in last_records:
                                    should_add = True
                            
                            if should_add and formatted_line not in new_buses_to_notify:
                                new_buses_to_notify.append(formatted_line)
                                if is_special:
                                    has_bold_trigger = True
                                    
                except Exception as line_err:
                    # 當行解析出錯時直接略過，確保迴圈繼續往下走
                    continue
                            
        # 有新動態才發通知
        if new_buses_to_notify:
            current_matches_str = "\n".join(new_buses_to_notify)
            
            # 精準排版：只要本次有任何一個加粗特見，就觸發 @everyone
            if has_bold_trigger:
                final_msg = f"@everyone\n\n{current_matches_str}"
            else:
                final_msg = f"\n\n{current_matches_str}"
                
            send_discord_message(final_msg)
            
        # 將當前所有最新的識別碼寫入本地存檔
        with open(DATA_FILE, 'w', encoding='utf-8') as f: 
            f.write("\n".join(current_today_records))
            
    except Exception as e: 
        print(f"總體檢查出錯: {e}")

def main():
    # 🎯 核心判定：轉回香港時間後，直接看 HKT 是否為午夜 00:XX 分
    # 只要是在香港時間 00:00 這一輪剛醒來，立即清除昨天的舊紀錄，完美重設初始化！
    hkt_hour = (datetime.utcnow() + timedelta(hours=8)).hour
    if hkt_hour == 0:
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
            print(" Midnight HKT！新的一天開始，已自動清空昨日特見存檔。")
            
    print("🚀 巴士監控循環啟動...")
    # 🎯 4小時接力架構：每次喚醒連續執行 235 次（共 3 小時 55 分鐘，每 60 秒檢查一次）
    for i in range(235):
        check_once()
        if i < 234:
            time.sleep(60)

if __name__ == "__main__":
    main()