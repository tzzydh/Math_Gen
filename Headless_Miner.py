import os
import json
import base64
import time
import shutil
import fitz  # PyMuPDF
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
import sys

from core.settings import settings, require_env
from core.openai_compat import call_openai_vision_json

# ==========================================
# 1. 核心配置区（v0.1 安全升级：改为环境变量）
# ==========================================
INPUT_DIR = "input_pdfs"
DONE_DIR = "processed_pdfs"
BANK_FILE = "bank_v2.json"

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(DONE_DIR, exist_ok=True)


def build_client() -> OpenAI:
    api_key = require_env("OPENAI_API_KEY")
    return OpenAI(api_key=api_key, base_url=settings.openai_base_url)


client = None
MODEL_NAME = settings.openai_model_name


def get_client() -> OpenAI:
    global client
    if client is None:
        client = build_client()
    return client

prompt = """
你是一个资深的中国高中数学教研专家。请精准识别这张图片上的所有数学题目。
要求：
1. 必须输出严格的 JSON 对象，包含 "questions" 键，其值为题目数组。格式：
{"questions": [{"stem":"题干主体", "options":["A","B","C","D"], "answer":"正确答案", "analysis":"完整解析"}]}
2. 如果是解答题，options 数组请保留为空 []。
3. 如果这页没有数学题，请输出 {"questions": []}。
4. 所有数学公式必须使用 LaTeX 格式，用 $ 包裹。
5. 只输出纯 JSON 字符串，不要输出 ```json 等标记。
"""


def process_page(pdf_name, page_num, img_bytes):
    """单独处理一页的逻辑"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            base64_image = base64.b64encode(img_bytes).decode('utf-8')

            image_data_url = f"data:image/png;base64,{base64_image}"
            result_text = call_openai_vision_json(
                client=get_client(),
                model=MODEL_NAME,
                prompt=prompt,
                image_data_url=image_data_url,
                timeout=45,
            ).strip()

            import re
            result_text = re.sub(r'^```json\s*', '', result_text, flags=re.IGNORECASE)
            result_text = re.sub(r'\s*```$', '', result_text)
            result_text = re.sub(r'\\(?![/\\bfnrt"])', r'\\\\', result_text)

            data = json.loads(result_text)
            q_list = data.get("questions", [])

            for q in q_list:
                q["id"] = f"Q_{uuid.uuid4().hex[:8].upper()}"
                q["source_pdf"] = pdf_name
                q["image"] = "[待补图片占位符]"
                q["meta"] = {"score": 5, "difficulty": "中", "chapter": "待分类", "knowledge_weights": {}}
            return q_list

        except Exception:
            if attempt == max_retries - 1:
                return []  # 彻底失败返回空，不阻碍主线程
            time.sleep(2)


def run_miner():
    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("📭 input_pdfs 文件夹为空，请放入 PDF 后再运行。")
        return

    db = []
    if os.path.exists(BANK_FILE):
        with open(BANK_FILE, 'r', encoding='utf-8') as f:
            try:
                db = json.load(f)
            except Exception:
                pass

    total_extracted = 0

    for pdf_file in pdf_files:
        pdf_path = os.path.join(INPUT_DIR, pdf_file)
        print("\n==========================================")
        print(f"📄 开始开采: 【{pdf_file}】")

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_data = []

        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=150)
            pages_data.append((pdf_file, page_num, pix.tobytes("png")))
        doc.close()

        pdf_extracted_count = 0
        completed_pages = 0

        # 打印初始进度条
        sys.stdout.write(f"⏳ 进度: [0/{total_pages} 页] 正在狂奔中...")
        sys.stdout.flush()

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_page = {executor.submit(process_page, *p): p for p in pages_data}
            for future in as_completed(future_to_page):
                completed_pages += 1
                q_list = future.result()

                if q_list:
                    db.extend(q_list)
                    pdf_extracted_count += len(q_list)

                # 【核心】：利用 \r 实时刷新当前行的数据，不刷屏！
                percent = int((completed_pages / total_pages) * 100)
                sys.stdout.write(f"\r⏳ 进度: [{completed_pages}/{total_pages} 页] 已提取 {pdf_extracted_count} 题 ({percent}%)  ")
                sys.stdout.flush()

        print(f"\n✅ 完工！这份卷子共收获 {pdf_extracted_count} 题。")
        total_extracted += pdf_extracted_count

        with open(BANK_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=4)

        shutil.move(pdf_path, os.path.join(DONE_DIR, pdf_file))

    print(f"\n🎉 所有矿机已停机！本次共计录入 {total_extracted} 道题进入总题库！")


if __name__ == "__main__":
    run_miner()
