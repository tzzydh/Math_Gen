import json
import subprocess
import os
from collections import defaultdict

# ==========================================
# 模块一：知识图谱与题库管理器
# ==========================================
class QuestionBank:
    def __init__(self):
        self.db = []
        
    def load_mock_data(self):
        """模拟从数据库加载带有《2025年高考一轮复习》精细分类标签的题库"""
        self.db = [
            {
                "id": "Q_001",
                "stem": "已知集合 $A=\\{1,2,3\\}, B=\\{2,3,4\\}$，则 $A \\cap B =$ （\\quad）",
                "options": ["$\\{1,4\\}$", "$\\{2,3\\}$", "$\\{1,2,3,4\\}$", "$\\varnothing$"],
                "answer": "B",
                "analysis": "根据交集定义，共有元素为 2, 3，故选 B。",
                "meta": {
                    "score": 5, "difficulty": "易",
                    "chapter": "第1讲 集合", 
                    "knowledge_weights": {"题型五:集合的交、并、补运算": 1.0}
                }
            },
            {
                "id": "Q_002",
                "stem": "在 $\\triangle ABC$ 中，若 $3\\overrightarrow{OA} + 4\\overrightarrow{OB} + 5\\overrightarrow{OC} = \\vec{0}$，则点 $O$ 是 $\\triangle ABC$ 的（\\quad）",
                "options": ["重心", "垂心", "内心", "外心"],
                "answer": "C",
                "analysis": "系数比等于对边长比，由奔驰定理推论可知为内心。",
                "meta": {
                    "score": 5, "difficulty": "中",
                    "chapter": "第37讲 三角形四心及奔驰定理", 
                    "knowledge_weights": {"题型一:奔驰定理": 0.6, "题型三:内心定理": 0.4}
                }
            },
            {
                "id": "Q_003",
                "stem": "已知椭圆 $C: \\frac{x^2}{a^2} + \\frac{y^2}{b^2} = 1$ 的离心率为 $\\frac{1}{2}$，且过定点，求其方程...",
                "options": ["$A$", "$B$", "$C$", "$D$"],
                "answer": "A",
                "analysis": "利用 $e=c/a$ 及代入法求解基本方程。",
                "meta": {
                    "score": 5, "difficulty": "难",
                    "chapter": "第64讲 椭圆及其性质", 
                    "knowledge_weights": {"题型一:椭圆的定义与标准方程": 0.5, "题型六:离心率的值及取值范围": 0.5}
                }
            }
        ]

    def filter_paper(self, chapters=None, difficulty=None):
        """按特定章节和难度智能抽卷"""
        selected = []
        for q in self.db:
            if chapters and q["meta"]["chapter"] not in chapters:
                continue
            if difficulty and q["meta"]["difficulty"] != difficulty:
                continue
            selected.append(q)
        return selected

# ==========================================
# 模块二：LaTeX 试卷生成器 (集成双发模式)
# ==========================================
class PaperGenerator:
    @staticmethod
    def generate_pdf(questions, paper_title="诊断测试卷", output_name="paper", show_answers=False):
        """将题目转换为 PDF (学生版 / 教师版)"""
        if not questions: return
        
        latex_code = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{amsmath}}\\usepackage{{amssymb}}\\usepackage{{ctex}}
\\usepackage{{tasks}}\\usepackage{{xcolor}}
\\settasks{{label=\\Alph*., label-width=1.5em, item-indent=2em}}

\\title{{\\vspace{{-2cm}}\\textbf{{{paper_title}}}}}
\\date{{}}
\\begin{{document}}
\\maketitle
\\vspace{{-1cm}}
\\section*{{一、 诊断测试题}}
"""
        for idx, q in enumerate(questions, 1):
            latex_code += f"{idx}. {q['stem']}\n\n"
            if q.get("options"):
                latex_code += "\\begin{tasks}(4)\n" + "".join([f"    \\task {opt}\n" for opt in q["options"]]) + "\\end{tasks}\n\n"
            
            if show_answers:
                latex_code += f"\\par\\noindent\\textcolor{{red}}{{\\textbf{{【答案】}} {q['answer']}}}\n"
                latex_code += f"\\par\\noindent\\textcolor{{blue}}{{\\textbf{{【解析】}} {q['analysis']}}}\n\n"
            latex_code += "\\vspace{1cm}\n"

        latex_code += "\\end{document}"
        
        tex_file = f"{output_name}.tex"
        with open(tex_file, 'w', encoding='utf-8') as f: f.write(latex_code)
        
        mode = "【教师解析版】" if show_answers else "【学生纯净版】"
        print(f"[*] 正在排版《{paper_title}》{mode}...")
        subprocess.run(['xelatex', '-interaction=nonstopmode', tex_file], capture_output=True)

# ==========================================
# 模块三：智能诊断推理引擎 (加权算法)
# ==========================================
class DiagnosticEngine:
    def __init__(self):
        # 记录：{ "知识点": [应得分, 实际得分] }
        self.stats = defaultdict(lambda: [0.0, 0.0])
        
    def evaluate(self, paper_questions, student_answers):
        total_score = 0; student_score = 0
        
        for q in paper_questions:
            meta = q["meta"]
            is_correct = (student_answers.get(q["id"]) == q["answer"])
            total_score += meta["score"]
            if is_correct: student_score += meta["score"]
            
            # 核心算法：将这道题的分数，按权重拆解到对应的细分题型上
            for kp, weight in meta["knowledge_weights"].items():
                kp_score = meta["score"] * weight
                self.stats[kp][0] += kp_score          # 累加该能力维度的总分
                if is_correct: self.stats[kp][1] += kp_score # 累加该能力维度的实际得分
                
        return student_score, total_score

    def print_report(self, student_name, student_score, total_score):
        print("\n" + "="*50)
        print(f" 🎯 【{student_name}】专属学情诊断报告")
        print(f" 📈 卷面总成绩: {student_score} / {total_score} 分")
        print("-" * 50)
        print(" 【细分题型掌握度画像（基于加权算法）】")
        
        weaknesses = []
        for kp, (expected, actual) in self.stats.items():
            rate = (actual / expected) * 100 if expected > 0 else 0
            # 进度条可视化
            bar = "█" * int(rate / 10) + "░" * (10 - int(rate / 10))
            print(f"  {kp[:15]:<15} | {bar} {rate:5.1f}% | 得分: {actual}/{expected}")
            
            if rate < 60.0: weaknesses.append(kp)
            
        print("-" * 50)
        if weaknesses:
            print(f" ⚠️ 专家诊断: 该生在【{', '.join(weaknesses)}】存在严重漏洞！")
            print(" 💡 学习建议: 系统已自动将上述薄弱考点加入该生的『错题重组池』。")
        else:
            print(" ✅ 专家诊断: 基础扎实，建议向压轴大题发起冲击。")
        print("="*50 + "\n")

# ==========================================
# 主控台：模拟一次真实的交互流程
# ==========================================
if __name__ == "__main__":
    # 1. 启动系统，加载全库
    bank = QuestionBank()
    bank.load_mock_data()
    
    # 2. 组卷：今天测验“集合”、“向量四心”和“椭圆”
    exam_paper = bank.filter_paper()
    
    # 3. 打印试卷（输出 PDF）
    PaperGenerator.generate_pdf(exam_paper, "高三综合诊断摸底测验", "Test_Student", show_answers=False)
    PaperGenerator.generate_pdf(exam_paper, "高三综合诊断摸底测验", "Test_Teacher", show_answers=True)
    
    # 4. 模拟学生作答 (此学生做对了集合和四心，但椭圆做错了)
    student_A_answers = {
        "Q_001": "B", # 对
        "Q_002": "C", # 对
        "Q_003": "D"  # 错 (正解是 A)
    }
    
    # 5. 引擎批改并输出深层次诊断报告
    engine = DiagnosticEngine()
    score, total = engine.evaluate(exam_paper, student_A_answers)
    engine.print_report("张三", score, total)