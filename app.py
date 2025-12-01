import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import datetime
import re

# ページ設定
st.set_page_config(page_title="住之江競艇AI予想", page_icon="🚤")

# 定数・設定
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
SUPERSTARS = ["茅原悠紀", "関浩哉", "峰竜太", "池田浩二", "毒島誠", "桐生順平", "白井英治", "馬場貴也", "石野貴之"]

def get_race_time_status(race_no):
    if race_no <= 4: return "デイレース帯"
    elif race_no <= 7: return "夕方（気温変化注意）"
    else: return "ナイター帯"

@st.cache_data(ttl=300)
def get_full_race_data(place_cd, race_no, date_str):
    url_list = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_no}&jcd={place_cd}&hd={date_str}"
    url_info = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={race_no}&jcd={place_cd}&hd={date_str}"
    try:
        resp_list = requests.get(url_list, headers=HEADERS); resp_list.encoding = resp_list.apparent_encoding
        soup_list = BeautifulSoup(resp_list.text, 'html.parser')
        tbodies = soup_list.find_all('tbody', class_='is-fs12')
    except: return None, "接続エラー", [], "不明"
    
    if not tbodies: return None, "データなし", [], "不明"

    racer_data = []
    for i, tbody in enumerate(tbodies[:6]):
        row_text = tbody.get_text()
        is_absent = "欠場" in row_text or "不参加" in row_text
        name_div = tbody.find('div', class_='is-fs18')
        name_raw = name_div.get_text(strip=True).replace('\u3000', '') if name_div else "不明"
        name_with_mark = f"{name_raw}{'★' if '大阪' in row_text else ''}{'【SS】' if any(s in name_raw for s in SUPERSTARS) else ''}"
        
        racer_class = "A1" if "A1" in row_text else ("A2" if "A2" in row_text else ("B1" if "B1" in row_text else "B2"))
        tds = tbody.find_all('td')
        vals = {"nation": "-", "local": "-", "motor": "-", "st": "-", "tenji": "-", "weight": "-"}
        
        if not is_absent and len(tds) >= 7:
            txt_all = tbody.get_text(separator=" ", strip=True)
            w_m = re.search(r'(\d{2})kg', txt_all)
            if w_m: vals["weight"] = w_m.group(1) + "kg"
            st_b = tds[3].get_text(separator="|", strip=True).split("|")
            for item in st_b: 
                if re.match(r'0\.\d{2}', item): vals["st"] = item
            
            nt = tds[4].get_text(separator="|", strip=True).split("|")
            if len(nt) > 0: vals["nation"] = re.search(r'(\d\.\d{2})', nt[0]).group(1) if re.search(r'(\d\.\d{2})', nt[0]) else "-"
            
            lt = tds[5].get_text(separator="|", strip=True).split("|")
            if len(lt) > 0: vals["local"] = re.search(r'(\d\.\d{2})', lt[0]).group(1) if re.search(r'(\d\.\d{2})', lt[0]) else "-"
            
            mt = tds[6].get_text(separator="|", strip=True).split("|")
            for item in mt:
                mn = re.search(r'(\d{2}\.\d{2})', item)
                if mn: 
                    v = float(mn.group(1))
                    if 10 <= v <= 99.9: vals["motor"] = f"{v}%"; break

        racer_data.append({"no": i+1, "name": name_with_mark, "class": racer_class, "weight": vals["weight"], "nation_rate": vals["nation"], "local_rate": vals["local"], "motor_rate": vals["motor"], "st": vals["st"], "tenji": vals["tenji"], "is_absent": is_absent})

    try:
        resp_info = requests.get(url_info, headers=HEADERS); resp_info.encoding = resp_info.apparent_encoding
        soup_info = BeautifulSoup(resp_info.text, 'html.parser')
        stab = "あり" if "安定板使用" in soup_info.get_text() else "なし"
        wb = soup_info.find('div', class_='weather1_body')
        weather_text = "情報なし"
        if wb:
            ft = wb.get_text(separator=" ", strip=True)
            tm = re.search(r'(\d+\.?\d*)\s*℃', ft); wm = re.search(r'風速.*?(\d+m)', ft)
            weather_text = f"気温:{tm.group(1)+'℃' if tm else '-'}, 風速:{wm.group(1) if wm else '-'}"
        
        course_list = []
        tables = soup_info.find_all('div', class_='table1')
        for table in tables:
            if "展示タイム" in table.get_text():
                rows = table.find_all('tbody')
                for i, row in enumerate(rows[:6]):
                    if i < len(racer_data) and len(row.find_all('td')) >= 6:
                        tt = row.find_all('td')[4].get_text(strip=True)
                        if re.match(r'\d\.\d{2}', tt): racer_data[i]['tenji'] = tt
            if "スタート展示" in table.get_text():
                for row in table.find_all('tbody'):
                    img = row.find('img', class_=lambda x: x and x.startswith('is-boatColor'))
                    if img: course_list.append(img.get('class')[0].replace('is-boatColor', ''))
    except: weather_text="取得エラー"; course_list=[]; stab="-"
    return racer_data, weather_text, course_list, stab

# UI
st.title("🚤 住之江競艇 AI予想")
st.markdown("完全ロジック（イン崩壊・SS特例・全国実績）搭載版")

with st.sidebar:
    st.header("レース設定")
    date_input = st.date_input("日付選択", datetime.date.today())
    race_no = st.slider("レース番号", 1, 12, 12)

if st.button("AI予想を開始する", type="primary"):
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        st.error("APIキーが設定されていません。")
        st.stop()

    s_date = date_input.strftime('%Y%m%d'); time_status = get_race_time_status(race_no)
    st.info(f"📡 データ取得中... 住之江 {s_date} {race_no}R")
    racers, weather, courses, stab = get_full_race_data("12", race_no, s_date)
    
    if racers:
        course_text = " -> ".join(courses) if courses else "枠なり (推定)"
        st.subheader("📊 出走表"); st.write(f"環境: {weather} / 安定板: {stab} / 進入: {course_text}")
        table_data = []; table_str = "| 枠 | 選手(★大阪/【SS】) | 級 | 全国率 | 当地率 | 機2連 | ST | 展示 |\n|---|---|---|---|---|---|---|---|\n"
        for r in racers:
            if not r['is_absent']:
                table_data.append({"枠": r['no'], "選手": r['name'], "級": r['class'], "全国": r['nation_rate'], "当地": r['local_rate'], "機2連": r['motor_rate'], "ST": r['st'], "展示": r['tenji']})
                table_str += f"| {r['no']} | {r['name']} | {r['class']} | {r['nation_rate']} | {r['local_rate']} | {r['motor_rate']} | {r['st']} | {r['tenji']} |\n"
        st.table(table_data)
        
        st.subheader("🧠 Gemini AIの結論")
        with st.spinner("AI思考中..."):
            prompt = f"""
            あなたはボートレース住之江の専門分析AIです。以下データに基づき予想せよ。
            【条件】住之江{race_no}R({time_status}) 天候:{weather} 進入:{course_text}
            【出走表】\n{table_str}
            【思考ロジック】
            1.全国率重視:当地率低くても全国率6.00以上A級は切るな。
            2.イン崩壊:1号艇B級or全国率5.5以下&機力弱ならセンターA級頭本線。
            3.4カドまくり:4号艇A級ST早なら4-5警戒。
            4.SS特例:【SS】選手は必ず3着内。
            【出力形式】
            ### 🎯 最終結論
            | 狙い | 買い目 (3連単) |
            | :--- | :--- |
            | **【本線】** | **... (※厚め)** |
            | **【抑え】** | **...** |
            | **【 穴 】** | **...** |
            **合計: X点**
            **根拠**: (1行で)
            """
            try:
                genai.configure(api_key=api_key); model = genai.GenerativeModel('gemini-2.0-flash')
                res = model.generate_content(prompt); st.markdown(res.text)
            except Exception as e: st.error(f"AIエラー: {e}")
    else: st.error("データ取得失敗")
