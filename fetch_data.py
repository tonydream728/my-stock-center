import requests
import pandas as pd
import datetime
import glob
import json

# ========================================================
# 1. 核心設定區
# ========================================================
twse_industry_code_map = {
    "01": "水泥工業", "02": "食品工業", "03": "塑料工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "07": "化學工業", "21": "化學工業", 
    "08": "玻璃陶瓷", "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業",
    "12": "汽車工業", "13": "建築材料", "14": "航運業", "15": "觀光餐旅",
    "16": "金融保險", "17": "貿易百貨", "18": "綜合業", "20": "其他類股",
    "22": "光電業", "23": "資訊服務", "24": "半導體業", "25": "電腦及週邊", 
    "26": "通信網路業", "27": "電子零組件", "28": "電子通路", "29": "其他電子業",
    "30": "油電燃氣", "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活"
}

# 2. 數據庫構建 (CSV 直驅 + 物理去重)
csv_dividend_database = {}
csv_files = glob.glob("t05st09_new_*.csv")
profile_files = glob.glob("t51sb01_*.csv")

# 讀取主母表
company_profile_db = {}
if profile_files:
    df_prof = pd.read_csv(profile_files[0])
    for _, row in df_prof.iterrows():
        c_code = str(row.get('公司代號', '')).strip()
        company_profile_db[c_code] = {
            "freq": str(row.get('普通股盈餘分派或虧損撥補頻率', '每年')).strip(),
            "official_ind": str(row.get('產業類別', '')).strip()
        }

# 讀取股利表
raw_group_dict = {}
processed_fingerprints = set()
for f_path in csv_files:
    with open(f_path, "r", encoding="utf-8") as f: lines = f.readlines()
    h_idx = next(i for i, line in enumerate(lines) if "公司代號名稱" in line)
    df = pd.read_csv(f_path, skiprows=h_idx, on_bad_lines='skip')
    df = df.dropna(subset=['公司代號名稱', '股利所屬年(季)度'])
    for _, row in df[df['公司代號名稱'] != '公司代號名稱'].iterrows():
        c_code = str(row['公司代號名稱']).split(' - ')[0].strip()
        yr_num = str(row['股利所屬年(季)度']).split('年')[0].strip()
        fprint = f"{c_code}-{yr_num}-{row.get('期別', '0')}-{row.get('董事會（擬擬議）股利分派日', '0')}"
        if fprint in processed_fingerprints: continue
        processed_fingerprints.add(fprint)
        
        c_val = sum([float(row[c]) for c in df.columns if '現金股利' in c or '公積發放' in c if pd.notna(row[c]) and str(row[c]).replace('.','',1).isdigit()])
        s_val = sum([float(row[s]) for s in df.columns if '轉增資配股' in s if pd.notna(row[s]) and str(row[s]).replace('.','',1).isdigit()])
        
        key = (c_code, yr_num)
        if key not in raw_group_dict: raw_group_dict[key] = {"cash": 0.0, "stock": 0.0}
        raw_group_dict[key]["cash"] += c_val
        raw_group_dict[key]["stock"] += s_val

for (c_code, yr_num), val in raw_group_dict.items():
    if c_code not in csv_dividend_database: csv_dividend_database[c_code] = []
    csv_dividend_database[c_code].append({"year": f"{yr_num}年度", "cash": f"{val['cash']:.2f} 元", "stock": f"{val['stock']:.2f} 股", "yr_int": int(yr_num)})
for c_code in csv_dividend_database:
    csv_dividend_database[c_code] = sorted(csv_dividend_database[c_code], key=lambda x: x['yr_int'], reverse=True)[:5]

# 3. HTML 渲染輸出 (完整無省略)
json_db_str = json.dumps(csv_dividend_database, ensure_ascii=False)
html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>存股大數據中心</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container my-5">
        <h1>📊 AI 價值存股數據中心</h1>
        <div id="data-container"></div>
    </div>
    <script>
        const GLOBAL_CSV_DATABASE = {json_db_str};
        console.log("數據庫已載入:", GLOBAL_CSV_DATABASE);
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("✅ 最終完整版程式碼部署完畢！")
