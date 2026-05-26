import pandas as pd
import glob, json, requests

# 1. 讀取主母表 (路徑已鎖定)
prof_files = glob.glob("t51sb01_*.csv")
prof_db = {}
if prof_files:
    df_prof = pd.read_csv(prof_files[0])
    for _, r in df_prof.iterrows():
        prof_db[str(r.get('公司代號', '')).strip()] = str(r.get('普通股盈餘分派或虧損撥補頻率', '每年')).strip()

# 2. 讀取並去重 12 份股利表
dividend_db = {}
processed = set()
for f in [f for f in glob.glob("t05st09_new_*.csv") if "t51sb01" not in f]:
    df = pd.read_csv(f, skiprows=next(i for i, l in enumerate(open(f, encoding='utf-8')) if "公司代號名稱" in l), on_bad_lines='skip')
    for _, row in df[df['公司代號名稱'] != '公司代號名稱'].iterrows():
        code = str(row['公司代號名稱']).split(' - ')[0].strip()
        yr = str(row['股利所屬年(季)度']).split('年')[0].strip()
        fp = f"{code}-{yr}-{row.get('期別', '0')}"
        if fp in processed: continue
        processed.add(fp)
        cash = sum([float(row[c]) for c in df.columns if '現金股利' in c or '公積發放' in c if pd.notna(row[c]) and str(row[c]).replace('.','',1).isdigit()])
        if code not in dividend_db: dividend_db[code] = []
        dividend_db[code].append({"year": f"{yr}年", "cash": f"{cash:.2f}元"})

# 3. 獲取行情並生成 JSON
data = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", timeout=30).json()
output = []
for item in data:
    code = item.get('Code', '').strip()
    if len(code) == 4:
        output.append({
            "code": code, "name": item.get('Name', ''),
            "yield": item.get('DividendYield', '0'),
            "pe": item.get('PEratio', 'N/A'),
            "freq": prof_db.get(code, "每年"),
            "history": dividend_db.get(code, [])[:5]
        })
with open("data.json", "w", encoding="utf-8") as f: json.dump(output, f, ensure_ascii=False)
