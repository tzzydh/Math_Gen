import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import uuid
import threading

from core.settings import settings

import google.generativeai as genai
import PIL.Image

if settings.proxy_url:
    os.environ['http_proxy'] = settings.proxy_url
    os.environ['https_proxy'] = settings.proxy_url
    os.environ['HTTP_PROXY'] = settings.proxy_url
    os.environ['HTTPS_PROXY'] = settings.proxy_url
    os.environ['grpc_proxy'] = settings.proxy_url
    os.environ['GRPC_PROXY'] = settings.proxy_url


class QuestionRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("高三数学题库 - AI 视觉极速录入中心 V4.0")
        self.root.geometry("850x900")
        
        self.bank_file = "bank_v2.json"
        self.tree_file = "knowledge_tree.json"
        
        self.knowledge_tree = self.load_tree()
        self.chapters = list(self.knowledge_tree.keys()) if self.knowledge_tree else ["未加载图谱"]
        
        self.create_ui()

    def load_tree(self):
        if os.path.exists(self.tree_file):
            with open(self.tree_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def create_ui(self):
        # ================== 0. AI 配置区 ==================
        frame_ai = tk.LabelFrame(self.root, text="第零步：AI 视觉引擎配置", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=5, fg="blue")
        frame_ai.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame_ai, text="Gemini API Key:").pack(side="left")
        self.api_key_var = tk.StringVar(value=settings.gemini_api_key)
        tk.Entry(frame_ai, textvariable=self.api_key_var, width=40, show="*").pack(side="left", padx=5)
        
        self.btn_ai = tk.Button(frame_ai, text="📸 传图并呼叫 AI 自动填表", bg="#2196F3", fg="white", font=("Microsoft YaHei", 10, "bold"), command=self.run_ai_thread)
        self.btn_ai.pack(side="right", fill="x", expand=True, padx=5)

        # ================== 1. 标签与属性区 ==================
        frame_meta = tk.LabelFrame(self.root, text="第一步：题目属性与考点挂载", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        frame_meta.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame_meta, text="难度:").grid(row=0, column=0, sticky="e", pady=5)
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

        tk.Label(frame_meta, text="配图路径:").grid(row=1, column=0, sticky="e", pady=5)
        self.img_var = tk.StringVar()
        tk.Entry(frame_meta, textvariable=self.img_var, width=15).grid(row=1, column=1, sticky="w", padx=5)

        # ================== 2. 题干与选项区 ==================
        frame_content = tk.LabelFrame(self.root, text="第二步：题目内容核对 (支持 LaTeX)", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        frame_content.pack(fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(frame_content, text="题干:").pack(anchor="w")
        self.text_stem = tk.Text(frame_content, height=4, font=("Consolas", 10))
        self.text_stem.pack(fill="x", pady=2)
        
        self.opt_vars = []
        for i, char in enumerate(['A', 'B', 'C', 'D']):
            f_opt = tk.Frame(frame_content)
            f_opt.pack(fill="x", pady=2)
            tk.Label(f_opt, text=f"选项 {char}: ").pack(side="left")
            var = tk.StringVar()
            tk.Entry(f_opt, textvariable=var, font=("Consolas", 10)).pack(side="left", fill="x", expand=True)
            self.opt_vars.append(var)

        # ================== 3. 解析与答案区 ==================
        frame_ans = tk.LabelFrame(self.root, text="第三步：答案与解析", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        frame_ans.pack(fill="both", expand=True, padx=10, pady=5)
        
        tk.Label(frame_ans, text="正确答案:").pack(anchor="w")
        self.ans_var = tk.StringVar(value="A")
        ttk.Combobox(frame_ans, textvariable=self.ans_var, values=["A", "B", "C", "D"], width=5).pack(anchor="w", pady=2)
        
        tk.Label(frame_ans, text="深度解析:").pack(anchor="w")
        self.text_analysis = tk.Text(frame_ans, height=5, font=("Consolas", 10))
        self.text_analysis.pack(fill="x", pady=2)

        # ================== 4. 动作区 ==================
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="🧹 清空面板", command=self.clear_form, width=15).pack(side="left")
        tk.Button(btn_frame, text="💾 确认无误，存入 JSON 题库", command=self.save_to_json, bg="#4CAF50", fg="white", font=("Microsoft YaHei", 11, "bold")).pack(side="right", fill="x", expand=True, padx=(10, 0))

    def update_topics(self, event=None):
        chap = self.chap_var.get()
        topics = self.knowledge_tree.get(chap, [])
        self.cb_topic['values'] = topics
        if topics:
            self.cb_topic.current(0)
        else:
            self.cb_topic.set('')

    def clear_form(self):
        self.text_stem.delete("1.0", tk.END)
        for var in self.opt_vars: var.set("")
        self.text_analysis.delete("1.0", tk.END)
        self.img_var.set("")
        self.ans_var.set("A")

    def run_ai_thread(self):
        api_key = self.api_key_var.get().strip() or settings.gemini_api_key
        if not api_key:
            messagebox.showwarning("缺少 API Key", "请先在上方输入 API Key，或设置环境变量 GEMINI_API_KEY！")
            return
            
        file_path = filedialog.askopenfilename(title="选择题目图片", filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if not file_path:
            return

        self.btn_ai.config(text="AI 正在疯狂燃烧算力中，请稍候...", state="disabled")
        
        # 使用多线程防止 UI 卡死
        threading.Thread(target=self.call_ai_vision, args=(api_key, file_path), daemon=True).start()

    def call_ai_vision(self, api_key, img_path):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            img = PIL.Image.open(img_path)
            
            prompt = """
            你是一个资深的高中数学教研专家。请识别这张图片中的数学题目，并严格按照以下 JSON 格式输出结果。
            要求：
            1. 数学公式必须使用 LaTeX 格式，且被 $ 符号包裹。
            2. 不要输出任何 markdown 标记（如 ```json），直接输出纯 JSON 字符串。
            3. 格式必须包含：
            {
                "stem": "题干内容",
                "options": ["A选项", "B选项", "C选项", "D选项"],
                "answer": "A/B/C/D",
                "analysis": "解题步骤"
            }
            """
            
            response = model.generate_content([prompt, img])
            result_text = response.text.strip()
            
            # 清理可能存在的 markdown 标记
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            data = json.loads(result_text.strip())
            
            # 回到主线程更新 UI
            self.root.after(0, self.fill_ui_from_ai, data)
            
        except Exception as e:
            # 【修复点】：提前把错误信息转成字符串存下来，防止被 Python 内存回收
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("AI 识别失败", f"错误详情：\n{msg}"))
        finally:
            self.root.after(0, lambda: self.btn_ai.config(text="📸 传图并呼叫 AI 自动填表", state="normal"))

    def fill_ui_from_ai(self, data):
        self.clear_form()
        self.text_stem.insert(tk.END, data.get("stem", ""))
        
        options = data.get("options", [])
        for i, var in enumerate(self.opt_vars):
            if i < len(options):
                var.set(options[i])
                
        self.ans_var.set(data.get("answer", "A"))
        self.text_analysis.insert(tk.END, data.get("analysis", ""))
        messagebox.showinfo("AI 识别完成", "AI 已为您填写完毕，请人工核对 LaTeX 格式是否有误，补充考点后即可入库！")

    def save_to_json(self):
        stem = self.text_stem.get("1.0", tk.END).strip()
        chap = self.chap_var.get()
        topic = self.topic_var.get()
        
        if not stem or not chap or not topic:
            messagebox.showwarning("校验失败", "题干、大章节、具体题型为必填项！")
            return
            
        options = [v.get().strip() for v in self.opt_vars if v.get().strip()]
        
        new_q = {
            "id": f"Q_{uuid.uuid4().hex[:8].upper()}",
            "stem": stem,
            "options": options,
            "answer": self.ans_var.get(),
            "analysis": self.text_analysis.get("1.0", tk.END).strip(),
            "meta": {
                "score": 5,
                "difficulty": self.diff_var.get(),
                "chapter": chap,
                "knowledge_weights": {
                    topic: 1.0
                }
            }
        }
        
        img_path = self.img_var.get().strip()
        if img_path: new_q["image"] = img_path

        db = []
        if os.path.exists(self.bank_file):
            try:
                with open(self.bank_file, 'r', encoding='utf-8') as f:
                    db = json.load(f)
            except: pass
            
        db.append(new_q)
        with open(self.bank_file, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
            
        messagebox.showinfo("成功", f"题目已成功入库！当前题库总题数：{len(db)}")
        self.clear_form()

if __name__ == "__main__":
    root = tk.Tk()
    app = QuestionRecorder(root)
    root.mainloop()
