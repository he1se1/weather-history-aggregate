import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import folium
from streamlit_folium import st_folium

# ページ設定
st.set_page_config(
    page_title="WeatherHistory4O",
    page_icon="🏃",
    layout="centered"
)

# --- ロジック部分 ---
def get_historical_weather(lat, lon, target_month, target_day, years, include_snow=False):
    current_year = datetime.now().year
    end_year = current_year - 1
    start_year = end_year - years + 1
    start_date = f"{start_year}-01-01"
    end_date = f"{end_year}-12-31"

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean", "precipitation_sum"],
        "timezone": "Asia/Tokyo"
    }
    if include_snow:
        params["daily"].append("snowfall_sum")

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'daily' not in data:
            return None, "APIエラー: データの取得に失敗しました。"

        df = pd.DataFrame(data['daily'])
        df['time'] = pd.to_datetime(df['time'])
        mask = (df['time'].dt.month == target_month) & (df['time'].dt.day == target_day)
        target_days = df[mask].copy()

        if target_days.empty:
            return None, "指定された日付のデータが見つかりませんでした。"

        results = []
        results.append(f"【過去の気象情報】 (過去{years}年間の{target_month}月{target_day}日の統計)")
        results.append(f"平均気温：{target_days['temperature_2m_mean'].mean():.1f}℃")
        results.append(f"平均最高気温：{target_days['temperature_2m_max'].mean():.1f}℃")
        results.append(f"平均最低気温：{target_days['temperature_2m_min'].mean():.1f}℃")
        
        precip = target_days['precipitation_sum']
        results.append(f"1mm以上の降水があった日数：{(precip >= 1.0).sum()}/{len(precip)}日")
        
        if include_snow and 'snowfall_sum' in target_days.columns:
            snow = target_days['snowfall_sum']
            results.append(f"降雪があった日数(1cm以上)：{(snow >= 1.0).sum()}/{len(snow)}日")
            results.append(f"最大降雪量：{snow.max():.2f}cm ({target_days.loc[snow.idxmax(), 'time'].year}年)")
            results.append(f"降雪があった日の平均降雪量：{snow.sum()/(snow >= 1.0).sum():.1f}cm")

        results.append("OpenMeteo Historical Weather API により作成")

        return "\n".join(results), None
    except Exception as e:
        return None, f"エラーが発生しました: {e}"

# --- UI部分 ---
st.title("気象統計取得ツール")
st.markdown("地図で地点を選択して、過去の気象統計を取得します。\nオリエンテーリング大会の要項作成を支援する目的で作成されています。")

# 設定エリア
with st.sidebar:
    st.header("設定")
    years = st.slider("遡る年数", 5, 50, 20)
    include_snow = st.checkbox("雪の統計を含める", value=False)
    
    st.divider()
    st.info("このツールは Open-Meteo API を使用しています。")

# 1. 地点選択
st.subheader("1. 地点を選択")
col1, col2 = st.columns([2, 1])

with col1:
    # デフォルトの地図表示（日本中心）
    m = folium.Map(location=[35.68, 139.76], zoom_start=5)
    m.add_child(folium.LatLngPopup())
    map_data = st_folium(m, height=400, width=500)

lat, lon = None, None
if map_data["last_clicked"]:
    lat = map_data["last_clicked"]["lat"]
    lon = map_data["last_clicked"]["lng"]

with col2:
    st.write("選択された座標:")
    lat_input = st.number_input("緯度", value=lat if lat else 35.68, format="%.6f")
    lon_input = st.number_input("経度", value=lon if lon else 139.76, format="%.6f")
    if not lat:
        st.warning("地図をクリックして地点を選択してください。")

st.subheader("2. 日付を選択")
target_date = st.date_input("大会開催日（月日のみ使用）", value=datetime.now())

# 3. 実行
if st.button("統計を取得してブリテン用テキストを生成", type="primary"):
    with st.spinner("データを取得中..."):
        res_text, error = get_historical_weather(
            lat_input, lon_input, target_date.month, target_date.day, years, include_snow
        )
        
        if error:
            st.error(error)
        else:
            st.success("取得完了！")
            st.subheader("結果")
            st.text_area("結果", res_text, height=300)
