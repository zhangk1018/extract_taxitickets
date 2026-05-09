import os
import re
import glob
import pdfplumber
import pandas as pd

def extract_travel_year(text):
    """精准提取行程真实年份，避开申请日期/打印日期干扰"""
    # 定向匹配“行程时间”或“行程起止日期”后的第一个四位年份
    match = re.search(r'行程[时间起止日期]*[：:]\s*(\d{4})', text)
    return match.group(1) if match else "2025"

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

        # 提取全文头部文本，精准获取行程年份
        full_text = " ".join(w['text'] for w in words)
        year_prefix = extract_travel_year(full_text)

        # 2. 定位表头行
        header_y = None
        for y in sorted_ys:
            txt = " ".join(w['text'] for w in lines[y])
            if '上车时间' in txt or '序号' in txt:
                header_y = y
                break
        if header_y is None: return records, header_x0

        header_words = sorted(lines[header_y], key=lambda x: x['x0'])
        header_x0 = header_words[0]['x0']

        # 🎯 获取关键列的X中心坐标
        std_cols = ['上车时间', '城市', '起点', '终点', '金额']
        col_centers = {}
        for w in header_words:
            t = w['text'].strip()
            for sc in std_cols:
                if sc in t or t.startswith(sc[:2]) or sc.startswith(t[:2]):
                    col_centers[sc] = (w['x0'] + w['x1']) / 2.0
                    break

        # 📐 动态计算列边界中线
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

        # 3. 数据行解析（状态机聚合多行）
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

            # 📍 X坐标边界归类
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

    # 4. 数据清洗（兼容双格式，修复年份提取）
    clean_data = []
    for rec in records:
        if not rec['金额'].strip(): continue

        left_combined = rec['上车时间'].strip() + " " + rec['城市'].strip()
        
        # 兼容 YYYY-MM-DD 与 MM-DD
        dt_yyyy = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', left_combined)
        dt_mmdd = re.search(r'(\d{2}-\d{2})\s+(\d{2}:\d{2})', left_combined)
        
        if dt_yyyy:
            date_val, time_val = dt_yyyy.group(1), dt_yyyy.group(2)
        elif dt_mmdd:
            # ✅ 使用精准提取的行程年份拼接
            date_val = f"{year_prefix}-{dt_mmdd.group(1)}"
            time_val = dt_mmdd.group(2)
        else:
            date_val = time_val = ""

        city_match = re.search(r'([\u4e00-\u9fa5]+市)', left_combined)
        city_val = city_match.group(1) if city_match else rec['城市'].strip()
        
        # 金额取最后一个带小数的数字，避开里程/页码干扰
        amt_list = re.findall(r'\d+\.\d+', rec['金额'])
        amt_val = float(amt_list[-1]) if amt_list else 0.0

        clean_data.append({
            '日期': date_val,
            '时间': time_val,
            '城市': city_val,
            '起点': rec['起点'].strip(),
            '终点': rec['终点'].strip(),
            '金额': amt_val
        })
        
    return clean_data, header_x0

def main():
    target_dir = os.path.join("aider-repository", "taxiticket")
    if not os.path.exists(target_dir):
        print(f"❌ 目录不存在: {target_dir}")
        return

    pdf_files = glob.glob(os.path.join(target_dir, "*.pdf"))
    if not pdf_files:
        print(f"⚠️ 未找到 PDF 文件。")
        return

    all_records = []
    for pdf_path in pdf_files:
        print(f"📄 解析: {os.path.basename(pdf_path)}")
        try:
            recs, hdr_x = process_pdf(pdf_path)
            all_records.extend(recs)
            print(f"   ✅ 提取 {len(recs)} 条")
        except Exception as e:
            print(f"   ❌ 异常: {e}")

    if all_records:
        df = pd.DataFrame(all_records)
        cols = ['日期', '时间', '城市', '起点', '终点', '金额']
        df = df[cols]

        output_path = os.path.join(target_dir, "网约车行程单汇总.xlsx")
        df.to_excel(output_path, index=False, float_format="%.2f")
        print(f"\n🎉 成功！Excel 已保存至: {output_path}")
    else:
        print("⚠️ 未提取到有效数据。")

if __name__ == "__main__":
    main()
    