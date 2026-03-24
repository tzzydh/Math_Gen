import fitz  
import re
import json
import os

def extract_knowledge_tree(pdf_path, output_json="knowledge_tree.json"):
    if not os.path.exists(pdf_path):
        print(f"[错误] 找不到文件：{pdf_path}，请确保它在当前目录下！")
        return
        
    print(f"[*] 启动 PDF 核心抓取引擎，正在解析 {pdf_path} ...")
    doc = fitz.open(pdf_path)
    
    knowledge_tree = {}
    current_chapter = None
    
    # 核心算法：正则表达式模式匹配
    re_chapter = re.compile(r'(?:第)?\s*(\d+)\s*讲\s*(.+)')
    re_type = re.compile(r'(题型[一二三四五六七八九十]+)\s*[:：]\s*(.+)')

    count_chapters = 0
    count_types = 0

    for page in doc:
        text = page.get_text()
        lines = text.split('\n')
        
        for line in lines:
            # ==================================================
            # 🧹 超级清洗器：专门对付 PDF 各种疑难杂症
            # ==================================================
            # 1. 干掉那个奇怪的  符号以及它的变体
            line = line.replace('', '').replace('\uf001', '').replace('\uf002', '')
            
            # 2. 去除两端空白，去掉可能被识别出来的排版乱码符号
            line = line.strip().replace('"', '').replace(',', '')
            if not line:
                continue
                
            # 3. 暴力斩断末尾的页码数字（例如："题型一...   950" -> "题型一..."）
            line = re.sub(r'\s*\d+\s*$', '', line).strip()
            
            # 4. 去除因为干掉数字后，可能遗留下来的真实点号或省略号 (如 ... 或 ．．．)
            line = re.sub(r'[\.．…\s]+$', '', line).strip()
            
            # 5. 切除部分 OCR 错位遗留的孤立 "第" 字
            line = re.sub(r'第$', '', line).strip()
            # ==================================================

            # 【嗅探器 1】：捕捉章节大类
            match_chapter = re_chapter.search(line)
            if match_chapter:
                chap_num = match_chapter.group(1)
                # 再次清理章节名末尾可能残留的乱码
                chap_name = re.sub(r'[\.．…\s]+$', '', match_chapter.group(2)).strip()
                current_chapter = f"第{chap_num}讲 {chap_name}"
                
                if current_chapter not in knowledge_tree:
                    knowledge_tree[current_chapter] = []
                    count_chapters += 1
                continue
                
            # 【嗅探器 2】：捕捉具体题型，并挂载到当前章节下
            match_type = re_type.search(line)
            if match_type and current_chapter:
                type_num_cn = match_type.group(1)       
                # 再次清理题型名末尾可能残留的乱码
                type_name = re.sub(r'[\.．…\s]+$', '', match_type.group(2)).strip()
                full_type = f"{type_num_cn}:{type_name}"
                
                if full_type not in knowledge_tree[current_chapter]:
                    knowledge_tree[current_chapter].append(full_type)
                    count_types += 1

    print(f"\n[*] 扫描清洗完毕！")
    print(f"[*] 战果统计：提取了 【{count_chapters}】 个大章节，【{count_types}】 个细分题型考点！")
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(knowledge_tree, f, ensure_ascii=False, indent=4)
    print(f"[√] 纯净版知识图谱已成功封存为：{output_json}\n")

if __name__ == "__main__":
    extract_knowledge_tree("目录.pdf", "knowledge_tree.json")