import os
import json
import google.generativeai as genai

# ==========================================
# 1. 强制代理配置 (确保您的科学上网软件已开启并监听 6789)
# ==========================================
proxy_url = 'http://127.0.0.1:6789'
os.environ['http_proxy'] = proxy_url
os.environ['https_proxy'] = proxy_url
os.environ['HTTP_PROXY'] = proxy_url
os.environ['HTTPS_PROXY'] = proxy_url
os.environ['grpc_proxy'] = proxy_url
os.environ['GRPC_PROXY'] = proxy_url

# ==========================================
# 2. API 秘钥配置 (换成咱们的 Gemini Key)
# ==========================================
GEMINI_API_KEY = "AIzaSyC7VcVn8l3D7Oo9W_bkIktFAwjXZs_9l4g"

# ==========================================
# 3. 模拟系统后台抓取到的“学生病历本”
# ==========================================
student_data = {
    "student_name": "张宇",
    "radar_scores": {
        "函数与导数": 85, 
        "三角函数": 90, 
        "数列": 60, 
        "空间向量与立体几何": 80, 
        "解析几何": 40, 
        "概率与统计": 70
    },
    "error_tags": [
        "错题5 (数列)：错位相减法计算失误", 
        "错题9 (解析几何)：双曲线离心率范围（数形结合思维薄弱）", 
        "错题10 (解析几何)：直线与抛物线联立（非对称韦达定理未掌握）"
    ]
}

# ==========================================
# 4. 核心资产：高客单价名师专属 Prompt
# ==========================================
def generate_diagnostic_report(data):
    genai.configure(api_key=GEMINI_API_KEY)
    
    # 采用 Gemini 2.5 Pro，它的长文本推理和语气模仿能力极强
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    system_prompt = """
    你现在是中国顶尖的高考数学教研专家兼金牌班主任。你极其严谨、一针见血，不贩卖焦虑但会明确指出学生的致命失分点。
    请根据提供的【学生测评数据】，为该学生撰写一份极具专业度与针对性的《专属学情诊断与提分处方》。
    
    【撰写要求】：
    1. 结构清晰：分为“优势与雷区概览”、“核心病灶深度剖析”、“未来7天靶向突破方案”三个部分。
    2. 深度剖析：绝不能只说“解析几何差”，必须结合 error_tags（错题标签），使用高级教研黑话（如：非对称韦达定理、数形结合、算理障碍、模型盲区）进行深度降维打击分析。
    3. 靶向处方：给出的建议必须是具体的动作，而不是“多做题”、“细心一点”这种废话。
    4. 语气风格：专业、威严、负责，让家长看到后立刻产生极强的信任感，觉得“必须把孩子交给这位老师”。
    """

    user_prompt = f"这是系统刚刚生成的测评数据，请生成诊断报告：\n{json.dumps(data, ensure_ascii=False)}"

    print("🚀 正在呼叫 Gemini-Pro 诊断引擎，请稍候 (可能需要 10-20 秒思考时间)...")
    
    # 把系统指令和用户输入拼在一起发给模型
    response = model.generate_content([system_prompt, user_prompt])
    
    return response.text

# ==========================================
# 5. 执行并打印结果
# ==========================================
if __name__ == "__main__":
    try:
        report = generate_diagnostic_report(student_data)
        print("\n" + "="*60)
        print("🎓 AI 名师专属诊断报告生成完毕：")
        print("="*60 + "\n")
        print(report)
        print("\n" + "="*60)
    except Exception as e:
        print(f"❌ 发生错误：{e}")