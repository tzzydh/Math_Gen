import json
import subprocess
import os
import random
import re
import tkinter as tk
from tkinter import ttk, messagebox

# ==========================================
# 1. 双核题库与图谱读取器 (保持不变)
# ==========================================
class QuestionBank:
    def __init__(self, bank_file="bank_v2.json", tree_file="knowledge_tree.json"):
        self.bank_file = bank_file
        self.tree_file = tree_file
        self.db = []
        self.tree = {}
        self.load_data()
            
    def load_data(self):
        msg = ""
        if os.path.exists(self.bank_file):
            try:
                with open(self.bank_file, 'r', encoding='utf-8') as f:
                    self.db = json.load(f)
                msg += f"题库({len(self.db)}题) "
            except: msg += f"题库加载失败! "
        else: msg += "未找到题库! "

        if os.path.exists(self.tree_file):
            try:
                with open(self.tree_file, 'r', encoding='utf-8') as f:
                    self.tree = json.load(f)
                msg += f"图谱({len(self.tree)}章) "
            except: msg += "图谱加载失败! "
        else: msg += "未找到图谱! "
        return msg

    def filter_paper(self, selected_chapters, selected_topics):
        selected_questions = []
        for q in self.db:
            meta = q.get("meta", {})
            q_chap = meta.get("chapter", "")
            q_topics = list(meta.get("knowledge_weights", {}).keys())
            
            if q_chap in selected_chapters:
                selected_questions.append(q)
                continue
            if any(t in selected_topics for t in q_topics):
                selected_questions.append(q)
                continue
        return selected_questions

# ==========================================
# 2. 试卷排版引擎 (保持不变)
# ==========================================
class PaperGenerator:
    @staticmethod
    def generate_pdf(questions, paper_title="高三数学诊断测试卷", output_name="Paper", show_answers=False):
        if not questions: return False
        
        latex_code = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{amsmath}}\\usepackage{{amssymb}}\\usepackage{{ctex}}
\\usepackage{{tasks}}\\usepackage{{xcolor}}\\usepackage{{graphicx}}
\\settasks{{label=\\Alph*., label-width=1.5em, item-indent=2em}}

\\title{{\\vspace{{-2cm}}\\textbf{{{paper_title}}}}}
\\date{{}}
\\begin{{document}}
\\maketitle
\\vspace{{-1cm}}
\\section*{{一、 单项选择题}}
"""
        for idx, q in enumerate(questions, 1):
            diff_raw = q.get("meta", {}).get("difficulty", "")
            diff_val = {"易": "0.8", "中": "0.6", "难": "0.3"}.get(diff_raw, diff_raw) 
            diff_tag = f"\\textbf{{[{diff_val}]}}" if diff_val else ""
            
            latex_code += f"{idx}. {diff_tag} {q['stem']}\n\n"
            
            if "image" in q and q["image"] and "占位符" not in q["image"]:
                if os.path.exists(q["image"]):
                    latex_code += f"\\begin{{center}}\\includegraphics[width=0.45\\textwidth]{{{q['image']}}}\\end{{center}}\n\n"
                else:
                    latex_code += f"\\par\\noindent\\textcolor{{gray}}{{（配图缺失）}}\n\n"
            
            if q.get("options"):
                clean_opts = []
                max_len = 0
                for opt in q["options"]:
                    cleaned = re.sub(r'^[A-D](?:\.|、|\s+)?', '', opt).strip()
                    clean_opts.append(cleaned)
                    max_len = max(max_len, len(cleaned))
                
                cols = 1 if max_len > 35 else (2 if max_len > 12 else 4)
                latex_code += f"\\begin{{tasks}}({cols})\n" + "".join([f"    \\task {o}\n" for o in clean_opts]) + "\\end{tasks}\n\n"

            if show_answers:
                ans_text = re.sub(r'^【?(答案|答)】?[:：\s]*', '', q.get('answer', '')).strip()
                ana_text = re.sub(r'^【?(解析|解|分析)】?[:：\s]*', '', q.get('analysis', '')).strip()
                ana_text = re.sub(r'^【?(解析|解|分析)】?[:：\s]*', '', ana_text).strip() 
                latex_code += f"\\par\\noindent\\textcolor{{red}}{{\\textbf{{【答案】}} {ans_text}}}\n"
                latex_code += f"\\par\\noindent\\textcolor{{blue}}{{\\textbf{{【解析】}} {ana_text}}}\n\n"
            
            latex_code += f"\\vspace{{{'0.5cm' if show_answers else '2.5cm'}}}\n\n"

        latex_code += "\\end{document}"
        tex_file = f"{output_name}.tex"
        with open(tex_file, 'w', encoding='utf-8') as f: f.write(latex_code)
        
        try:
            result = subprocess.run(['xelatex', '-interaction=nonstopmode', tex_file], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=60)
            return result.returncode == 0
        except Exception as e: return False

# ==========================================
# 3. 现代化 GUI 用户界面
# ==========================================
class MathApp:
    def __init__(self, root):
        self.root = root
        self.root.title("高三数学智能教研平台 V3.5")
        self.root.geometry("1000x700") # 改用宽屏比例
        self.root.configure(bg="#F8F9FA") # 现代化的浅灰背景色
        
        self.bank = QuestionBank('bank_v2.json', 'knowledge_tree.json')
        self.setup_styles()
        self.create_ui()
        
        msg = self.bank.load_data()
        self.refresh_ui_tree()
        self.log(f"[*] 引擎启动成功！加载状态: {msg}")

    def setup_styles(self):
        """配置全局 UI 样式，去掉老旧的 3D 边框"""
        style = ttk.Style()
        style.theme_use('clam') # 使用更平面的现代主题
        style.configure("TLabel", background="#F8F9FA", font=("Microsoft YaHei", 10))
        style.configure("TCheckbutton", background="#F8F9FA", font=("Microsoft YaHei", 10))
        style.configure("TFrame", background="#F8F9FA")
        style.configure("TLabelframe", background="#F8F9FA", font=("Microsoft YaHei", 10, "bold"))
        style.configure("TLabelframe.Label", background="#F8F9FA", foreground="#333333")
        # 美化 Treeview
        style.configure("Treeview", font=("Microsoft YaHei", 10), rowheight=28, borderwidth=0)
        style.map("Treeview", background=[("selected", "#0078D7")], foreground=[("selected", "white")])

    def create_ui(self):
        # 顶部导航栏
        header = tk.Frame(self.root, bg="#FFFFFF", height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(header, text=" 🎯 智能自适应组卷控制台", font=("Microsoft YaHei", 16, "bold"), bg="#FFFFFF", fg="#2C3E50").pack(side="left", padx=15, pady=15)
        tk.Button(header, text="🔄 刷新题库", command=self.reload_db, font=("Microsoft YaHei", 10), bg="#E0E0E0", relief="flat", padx=10).pack(side="right", padx=20, pady=15)

        # 核心内容区：左右分栏布局
        main_content = tk.Frame(self.root, bg="#F8F9FA")
        main_content.pack(fill="both", expand=True, padx=20, pady=15)

        # ==================== 左侧：知识树与搜索区 ====================
        left_panel = tk.Frame(main_content, bg="#F8F9FA")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # 搜索框
        search_frame = tk.Frame(left_panel, bg="#F8F9FA")
        search_frame.pack(fill="x", pady=(0, 10))
        tk.Label(search_frame, text="🔍 快速检索考点:", font=("Microsoft YaHei", 10, "bold")).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_tree) # 绑定输入事件，实时搜索
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Microsoft YaHei", 11), relief="solid", bd=1)
        search_entry.pack(side="left", fill="x", expand=True, padx=(10, 0), ipady=3)

        # 知识树
        tree_frame = tk.Frame(left_panel, bg="white", highlightbackground="#DDDDDD", highlightthickness=1)
        tree_frame.pack(fill="both", expand=True)
        
        scrollbar_y = ttk.Scrollbar(tree_frame)
        scrollbar_y.pack(side="right", fill="y")
        self.tree = ttk.Treeview(tree_frame, selectmode="extended", yscrollcommand=scrollbar_y.set, show="tree")
        self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar_y.config(command=self.tree.yview)

        # ==================== 右侧：配置与生成区 ====================
        right_panel = tk.Frame(main_content, bg="#F8F9FA", width=400)
        right_panel.pack(side="right", fill="y", padx=(10, 0))
        right_panel.pack_propagate(False) # 固定右侧宽度

        # 1. 试卷属性卡片
        frame_prop = ttk.LabelFrame(right_panel, text=" 试卷属性配置 ")
        frame_prop.pack(fill="x", pady=(0, 15), ipady=5)
        
        tk.Label(frame_prop, text="主标题:").grid(row=0, column=0, sticky="e", padx=10, pady=10)
        self.title_var = tk.StringVar(value="高三数学自适应诊断测试卷")
        tk.Entry(frame_prop, textvariable=self.title_var, font=("Microsoft YaHei", 10), width=28, relief="solid", bd=1).grid(row=0, column=1, sticky="w")
        
        tk.Label(frame_prop, text="文件名:").grid(row=1, column=0, sticky="e", padx=10, pady=5)
        self.filename_var = tk.StringVar(value="Math_Exam")
        tk.Entry(frame_prop, textvariable=self.filename_var, font=("Microsoft YaHei", 10), width=28, relief="solid", bd=1).grid(row=1, column=1, sticky="w")
        
        # 2. 导出类型卡片
        frame_type = ttk.LabelFrame(right_panel, text=" 导出版本 ")
        frame_type.pack(fill="x", pady=(0, 15), ipady=5)
        self.gen_student_var = tk.BooleanVar(value=True)  
        self.gen_teacher_var = tk.BooleanVar(value=True)  
        ttk.Checkbutton(frame_type, text="学生纯净版 (留白草稿区)", variable=self.gen_student_var).pack(anchor="w", padx=15, pady=5)
        ttk.Checkbutton(frame_type, text="教师解析版 (带红蓝解析)", variable=self.gen_teacher_var).pack(anchor="w", padx=15, pady=5)

        # 3. 抽题配比卡片
        frame_diff = ttk.LabelFrame(right_panel, text=" 智能抽题参数 ")
        frame_diff.pack(fill="x", pady=(0, 15), ipady=5)
        
        sub_frame_diff = tk.Frame(frame_diff, bg="#F8F9FA")
        sub_frame_diff.pack(fill="x", padx=15, pady=10)
        
        self.var_easy = tk.IntVar(value=40)
        self.var_medium = tk.IntVar(value=40)
        self.var_hard = tk.IntVar(value=20)
        
        tk.Label(sub_frame_diff, text="易(%):").grid(row=0, column=0)
        ttk.Spinbox(sub_frame_diff, from_=0, to=100, textvariable=self.var_easy, width=4).grid(row=0, column=1, padx=(0, 15))
        tk.Label(sub_frame_diff, text="中(%):").grid(row=0, column=2)
        ttk.Spinbox(sub_frame_diff, from_=0, to=100, textvariable=self.var_medium, width=4).grid(row=0, column=3, padx=(0, 15))
        tk.Label(sub_frame_diff, text="难(%):").grid(row=0, column=4)
        ttk.Spinbox(sub_frame_diff, from_=0, to=100, textvariable=self.var_hard, width=4).grid(row=0, column=5)

        sub_frame_num = tk.Frame(frame_diff, bg="#F8F9FA")
        sub_frame_num.pack(fill="x", padx=15, pady=5)
        tk.Label(sub_frame_num, text="题量总数 (道): ").pack(side="left")
        self.num_var = tk.IntVar(value=10) 
        ttk.Spinbox(sub_frame_num, from_=1, to=100, textvariable=self.num_var, width=5).pack(side="left")

        # 4. 操作与日志区
        self.btn_generate = tk.Button(right_panel, text="⚡ 一键抽取并生成试卷", bg="#0078D7", fg="white", font=("Microsoft YaHei", 12, "bold"), relief="flat", command=self.on_generate)
        self.btn_generate.pack(fill="x", pady=(10, 15), ipady=8)
        
        self.log_text = tk.Text(right_panel, height=6, bg="#E9ECEF", font=("Consolas", 9), relief="flat", padx=5, pady=5)
        self.log_text.pack(fill="both", expand=True)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()

    def refresh_ui_tree(self):
        """初始化加载完整知识树"""
        self.tree.delete(*self.tree.get_children())
        if not self.bank.tree:
            for chap in self.bank.get_all_chapters():
                self.tree.insert("", "end", iid=chap, text=chap)
            return

        for chap_name, topics in self.bank.tree.items():
            chap_node = self.tree.insert("", "end", iid=chap_name, text=chap_name)
            for topic in topics:
                self.tree.insert(chap_node, "end", iid=f"{chap_name}||{topic}", text=topic)

    def filter_tree(self, *args):
        """【核心新功能】：实时搜索过滤树节点"""
        query = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children()) # 清空当前树
        
        if not query:
            self.refresh_ui_tree() # 如果搜索框为空，恢复显示全部
            return
            
        # 遍历图谱进行匹配
        for chap_name, topics in self.bank.tree.items():
            # 找到名字里包含关键字的具体题型
            matching_topics = [t for t in topics if query in t.lower()]
            
            # 如果大章节名字匹配，或者它下面的题型匹配，就把这个大章节显示出来
            if query in chap_name.lower() or matching_topics:
                # 插入大章节节点，并且自动展开 (open=True) 以便直接看到匹配的内容
                chap_node = self.tree.insert("", "end", iid=chap_name, text=chap_name, open=True)
                
                # 如果是章节名中了，显示它下面所有的题型；如果是具体题型中了，只显示命中的题型
                topics_to_show = topics if query in chap_name.lower() else matching_topics
                for topic in topics_to_show:
                    self.tree.insert(chap_node, "end", iid=f"{chap_name}||{topic}", text=topic)

    def reload_db(self):
        self.log("-" * 30)
        self.log("[*] 正在重新读取底层数据...")
        msg = self.bank.load_data()
        self.search_var.set("") # 清空搜索框
        self.refresh_ui_tree()
        self.log(f"[√] {msg} 数据已更新。")

    def sanitize_filename(self, filename):
        return re.sub(r'[\\/*?:"<>|]', "", filename)

    def on_generate(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showwarning("提示", "请在左侧知识树中勾选考察范围！")
            return
            
        selected_chapters, selected_topics = [], []
        for iid in selected_iids:
            if "||" in iid: selected_topics.append(iid.split("||")[1])
            else: selected_chapters.append(iid)

        if not self.gen_student_var.get() and not self.gen_teacher_var.get():
            messagebox.showwarning("提示", "请在右侧勾选需要导出的试卷版本！")
            return
            
        pct_easy, pct_med, pct_hard = self.var_easy.get(), self.var_medium.get(), self.var_hard.get()
        if pct_easy + pct_med + pct_hard != 100:
            messagebox.showwarning("提示", "易、中、难比例总和必须为 100%！")
            return
            
        paper_title = self.title_var.get().strip() or "高三数学诊断测试卷"
        base_filename = self.sanitize_filename(self.filename_var.get().strip()) or "Math_Exam"
        target_num = self.num_var.get()
        
        self.log("-" * 30)
        self.log(f"[*] 启动深层检索... \n选中章节: {len(selected_chapters)}个 | 具体题型: {len(selected_topics)}个")
        
        num_easy = round(target_num * pct_easy / 100)
        num_med = round(target_num * pct_med / 100)
        num_hard = target_num - num_easy - num_med 

        pool = self.bank.filter_paper(selected_chapters, selected_topics)
        pool_easy = [q for q in pool if q.get("meta", {}).get("difficulty") == "易"]
        pool_med = [q for q in pool if q.get("meta", {}).get("difficulty") == "中"]
        pool_hard = [q for q in pool if q.get("meta", {}).get("difficulty") == "难"]
        
        final_questions = []
        def sample_questions(sub_pool, needed_num, diff_name):
            if needed_num <= 0: return []
            if len(sub_pool) >= needed_num: return random.sample(sub_pool, needed_num)
            else:
                self.log(f"[!] 警告: {diff_name}题库存不足! 仅剩 {len(sub_pool)} 道。")
                res = sub_pool.copy()
                random.shuffle(res)
                return res

        final_questions.extend(sample_questions(pool_easy, num_easy, "易"))
        final_questions.extend(sample_questions(pool_med, num_med, "中"))
        final_questions.extend(sample_questions(pool_hard, num_hard, "难"))
        
        if len(final_questions) == 0:
            messagebox.showinfo("提示", "未检索到任何题目！请扩大勾选范围。")
            return
            
        random.shuffle(final_questions)
        self.log(f"[*] 提取完成！合计抽取 {len(final_questions)} 题。")
        self.btn_generate.config(state="disabled", text="拼命渲染排版中...")
        success_files, has_error = [], False
        
        if self.gen_student_var.get():
            out_name = f"{base_filename}_Student"
            if PaperGenerator.generate_pdf(final_questions, paper_title, out_name, False): success_files.append(f"{out_name}.pdf")
            else: has_error = True
                
        if self.gen_teacher_var.get():
            out_name = f"{base_filename}_Teacher"
            if PaperGenerator.generate_pdf(final_questions, paper_title, out_name, True): success_files.append(f"{out_name}.pdf")
            else: has_error = True
        
        if not has_error:
            self.log(f"[√] 任务圆满完毕！")
            messagebox.showinfo("成功", f"生成完毕！\n已生成:\n" + "\n".join(success_files))
        else:
            self.log("[x] 发生错误！")
            messagebox.showerror("错误", "PDF 编译失败，请检查 LaTeX 环境！")
            
        self.btn_generate.config(state="normal", text="⚡ 一键抽取并生成试卷")

if __name__ == "__main__":
    root = tk.Tk()
    app = MathApp(root)
    root.mainloop()