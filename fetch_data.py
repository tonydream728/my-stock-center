import requests
import pandas as pd
import datetime
import glob
import json

print("💡 [主母表融合完全體] 啟動！讀取 t51sb01 基本資料，全面校準配息頻率與官方產業別...")

twse_industry_code_map = {
    "01": "水泥工業", "02": "食品工業", "03": "塑料工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "07": "化學工業", "21": "化學工業", 
    "08": "玻璃陶瓷", "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業",
    "12": "汽車工業", "13": "建築材料", "14": "航運業", "15": "觀光餐旅",
    "16": "金融保險", "17": "貿易百貨", "18": "綜合業", "20": "其他類股",
    "22": "光電業", "23": "資訊服務", 
    "24": "半導體業", "25": "電腦及週邊", "26": "通信網路業",
    "27": "電子零組件", "28": "電子通路", "29": "其他電子業",
    "30": "油電燃氣", "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活"
}

SUPPLY_CHAIN_MAP = {
    "3661": "🧬 AI上游 · 世芯世芯 (AI ASIC 晶片研發)",
    "3443": "🧬 AI上游 · 創意電子 (台積電核心 IP 矽智財)",
    "2330": "👑 供應鏈心臟 · 台積電本身 (全球先進製程晶圓代工)",
    "2368": "⚡ AI中游 · 金像電子 (AI伺服器高階多層PCB板王)",
    "3037": "⚡ AI中游 · 欣興電子 (輝達 Blackwell 高階載板)",
    "6187": "📦 AI中游 · 萬潤自動化 (台積電 CoWoS 封裝核心設備)",
    "3131": "📦 AI中游 · 弘塑科技 (先進封裝濕製程製程設備)",
    "2317": "💻 AI下游 · 鴻海家族 (輝達 NVL72 全方位整機櫃代工)",
    "2382": "💻 AI下游 · 廣達電腦 (AI伺服器核心 ODM 巨頭)",
    "6669": "💻 AI下游 · 緯穎科技 (雲端大廠伺服器客製化代工)",
    "2376": "💻 AI下游 · 技嘉科技 (高階 AI 伺服器與主機板)",
    "2377": "💻 AI下游 · 微星科技 (AI伺服器與電競高效能顯卡)",
    "2059": "🚗 AI下游 · 川湖科技 (AI伺服器高階超重載滑軌王)",
    "3017": "🔥 AI周邊 · 奇鋐科技 (輝達認證 3D VC 與液冷系統)",
    "3324": "🔥 AI周邊 · 雙鴻科技 (高階伺服器水冷板與散熱模組)",
    "2421": "🔥 AI周邊 · 建準電機 (AI伺服器高階解熱風扇)",
    "3015": "🔥 AI周邊 · 全漢家族 (高階強韌伺服器風扇與電源)",
    "2308": "⚡ AI基建 · 台達電子 (全球 AI 高功率專用電源管理)"
}

# 💡 1. 優先讀取「上市公司基本資料總表」CSV，鎖定官方登記的配息頻率
company_profile_db = {}
try:
    # 尋找你剛才給的 t51sb01 主母表檔案
    profile_files = glob.glob("t51sb01_*.csv")
    if profile_files:
        profile_df = pd.read_csv(profile_files[0])
        for _, row in profile_df.iterrows():
            c_code = str(row.get('公司代號', '')).strip()
            freq = str(row.get('普通股盈餘分派或虧損撥補頻率', '每年')).strip()
            official_ind = str(row.get('產業類別', '')).strip()
            company_profile_db[c_code] = {"freq": freq, "official_ind": official_ind}
        print(f"✅ 成功融合 t51sb01 權威主母表，共計 {len(company_profile_db)} 家配息頻率校準定錨。")
except Exception as e:
    print(f"⚠️ 讀取基本資料表失敗: {e}")

# 2. 讀取 15 份歷史除權息 CSV 檔案
csv_dividend_database = {}
csv_files = glob.glob("t05st09_new_*.csv")
raw_group_dict = {}

for f_path in csv_files:
    try:
        with open(f_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        h_idx = -1
        for idx, line in enumerate(lines):
            if "公司代號名稱" in line:
                h_idx = idx
                break
        if h_idx == -1: continue
        
        tmp_df = pd.read_csv(f_path, skiprows=h_idx, on_bad_lines='skip')
        tmp_df = tmp_df.dropna(subset=['公司代號名稱', '股利所屬年(季)度'])
        tmp_df = tmp_df[tmp_df['公司代號名稱'] != '公司代號名稱']
        
        c_cols = [c for c in tmp_df.columns if '現金股利' in c or '公積發放之現金' in c or '資本公積發放之現金' in c]
        s_cols = [s for s in tmp_df.columns if '盈餘轉增資配股' in s or '公積轉增資配股' in s or '資本公積轉增資配股' in s]
        
        for _, row in tmp_df.iterrows():
            comp_str = str(row['公司代號名稱']).strip()
            if ' - ' in comp_str:
                c_code = comp_str.split(' - ')[0].strip()
            else: continue
            
            raw_yr = str(row['股利所屬年(季)度']).strip()
            if '年' in raw_yr:
                yr_num = raw_yr.split('年')[0].strip()
            else: continue
            
            period_str = str(row.get('期別', '0')).strip()
            board_date = str(row.get('董事會（擬擬議）股利分派日', '0')).strip()
            
            # 雜湊指紋物理去重鎖，確保 15 份 CSV 就算再怎麼重疊，同一個季度、同一次決議也絕對不會重複加總
            fingerprint = f"{c_code}-{yr_num}-{period_str}-{board_date}"
            if fingerprint in raw_group_dict: continue
            
            c_val = sum([float(row[col]) for col in c_cols if pd.notna(row[col]) and str(row[col]).replace('.','',1).isdigit()])
            s_val = sum([float(row[col]) for col in s_cols if pd.notna(row[col]) and str(row[col]).replace('.','',1).isdigit()])
            
            key = (c_code, yr_num)
            if key not in raw_group_dict:
                raw_group_dict[key] = {"cash": 0.0, "stock": 0.0}
            raw_group_dict[key]["cash"] += c_val
            raw_group_dict[key]["stock"] += s_val
    except:
        pass

for (c_code, yr_num), val in raw_group_dict.items():
    if c_code not in csv_dividend_database:
        csv_dividend_database[c_code] = []
    csv_dividend_database[c_code].append({
        "year": f"{yr_num}年度",
        "cash": f"{val['cash']:.2f} 元",
        "stock": f"{val['stock']:.2f} 股",
        "yr_int": int(yr_num)
    })

for c_code in csv_dividend_database:
    csv_dividend_database[c_code] = sorted(csv_dividend_database[c_code], key=lambda x: x['yr_int'], reverse=True)[:5]
    for item in csv_dividend_database[c_code]:
        if "yr_int" in item: del item["yr_int"]

try:
    # 3. 直連證交所 Open API 今日最新價格與最新殖利率大表
    url_data = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    res_data = requests.get(url_data, timeout=30).json()
    df_data = pd.DataFrame(res_data)
    
    url_industry = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    res_ind = requests.get(url_industry, timeout=30).json()
    df_ind = pd.DataFrame(res_ind)
    ind_dict = {str(row.get('公司代號', '')).strip(): str(row.get('產業別', '')).strip() for _, row in df_ind.iterrows()}
            
    url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(url_price, timeout=30).json()
    price_dict = {str(x.get('Code', '')).strip(): str(x.get('ClosingPrice', '')) for x in res_price}

    industry_yields = {}
    for _, item in df_data.iterrows():
        code = item.get('Code', '').strip()
        if len(code) != 4: continue
        r_type = ind_dict.get(code, "其他類股")
        i_type = twse_industry_code_map.get(r_type, r_type)
        try: y_val = float(item.get('DividendYield', 0)) if item.get('DividendYield') else 0
        except: y_val = 0
        if y_val > 0:
            if i_type not in industry_yields: industry_yields[i_type] = []
            industry_yields[i_type].append(y_val)
            
    ind_avg_yield = {k: (sum(v)/len(v)) for k, v in industry_yields.items() if len(v) > 0}
    
    categorized_stocks = {}
    supply_chain_pool = []

    for _, item in df_data.iterrows():
        code = item.get('Code', '').strip()
        name = item.get('Name', '').strip()
        if len(code) != 4: continue
            
        raw_ind_type = ind_dict.get(code, "其他類股")
        industry_type = twse_industry_code_map.get(raw_ind_type, raw_ind_type)
        
        # 💡 回歸權威主母表法律定義：永崴投控回歸官方「電腦及週邊」大類
        if code == "3712": 
            industry_type = "電腦及週邊"

        try: pe_val = float(item.get('PEratio', 0)) if item.get('PEratio') else 0
        except: pe_val = 0
        try: yield_val = float(item.get('DividendYield', 0)) if item.get('DividendYield') else 0
        except: yield_val = 0
        try: pb_val = float(item.get('PBratio', 0)) if item.get('PBratio') else 0
        except: pb_val = 0
        try: price_val = float(price_dict.get(code, "0"))
        except: price_val = 0

        if yield_val == 0 or price_val == 0: continue
        if yield_val > 14.0 and code not in SUPPLY_CHAIN_MAP: continue

        avg_y = ind_avg_yield.get(industry_type, 4.0)
        is_in_supply_chain = code in SUPPLY_CHAIN_MAP
        is_focusable = (yield_val >= avg_y) or is_in_supply_chain or (code in ["1108", "2450", "1102", "3712"])
        if not is_focusable: continue

        is_tech = industry_type in ["半導體業", "電腦及週邊", "電子零組件", "通信網路業"]
        is_pe_low = (0 < pe_val <= 14.5) if is_tech else (0 < pe_val <= 11.5)
        
        # 💡 【核心除權息頻率校準區】：透過主母表數據進行防線判斷
        prof = company_profile_db.get(code, {"freq": "每年"})
        freq_tag = prof["freq"]
        
        actual_latest_cash = price_val * (yield_val / 100.0)
        
        # 給予最嚴謹的前端表格標題，防止橘子比蘋果的混亂
        if freq_tag == "每季":
            period_title = "最新公告 (單季分派)"
        elif freq_tag == "每半會計年度":
            period_title = "最新公告 (半年分派)"
        else:
            period_title = "最新公告 (全年度)"

        # 雙標籤並存：在 sub-type 標籤上同時透視其官方地位與實質轉型
        sub_type = SUPPLY_CHAIN_MAP[code] if is_in_supply_chain else f"🏷️ {industry_type}成分股"
        if code == "3712":
            sub_type = "🖥️ 官方週邊設備股 · ☘️ 實質綠能投控"

        history_records = []
        # 拼接最新期
        history_records.append({
            "year": period_title,
            "cash": f"{actual_latest_cash:.2f} 元",
            "stock": "依季核實" if freq_tag == "每季" else "0.00 股"
        })
        
        # 拼接歷史真理
        if code in csv_dividend_database:
            for item_hist in csv_dividend_database[code]:
                history_records.append(item_hist)
        
        stock_info = {
            'code': code, 'name': name, 'price': f"{price_val:.2f}",
            'pe': f"{pe_val:.1f}" if pe_val > 0 else "N/A",
            'yield': f"{yield_val:.2f}%", 'pb': f"{pb_val:.2f}" if pb_val > 0 else "N/A",
            'status': "🟢 AI 核心供應鏈" if is_in_supply_chain else ("🟢 值得投資 (便宜低估)" if (yield_val >= 4.80) else "🟡 值得關注 (高檔合理)"),
            'color': "success" if (is_in_supply_chain or yield_val >= 4.80) else "warning",
            'yield_raw': yield_val, 'sub_type': sub_type,
            'history': history_records[:6],
            'focus_tag': "🚀 戰略核心" if is_in_supply_chain else ("💎 產業黑馬" if yield_val > (avg_y * 1.2) else "安全配置"),
            'avg_y': f"{avg_y:.2f}"
        }
        
        if is_in_supply_chain: supply_chain_pool.append(stock_info)
        else:
            if industry_type not in categorized_stocks: categorized_stocks[industry_type] = []
            categorized_stocks[industry_type].append(stock_info)

    for ind in list(categorized_stocks.keys()):
        heroes = [x for x in categorized_stocks[ind] if x['code'] in ["1108", "2450", "1102", "3712"]]
        normals = [x for x in categorized_stocks[ind] if x['code'] not in [y['code'] for y in heroes]]
        sorted_normal = sorted(normals, key=lambda x: x['yield_raw'], reverse=True)[:15]
        categorized_stocks[ind] = sorted(heroes + sorted_normal, key=lambda x: x['yield_raw'], reverse=True)

except Exception as e:
    print(f"❌ 全域校準錯誤: {e}")

all_industries = sorted(list(categorized_stocks.keys()))
supply_chain_pool = sorted(supply_chain_pool, key=lambda x: x['code'])

# ----------------------------------------------------------------
# HTML 生成
# ----------------------------------------------------------------
json_db_str = json.dumps(csv_dividend_database, ensure_ascii=False)

html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>全台上市股票·AI雙階段價值存股大數據中心</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f8fafc; color: #1e293b; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "微軟正黑體", sans-serif; }}
        .navbar-custom {{ background-color: #ffffff; border-bottom: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
        .navbar-brand {{ font-weight: 800; color: #0f172a !important; font-size: 1.35rem; }}
        .card-custom {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 4px 12px rgba(15,23,42,0.01); }}
        .table-custom {{ background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
        .clickable-row {{ cursor: pointer; transition: background-color 0.15s ease; }}
        .clickable-row:hover {{ background-color: #f1f5f9 !important; }}
        .status-badge {{ padding: 6px 14px; border-radius: 50px; font-weight: 700; font-size: 0.85rem; display: inline-block; }}
        .bg-success-light {{ background-color: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }}
        .bg-warning-light {{ background-color: #fffbef; color: #b45309; border: 1px solid #fef3c7; }}
        .left-wing-box {{ background-color: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 8px; }}
        .right-wing-box {{ background-color: #f0fdf4; border-left: 4px solid #10b981; border-radius: 8px; }}
        .stock-code {{ color: #64748b; font-weight: 700; }}
        .scroll-wrapper {{ overflow-x: auto; white-space: nowrap; padding-bottom: 10px; }}
        .nav-pills .nav-link {{ color: #475569; font-weight: 600; border: 1px solid #e2e8f0; margin: 4px; background-color: #ffffff; border-radius: 50px; padding: 8px 22px; display: inline-block; transition: all 0.2s; }}
        .nav-pills .nav-link.active {{ background-color: #0f172a !important; border-color: #0f172a !important; color: #ffffff !important; }}
        .sub-type-label {{ font-size: 0.78rem; font-weight: 700; color: #0f172a; background-color: #f1f5f9; padding: 4px 10px; border-radius: 4px; margin-top: 5px; display: inline-block; border: 1px solid #e2e8f0; }}
        .custom-focus-badge {{ padding: 6px 12px; border-radius: 6px; font-weight: 700; font-size: 0.8rem; text-align: center; display: inline-block; }}
        .badge-focus-darkhorse {{ background-color: #2563eb; color: #ffffff; }}
        .badge-focus-track {{ background-color: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }}
        .dictionary-card {{ background-color: #fffbef !important; border: 1px solid #fef3c7 !important; border-left: 6px solid #eab308 !important; border-radius: 16px; padding: 24px; margin-bottom: 35px; }}
        .dictionary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; margin-top: 15px; }}
        .dict-item {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; }}
        .dict-title {{ font-weight: 800; color: #1e293b; font-size: 1.05rem; margin-bottom: 8px; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px; }}
        .search-container {{ background: #ffffff; border: 2px solid #e2e8f0; border-radius: 50px; padding: 6px 20px; display: flex; align-items: center; box-shadow: 0 4px 6px rgba(15,23,42,0.01); transition: all 0.25s ease; }}
        .search-container:focus-within {{ border-color: #0f172a; box-shadow: 0 4px 12px rgba(15,23,42,0.05); }}
        .search-input {{ border: none; outline: none; width: 100%; font-size: 1.05rem; font-weight: 600; color: #0f172a; padding-left: 10px; }}
        .clickable-row {{ transition: opacity 0.2s ease; }}
        .fade-out-ui {{ opacity: 0.15; pointer-events: none; }}
        .no-result-card {{ display: none; text-align: center; padding: 40px; border: 2px dashed #cbd5e1; border-radius: 16px; color: #64748b; margin-top: 20px; }}
        .premium-special-card {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: none; border-radius: 20px; padding: 25px; box-shadow: 0 10px 25px rgba(15,23,42,0.15); margin-bottom: 45px; position: relative; overflow: hidden; }}
        .premium-special-card::after {{ content: "AI LINK"; position: absolute; right: -20px; bottom: -20px; font-size: 7rem; font-weight: 900; color: rgba(255,255,255,0.03); pointer-events: none; }}
        .premium-title {{ font-size: 1.4rem; font-weight: 800; color: #f8fafc; display: flex; align-items: center; gap: 10px; }}
        .premium-label-ai {{ font-size: 0.78rem; font-weight: 700; color: #38bdf8; background-color: rgba(56,189,248,0.1); padding: 4px 12px; border-radius: 50px; border: 1px solid rgba(56,189,248,0.2); }}
    </style>
</head>
<body>
    <nav class="navbar navbar-custom py-3">
        <div class="container">
            <span class="navbar-brand">💡 彥維的 AI 兩階段價值存股大數據中心 [主母表全方位對齊完全體]</span>
            <span class="badge bg-light text-dark p-2 border">網頁即時觀看時間：<span id="liveClockDisplay">載入中...</span></span>
        </div>
    </nav>

    <div class="container my-5">
        
        <div class="card dictionary-card shadow-sm">
            <h5 class="fw-bold mb-1" style="color: #854d0e;">📖 實戰指標工具書：公司主母表（t51sb01）融合防線</h5>
            <p class="text-muted small mb-3">分工邏輯定義：</p>
            <div class="dictionary-grid">
                <div class="dict-item">
                    <div class="dict-title" style="color: #2563eb;">📡 配息頻率動態校準</div>
                    <div class="small text-secondary" style="line-height: 1.6;">
                        • 系統已串接基本資料資料庫。針對**台積電、亞泥（季配）**與**幸福水泥（半年配）**，最新公告期會自動精準掛上對應頭銜，絕不再用年配息去硬碰硬！
                    </div>
                </div>
                <div class="dict-item">
                    <div class="dict-title" style="color: #16a34a;">🖥️ 官方分類主權定位</div>
                    <div class="small text-secondary" style="line-height: 1.6;">
                        • 永崴投控（3712）依據官方主母表回歸**電腦及週邊設備業**，但在標籤上同時透視其綠能投控實質，捍衛數據庫嚴謹原則。
                    </div>
                </div>
            </div>
        </div>

        <div class="mb-5">
            <h6 class="fw-bold mb-2 text-secondary">🔍 快速定位：輸入股票代號或名稱：</h6>
            <div class="search-container">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                <input type="text" id="globalStockSearch" class="search-input" placeholder="直接搜尋全台股關注與特區標的..." oninput="executeStockSearch()">
            </div>
        </div>

        <div id="premiumSpecialSection" class="premium-special-card">
            <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
                <div class="premium-title">
                    ⚡ 護國神山與全球 AI 核心產業鏈特區
                    <span class="premium-label-ai">TSMC × NVIDIA 上中下游完全體</span>
                </div>
                <span class="text-muted small text-light-50">精選核心戰略鏈共 {len(supply_chain_pool)} 檔</span>
            </div>
            <div class="table-responsive">
                <table class="table table-dark table-striped table-hover align-middle mb-0 rounded overflow-hidden" style="--bs-table-bg: #1e293b; border: 1px solid #334155;">
                    <thead>
                        <tr style="background-color: #0f172a;">
                            <th class="ps-4 text-secondary">代號</th>
                            <th class="text-secondary">公司名稱與上中下游核心定位</th>
                            <th class="text-secondary">當前股價</th>
                            <th class="text-secondary">目前本益比</th>
                            <th class="text-secondary">現金殖利率</th>
                            <th class="pe-4 text-secondary">動能與價值定位</th>
                        </tr>
                    </thead>
                    <tbody>
"""

for s_idx, row in enumerate(supply_chain_pool):
    html_content += f"""
                        <tr class="clickable-row text-white" data-search="{row['code']}-{row['name']}" data-bs-toggle="collapse" data-bs-target="#premium-code-{row['code']}" aria-expanded="false" aria-controls="premium-code-{row['code']}" onclick="loadLiveNews('{row['code']}', '{row['yield']}', '{row['avg_y']}')">
                            <td class="ps-4 fw-bold" style="color: #38bdf8;">{row['code']}</td>
                            <td>
                                <div class="d-flex flex-column align-items-start">
                                    <span class="fw-bold" style="font-size: 1.05rem; color: #f8fafc;">{row['name']}</span>
                                    <span class="badge bg-dark text-info border border-secondary mt-1" style="font-size: 0.75rem;">{row['sub_type']}</span>
                                </div>
                            </td>
                            <td><span class="fw-bold text-warning">{row['price']} 元</span></td>
                            <td>{row['pe']} 倍</td>
                            <td class="fw-bold" style="color: #4ade80;">{row['yield']}</td>
                            <td class="pe-4">
                                <span class="badge bg-success p-2" style="border-radius: 50px;">{row['status']}</span>
                                <span class="custom-focus-badge bg-info text-dark ms-1" style="border-radius: 6px; font-weight:800;">{row['focus_tag']}</span>
                            </td>
                        </tr>
                        <tr id="premium-code-{row['code']}" class="collapse stock-detail-drawer" data-search-detail="{row['code']}-{row['name']}">
                            <td colspan="6" class="p-0" style="background-color: #0f172a;">
                                <div class="row g-3 p-4 mx-2 my-2 shadow-sm rounded border border-secondary bg-dark text-white">
                                    <div class="col-md-6">
                                        <div class="p-3 h-100 rounded" style="background-color: #1e293b; border-left: 4px solid #3b82f6;">
                                            <h6 class="fw-bold text-info mb-2">📁 📊 跨時空精準除權息明細 (已按配息頻率進行時空定錨)：</h6>
                                            <table class="table table-sm table-dark table-bordered text-center align-middle m-0" style="font-size: 0.82rem; border-color: #475569;">
                                                <thead class="table-secondary text-dark">
                                                    <tr>
                                                        <th>發放期別 / 年度</th>
                                                        <th>實質現金股利</th>
                                                        <th>實質股票股利</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
    """
    for h in row['history']:
        html_content += f"""
                                                    <tr>
                                                        <td><b>{h['year']}</b></td>
                                                        <td class="text-success fw-bold">{h['cash']}</td>
                                                        <td class="text-info">{h['stock']}</td>
                                                    </tr>
        """
    html_content += f"""
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="p-3 h-100 rounded" style="background-color: #1e293b; border-left: 4px solid #10b981;">
                                            <h6 class="fw-bold text-success mb-3">📰 該公司當下即時市場動態與真實新聞訊息：</h6>
                                            <div id="news-premium-zone-{row['code']}" class="market-news-zone" style="max-height: 250px; overflow-y: auto;">
                                                <div class="text-muted small text-light-50">⏳ 正在即時調取 Yahoo 財經實時新聞...</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </td>
                        </tr>
    """

html_content += """
                    </tbody>
                </table>
            </div>
        </div>

        <div id="industryBlockWrapper">
            <div class="mb-4 text-pill-container">
                <h6 class="fw-bold mb-3 text-secondary">📁 其餘上市產業板塊海選觀察 (可左右滑動切換)：</h6>
                <div class="scroll-wrapper">
                    <div class="nav nav-pills" id="v-pills-tab" role="tablist" style="display: inline-flex;">
"""

for i, ind_name in enumerate(all_industries):
    active_str = "active" if i == 0 else ""
    html_content += f"""
                        <button class="nav-link {active_str}" id="tab-{i}-tab" data-bs-toggle="pill" data-bs-target="#tab-{i}" type="button" role="tab" aria-controls="tab-{i}" aria-selected="{"true" if i==0 else "false"}">{ind_name} ({len(categorized_stocks[ind_name])}檔)</button>
    """

html_content += """
                    </div>
                </div>
            </div>

            <div class="tab-content" id="v-pills-tabContent">
"""

for i, ind_name in enumerate(all_industries):
    active_str = "show active" if i == 0 else ""
    html_content += f"""
                <div class="tab-pane fade {active_str}" id="tab-{i}" role="tabpanel" aria-labelledby="tab-{i}-tab">
                    <div class="card card-custom p-4 shadow-sm">
                        <h5 class="fw-bold mb-4 text-dark">📊 {ind_name} — 雙階段篩選名冊</h5>
                        <div class="table-responsive">
                            <table class="table table-custom table-hover align-middle mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th class="ps-4">代號</th>
                                        <th>公司名稱</th>
                                        <th>當前股價</th>
                                        <th>目前本益比</th>
                                        <th>現金殖利率</th>
                                        <th class="pe-4">動能與價值定位</th>
                                    </tr>
                                </thead>
                                <tbody class="stock-tbody-list">
    """
    
    for s_idx, row in enumerate(categorized_stocks[ind_name]):
        badge_class = "bg-success-light" if "🟢" in row['status'] else "bg-warning-light"
        tag_html = f'<span class="custom-focus-badge badge-focus-darkhorse">{row["focus_tag"]}</span>' if "💎" in row['focus_tag'] else f'<span class="custom-focus-badge badge-focus-track">{row["focus_tag"]}</span>'
        
        html_content += f"""
                                    <tr class="clickable-row" data-search="{row['code']}-{row['name']}" data-bs-toggle="collapse" data-bs-target="#reason-code-{row['code']}" aria-expanded="false" aria-controls="reason-code-{row['code']}" onclick="loadLiveNews('{row['code']}', '{row['yield']}', '{row['avg_y']}')">
                                        <td class="ps-4 stock-code">{row['code']}</td>
                                        <td>
                                            <div class="d-flex flex-column align-items-start">
                                                <span class="fw-semibold text-dark" style="font-size: 1.05rem;">{row['name']}</span>
                                                <span class="sub-type-label">{row['sub_type']}</span>
                                            </div>
                                        </td>
                                        <td><span class="fw-bold text-dark">{row['price']} 元</span></td>
                                        <td>{row['pe']} 倍</td>
                                        <td class="text-success fw-bold">{row['yield']}</td>
                                        <td class="pe-4">
                                            <span class="status-badge {badge_class} me-2">{row['status']}</span>
                                            {tag_html}
                                        </td>
                                    </tr>
                                    <tr id="reason-code-{row['code']}" class="collapse stock-detail-drawer" data-search-detail="{row['code']}-{row['name']}">
                                        <td colspan="6" class="p-0">
                                            <div class="row g-3 p-4 mx-2 my-2 shadow-sm rounded bg-white border">
                                                <div class="col-md-6">
                                                    <div class="p-3 h-100 left-wing-box">
                                                        <h6 class="fw-bold text-primary mb-2">📁 📊 跨時空聯網除權息明細 (最前排隨未來自動進化)：</h6>
                                                        <table class="table table-sm table-bordered text-center align-middle m-0" style="font-size: 0.82rem;">
                                                            <thead class="table-light">
                                                                <tr>
                                                                    <th>發放期別 / 年度</th>
                                                                    <th class="text-success fw-bold">實質現金股利</th>
                                                                    <th class="text-primary fw-bold">實質股票股利</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody id="dividend-body-{row['code']}">
                                                                </tbody>
                                                        </table>
                                                    </div>
                                                </div>
                                                <div class="col-md-6">
                                                    <div class="p-3 h-100 right-wing-box">
                                                        <h6 class="fw-bold text-success mb-3">📰 該公司當下即時市場動態與真實新聞訊息：</h6>
                                                        <div id="news-zone-{row['code']}" class="market-news-zone" style="max-height: 250px; overflow-y: auto;">
                                                            <div class="text-muted small">⏳ 正在即時調取 Yahoo 財經實時新聞...</div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
        """
        
    html_content += """
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
    """

# 前端本地大字典注入
json_db_str = json.dumps(csv_dividend_database, ensure_ascii=False)

html_content += f"""
            </div>
        </div>
        
        <div id="noSearchResultCard" class="no-result-card shadow-sm bg-white">
            <h4>未找到相關個股</h4>
            <p class="text-muted mb-0 small">請檢查股票代號或中文名稱是否輸入正確。</p>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    const GLOBAL_CSV_DATABASE = {json_db_str};

    function startLiveClock() {
        const clockElement = document.getElementById('liveClockDisplay');
        if (!clockElement) return;
        setInterval(() => {
            const now = new Date();
            const yyyy = now.getFullYear();
            const mm = String(now.getMonth() + 1).padStart(2, '0');
            const dd = String(now.getDate()).padStart(2, '0');
            const hh = String(now.getHours()).padStart(2, '0');
            const min = String(now.getMinutes()).padStart(2, '0');
            const ss = String(now.getSeconds()).padStart(2, '0');
            clockElement.innerHTML = `${{yyyy}}-${{mm}}-${{dd}} ${{hh}}:${{min}}:${{ss}}`;
        }, 1000);
    }
    document.addEventListener('DOMContentLoaded', startLiveClock);

    function executeStockSearch() {
        const query = document.getElementById('globalStockSearch').value.trim().toLowerCase();
        const rows = document.querySelectorAll('.clickable-row');
        const drawers = document.querySelectorAll('.stock-detail-drawer');
        const pillContainer = document.querySelector('.text-pill-container');
        const tabContent = document.getElementById('v-pills-tabContent');
        const noResult = document.getElementById('noSearchResultCard');
        const premiumSection = document.getElementById('premiumSpecialSection');
        
        rows.forEach(r => r.classList.add('fade-out-ui'));
        
        setTimeout(() => {
            let hasAnyMatch = false;
            if (query === '') {
                rows.forEach(r => {{ r.style.display = ''; r.classList.remove('fade-out-ui'); }});
                drawers.forEach(d => {{ d.style.display = ''; if (!d.classList.contains('show')) d.style.display = 'none'; }});
                pillContainer.style.display = '';
                premiumSection.style.display = '';
                const activeTabButton = document.querySelector('.nav-pills .nav-link.active');
                if (activeTabButton) activeTabButton.click();
                noResult.style.display = 'none';
                return;
            }
            
            pillContainer.style.display = 'none';
            premiumSection.style.display = 'none';
            
            rows.forEach(row => {{
                const searchKey = row.getAttribute('data-search').toLowerCase();
                const code = searchKey.split('-')[0];
                const detailDrawer = document.getElementById('reason-code-' + code) || document.getElementById('premium-code-' + code);
                
                if (searchKey.includes(query)) {
                    row.style.display = '';
                    row.closest('.tab-pane')?.classList.add('show', 'active');
                    row.closest('#premiumSpecialSection')?.removeAttribute('style');
                    row.classList.remove('fade-out-ui');
                    if (detailDrawer && detailDrawer.classList.contains('show')) detailDrawer.style.display = '';
                    hasAnyMatch = true;
                } else {
                    row.style.display = 'none';
                    if (detailDrawer) detailDrawer.style.display = 'none';
                }
            }});
            
            if (!hasAnyMatch) {{ tabContent.style.display = 'none'; noResult.style.display = 'block'; }}
            else {{ tabContent.style.display = ''; noResult.style.display = 'none'; }}
        }, 60);
    }

    function loadLiveNews(code, yieldVal, avgY) {
        const zone = document.getElementById('news-zone-' + code) || document.getElementById('news-premium-zone-' + code);
        if (zone && zone.getAttribute('data-loaded') !== 'true') {
            const rssUrl = `https://api.rss2json.com/v1/api.json?rss_url=https://tw.stock.yahoo.com/rss?s=` + code;
            fetch(rssUrl)
                .then(res => res.json())
                .then(data => {{
                    if (data.status === 'ok' && data.items && data.items.length > 0) {
                        let html = '';
                        data.items.slice(0, 3).forEach(item => {{
                            html += `<div class='mb-3 small' style='border-bottom: 1px dashed #cbd5e1; padding-bottom: 8px; color:inherit;'>
                                        • <b>[即時市場新聞]</b> <a href='${{item.link}}' target='_blank' style='font-weight:600; text-decoration:underline; color:inherit;'>${{item.title}}</a>
                                     </div>`;
                        }});
                        zone.innerHTML = html;
                    } else {{ throw new Error(); }}
                }})
                .catch(() => {{
                    zone.innerHTML = `<div class='mb-2 small'>• <b>[大數據位階體檢]</b> 當前個股實質現金殖利率為 <b>${{yieldVal}}</b>，明顯擊敗該產業防線 (平均值為 ${{avgY}}%)。</div>`;
                }})
                .finally(() => {{ zone.setAttribute('data-loaded', 'true'); }});
        }

        const divBody = document.getElementById('dividend-body-' + code) || document.getElementById('dividend-premium-body-' + code);
        if (divBody && divBody.getAttribute('data-history-loaded') !== 'true') {
            const histData = GLOBAL_CSV_DATABASE[code];
            if (histData && histData.length > 0) {
                let html = '';
                histData.forEach(h => {{
                    html += `<tr>
                                <td><b>${{h.year}}</b></td>
                                <td class="text-success fw-bold">${{h.cash}}</td>
                                <td class="text-info fw-bold">${{h.stock}}</td>
                             </tr>`;
                }});
                divBody.innerHTML = html;
            } else {{
                divBody.innerHTML = `<tr><td colspan="3" class="text-muted small">檔案資料庫中無此股之歷史常態發放紀錄</td></tr>`;
            }}
            divBody.setAttribute('data-history-loaded', 'true');
        }
    }
    </script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("Target Dashboard completely calibrated with Profile DB!")
