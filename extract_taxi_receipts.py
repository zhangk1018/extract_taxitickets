import os
import re
import glob
import sys
import pdfplumber
import pandas as pd
import tkinter as tk
from tkinter import filedialog

def extract_travel_year(text):
    """精准提取行程真实年份，避开申请日期/打印日期干扰"""
    match = re.search(r'行程[时间起止日期]*[：:]\s*(\d{4})', text)
    return match.group(1) if match else "2025"

def clean_address(text):
    """🔧 新增：清除PDF解析产生的内部空格，符合标准中文地址格式"""
    if not text: return ""
    return re.sub(r'\s+', '', text).strip()

def process_pdf(pdf_path):
    records = []
    header_x0 = None

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(x_tolerance=2, y_tolerance=4)
        if not words: return records, header_x0

        lines = {}
        for w in words:
            lines.setdefault(round(w['top'], 1), []).append(w)
        sorted_ys = sorted(lines.keys())

        full_text = " ".join(w['text'] for w in words)
        year_prefix = extract_travel_year(full_text)

        header_y = None
        for y in sorted_ys:
            txt = " ".join(w['text'] for w in lines[y])
            if '上车时间' in txt or '序号' in txt:
                header_y = y
                break
        if header_y is None: return records, header_x0

        header_words = sorted(lines[header_y], key=lambda x: x['x0'])
        header_x0 = header_words[0]['x0']

        std_cols = ['上车时间', '城市', '起点', '终点', '金额']
        col_centers = {}
        for w in header_words:
            t = w['text'].strip()
            for sc in std_cols:
                if sc in t or t.startswith(sc[:2]) or sc.startswith(t[:2]):
                    col_centers[sc] = (w['x0'] + w['x1']) / 2.0
                    break

        sorted_centers = sorted(col_centers.items(), key=lambda x: x[1])
        boundaries = {}
        for i in range(len(sorted_centers) - 1):
            col1, x1 = sorted_centers[i]
            col2, x2 = sorted_centers[i+1]
            mid = (x1 + x2) / 2.0
            if col1 == '上车时间': boundaries['time_city'] = mid
            elif col1 == '城市': boundaries['city_start'] = mid
            elif col1 == '起点': boundaries['start_end'] = mid
            elif col1 == '终点': boundaries['end_amount'] = mid

        current_rec = {'上车时间': '', '城市': '', '起点': '', '终点': '', '金额': ''}
        is_active = False

        for y in sorted_ys:
            if y <= header_y + 2: continue
            line_txt = " ".join(w['text'] for w in lines[y])
            if '页码' in line_txt or 'AMAP' in line_txt or 'DIDI' in line_txt: break

            is_new_row = bool(re.match(r'^\s*\d', line_txt))
            if is_new_row and is_active:
                records.append(current_rec.copy())
                current_rec = {k: '' for k in current_rec}
            if is_new_row: is_active = True

            for w in lines[y]:
                cx = (w['x0'] + w['x1']) / 2.0
                if cx < boundaries.get('time_city', 300):
                    current_rec['上车时间'] += w['text'] + " "
                elif cx < boundaries.get('city_start', 400):
                    current_rec['城市'] += w['text'] + " "
                elif cx < boundaries.get('start_end', 500):
                    current_rec['起点'] += w['text'] + " "
                elif cx < boundaries.get('end_amount', 600):
                    current_rec['终点'] += w['text'] + " "
                else:
                    current_rec['金额'] += w['text'] + " "

        if is_active and current_rec['金额'].strip():
            records.append(current_rec)

    # 4. 数据清洗（新增地址空格过滤）
    clean_data = []
    for rec in records:
        if not rec['金额'].strip(): continue

        left_combined = rec['上车时间'].strip() + " " + rec['城市'].strip()
        dt_yyyy = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', left_combined)
        dt_mmdd = re.search(r'(\d{2}-\d{2})\s+(\d{2}:\d{2})', left_combined)
        
        if dt_yyyy:
            date_val, time_val = dt_yyyy.group(1), dt_yyyy.group(2)
        elif dt_mmdd:
            date_val = f"{year_prefix}-{dt_mmdd.group(1)}"
            time_val = dt_mmdd.group(2)
        else:
            date_val = time_val = ""

        city_match = re.search(r'([\u4e00-\u9fa5]+市)', left_combined)
        city_val = city_match.group(1) if city_match else rec['城市'].strip()
        
        amt_list = re.findall(r'\d+\.\d+', rec['金额'])
        amt_val = float(amt_list[-1]) if amt_list else 0.0

        clean_data.append({
            '日期': date_val,
            '时间': time_val,
            '城市': city_val,
            '起点': clean_address(rec['起点']),  # ✅ 应用空格清洗
            '终点': clean_address(rec['终点']),  # ✅ 应用空格清洗
            '金额': amt_val
        })
        
    return clean_data, header_x0

def main():
    # 🔧 智能获取 exe 或脚本所在目录（兼容打包后运行）
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))

    target_dir = os.path.join(script_dir, "taxiticket")
    
    # 🔍 检查默认目录是否存在且包含 PDF
    default_valid = os.path.exists(target_dir) and len(glob.glob(os.path.join(target_dir, "*.pdf"))) > 0

    if not default_valid:
        print("⚠️ 未检测到默认 'taxiticket' 文件夹或其中无行程单，请选择行程单所在目录...")
        # 🖥️ 调用系统原生文件夹选择对话框
        root = tk.Tk()
        root.withdraw()  # 隐藏 tkinter 主窗口
        target_dir = filedialog.askdirectory(title="请选择行程单所在目录")
        root.destroy()
        
        if not target_dir:
            print("❌ 未选择文件夹，程序退出。")
            return
        print(f"✅ 已选择目录: {target_dir}")

    pdf_files = glob.glob(os.path.join(target_dir, "*.pdf"))
    if not pdf_files:
        print(f"⚠️ 未在 {target_dir} 中找到 PDF 文件。")
        return

    all_records = []
    for pdf_path in pdf_files:
        print(f"📄 解析: {os.path.basename(pdf_path)}")
        try:
            recs, _ = process_pdf(pdf_path)
            all_records.extend(recs)
            print(f"   ✅ 提取 {len(recs)} 条")
        except Exception as e:
            print(f"   ❌ 异常: {e}")

    if all_records:
        df = pd.DataFrame(all_records)
        cols = ['日期', '时间', '城市', '起点', '终点', '金额']
        df = df[cols]

        # 💾 Excel 自动保存到用户选择的目录
        output_path = os.path.join(target_dir, "taxiticket.xlsx")
        df.to_excel(output_path, index=False, float_format="%.2f")
        print(f"\n🎉 成功！Excel 已保存至: {output_path}")
    else:
        print("⚠️ 未提取到有效数据。")

if __name__ == "__main__":
    main()
