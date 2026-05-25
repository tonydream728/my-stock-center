import os
import requests
import pandas as pd
import datetime

# 從保險箱讀取密鑰
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN")

# 23 檔黃仁勳核心供應鏈清單
stock_list = {
    '3037': '欣興', '2308': '台達電', '5289': '宜鼎', '2454': '聯發科',
    '2330': '台積電', '2449': '京元電', '2345': '智邦', '6669': '緯穎',
    '2301': '光寶科', '3017': '奇鋐', '2317': '鴻海', '2395': '研華',
    '2357': '華碩', '2376': '技嘉', '3231': '緯創', '2324': '仁寶',
    '2382': '廣達', '2356': '英業達', '3515': '華擎', '2353': '宏碁',
    '4938': '和碩', '2377': '微星', '6125': '廣運'
}

today = datetime.datetime.now()
start_date = (today - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')

data_rows = []

print("🚀 啟動 AI 籌碼監控中心...")

for code, name in stock_list.items():
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        
        # 1. 抓取股價
        price_param = {"dataset": "TaiwanStockPrice", "data_id": code, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
        price_df = pd.DataFrame(requests.get(url, params=price_param).json()['data'])
        if price_df.empty: continue
        current_price = price_df.iloc[-1]['close']
        
        # 2. 抓取估值
        val_param = {"dataset": "TaiwanStockPERValuation", "data_id": code, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
        val_df = pd.DataFrame(requests.get(url, params=val_param).json()['data'])
        trailing_pe = val_df.iloc[-1]['PE'] if not val_df.empty else "N/A"
        dividend_yield = val_df.iloc[-1]['DividendYield'] if not val_df.empty else 0
        
        # 3. 抓取融資
        margin_param = {"dataset": "TaiwanStockMarginPurchaseShortSale", "data_id": code, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
        margin_df = pd.DataFrame(requests.get(url, params=margin_param).json()['data'])
        
        # 4. 抓取三大法人買賣
        inst_param = {"dataset": "InstitutionalInvestorsBuySell", "data_id": code, "start_date": start_date, "end_date": end_date, "token": FINMIND_TOKEN}
        inst_df = pd.DataFrame(requests.get(url, params=inst_param).json()['data'])
        
        margin_change = 0
        if not margin_df.empty and len(margin_df) >= 2:
            m_today = margin_df[margin_df['name'] == 'MarginPurchase']
            if len(m_today) >= 2:
                margin_change = m_today.iloc[-1]['TodayBalance'] - m_today.iloc[-2]['TodayBalance']
                
        foreign_buy = 0
        if not inst_df.empty:
            f_today = inst_df[(inst_df['name'] == 'Foreign_Investor') & (inst_df['date'] == inst_df.iloc[-1]['date'])]
            if not f_today.empty:
                foreign_buy = f_today.iloc[-1]['buy'] - f_today.iloc[-1]['sell']

        # 價值與籌碼交叉驗證邏輯
        is_value = (dividend_yield >= 4.5) or (isinstance(trailing_pe, (int, float)) and trailing_pe < 16)
        is_chip_safe = (margin_change <= 0) and (foreign_buy >= 0)
        
        if is_value and is_chip_safe:
            status = "🟢 便宜價 (外資回頭吃貨，籌碼穩健)"
            color = "success"
            reason = f"【外資與籌碼背景解密】此標的目前官方殖利率達 {dividend_yield:.2f}%。數據顯示外資今日已結束提款，反手買超現貨 {foreign_buy} 張；同時散戶融資出現停損清洗（今日大減 {abs(margin_change)} 張）。符合巴菲特『好公司遇到暫時性籌碼麻煩』的打折存股時機，適合長線購入。"
        elif is_value and not is_chip_safe:
            status = "🟡 合理價 (估值便宜但外資賣壓仍在)"
            color = "warning"
            reason = f"【外資與籌碼背景解密】雖然殖利率已落入歷史便宜區，但散戶融資仍在高檔死守，且外資今日持續賣超現貨 {abs(foreign_buy)} 張。顯示外商主力正在執行『刻意壓低股價以迫使散戶融資斷頭』的策略。此時不宜跟外資對幹，建議維持原有定期定額節奏。"
        else:
            status = "🔴 昂貴價 (市場情緒過熱，不建議追高)"
            color = "danger"
            reason = f"【外資與籌碼背景解密】目前市場預期過度瘋狂，推升本益比至 {trailing_pe} 倍的高位階，殖利率被稀釋至 {dividend_yield:.2f}%。不符合巴菲特看重實質現金流與安全邊際的標準。策略上應保持耐心、暫時觀望，將資金留存，靜待非理性修正帶來的打折機會。"

        data_rows.append({
            'code': code, 'name': name, 'price': current_price,
            'pe': f"{trailing_pe:.1f}" if isinstance(trailing_pe, (int, float)) else "N/A",
            'yield': f"{dividend_yield:.2f}%", 'status': status, 'color': color, 'reason': reason
        })
    except Exception as e:
        print(f"無法分析 {name}: {e}")

# 生成清爽明亮的網頁 HTML
html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>我的不看盤價值投資中心</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f7f9fa; color: #333333; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "微軟正黑體", sans-serif; }}
        .navbar-custom {{ background-color: #ffffff; border-bottom: 1px solid #eef2f5; }}
        .navbar-brand {{ font-weight: 700; color: #1e293b !important; }}
        .card-custom {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); }}
        .table-custom {{ background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
        .status-badge {{ padding: 6px 14px; border-radius: 50px; font-weight: 600; font-size: 0.85rem; display: inline-block; }}
        .bg-success-light {{ background-color: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }}
        .bg-warning-light {{ background-color: #fffbef; color: #92400e; border: 1px solid #fef3c7; }}
        .bg-danger-light {{ background-color: #fef2f2; color: #991b1b; border: 1px solid #fee2e2; }}
        .analysis-box {{ background-color: #f8fafc; border-left: 4px solid #3b82f6; border-radius: 0 8px 8px 0; }}
    </style>
</head>
<body>
    <nav class="navbar navbar-custom py-3">
        <div class="container">
            <span class="navbar-brand">💡 我的不看盤價值投資中心</span>
            <span class="badge bg-light text-dark p-2 border">最後更新：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
        </div>
    </nav>

    <div class="container my-5">
        <div class="card card-custom p-4 mb-5" style="background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%); border-left: 6px solid #10b981;">
            <h5 class="fw-bold text-success mb-2">巴菲特長線存股心法 🎯</h5>
            <p class="mb-0 text-secondary" style="font-size: 0.95rem; line-height: 1.6;">「如果你不想持有這隻股票十年，那你就連十分鐘也不要持有。」我們透過大數據洞察外商與大戶動向，在好公司股價打折時，優雅地累積零股賺取長線股利。</p>
        </div>

        <div class="card card-custom p-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="fw-bold m-0 text-dark">🚀 黃仁勳核心供應鏈 — 23 檔動態體檢表</h5>
                <span class="text-muted small">💡 提示：點擊股票即可展開原因說明</span>
            </div>
            <div class="table-responsive">
                <table class="table table-custom table-hover align-middle mb-0">
                    <thead class="table-light">
                        <tr>
                            <th class="ps-4">代號</th>
                            <th>公司名稱</th>
                            <th>當前股價 (元)</th>
                            <th>目前本益比</th>
                            <th>現金殖利率</th>
                            <th class="pe-4">投資策略建議</th>
                        </tr>
                    </thead>
                    <tbody>
"""

for idx, row in enumerate(data_rows):
    badge_class = "bg-success-light" if "🟢" in row['status'] else ("bg-warning-light" if "🟡" in row['status'] else "bg-danger-light")
    html_content += f"""
                        <tr data-bs-toggle="collapse" data-bs-target="#reason-{idx}" style="cursor: pointer;">
                            <td class="ps-4"><b>{row['code']}</b></td>
                            <td><span class="fw-semibold text-dark">{row['name']}</span></td>
                            <td><span class="badge bg-light text-dark border p-2">{row['price']}</span></td>
                            <td>{row['pe']}</td>
                            <td class="text-success fw-bold">{row['yield']}</td>
                            <td class="pe-4"><span class="status-badge {badge_class}">{row['status']}</span></td>
                        </tr>
                        <tr id="reason-{idx}" class="collapse">
                            <td colspan="6" class="p-0">
                                <div class="p-4 mx-4 my-2 analysis-box shadow-sm">
                                    <h6 class="fw-bold text-primary mb-2">🔍 籌碼面背景原因深度解析：</h6>
                                    <p class="text-dark mb-0" style="font-size: 0.92rem; line-height: 1.65;">{row['reason']}</p>
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
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("index.html 網頁生成成功！")
