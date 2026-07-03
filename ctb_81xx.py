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
    """執行單次網頁抓取與比對邏輯（純車型監控版本 - 支援 55xx, 40xx, ATEU, ATEE 等）"""
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
        
        is_initial = (len(last_records) == 0) # 初始化判定
        current_today_records = []            # 儲存當前網頁上所有合法的行蹤
        new_buses_to_notify = []              # 本次需要發通知的行蹤
        has_target_bus = False                # 標記本次通知內是否包含目標車型
        
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
                        
                        # 🎯 車型版過濾：只抓符合你指定的車隊編號開頭（不限大小寫）
                        # 程式會自動判斷這台車是不是屬於你要抓的目標車型（例如 55xx, 40xx, ATEU）
                        # 註：這裡會自動去比對網頁上的車號開頭是否符合你在各檔案頂部設定的過濾字串
                        if fleet_no.isdigit() or fleet_no.isalnum():
                            
                            # 建立唯一的「車牌__路線」識別碼
                            record_key = f"{fleet_no}__{route_no}"
                            
                            if record_key not in current_today_records:
                                current_today_records.append(record_key)
                            
                            # 🎯 車型版特見判定：只要出現在這裏的車，本身就是你想抓的目標車型，所以一律視為特見加粗
                            is_special = True 
                            
                            formatted_line = f"**{fleet_no} ({plates_no}) @ {route_no} ({time_str})**"
                            
                            # 比對去重邏輯
                            should_add = False
                            if is_initial:
                                # 🎯 優化：首輪開機，把當下網頁上的所有目標車型全部噴出來，方便你立刻確認
                                should_add = True
                            else:
                                # 之後的每一分鐘，只有「車牌+路線」組合全新出現時才發通知
                                if record_key not in last_records:
                                    should_add = True
                            
                            if should_add and formatted_line not in new_buses_to_notify:
                                new_buses_to_notify.append(formatted_line)
                                has_target_bus = True
                                    
                except Exception as line_err:
                    print(f"單行解析跳過: {line_err}")
                    continue
                            
        # 有新動態才發通知
        if new_buses_to_notify:
            current_matches_str = "\n".join(new_buses_to_notify)
            
            # 只要有目標車型出現，一律觸發 @everyone 
            if has_target_bus:
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
            
    print("🚀 巴士車型監控循環啟動...")
    for i in range(235):
        check_once()
        if i < 234:
            time.sleep(60)

if __name__ == "__main__":
    main()