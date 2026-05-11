# -*- coding: utf-8 -*-
"""
出租车行程单PDF提取工具
功能：批量解析文件夹内的PDF行程单，提取行程数据并生成标准化Excel报表
核心：pdfplumber解析PDF文本 + 正则匹配数据 + pandas生成Excel
"""
import os          # 文件/文件夹操作
import re         # 正则表达式，用于文本匹配提取
import glob       # 批量查找文件
import sys        # 系统接口
import pdfplumber # PDF文本精准解析库
import pandas as pd  # 数据处理与Excel导出

def extract_travel_year(text):
    """
    精准提取行程真实年份
    避开申请日期/打印日期等干扰信息，优先匹配行程相关日期
    :param text: PDF全文文本
    :return: 提取的年份字符串，默认2025
    """
    match = re.search(r'行程[时间起止日期]*[：:]\s*(\d{4})', text)
    return match.group(1) if match else "2025"

def clean_address(text):
    """
    地址数据清洗
    清除PDF解析产生的多余空格，统一中文地址格式
    :param text: 原始地址文本
    :return: 清洗后的标准地址
    """
    if not text: return ""
    return re.sub(r'\s+', '', text).strip()

def process_pdf(pdf_path):
    """
    处理单个PDF行程单，提取结构化数据
    :param pdf_path: PDF文件路径
    :return: 清洗后的行程数据列表 + 表头坐标（备用）
    """
    records = []          # 存储原始解析数据
    header_x0 = None      # 表头起始X坐标

    # 打开并解析PDF第一页
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        # 提取PDF文字（设置容差，适配不同排版）
        words = page.extract_words(x_tolerance=2, y_tolerance=4)
        if not words: return records, header_x0

        # 按行分组文字（根据Y坐标归类同一行文字）
        lines = {}
        for w in words:
            lines.setdefault(round(w['top'], 1), []).append(w)
        sorted_ys = sorted(lines.keys())  # 按从上到下排序行

        # 拼接全文，提取行程年份
        full_text = " ".join(w['text'] for w in words)
        year_prefix = extract_travel_year(full_text)

        # 定位表头行（识别"上车时间"/"序号"关键字）
        header_y = None
        for y in sorted_ys:
            txt = " ".join(w['text'] for w in lines[y])
            if '上车时间' in txt or '序号' in txt:
                header_y = y
                break
        if header_y is None: return records, header_x0

        # 排序表头文字，获取起始坐标
        header_words = sorted(lines[header_y], key=lambda x: x['x0'])
        header_x0 = header_words[0]['x0']

        # 匹配标准列：上车时间、城市、起点、终点、金额
        std_cols = ['上车时间', '城市', '起点', '终点', '金额']
        col_centers = {}
        for w in header_words:
            t = w['text'].strip()
            for sc in std_cols:
                if sc in t or t.startswith(sc[:2]) or sc.startswith(t[:2]):
                    col_centers[sc] = (w['x0'] + w['x1']) / 2.0
                    break

        # 计算列分割线（根据列中心坐标取中点）
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

        # 逐行解析数据，匹配对应列
        current_rec = {'上车时间': '', '城市': '', '起点': '', '终点': '', '金额': ''}
        is_active = False  # 数据行激活标志

        for y in sorted_ys:
            if y <= header_y + 2: continue  # 跳过表头行
            line_txt = " ".join(w['text'] for w in lines[y])
            # 遇到页码/广告标识，停止解析
            if '页码' in line_txt or 'AMAP' in line_txt or 'DIDI' in line_txt: break

            # 判断新行（以序号开头）
            is_new_row = bool(re.match(r'^\s*\d', line_txt))
            if is_new_row and is_active:
                records.append(current_rec.copy())
                current_rec = {k: '' for k in current_rec}
            if is_new_row: is_active = True

            # 根据X坐标将文字分配到对应列
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

        # 保存最后一条有效记录
        if is_active and current_rec['金额'].strip():
            records.append(current_rec)

    # ===================== 数据清洗与标准化 =====================
    clean_data = []
    for rec in records:
        if not rec['金额'].strip(): continue

        # 拼接时间+城市文本，提取日期和时间
        left_combined = rec['上车时间'].strip() + " " + rec['城市'].strip()
        dt_yyyy = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', left_combined)
        dt_mmdd = re.search(r'(\d{2}-\d{2})\s+(\d{2}:\d{2})', left_combined)
        
        # 标准化日期格式（补全年份）
        if dt_yyyy:
            date_val, time_val = dt_yyyy.group(1), dt_yyyy.group(2)
        elif dt_mmdd:
            date_val = f"{year_prefix}-{dt_mmdd.group(1)}"
            time_val = dt_mmdd.group(2)
        else:
            date_val = time_val = ""

        # 提取城市名称
        city_match = re.search(r'([\u4e00-\u9fa5]+市)', left_combined)
        city_val = city_match.group(1) if city_match else rec['城市'].strip()
        
        # 提取金额（浮点型）
        amt_list = re.findall(r'\d+\.\d+', rec['金额'])
        amt_val = float(amt_list[-1]) if amt_list else 0.0

        # 组装清洗后的数据
        clean_data.append({
            '日期': date_val,
            '时间': time_val,
            '城市': city_val,
            '起点': clean_address(rec['起点']),
            '终点': clean_address(rec['终点']),
            '金额': amt_val
        })
        
    return clean_data, header_x0

# ==============================================
# 主函数：批量处理文件夹PDF，生成Excel报表
# ==============================================
def extract_taxi_receipts(folder_path, log_func=print):
    """
    提取指定文件夹下出租车行程单PDF中的数据，并保存为Excel文件
    :param folder_path: 存放出租车行程单PDF的文件夹路径
    :param log_func: 日志输出函数（GUI专用，命令行默认print）
    :return: 处理后的DataFrame（无数据时返回None）
    """
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        log_func(f"❌ 错误：文件夹 {folder_path} 不存在")
        return None
    
    # 批量查找所有PDF文件
    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    if not pdf_files:
        log_func(f"⚠️ 未在 {folder_path} 中找到任何PDF行程单")
        return None

    all_records = []
    # 遍历解析所有PDF
    for pdf_path in pdf_files:
        log_func(f"📄 解析: {os.path.basename(pdf_path)}")
        try:
            recs, _ = process_pdf(pdf_path)
            all_records.extend(recs)
            log_func(f"   ✅ 提取 {len(recs)} 条有效记录")
        except Exception as e:
            log_func(f"   ❌ 解析失败: {e}")

    # 无有效数据时退出
    if not all_records:
        log_func("⚠️ 未提取到任何有效行程数据")
        return None

    # 整理数据并导出Excel
    df = pd.DataFrame(all_records)
    cols = ['日期', '时间', '城市', '起点', '终点', '金额']
    df = df[cols]

    # 保存Excel到原文件夹
    output_path = os.path.join(folder_path, "taxiticket.xlsx")
    df.to_excel(output_path, index=False, float_format="%.2f")
    log_func(f"\n🎉 处理完成！Excel文件已保存至: {output_path}")
    
    return df

# ===================== 命令行独立运行测试 =====================
if __name__ == "__main__":
    # 测试：传入你的文件夹路径，直接运行即可测试
    test_folder = "/Users/zhangk/myproject/extract_taxitickets"
    extract_taxi_receipts(test_folder)