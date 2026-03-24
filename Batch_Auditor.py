import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import uuid
import threading
import re
import time
import base64

# ==========================================
# 🚀 1. 代理与 API Key 集中配置区 (在这里写死)
# ==========================================
# 挂载代理 (确保能连通外网)
os.environ['http_proxy'] = 'http://127.0.0.1:33210'
os.environ['https_proxy'] = 'http://127.0.0.1:33210'
#os.environ['all_proxy'] = 'socks5://127.0.0.1:33211'

# 在这里填入您的秘钥（写死后，界面上就不需要输入了）
GEMINI_API_KEY = "AIzaSyC7VcVn8l3D7Oo9W_bkIktFAwjXZs_9l4g"
OPENAI_API_KEY = "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"
# 如果您使用的是国内中转站的 GPT 接口，请修改下方地址，否则保持默认
OPENAI_BASE_URL = "https://api.openai.com/v1" 

import google.generativeai as genai
from openai import OpenAI
import fitz  
import PIL.Image
import io

class BatchAuditor:
    def __init__(self, root):
        self.root = root
        self.root.title("高三数学题库 - V6.0 双引擎批处理流水线")
        self.root.geometry("900x950")
        
        self.bank_file = "bank_v2.json"
        self.tree_file = "knowledge_tree.json"
        self.knowledge_tree = self.load_tree()
        self.chapters = list(self.knowledge_tree.keys()) if self.knowledge_tree else ["未加载图谱"]
        
        self.question_queue = []
        self.current_q = None
        self.create_ui()

    def load_tree(self):
        if os.path.exists(self.tree_file):
            with open(self.tree_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def create_ui(self):
        # ================= 0. 引擎控制台 =================
        frame_top = tk.LabelFrame(self.root, text="核心大模型引擎路由", font=("Microsoft YaHei", 10, "bold"), fg="blue", padx=10, pady=5)
        frame_top.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame_top, text="选择打工 AI:").pack(side="left")
        self.model_var = tk.StringVar(value="Gemini-2.5-Flash (免费大碗)")
        self.cb_model = ttk.Combobox(frame_top, textvariable=self.model_var, width=30, state="readonly")
        self.cb_model['values'] = [
            "Gemini-2.5-Flash (免费大碗)",
            "Gemini-2.5-Pro (深度推理)",
            "GPT-4o (顶级识别)",
            "GPT-4o-mini (快速低价)"
        ]
        self.cb_model.pack(side="left", padx=5)
        
        self.btn_load_pdf = tk.Button(frame_top, text="📂 丢入 PDF 开启流水线", bg="#FF9800", fg="white", font=("Microsoft YaHei", 10, "bold"), command=self.start_batch_thread)
        self.btn_load_pdf.pack(side="right", padx=5)
        
        self.lbl_status = tk.Label(frame_top, text="待审: 0 题", font=("Microsoft YaHei", 10, "bold"), fg="red")
        self.lbl_status.pack(side="right", padx=20)

        # ================= 1. 分类打标区 =================
        frame_meta = tk.LabelFrame(self.root, text="第一步：人工打标", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=5)
        frame_meta.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame_meta, text="难度:").grid(row=0, column=0, sticky="e")
        self.diff_var = tk.StringVar(value="中")
        ttk.Combobox(frame_meta, textvariable=self.diff_var, values=["易", "中", "难"], width=5).grid(row=0, column=1, sticky="w", padx=5)
        
        tk.Label(frame_meta, text="大章节:").grid(row=0, column=2, sticky="e")
        self.chap_var = tk.StringVar()
        self.cb_chap = ttk.Combobox(frame_meta, textvariable=self.chap_var, values=self.chapters, width=35)
        self.cb_chap.grid(row=0, column=3, sticky="w", padx=5)
        self.cb_chap.bind("<<ComboboxSelected>>", self.update_topics)
        
        tk.Label(frame_meta, text="具体题型:").grid(row=1, column=2, sticky="e", pady=5)
        self.topic_var = tk.StringVar()
        self.cb_topic = ttk.Combobox(frame_meta, textvariable=self.topic_var, width=35)
        self.cb_topic.grid(row=1, column=3, sticky="w", padx=5)

        # ================= 2. 审核编辑区 =================
        frame_content = tk.LabelFrame(self.root, text="第二步：AI 识别内容核对 (可直接修改)", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=5)
        frame_content.pack(fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(frame_content, text="题干:").pack(anchor="w")
        self.text_stem = tk.Text(frame_content, height=5, font=("Consolas", 10))
        self.text_stem.pack(fill="x", pady=2)
        
        self.opt_vars = []
        for char in ['A', 'B', 'C', 'D']:
            f_opt = tk.Frame(frame_content)
            f_opt.pack(fill="x", pady=2)
            tk.Label(f_opt, text=f"选项 {char}: ").pack(side="left")
            var = tk.StringVar()
            tk.Entry(f_opt, textvariable=var, font=("Consolas", 10)).pack(side="left", fill="x", expand=True)
            self.opt_vars.append(var)
            
        tk.Label(frame_content, text="正确答案:").pack(anchor="w", pady=(5,0))
        self.ans_var = tk.StringVar(value="A")
        tk.Entry(frame_content, textvariable=self.ans_var, font=("Consolas", 10)).pack(fill="x", pady=2)
        
        tk.Label(frame_content, text="深度解析:").pack(anchor="w")
        self.text_analysis = tk.Text(frame_content, height=6, font=("Consolas", 10))
        self.text_analysis.pack(fill="x", pady=2)

        # ================= 3. 动作操作区 =================
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=15)
        tk.Button(btn_frame, text="🗑️ 丢弃此题", command=self.discard_question, bg="#F44336", fg="white", font=("Microsoft YaHei", 11, "bold"), width=15).pack(side="left")
        tk.Button(btn_frame, text="✅ 审核 Pass，入库并看下一题", command=self.pass_question, bg="#4CAF50", fg="white", font=("Microsoft YaHei", 11, "bold")).pack(side="right", fill="x", expand=True, padx=(10, 0))

    def update_topics(self, event=None):
        chap = self.chap_var.get()
        topics = self.knowledge_tree.get(chap, [])
        self.cb_topic['values'] = topics
        if topics: self.cb_topic.current(0)
        else: self.cb_topic.set('')

    def start_batch_thread(self):
        pdf_path = filedialog.askopenfilename(title="选择章节 PDF", filetypes=[("PDF Files", "*.pdf")])
        if not pdf_path: return
        self.btn_load_pdf.config(text="AI 引擎轰鸣中...", state="disabled")
        threading.Thread(target=self.process_pdf, args=(pdf_path,), daemon=True).start()

    def process_pdf(self, pdf_path):
        try:
            selected_model = self.model_var.get()
            doc = fitz.open(pdf_path)
            total_extracted = 0
            
            prompt = """
            你是一个资深的中国高中数学教研专家。请精准识别这张 PDF 页面图片上的**所有数学题目及其对应的答案和解析**。
            要求：
            1. 每一道题提取为一个独立的 JSON 对象，按顺序放入数组中：[{"stem":"...", "options":["..."], "answer":"...", "analysis":"..."}]
            2. 智能切分：
               - 题干 (stem)：题目主体部分。
               - 选项 (options)：如果是选择题，提取A/B/C/D四个选项。如果是填空/解答题，返回 []。
               - 答案 (answer)：寻找“【答案】”、“故选”、“填”等关键字，提取最终结论。
               - 解析 (analysis)：寻找“【解析】”、“【解题思路】”、“【总结】”等关键字，提取完整的推理过程。
            3. 如果图片中某道题只有题干没有解析，则 answer 和 analysis 留空字符串 ""。
            4. 所有数学公式必须使用 LaTeX 格式，用 $ 包裹。
            5. 只输出纯 JSON 字符串，绝不要输出 ```json 或任何 markdown 标记。
            """

            for page_num in range(len(doc)):
                self.root.after(0, lambda p=page_num+1, t=len(doc): self.btn_load_pdf.config(text=f"扫页中 {p}/{t}..."))
                
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                
                result_text = ""
                
                # 路由选择器：决定把图片发给谁
                if "Gemini" in selected_model:
                    genai.configure(api_key=GEMINI_API_KEY)
                    engine_name = 'gemini-2.5-pro' if "Pro" in selected_model else 'gemini-2.5-flash'
                    model = genai.GenerativeModel(engine_name)
                    img = PIL.Image.open(io.BytesIO(img_bytes))
                    response = model.generate_content([prompt, img])
                    result_text = response.text.strip()
                    time.sleep(2) # 保护免费配额
                    
                elif "GPT" in selected_model:
                    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
                    engine_name = 'gpt-4o' if "gpt-4o" in selected_model.lower() and "mini" not in selected_model.lower() else 'gpt-4o-mini'
                    base64_image = base64.b64encode(img_bytes).decode('utf-8')
                    response = client.chat.completions.create(
                        model=engine_name,
                        messages=[
                            {"role": "user", "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                            ]}
                        ]
                    )
                    result_text = response.choices[0].message.content.strip()

                # 清洗结果
                result_text = re.sub(r'^```json\s*', '', result_text, flags=re.IGNORECASE)
                result_text = re.sub(r'\s*```$', '', result_text)
                
                try:
                    q_list = json.loads(result_text)
                    if isinstance(q_list, list) and len(q_list) > 0:
                        self.question_queue.extend(q_list)
                        total_extracted += len(q_list)
                        self.root.after(0, self.update_queue_ui)
                except Exception as json_e:
                    print(f"解析 JSON 失败: {json_e}")
                    continue
                    
            self.root.after(0, lambda: messagebox.showinfo("完成", f"共提取 {total_extracted} 题，已入列队！"))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("崩溃", f"发生错误：\n{msg}"))
        finally:
            self.root.after(0, lambda: self.btn_load_pdf.config(text="📂 丢入 PDF 开启流水线", state="normal"))

    # ... 以下 ui 刷新逻辑保持不变 ...
    def update_queue_ui(self):
        self.lbl_status.config(text=f"待审: {len(self.question_queue)} 题")
        if self.current_q is None and len(self.question_queue) > 0: self.load_next_question()

    def load_next_question(self):
        if len(self.question_queue) == 0:
            self.current_q = None
            self.clear_form()
            messagebox.showinfo("全部搞定", "待审队列已清空！")
            return
        self.current_q = self.question_queue.pop(0)
        self.lbl_status.config(text=f"待审: {len(self.question_queue)} 题")
        self.clear_form()
        self.text_stem.insert(tk.END, self.current_q.get("stem", ""))
        options = self.current_q.get("options", [])
        for i, var in enumerate(self.opt_vars):
            if i < len(options): var.set(options[i])
        self.ans_var.set(self.current_q.get("answer", ""))
        self.text_analysis.insert(tk.END, self.current_q.get("analysis", ""))

    def clear_form(self):
        self.text_stem.delete("1.0", tk.END)
        for var in self.opt_vars: var.set("")
        self.text_analysis.delete("1.0", tk.END)
        self.ans_var.set("")

    def discard_question(self):
        if self.current_q is None: return
        self.load_next_question()

    def pass_question(self):
        if self.current_q is None: return
        stem = self.text_stem.get("1.0", tk.END).strip()
        chap = self.chap_var.get()
        topic = self.topic_var.get()
        if not stem or not chap or not topic:
            messagebox.showwarning("拦截", "必须指定章节和题型！")
            return
        options = [v.get().strip() for v in self.opt_vars if v.get().strip()]
        new_q = {
            "id": f"Q_{uuid.uuid4().hex[:8].upper()}", "stem": stem, "options": options,
            "answer": self.ans_var.get(), "analysis": self.text_analysis.get("1.0", tk.END).strip(),
            "image": "[待补图片占位符]",
            "meta": { "score": 5, "difficulty": self.diff_var.get(), "chapter": chap, "knowledge_weights": { topic: 1.0 } }
        }
        db = []
        if os.path.exists(self.bank_file):
            try:
                with open(self.bank_file, 'r', encoding='utf-8') as f: db = json.load(f)
            except: pass
        db.append(new_q)
        with open(self.bank_file, 'w', encoding='utf-8') as f: json.dump(db, f, ensure_ascii=False, indent=4)
        self.load_next_question()

if __name__ == "__main__":
    root = tk.Tk()
    app = BatchAuditor(root)
    root.mainloop()