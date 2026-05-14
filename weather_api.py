import argparse
import sys
import webbrowser
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

# --- データ取得・計算ロジック ---
def get_historical_weather(lat, lon, target_month, target_day, years, include_snow=False):
    """
    Open-Meteo APIを使用して過去の気象データを取得し、統計を計算する
    """
    current_year = datetime.now().year
    # 昨年を起点として years 分遡る (例: 2026年実行なら 2006年〜2025年)
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
            return f"APIエラー: データの取得に失敗しました。\n{data.get('reason', '原因不明')}"

        df = pd.DataFrame(data['daily'])
        df['time'] = pd.to_datetime(df['time'])
        
        # 指定した月日のデータを抽出
        mask = (df['time'].dt.month == target_month) & (df['time'].dt.day == target_day)
        target_days = df[mask].copy()

        if target_days.empty:
            return "指定された日付のデータが期間内に見つかりませんでした。"

        results = []
        results.append(f"--- 統計結果 ({years}年間) ---")
        results.append(f"地点: 緯度 {lat}, 経度 {lon}")
        results.append(f"対象日: {target_month}月{target_day}日")
        results.append("-" * 30)
        results.append(f"平均気温: {target_days['temperature_2m_mean'].mean():.2f}℃")
        results.append(f"最高気温平均: {target_days['temperature_2m_max'].mean():.2f}℃")
        results.append(f"最低気温平均: {target_days['temperature_2m_min'].mean():.2f}℃")
        
        precip = target_days['precipitation_sum']
        results.append(f"1mm以上の降水があった割合: {(precip >= 1.0).sum()}/{len(precip)}日")
        
        if include_snow and 'snowfall_sum' in target_days.columns:
            snow = target_days['snowfall_sum']
            results.append("-" * 30)
            results.append(f"平均降雪量: {snow.mean():.2f}cm")
            results.append(f"降雪があった日数: {(snow > 0).sum()}/{len(snow)}日")
            max_snow = snow.max()
            results.append(f"期間中最大降雪量: {max_snow:.2f}cm ({target_days.loc[snow.idxmax(), 'time'].year}年)")

        return "\n".join(results)
    except Exception as e:
        return f"エラーが発生しました: {e}"

# --- GUI クラス ---
class WeatherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Open-Meteo Weather History Tool")
        self.root.geometry("500x650")
        
        # スタイル設定
        style = ttk.Style()
        style.configure("TButton", padding=5)
        style.configure("Header.TLabel", font=("MS Gothic", 12, "bold"))

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(expand=True, fill="both")

        # 1. 地点指定セクション
        ttk.Label(main_frame, text="1. 座標を入力 (緯度, 経度)", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
        
        loc_input_frame = ttk.Frame(main_frame)
        loc_input_frame.pack(fill="x", pady=5)
        
        self.loc_entry = ttk.Entry(loc_input_frame, font=("Consolas", 11))
        self.loc_entry.pack(fill="x", expand=True, padx=5)
        # self.loc_entry.insert(0, "") # 空にする
        ttk.Label(main_frame, text="例: 34.7461, 135.4106 (OSMからコピペ)", foreground="gray").pack(anchor="w")

        ttk.Button(main_frame, text="OpenStreetMapで場所を確認", command=self.open_osm).pack(pady=10)

        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=15)

        # 2. 条件設定セクション
        ttk.Label(main_frame, text="2. 条件を設定", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
        
        config_grid = ttk.Frame(main_frame)
        config_grid.pack()
        
        ttk.Label(config_grid, text="対象月:").grid(row=0, column=0, pady=5, sticky="e")
        self.month_entry = ttk.Entry(config_grid, width=8)
        self.month_entry.grid(row=0, column=1, padx=5, sticky="w")

        ttk.Label(config_grid, text="対象日:").grid(row=0, column=2, pady=5, sticky="e")
        self.day_entry = ttk.Entry(config_grid, width=8)
        self.day_entry.grid(row=0, column=3, padx=5, sticky="w")

        ttk.Label(config_grid, text="遡る年数:").grid(row=1, column=0, pady=5, sticky="e")
        self.years_entry = ttk.Entry(config_grid, width=8)
        self.years_entry.grid(row=1, column=1, padx=5, sticky="w")
        self.years_entry.insert(0, "20")

        self.snow_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(config_grid, text="雪の統計を含める", variable=self.snow_var).grid(row=1, column=2, columnspan=2, padx=5)

        # 3. 実行セクション
        ttk.Button(main_frame, text="解析を実行", command=self.run_analysis, style="Accent.TButton").pack(pady=20)

        # 4. 結果表示
        self.result_text = tk.Text(main_frame, height=12, width=55, font=("Consolas", 10))
        self.result_text.pack(expand=True, fill="both", pady=5)

    def parse_gui_coords(self):
        val = self.loc_entry.get().strip()
        try:
            parts = val.replace(' ', '').split(',')
            return float(parts[0]), float(parts[1])
        except Exception:
            raise ValueError("座標の形式が正しくありません。「緯度, 経度」の形式で入力してください。")

    def open_osm(self):
        val = self.loc_entry.get().strip()
        if not val:
            # 空ならトップページを開く
            webbrowser.open("https://www.openstreetmap.org/")
            return

        try:
            lat, lon = self.parse_gui_coords()
            webbrowser.open(f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=12/{lat}/{lon}")
        except ValueError as e:
            messagebox.showerror("エラー", str(e))

    def run_analysis(self):
        try:
            lat, lon = self.parse_gui_coords()
            m = int(self.month_entry.get())
            d = int(self.day_entry.get())
            y = int(self.years_entry.get())
            snow = self.snow_var.get()
            
            res = get_historical_weather(lat, lon, m, d, y, snow)
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, res)
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
        except Exception as e:
            messagebox.showerror("エラー", f"予期せぬエラーが発生しました: {e}")

    def mainloop(self):
        self.root.mainloop()

# --- メイン処理 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Open-Meteo Weather History Tool')
    # 短縮版の引数
    parser.add_argument('-d', '--date', type=str, help='対象月日 (例: 2/28, 02-28)')
    parser.add_argument('-l', '--loc', type=str, help='座標 (例: 34.68,135.52)')
    parser.add_argument('-y', '--years', type=int, default=20, help='遡る年数 (デフォルト: 20)')
    parser.add_argument('-s', '--snow', action='store_true', help='雪に関する統計を含める')
    
    # 従来の引数（互換性のため残す）
    parser.add_argument('--month', type=int)
    parser.add_argument('--day', type=int)
    parser.add_argument('--lat', type=float)
    parser.add_argument('--lon', type=float)

    args = parser.parse_args()

    # 引数のパース処理
    month, day = args.month, args.day
    lat, lon = args.lat, args.lon

    if args.date:
        try:
            # "/" か "-" で分割
            for sep in ['/', '-']:
                if sep in args.date:
                    parts = args.date.split(sep)
                    month, day = int(parts[0]), int(parts[1])
                    break
        except Exception:
            print("エラー: 日付形式が不正です (-d 2/28 のように入力してください)")
            sys.exit(1)

    if args.loc:
        try:
            parts = args.loc.split(',')
            lat, lon = float(parts[0]), float(parts[1])
        except Exception:
            print("エラー: 座標形式が不正です (-l 34.6,135.5 のように入力してください)")
            sys.exit(1)

    # 必要な引数が揃っている場合はCLIモード
    if month and day and lat and lon:
        result = get_historical_weather(lat, lon, month, day, args.years, args.snow)
        print(result)
    else:
        # 揃っていなければGUI起動
        gui = WeatherGUI()
        gui.mainloop()
