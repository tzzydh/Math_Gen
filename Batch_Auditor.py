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
import PIL.ImageTk
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
        self.preview_img_tk = None
        self.preview_dir = os.path.join("figures", "pdf_previews")
        os.makedirs(self.preview_dir, exist_ok=True)
        self.latex_preview_dir = os.path.join("figures", "latex_previews")
        os.makedirs(self.latex_preview_dir, exist_ok=True)
        self.latex_preview_img_tk = None
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

        # ================= 1.5 生成PDF效果预览区 =================
        frame_latex_preview = tk.LabelFrame(
            self.root,
            text="生成PDF效果预览（单题排版）",
            font=("Microsoft YaHei", 10, "bold"),
            padx=10,
            pady=5
        )
        frame_latex_preview.pack(fill="both", expand=False, padx=10, pady=5)

        self.preview_teacher_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame_latex_preview,
            text="教师解析版（显示【答案】【解析】）",
            variable=self.preview_teacher_var
        ).pack(anchor="w")

        btns = tk.Frame(frame_latex_preview)
        btns.pack(fill="x", pady=5)
        self.btn_preview_latex = tk.Button(
            btns,
            text="🔍 预览当前题在生成PDF中的样子",
            command=self.preview_current_question_in_pdf,
            bg="#607D8B",
            fg="white",
            font=("Microsoft YaHei", 10, "bold"),
            relief="flat"
        )
        self.btn_preview_latex.pack(side="left", padx=(0, 10))

        self.lbl_latex_status = tk.Label(frame_latex_preview, text="状态：未预览", font=("Microsoft YaHei", 10, "bold"), fg="#555555")
        self.lbl_latex_status.pack(anchor="w")

        self.latex_preview_label = tk.Label(frame_latex_preview, bg="white", anchor="center")
        self.latex_preview_label.pack(fill="both", expand=False, padx=5, pady=5)

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
                page_image = PIL.Image.open(io.BytesIO(img_bytes))
                preview_path = os.path.join(self.preview_dir, f"page_{page_num+1:04d}.png")
                try:
                    if not os.path.exists(preview_path):
                        page_image.save(preview_path)
                except Exception:
                    # 预览失败不影响主流程：只会导致界面里看不到截图
                    preview_path = None
                
                result_text = ""
                
                # 路由选择器：决定把图片发给谁
                if "Gemini" in selected_model:
                    genai.configure(api_key=GEMINI_API_KEY)
                    engine_name = 'gemini-2.5-pro' if "Pro" in selected_model else 'gemini-2.5-flash'
                    model = genai.GenerativeModel(engine_name)
                    response = model.generate_content([prompt, page_image])
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
                        # 内部为图片渲染准备：为每个题目挂上该页截图，便于在生成PDF中 includegraphics
                        for q in q_list:
                            if isinstance(q, dict):
                                if preview_path:
                                    q.setdefault("image_preview", preview_path)
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
        self.clear_latex_preview()

    def clear_form(self):
        self.text_stem.delete("1.0", tk.END)
        for var in self.opt_vars: var.set("")
        self.text_analysis.delete("1.0", tk.END)
        self.ans_var.set("")
        self.clear_latex_preview()

    def clear_latex_preview(self):
        self.lbl_latex_status.config(text="状态：未预览")
        self.latex_preview_label.config(image="")
        self.latex_preview_img_tk = None

    def get_question_from_ui(self):
        """从编辑区读取当前题内容，用于生成预览/入库。"""
        stem = self.text_stem.get("1.0", tk.END).strip()
        options = [v.get().strip() for v in self.opt_vars if v.get().strip()]
        answer = self.ans_var.get().strip()
        analysis = self.text_analysis.get("1.0", tk.END).strip()
        # 图片预览依赖 q['image']，这里用批处理阶段挂的该页截图（image_preview）
        img_path = self.current_q.get("image_preview") if isinstance(self.current_q, dict) else None
        return {
            "stem": stem,
            "options": options,
            "answer": answer,
            "analysis": analysis,
            "image": img_path,
        }

    def build_single_question_latex(self, q, show_answers=False):
        """构造单题 LaTeX，用于预览生成PDF的排版。"""
        diff_val = {"易": "0.8", "中": "0.6", "难": "0.3"}.get(self.diff_var.get(), self.diff_var.get())
        diff_tag = f"\\textbf{{[{diff_val}]}}" if diff_val else ""

        # 图片：只要存在就 includegraphics
        img_block = ""
        img_path = q.get("image")
        if img_path and os.path.exists(img_path) and "占位符" not in str(img_path):
            img_abs = os.path.abspath(img_path).replace("\\", "/")
            img_block = f"\\begin{{center}}\\includegraphics[width=0.45\\textwidth]{{{img_abs}}}\\end{{center}}\n\n"

        # 选项排版列数：复刻 math_app.py 的策略
        options = q.get("options") or []
        opts_block = ""
        if options:
            clean_opts = []
            max_len = 0
            for opt in options:
                cleaned = re.sub(r'^[A-D](?:\.|、|\\s+)?', '', opt).strip()
                clean_opts.append(cleaned)
                max_len = max(max_len, len(cleaned))
            cols = 1 if max_len > 35 else (2 if max_len > 12 else 4)
            opts_block = (
                f"\\begin{{tasks}}({cols})\n"
                + "".join([f"    \\task {o}\n" for o in clean_opts])
                + "\\end{tasks}\n\n"
            )

        # 解析/答案
        ans_block = ""
        if show_answers:
            ans_text = re.sub(r'^【?(答案|答)】?[:：\\s]*', '', q.get("answer", "")).strip()
            ana_text = re.sub(r'^【?(解析|解|分析)】?[:：\\s]*', '', q.get("analysis", "")).strip()
            ans_block = (
                f"\\par\\noindent\\textcolor{{red}}{{\\textbf{{【答案】}} {ans_text}}}\n"
                f"\\par\\noindent\\textcolor{{blue}}{{\\textbf{{【解析】}} {ana_text}}}\n\n"
            )

        latex_code = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{amsmath}}\\usepackage{{amssymb}}\\usepackage{{ctex}}
\\usepackage{{tasks}}\\usepackage{{xcolor}}\\usepackage{{graphicx}}
\\settasks{{label=\\Alph*., label-width=1.5em, item-indent=2em}}
\\begin{{document}}
\\vspace{{-0.5cm}}
\\section*{{单题预览}}

{diff_tag} {q.get('stem', '')}

{img_block}{opts_block}{ans_block}
\\end{{document}}
"""
        return latex_code

    def preview_current_question_in_pdf(self):
        """编译单题 LaTeX 并把渲染结果展示出来。"""
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

            # 编译：避免长时间卡住，失败会抛异常
            result = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "preview.tex"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=60
            )
            if result.returncode != 0:
                raise RuntimeError("xelatex 编译失败，请检查 LaTeX 环境。")

            pdf_path = os.path.join(work_dir, "preview.pdf")
            if not os.path.exists(pdf_path):
                raise RuntimeError("未生成 preview.pdf。")

            # 用 fitz 渲染为图片显示
            doc = fitz.open(pdf_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=160)
            png_path = os.path.join(work_dir, "preview.png")
            pix.save(png_path)
            doc.close()

            # 回到主线程更新 UI
            def _ui_update():
                try:
                    img = PIL.Image.open(png_path)
                    img.thumbnail((820, 260), PIL.Image.LANCZOS)
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
            "image": self.current_q.get("image_preview", "[待补图片占位符]"),
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