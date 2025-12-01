import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import datetime
import re

# ==========================================================
# ページ設定（スマホ対応）
# ==========================================================
st.set_page_config(page_title="住之江AI", page_icon="🚤", layout="centered")

# CSSでスマホの文字サイズを強制的に大きくする
st.markdown("""
<style>
    .big-font { font-size: 24px !important; font-weight: bold; color: #1f77b4; }
    .med-font { font-size: 18px !important; font-weight: bold; }
    .stAlert { padding: 10px !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# ロジック・関数定義
# ==========================================================
HEADERS = {'User-Agent': 'Mozilla/5.0'}
SUPERSTARS = ["茅原悠紀", "関浩哉", "峰竜太", "池田浩二", "毒島誠", "桐生順平", "白井英治", "馬場貴也", "石野貴之"]

def get_race_time_status(race_no):
    if race_no <= 4: return "デイレース"
    elif race_no <= 7: return "夕方"
    else: return "ナイター"

@st.cache_data(ttl=300)
def get_full_race_data(place_cd, race_no, date_str):
    url_list = f"https://www.boatrace.jp/owpc/pc/race/racelist?rno={race_no}&jcd={place_cd}&hd={date_str}"
    url_info = f"https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={race_no}&jcd={place_cd}&hd={date_str}"
    try:
        resp_list = requests.get(url_list, headers=HEADERS); resp_list.encoding = resp_list.apparent_encoding
        soup_list = BeautifulSoup(resp_list.text, 'html.parser')
        tbodies = soup_list.find_all('tbody', class_='is-fs12')
    except: return None, "エラー", [], "-"
    
    if not tbodies: return None, "データなし", [], "-"

    racer_data = []
    for i, tbody in enumerate(tbodies[:6]):
        row_text = tbody.get_text()
        is_absent = "欠場" in row_text
        name_div = tbody.find('div', class_='is-fs18')
        name_raw = name_div.get_text(strip=True).replace('\u3000', '') if name_div else "不明"
        name_with_mark = f"{name_raw}{'★' if '大阪' in row_text else ''}{'【SS】' if any(s in name_raw for s in SUPERSTARS) else ''}"
        
        tds = tbody.find_all('td')
        vals = {"nation": "-", "local": "-", "motor": "-", "st": "-", "tenji": "-", "weight": "-"}
        
        if not is_absent and len(tds) >= 7:
            txt_all = tbody.get_text(separator=" ", strip=True)
            w_m = re.search(r'(\d{2})kg', txt_all)
            if w_m: vals["weight"] = w_m.group(1)
            
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

        racer_data.append({"no": i+1, "name": name_with_mark, "class": "A1" if "A1" in row_text else "A2" if "A2" in row_text else "B1" if "B1" in row_text else "B2", "weight": vals["weight"], "nation_rate": vals["nation"], "local_rate": vals["local"], "motor_rate": vals["motor"], "st": vals["st"], "tenji": vals["tenji"], "is_absent": is_absent})

    try:
        resp_info = requests.get(url_info, headers=HEADERS); resp_info.encoding = resp_info.apparent_encoding
        soup_info = BeautifulSoup(resp_info.text, 'html.parser')
        stab = "あり" if "安定板使用" in soup_info.get_text() else "なし"
        
        wb = soup_info.find('div', class_='weather1_body')
        weather_text = "不明"
        if wb:
            ft = wb.get_text(separator=" ", strip=True)
            tm = re.search(r'(\d+\.?\d*)\s*℃', ft); wm = re.search(r'風速.*?(\d+m)', ft)
            weather_text = f"{tm.group(1)+'℃' if tm else '-'} / {wm.group(1) if wm else '-'}"
        
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
    except: weather_text="-"; course_list=[]; stab="-"
    return racer_data, weather_text, course_list, stab

# ==========================================================
# UIメイン
# ==========================================================
st.title("🚤 住之江AI")

# サイドバー設定
with st.sidebar:
    st.header("設定")
    date_input = st.date_input("日付", datetime.date.today())
    race_no = st.slider("レース", 1, 12, 12)

# メインボタン（大きく）
if st.button("🔥 AI予想を実行 🔥", type="primary", use_container_width=True):
    # APIキー取得
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        st.error("APIキー未設定"); st.stop()

    s_date = date_input.strftime('%Y%m%d')
    time_status = get_race_time_status(race_no)
    
    with st.status("🚀 データを解析中...", expanded=True) as status:
        racers, weather, courses, stab = get_full_race_data("12", race_no, s_date)
        status.update(label="✅ 解析完了！", state="complete", expanded=False)
    
    if racers:
        course_text = "→".join(courses) if courses else "枠なり"
        
        # プロンプト作成
        table_str = "|枠|選手(★大阪/【SS】)|級|全国|当地|機2連|ST|\n|---|---|---|---|---|---|---|\n"
        for r in racers:
            if not r['is_absent']:
                table_str += f"|{r['no']}|{r['name']}|{r['class']}|{r['nation_rate']}|{r['local_rate']}|{r['motor_rate']}|{r['st']}|\n"

        prompt = f"""
        あなたはボートレース住之江のAIです。
        スマホで見やすいように、**表形式は使わず、箇条書きと太字**で大きく結論を出してください。

        【条件】住之江{race_no}R({time_status}) 天候:{weather} 進入:{course_text}
        【出走表】\n{table_str}

        【思考ロジック】
        1.全国率重視:当地率低くても全国率6.00以上A級は実力上位。
        2.イン崩壊:1号艇B級or全国率5.5以下&機力弱ならセンターA級頭本線。
        3.4カドまくり:4号艇A級ST早なら4-5警戒。
        4.SS特例:【SS】選手は必ず3着内。
        5.点数:基本6点。穴狙い最大8点。

        【出力デザイン】
        - 結論（買い目）を一番上に持ってくること。
        - 「本線」「抑え」「穴」を明確に分けること。
        - 買い目の数字は **1-2-3** のように太字で大きく書くこと。
        - 理由や展開予想は、買い目の後に短く書くこと。
        """
        
        with st.spinner("🧠 AIが買い目を計算中..."):
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.0-flash')
                res = model.generate_content(prompt)
                
                # 結果表示エリア（枠で囲む）
                st.markdown("---")
                st.subheader("🎯 AI最終結論")
                st.info(res.text) # AIの回答をそのまま見やすいボックスに入れる
                st.markdown("---")

            except Exception as e: st.error(f"AIエラー: {e}")
        
        # 詳細データは隠す（見たい時だけ開く）
        with st.expander("📊 出走表・詳細データを見る"):
            st.write(f"**気象**: {weather} / **安定板**: {stab}")
            st.write(f"**進入**: {course_text}")
            st.table([{
                "枠": r['no'], "選手": r['name'], "級": r['class'], 
                "全国": r['nation_rate'], "当地": r['local_rate'], 
                "機2連": r['motor_rate'], "ST": r['st']
            } for r in racers if not r['is_absent']])
                
    else:
        st.error("データ取得失敗。レースが開催されていない可能性があります。")
