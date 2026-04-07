import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import uuid
import threading
import re
import time
import base64
import subprocess
import uuid as _uuid

# ==========================================
# 🚀 1. 代理与 API Key 集中配置区
# ==========================================
proxy_url = 'http://127.0.0.1:6789'
os.environ['http_proxy'] = proxy_url
os.environ['https_proxy'] = proxy_url
os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
os.environ['grpc_proxy'] = proxy_url
os.environ['GRPC_PROXY'] = proxy_url

GEMINI_API_KEY = "AIzaSyC7VcVn8l3D7Oo9W_bkIktFAwjXZs_9l4g"
OPENAI_API_KEY = "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"
OPENAI_BASE_URL = "https://api.openai.com/v1" 

import google.generativeai as genai
from openai import OpenAI
import fitz
import PIL.Image
import PIL.ImageTk
from PIL import ImageGrab 
import io

# 导入自动分类器
try:
    from auto_classify import MathClassifier
    AUTO_CLASSIFY_AVAILABLE = True
except ImportError:
    AUTO_CLASSIFY_AVAILABLE = False
    print("[警告] auto_classify.py 未找到，自动分类功能不可用")

class BatchAuditor:
    def __init__(self, root):
        self.root = root
        # 🌟 标志性标题，确保代码更新成功
        self.root.title("高三数学题库 - V7.3 智能自愈防崩版")
        self.root.geometry("900x980")
        
        self.bank_file = "bank_v2.json"
        self.tree_file = "knowledge_tree.json"
        self.knowledge_tree = self.load_tree()
        self.chapters = list(self.knowledge_tree.keys()) if self.knowledge_tree else ["未加载图谱"]
        
        self.question_queue = []
        self.current_q = None
        self.attached_image_path = "" 

        self.classifier = None
        if AUTO_CLASSIFY_AVAILABLE:
            try:
                self.classifier = MathClassifier(self.tree_file)
            except Exception:
                pass

        self.preview_dir = os.path.join("figures", "pdf_previews")
        self.latex_preview_dir = os.path.join("figures", "latex_previews")
        self.q_images_dir = os.path.join("figures", "q_images")
        os.makedirs(self.preview_dir, exist_ok=True)
        os.makedirs(self.latex_preview_dir, exist_ok=True)
        os.makedirs(self.q_images_dir, exist_ok=True)
        
        self.latex_preview_img_tk = None
        self.create_ui()

    def load_tree(self):
        if os.path.exists(self.tree_file):
            with open(self.tree_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    # 🔥 核心更新：去除导致崩溃的多余正则，加入智能容错
    def safe_parse_json(self, text):
        text = text.strip()
        text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 如果 AI 偶尔犯傻单转义了 LaTeX（比如写了 \pi），触发终极容错机制
            text = text.replace('\\', '\\\\')
            text = text.replace('\\\\"', '\\"')  # 恢复双引号转义
            text = text.replace('\\\\n', '\\n')  # 恢复换行符
            text = text.replace('\\\\t', '\\t')  # 恢复制表符
            try:
                return json.loads(text)
            except Exception as e:
                raise RuntimeError(f"解析 JSON 彻底失败: {e}\nAI返回的原始数据：\n{text[:200]}...")

    def create_ui(self):
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

        frame_clipboard = tk.LabelFrame(self.root, text="⚡ 快捷扩展：截图识别与贴图 (优先使用)", font=("Microsoft YaHei", 10, "bold"), fg="#E91E63", padx=10, pady=5)
        frame_clipboard.pack(fill="x", padx=10, pady=5)

        self.btn_clip_rec = tk.Button(frame_clipboard, text="📋 从剪贴板识别题目 (AI自动算答案)", command=self.start_clipboard_recognize_thread, bg="#2196F3", fg="white", font=("Microsoft YaHei", 9, "bold"))
        self.btn_clip_rec.pack(side="left", padx=5)

        self.btn_clip_img = tk.Button(frame_clipboard, text="🖼️ 截图作为本题配图", command=self.attach_image_from_clipboard, bg="#9C27B0", fg="white", font=("Microsoft YaHei", 9, "bold"))
        self.btn_clip_img.pack(side="left", padx=5)

        self.lbl_attached_img = tk.Label(frame_clipboard, text="当前配图: 无", fg="#888")
        self.lbl_attached_img.pack(side="left", padx=10)

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
        
        self.btn_reclassify = tk.Button(frame_meta, text="🤖 重新分类", command=self.reclassify_current, bg="#009688", fg="white", font=("Microsoft YaHei", 9, "bold"))
        self.btn_reclassify.grid(row=0, column=4, padx=5)

        tk.Label(frame_meta, text="具体题型:").grid(row=1, column=2, sticky="e", pady=5)
        self.topic_var = tk.StringVar()
        self.cb_topic = ttk.Combobox(frame_meta, textvariable=self.topic_var, width=35)
        self.cb_topic.grid(row=1, column=3, sticky="w", padx=5)

        self.lbl_confidence = tk.Label(frame_meta, text="AI 置信度: --", font=("Microsoft YaHei", 9, "bold"), fg="#999")
        self.lbl_confidence.grid(row=1, column=4, padx=5)

        frame_latex_preview = tk.LabelFrame(self.root, text="生成PDF效果预览（单题排版）", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=5)
        frame_latex_preview.pack(fill="x", expand=False, padx=10, pady=5)

        self.preview_teacher_var = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_latex_preview, text="教师解析版（显示【答案】【解析】）", variable=self.preview_teacher_var).pack(anchor="w")

        btns = tk.Frame(frame_latex_preview)
        btns.pack(fill="x", pady=5)
        self.btn_preview_latex = tk.Button(btns, text="🔍 预览当前题在生成PDF中的样子", command=self.preview_current_question_in_pdf, bg="#607D8B", fg="white", font=("Microsoft YaHei", 10, "bold"), relief="flat")
        self.btn_preview_latex.pack(side="left", padx=(0, 10))

        self.lbl_latex_status = tk.Label(frame_latex_preview, text="状态：未预览", font=("Microsoft YaHei", 10, "bold"), fg="#555555")
        self.lbl_latex_status.pack(anchor="w")

        self.latex_preview_label = tk.Label(frame_latex_preview, bg="white", anchor="center")
        self.latex_preview_label.pack(fill="both", expand=False, padx=5, pady=5)

        frame_content = tk.LabelFrame(self.root, text="第二步：AI 识别内容核对 (可直接修改)", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=5)
        frame_content.pack(fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(frame_content, text="题干:").pack(anchor="w")
        self.text_stem = tk.Text(frame_content, height=4, font=("Consolas", 10))
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
        self.ans_var = tk.StringVar(value="")
        tk.Entry(frame_content, textvariable=self.ans_var, font=("Consolas", 10)).pack(fill="x", pady=2)
        
        tk.Label(frame_content, text="深度解析:").pack(anchor="w")
        self.text_analysis = tk.Text(frame_content, height=5, font=("Consolas", 10))
        self.text_analysis.pack(fill="x", pady=2)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="🗑️ 丢弃此题", command=self.discard_question, bg="#F44336", fg="white", font=("Microsoft YaHei", 11, "bold"), width=15).pack(side="left")
        tk.Button(btn_frame, text="✅ 审核 Pass，入库并看下一题", command=self.pass_question, bg="#4CAF50", fg="white", font=("Microsoft YaHei", 11, "bold")).pack(side="right", fill="x", expand=True, padx=(10, 0))

    def attach_image_from_clipboard(self):
        try:
            img = ImageGrab.grabclipboard()
            if img is None:
                messagebox.showwarning("提示", "剪贴板中没有图片，请先截图再点击！")
                return
            
            if isinstance(img, list):
                img = PIL.Image.open(img[0])

            filename = f"fig_{_uuid.uuid4().hex[:8].upper()}.png"
            filepath = os.path.join(self.q_images_dir, filename)
            img.save(filepath)
            
            self.attached_image_path = filepath
            self.lbl_attached_img.config(text=f"当前配图: {filename}", fg="blue")
            messagebox.showinfo("成功", "配图已成功挂载！点击预览看看排版效果吧。")
            self.reclassify_current()

        except Exception as e:
            messagebox.showerror("错误", f"提取配图失败：\n{e}")

    def start_clipboard_recognize_thread(self):
        img = ImageGrab.grabclipboard()
        if img is None:
            messagebox.showwarning("提示", "剪贴板中没有图片！请先对准一道数学题截图，再点击此按钮。")
            return
        
        self.btn_clip_rec.config(text="🤖 AI 疯狂算题中...", state="disabled")
        threading.Thread(target=self._process_clipboard_image, args=(img,), daemon=True).start()

    def _process_clipboard_image(self, img):
        try:
            if isinstance(img, list): img = PIL.Image.open(img[0])
            
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_bytes = buffered.getvalue()
            base64_image = base64.b64encode(img_bytes).decode('utf-8')

            # 🔥 加入严厉警告，防止 AI 生成非法的 JSON 转义符
            prompt = """
            你是一个资深的中国高中数学教研专家。请精准识别这张图片上的数学题目。
            要求：
            1. 必须输出严格的 JSON 对象：{"questions": [{"stem":"题干", "options":["A","B","C","D"], "answer":"正确答案", "analysis":"完整解析"}]}
            2. 如果是解答题，options 数组保留为空 []。
            3. 💥【核心指令】：如果图片中只有题目而没有答案和解析，你必须亲自解答这道题！将答案填入 "answer"，详细推导过程填入 "analysis"。
            4. 💥【格式警告】：公式必须使用 LaTeX 格式用 $ 包裹。特别注意：在 JSON 字符串中，所有的 LaTeX 反斜杠必须双重转义，例如必须写成 \\frac 而不能是 \frac，必须写成 \\pi 而不能是 \pi！
            """

            selected_model = self.model_var.get()
            q_list = []
            raw_text = ""

            if "Gemini" in selected_model:
                genai.configure(api_key=GEMINI_API_KEY)
                engine_name = 'gemini-2.5-pro' if "Pro" in selected_model else 'gemini-2.5-flash'
                model = genai.GenerativeModel(engine_name, generation_config={"response_mime_type": "application/json"})
                response = model.generate_content([prompt, img])
                raw_text = response.text

            elif "GPT" in selected_model:
                openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
                engine_name = 'gpt-4o' if "mini" not in selected_model.lower() else 'gpt-4o-mini'
                response = openai_client.chat.completions.create(
                    model=engine_name,
                    response_format={ "type": "json_object" },
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]}]
                )
                raw_text = response.choices[0].message.content

            data = self.safe_parse_json(raw_text)
            q_list = data.get("questions", [])

            if q_list:
                self.question_queue.insert(0, q_list[0])
                self.root.after(0, self.update_queue_ui)
                self.root.after(0, lambda: messagebox.showinfo("算题完毕", "AI 已经成功提取并给出了它的解答，请核对！"))
            else:
                self.root.after(0, lambda: messagebox.showwarning("失败", "AI 未能识别出题目。"))

        except Exception as e:
            self.root.after(0, lambda msg=str(e): messagebox.showerror("崩溃", f"发生错误：\n{msg}"))
        finally:
            self.root.after(0, lambda: self.btn_clip_rec.config(text="📋 从剪贴板识别题目 (AI自动算答案)", state="normal"))

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
            from concurrent.futures import ThreadPoolExecutor, as_completed

            selected_model = self.model_var.get()
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            pages_data = [(i, doc.load_page(i).get_pixmap(dpi=120).tobytes("png"), None) for i in range(total_pages)]
            doc.close()

            prompt = """
            你是一个资深的高中数学专家。请精准识别图片上的数学题目。
            输出 JSON：{"questions": [{"stem":"...", "options":["A"], "answer":"...", "analysis":"..."}]}
            公式必须用 LaTeX，用 $ 包裹。特别注意：在 JSON 中所有的反斜杠必须双转义，如 \\frac。
            """

            genai.configure(api_key=GEMINI_API_KEY)
            openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

            def process_one_page(args):
                page_num, img_bytes, _ = args
                for attempt in range(3):
                    try:
                        page_image = PIL.Image.open(io.BytesIO(img_bytes))
                        raw_text = ""

                        if "Gemini" in selected_model:
                            engine_name = 'gemini-2.5-pro' if "Pro" in selected_model else 'gemini-2.5-flash'
                            model = genai.GenerativeModel(engine_name, generation_config={"response_mime_type": "application/json"})
                            response = model.generate_content([prompt, page_image])
                            raw_text = response.text
                            if "Flash" in selected_model: time.sleep(4)

                        elif "GPT" in selected_model:
                            engine_name = 'gpt-4o' if "mini" not in selected_model.lower() else 'gpt-4o-mini'
                            base64_img = base64.b64encode(img_bytes).decode('utf-8')
                            response = openai_client.chat.completions.create(
                                model=engine_name,
                                response_format={ "type": "json_object" },
                                messages=[{"role": "user", "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
                                ]}]
                            )
                            raw_text = response.choices[0].message.content

                        data = self.safe_parse_json(raw_text)
                        return page_num, data.get("questions", [])
                    except Exception:
                        if attempt == 2: return page_num, []
                        time.sleep(5)
                return page_num, []

            max_workers = 1 if "Gemini" in selected_model else 3
            total_extracted = completed = 0

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_page = {executor.submit(process_one_page, p): p[0] for p in pages_data}
                for future in as_completed(future_to_page):
                    page_num, q_list = future.result()
                    completed += 1
                    self.root.after(0, lambda c=completed, t=total_pages: self.btn_load_pdf.config(text=f"提取中 {c}/{t} 页..."))
                    if q_list:
                        self.question_queue.extend(q_list)
                        total_extracted += len(q_list)
                        self.root.after(0, self.update_queue_ui)

            self.root.after(0, lambda: messagebox.showinfo("完成", f"提取 {total_extracted} 题，已入列队！"))

        except Exception as e:
            self.root.after(0, lambda msg=str(e): messagebox.showerror("崩溃", f"发生致命错误：\n{msg}"))
        finally:
            self.root.after(0, lambda: self.btn_load_pdf.config(text="📂 丢入 PDF 开启流水线", state="normal"))

    def update_queue_ui(self):
        self.lbl_status.config(text=f"待审: {len(self.question_queue)} 题")
        if self.current_q is None and len(self.question_queue) > 0: self.load_next_question()

    def auto_classify_question(self, q_dict):
        if not self.classifier: return None, None, 0.0
        try:
            result = self.classifier.classify_question(q_dict)
            chapter = result.get("chapter", "")
            weights = result.get("knowledge_weights", {})
            confidence = result.get("confidence", 0.0)
            topic = max(weights, key=weights.get) if weights else ""
            return chapter, topic, confidence
        except: return None, None, 0.0

    def reclassify_current(self):
        q = self.get_question_from_ui()
        if not q["stem"]: return
        chapter, topic, confidence = self.auto_classify_question(q)
        if chapter and chapter in self.chapters:
            self.chap_var.set(chapter)
            self.update_topics()
            if topic: self.topic_var.set(topic)
            pct = int(confidence * 100)
            color = "#4CAF50" if pct >= 70 else ("#FF9800" if pct >= 40 else "#F44336")
            self.lbl_confidence.config(text=f"AI 置信度: {pct}%", fg=color)
        else:
            self.lbl_confidence.config(text="AI 置信度: 未匹配", fg="#F44336")

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

        chapter, topic, confidence = self.auto_classify_question(self.current_q)
        if chapter and chapter in self.chapters:
            self.chap_var.set(chapter)
            self.update_topics() 
            if topic: self.topic_var.set(topic)
            pct = int(confidence * 100)
            color = "#4CAF50" if pct >= 70 else ("#FF9800" if pct >= 40 else "#F44336")
            self.lbl_confidence.config(text=f"AI 置信度: {pct}%", fg=color)
        else:
            self.lbl_confidence.config(text="AI 置信度: --", fg="#999")

    def clear_form(self):
        self.text_stem.delete("1.0", tk.END)
        for var in self.opt_vars: var.set("")
        self.text_analysis.delete("1.0", tk.END)
        self.ans_var.set("")
        self.clear_latex_preview()
        self.attached_image_path = ""
        self.lbl_attached_img.config(text="当前配图: 无", fg="#888")

    def clear_latex_preview(self):
        self.lbl_latex_status.config(text="状态：未预览")
        self.latex_preview_label.config(image="")
        self.latex_preview_img_tk = None

    def get_question_from_ui(self):
        stem = self.text_stem.get("1.0", tk.END).strip()
        options = [v.get().strip() for v in self.opt_vars if v.get().strip()]
        answer = self.ans_var.get().strip()
        analysis = self.text_analysis.get("1.0", tk.END).strip()
        return {
            "stem": stem,
            "options": options,
            "answer": answer,
            "analysis": analysis,
            "image": self.attached_image_path if self.attached_image_path else "", 
        }

    def build_single_question_latex(self, q, show_answers=False):
        diff_val = {"易": "0.8", "中": "0.6", "难": "0.3"}.get(self.diff_var.get(), self.diff_var.get())
        diff_tag = f"\\textbf{{[{diff_val}]}}" if diff_val else ""

        img_block = ""
        img_path = q.get("image")
        if img_path and os.path.exists(img_path):
            img_abs = os.path.abspath(img_path).replace("\\", "/")
            img_block = f"\\begin{{center}}\\includegraphics[width=0.45\\textwidth]{{{img_abs}}}\\end{{center}}\n\n"

        options = q.get("options") or []
        opts_block = ""
        if options:
            clean_opts = []
            max_len = 0
            for opt in options:
                cleaned = re.sub(r'^[A-D](?:\.|、|\s+)?', '', opt).strip()
                clean_opts.append(cleaned)
                max_len = max(max_len, len(cleaned))
            cols = 1 if max_len > 35 else (2 if max_len > 12 else 4)
            opts_block = (
                f"\\begin{{tasks}}({cols})\n"
                + "".join([f"    \\task {o}\n" for o in clean_opts])
                + "\\end{tasks}\n\n"
            )

        ans_block = ""
        if show_answers:
            ans_text = re.sub(r'^【?(答案|答)】?[:：\s]*', '', q.get("answer", "")).strip()
            ana_text = re.sub(r'^【?(解析|解|分析)】?[:：\s]*', '', q.get("analysis", "")).strip()
            ans_block = (
                f"\\vspace{{0.2cm}}\\par\\noindent\\textcolor{{red}}{{\\textbf{{【答案】}} {ans_text}}}\n"
                f"\\par\\noindent\\textcolor{{blue}}{{\\textbf{{【解析】}} {ana_text}}}\n\n"
            )

        latex_code = f"""\\documentclass[varwidth=16cm, border=2mm]{{standalone}}
\\usepackage{{amsmath}}\\usepackage{{amssymb}}\\usepackage{{ctex}}
\\usepackage{{tasks}}\\usepackage{{xcolor}}\\usepackage{{graphicx}}
\\settasks{{label=\\Alph*., label-width=1.5em, item-indent=2em}}
\\begin{{document}}
{diff_tag} {q.get('stem', '')}

{img_block}{opts_block}{ans_block}
\\end{{document}}
"""
        return latex_code

    def preview_current_question_in_pdf(self):
        q = self.get_question_from_ui()
        if not q["stem"] and not q["options"]:
            messagebox.showwarning("预览失败", "题干为空，先填写后再预览。")
            return

        self.btn_preview_latex.config(state="disabled")
        self.lbl_latex_status.config(text="状态：正在编译预览中...")
        show_answers = bool(self.preview_teacher_var.get())

        threading.Thread(
            target=self._render_latex_preview_thread,
            args=(q, show_answers),
            daemon=True
        ).start()

    def _render_latex_preview_thread(self, q, show_answers):
        try:
            latex_code = self.build_single_question_latex(q, show_answers=show_answers)
            run_id = _uuid.uuid4().hex[:10].upper()
            work_dir = os.path.join(self.latex_preview_dir, f"run_{run_id}")
            os.makedirs(work_dir, exist_ok=True)

            tex_file = os.path.join(work_dir, "preview.tex")
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(latex_code)

            result = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "preview.tex"],
                cwd=work_dir, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=60
            )
            
            if result.returncode != 0:
                err_msg = "未知语法错误"
                log_path = os.path.join(work_dir, "preview.log")
                if os.path.exists(log_path):
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            if line.startswith("!"):
                                err_msg = "".join(lines[i:i+4]).strip()
                                break
                raise RuntimeError(f"LaTeX 语法错误！\n请检查是否有未转义的 %, &, 或缺失的 $。\n\n【底层报错抓取】:\n{err_msg}")

            pdf_path = os.path.join(work_dir, "preview.pdf")
            if not os.path.exists(pdf_path): raise RuntimeError("未生成 preview.pdf。")

            doc = fitz.open(pdf_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=160)
            png_path = os.path.join(work_dir, "preview.png")
            pix.save(png_path)
            doc.close()

            def _ui_update():
                try:
                    img = PIL.Image.open(png_path)
                    img.thumbnail((820, 450), PIL.Image.LANCZOS)
                    self.latex_preview_img_tk = PIL.ImageTk.PhotoImage(img)
                    self.latex_preview_label.config(image=self.latex_preview_img_tk)
                    self.lbl_latex_status.config(text="状态：预览完成")
                except Exception:
                    self.lbl_latex_status.config(text="状态：预览渲染失败")
                finally:
                    self.btn_preview_latex.config(state="normal")

            self.root.after(0, _ui_update)

        except Exception as e:
            err = str(e)
            def _ui_err():
                self.lbl_latex_status.config(text="状态：预览失败")
                self.btn_preview_latex.config(state="normal")
                messagebox.showerror("预览失败", f"发生错误：\n{err}")
            self.root.after(0, _ui_err)

    def discard_question(self):
        if self.current_q is None: return
        self.load_next_question()

    def pass_question(self):
        if self.current_q is None: return
        
        q = self.get_question_from_ui() 
        chap = self.chap_var.get()
        topic = self.topic_var.get()
        
        if not q["stem"] or not chap or not topic:
            messagebox.showwarning("拦截", "必须指定章节、题型并包含题干！")
            return
            
        new_q = {
            "id": f"Q_{uuid.uuid4().hex[:8].upper()}", 
            "stem": q["stem"], 
            "options": q["options"],
            "answer": q["answer"], 
            "analysis": q["analysis"],
            "image": q["image"], 
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