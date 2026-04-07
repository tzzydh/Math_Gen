#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数学题目自动分类器
根据 knowledge_tree.json 将题目自动匹配到对应的章节和题型。

用法:
  1. 单题分类:
     python auto_classify.py --stem "已知等差数列{a_n}的前n项和为S_n，若a_3+a_4=7，求S_10"

  2. 批量分类 (从 JSON 文件读取):
     python auto_classify.py --input questions.json --output classified.json

  3. 交互模式:
     python auto_classify.py --interactive

questions.json 格式示例:
[
  {"id": "Q_001", "stem": "题目文本...", "options": [...], "answer": "A", "analysis": "..."},
  ...
]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# ============================================================
# 1. 关键词词库  —— 每个章节对应的核心关键词
#    权重越高表示该关键词对此章节的区分度越强
# ============================================================

CHAPTER_KEYWORDS = {
    "第1讲 集合": {
        "keywords": ["集合", "交集", "并集", "补集", "子集", "真子集",
                      "空集", "∩", "∪", "⊂", "⊆", "元素", "列举法", "描述法",
                      "A∩B", "A∪B", "CUA", "互异性", "cap", "cup",
                      "容斥", "A=\\{", "B=\\{", "集合A", "集合B",
                      "A \\cup B", "A \\cap B", "\\in A", "\\in B",
                      "\\subseteq", "\\subset", "\\varnothing"],
        "weight": 1.0,
        "anti_keywords": []  # 排斥词：出现这些词则降低匹配分
    },
    "第2讲 常用逻辑用语": {
        "keywords": ["充分条件", "必要条件", "充要条件", "全称量词", "存在量词",
                      "命题", "逆命题", "否命题", "逆否命题", "∀", "∃",
                      "充分不必要", "必要不充分"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第3讲 等式与不等式的性质": {
        "keywords": ["不等式性质", "比较大小", "比较法", "糖水不等式"],
        "weight": 0.8,
        "anti_keywords": ["基本不等式", "一元二次不等式", "导数"]
    },
    "第4讲 基本不等式及其应用": {
        "keywords": ["基本不等式", "均值不等式", "a+b≥2√ab", "AM-GM",
                      "当且仅当等号成立", "1的代换", "齐次化求最值",
                      "对勾函数"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第5讲 一元二次不等式与其它不等式解法": {
        "keywords": ["一元二次不等式", "不等式解法", "韦达定理", "判别式",
                      "不等式解集", "二次不等式", "分式不等式", "绝对值不等式",
                      "恒成立", "根的分布"],
        "weight": 1.0,
        "anti_keywords": ["导数"]
    },
    "第6讲 函数的概念": {
        "keywords": ["定义域", "值域", "解析式", "分段函数", "函数概念",
                      "同一函数"],
        "weight": 0.9,
        "anti_keywords": ["导数", "三角函数", "指数函数", "对数函数"]
    },
    "第7讲 函数的性质": {
        "keywords": ["单调性", "奇偶性", "周期性", "对称性", "单调递增",
                      "单调递减", "奇函数", "偶函数", "f(-x)", "f(x+T)"],
        "weight": 0.9,
        "anti_keywords": ["导数", "三角函数"]
    },
    "第8讲 幂函数与二次函数": {
        "keywords": ["幂函数", "x^α", "二次函数", "抛物线开口",
                      "动轴定区间", "定轴动区间"],
        "weight": 1.0,
        "anti_keywords": ["抛物线的焦点", "抛物线方程", "圆锥曲线"]
    },
    "第9讲 指数与指数函数": {
        "keywords": ["指数函数", "指数运算", "指数方程", "指数不等式",
                      "a^x", "e^x", "2^x", "3^x",
                      "2^{", "3^{", "^{-0.5}", "^{0.5}",
                      "\\sqrt{7}}", "^{\\sqrt", "^{\\frac",
                      "2^{-x}", "e^{", "指数"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第10讲 对数与对数函数": {
        "keywords": ["对数函数", "对数运算", "lg", "ln", "log",
                      "对数方程", "对数不等式", "换底公式"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第11讲 函数的图像": {
        "keywords": ["函数图像", "图象变换", "由图选式", "由式选图",
                      "识图", "图像变换"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第12讲 函数与方程": {
        "keywords": ["零点", "函数方程", "二分法", "零点个数",
                      "零点所在区间"],
        "weight": 1.0,
        "anti_keywords": ["导数", "极值点偏移"]
    },
    "第13讲 函数模型及其应用": {
        "keywords": ["函数模型", "实际问题", "增长率", "对勾函数模型"],
        "weight": 0.8,
        "anti_keywords": []
    },
    "第14讲 导数的概念与运算": {
        "keywords": ["导数定义", "求导", "导数运算", "切线方程",
                      "导数的几何意义", "瞬时变化率"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第15讲 单调性问题": {
        "keywords": ["导数", "单调区间", "f'(x)"],
        "weight": 0.7,
        "anti_keywords": [],
        "require_all": ["导数", "单调"]  # 需要同时出现
    },
    "第16讲 极值与最值": {
        "keywords": ["极值", "极大值", "极小值", "最值", "极值点",
                      "导数"],
        "weight": 0.8,
        "anti_keywords": [],
        "require_all": ["导数"]
    },
    "第17讲 幂指对比较大小": {
        "keywords": ["比较大小", "幂指对", "构造函数比较"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第18讲 函数的综合应用": {
        "keywords": ["函数综合", "倍值函数", "不动点", "铅锤距离"],
        "weight": 0.7,
        "anti_keywords": []
    },
    "第19讲 原函数与导函数混合还原": {
        "keywords": ["构造函数", "xf'(x)", "e^xf(x)", "导函数还原",
                      "原函数"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第20讲 三次函数的图象和性质": {
        "keywords": ["三次函数", "ax³", "x³"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第21讲 极值点偏移": {
        "keywords": ["极值点偏移"],
        "weight": 2.0,
        "anti_keywords": []
    },
    "第22讲 双变量问题": {
        "keywords": ["双变量"],
        "weight": 2.0,
        "anti_keywords": []
    },
    "第23讲 不等式恒成立": {
        "keywords": ["恒成立", "分离参数", "洛必达", "同构法"],
        "weight": 0.9,
        "anti_keywords": [],
        "require_context": ["导数", "不等式"]
    },
    "第24讲 不等式的证明问题": {
        "keywords": ["证明不等式", "放缩法", "虚设零点", "凹凸反转"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第25讲 函数的零点问题": {
        "keywords": ["零点问题", "零点个数", "零点差"],
        "weight": 1.0,
        "anti_keywords": [],
        "require_context": ["导数"]
    },
    "第26讲 导数同构": {
        "keywords": ["同构", "导数同构"],
        "weight": 1.5,
        "anti_keywords": [],
        "require_context": ["导数"]
    },
    "第27讲 多元最值问题": {
        "keywords": ["多元最值", "柯西不等式", "拉格朗日乘数法",
                      "权方和不等式", "琴生不等式"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第28讲 三角函数概念及诱导公式": {
        "keywords": ["诱导公式", "终边相同", "弧度制", "弧长", "扇形面积",
                      "象限", "同角三角函数"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第29讲 三角恒等变换": {
        "keywords": ["两角和", "两角差", "二倍角", "半角公式", "辅助角",
                      "和差化积", "积化和差", "sin(α+β)", "cos(α-β)",
                      "tan(α+β)", "给值求值", "给角求值", "给值求角"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第30讲 三角函数的图像与性质": {
        "keywords": ["sinx", "cosx", "三角函数图像", "五点作图",
                      "Asin(ωx+φ)", "三角函数性质", "三角函数周期",
                      "三角函数单调"],
        "weight": 1.0,
        "anti_keywords": ["解三角形", "正弦定理", "余弦定理"]
    },
    "第31讲 ω 的取值范围与最值问题": {
        "keywords": ["ω的取值", "ω取值范围"],
        "weight": 1.5,
        "anti_keywords": []
    },
    "第32讲 解三角形": {
        "keywords": ["正弦定理", "余弦定理", "解三角形", "三角形面积",
                      "三角形形状", "三角形周长"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第33讲 解三角形图形问题": {
        "keywords": ["张角定理", "角平分线", "中线", "外接圆",
                      "内切圆"],
        "weight": 0.9,
        "anti_keywords": [],
        "require_context": ["三角形"]
    },
    "第34讲 三角形中最值与范围": {
        "keywords": ["三角形最值", "三角形范围", "费马点", "布洛卡点"],
        "weight": 0.9,
        "anti_keywords": [],
        "require_context": ["三角形", "最值"]
    },
    "第35讲 平面向量的概念与坐标运算": {
        "keywords": ["平面向量", "向量", "线性表示", "向量共线",
                      "基底", "向量坐标"],
        "weight": 1.0,
        "anti_keywords": ["数量积", "空间向量"]
    },
    "第36讲 平面向量的数量积及运算": {
        "keywords": ["数量积", "点积", "向量夹角", "向量模长",
                      "投影", "向量垂直"],
        "weight": 1.0,
        "anti_keywords": ["空间向量"]
    },
    "第37讲 三角形四心及奔驰定理": {
        "keywords": ["奔驰定理", "重心", "内心", "外心", "垂心", "四心"],
        "weight": 1.2,
        "anti_keywords": [],
        "require_context": ["向量", "三角形"]
    },
    "第38讲 向量中的隐圆": {
        "keywords": ["隐圆", "向量模"],
        "weight": 1.0,
        "anti_keywords": [],
        "require_context": ["向量"]
    },
    "第39讲 复数": {
        "keywords": ["复数", "虚部", "实部", "共轭复数", "复平面",
                      "i²=-1", "虚数单位"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第40讲 数列的基本知识与概念": {
        "keywords": ["数列", "通项", "递推"],
        "weight": 0.6,
        "anti_keywords": ["等差", "等比"]
    },
    "第41讲 等差数列及其前n项和": {
        "keywords": ["等差数列", "公差", "等差中项", "前n项和",
                      "S_n", "Sn"],
        "weight": 1.2,
        "anti_keywords": ["等比"]
    },
    "第42讲 等比数列及其前n项和": {
        "keywords": ["等比数列", "公比", "等比中项"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第43讲 数列的通项公式": {
        "keywords": ["通项公式", "求通项", "叠加法", "叠乘法",
                      "待定系数", "an与Sn"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第44讲 数列求和": {
        "keywords": ["数列求和", "错位相减", "裂项相消", "倒序相加",
                      "分组求和"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第45讲 数列的综合应用": {
        "keywords": ["数列综合", "数列不等式"],
        "weight": 0.7,
        "anti_keywords": []
    },
    "第46讲 空间几何体的结构特征、表面积与体积": {
        "keywords": ["表面积", "体积", "棱柱", "棱锥", "棱台",
                      "圆柱", "圆锥", "圆台", "三视图", "直观图",
                      "展开图"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第47讲 空间点、直线、平面之间的位置关系": {
        "keywords": ["共面", "共线", "截面", "异面直线", "异面"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第48讲 直线、平面平行的判定与性质": {
        "keywords": ["线面平行", "面面平行", "平行判定"],
        "weight": 1.0,
        "anti_keywords": [],
        "require_context": ["立体几何", "空间", "平面"]
    },
    "第49讲 直线、平面垂直的判定与性质": {
        "keywords": ["线面垂直", "面面垂直", "垂直判定"],
        "weight": 1.0,
        "anti_keywords": [],
        "require_context": ["立体几何", "空间", "平面"]
    },
    "第50讲 外接球、内切球、棱切球": {
        "keywords": ["外接球", "内切球", "棱切球", "球的半径",
                      "球的表面积"],
        "weight": 1.5,
        "anti_keywords": []
    },
    "第51讲 立体几何中的截面问题": {
        "keywords": ["截面"],
        "weight": 1.0,
        "anti_keywords": [],
        "require_context": ["立体几何", "几何体"]
    },
    "第52讲 立体几何中的轨迹问题": {
        "keywords": ["轨迹"],
        "weight": 0.8,
        "anti_keywords": [],
        "require_context": ["立体几何", "空间"]
    },
    "第53讲 传统方法求角度与距离": {
        "keywords": ["二面角", "线面角", "异面直线所成角", "点面距"],
        "weight": 1.0,
        "anti_keywords": ["向量法"]
    },
    "第54讲 空间向量及其应用": {
        "keywords": ["空间向量", "法向量", "建立空间直角坐标系"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第55讲 立体几何中的压轴小题": {
        "keywords": ["立体几何压轴"],
        "weight": 0.5,
        "anti_keywords": []
    },
    "第56讲 立体几何解答题": {
        "keywords": ["立体几何解答", "折叠"],
        "weight": 0.5,
        "anti_keywords": []
    },
    "第57讲 直线的方程": {
        "keywords": ["倾斜角", "斜率", "直线方程", "截距",
                      "点斜式", "斜截式", "两点式", "一般式"],
        "weight": 1.0,
        "anti_keywords": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第58讲 两条直线的位置关系": {
        "keywords": ["平行直线", "垂直直线", "两直线交点",
                      "点到直线距离", "对称点", "线线对称"],
        "weight": 1.0,
        "anti_keywords": ["椭圆", "双曲线", "抛物线"]
    },
    "第59讲 圆的方程": {
        "keywords": ["圆的方程", "圆的标准方程", "圆的一般方程",
                      "x²+y²"],
        "weight": 1.0,
        "anti_keywords": ["椭圆", "双曲线", "抛物线"]
    },
    "第60讲 直线与圆、圆与圆的位置关系": {
        "keywords": ["直线与圆", "切线", "弦长", "圆与圆"],
        "weight": 1.0,
        "anti_keywords": ["椭圆", "双曲线", "抛物线"],
        "require_context": ["圆"]
    },
    "第61讲 圆中的范围与最值": {
        "keywords": ["圆的最值", "圆的范围"],
        "weight": 0.8,
        "anti_keywords": [],
        "require_context": ["圆"]
    },
    "第62讲 隐圆问题": {
        "keywords": ["隐圆"],
        "weight": 1.5,
        "anti_keywords": [],
    },
    "第63讲 直线与圆的综合": {
        "keywords": ["切比雪夫距离", "曼哈顿距离", "阿波罗尼斯圆"],
        "weight": 1.5,
        "anti_keywords": []
    },
    "第64讲 椭圆及其性质": {
        "keywords": ["椭圆", "离心率", "焦点", "长轴", "短轴",
                      "焦距", "x²/a²+y²/b²=1"],
        "weight": 1.2,
        "anti_keywords": ["双曲线", "抛物线"]
    },
    "第65讲 双曲线及其性质": {
        "keywords": ["双曲线", "渐近线", "实轴", "虚轴",
                      "x²/a²-y²/b²=1"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第66讲 抛物线及其性质": {
        "keywords": ["抛物线", "准线", "焦半径", "y²=2px", "x²=2py"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第67讲 圆锥曲线离心率题型全归纳": {
        "keywords": ["离心率"],
        "weight": 0.9,
        "anti_keywords": [],
        "require_context": ["圆锥曲线", "椭圆", "双曲线"]
    },
    "第68讲 曲线的轨迹方程": {
        "keywords": ["轨迹方程", "相关点法", "交轨法", "参数法"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第69讲 直线与圆锥曲线的位置关系": {
        "keywords": ["直线与圆锥曲线", "中点弦", "弦长"],
        "weight": 0.8,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线"]
    },
    "第70讲 弦长问题": {
        "keywords": ["弦长"],
        "weight": 0.7,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第71讲 面积问题": {
        "keywords": ["面积"],
        "weight": 0.6,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第72讲 垂直弦问题": {
        "keywords": ["垂直弦", "内接直角三角形"],
        "weight": 1.5,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线"]
    },
    "第73讲 斜率题型全归纳": {
        "keywords": ["斜率和", "斜率差", "斜率积", "斜率商"],
        "weight": 1.2,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第74讲 存在性问题的探究": {
        "keywords": ["存在性", "是否存在"],
        "weight": 0.8,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第75讲 切点与切点弦": {
        "keywords": ["切点弦", "切线"],
        "weight": 1.0,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第76讲 双切线问题": {
        "keywords": ["双切线", "交点弦"],
        "weight": 1.5,
        "anti_keywords": []
    },
    "第77讲 定点、定值问题": {
        "keywords": ["定点", "定值", "过定点"],
        "weight": 0.9,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第78讲 参数范围与最值": {
        "keywords": ["参数范围", "最值"],
        "weight": 0.6,
        "anti_keywords": [],
        "require_context": ["椭圆", "双曲线", "抛物线", "圆锥曲线"]
    },
    "第79讲 圆锥曲线中的圆问题": {
        "keywords": ["蒙日圆", "四点共圆"],
        "weight": 1.5,
        "anti_keywords": [],
        "require_context": ["圆锥曲线", "椭圆", "双曲线", "抛物线"]
    },
    "第80讲 阿基米德三角形": {
        "keywords": ["阿基米德三角形"],
        "weight": 2.0,
        "anti_keywords": []
    },
    "第81讲 圆锥曲线拓展题型一": {
        "keywords": ["定比点差法", "齐次化", "极点极线", "蝴蝶问题"],
        "weight": 1.5,
        "anti_keywords": []
    },
    "第82讲 圆锥曲线题型拓展(二)": {
        "keywords": ["仿射变换", "光学性质", "非对称韦达"],
        "weight": 1.5,
        "anti_keywords": []
    },
    "第83讲 统计": {
        "keywords": ["统计", "抽样", "频率分布直方图", "平均数",
                      "方差", "标准差", "中位数", "众数", "百分位数",
                      "分层抽样"],
        "weight": 1.0,
        "anti_keywords": ["概率"]
    },
    "第84讲 成对数据的统计分析": {
        "keywords": ["回归", "相关系数", "散点图", "列联表",
                      "独立性检验", "残差"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第85讲 计数原理": {
        "keywords": ["分类加法", "分步乘法", "计数原理"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第86讲 排列与组合": {
        "keywords": ["排列", "组合", "A_n^m", "C_n^m", "P_n^m",
                      "捆绑法", "插空法", "隔板法", "涂色"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第87讲 二项式定理": {
        "keywords": ["二项式", "展开式", "通项", "二项式系数",
                      "杨辉三角", "(a+b)^n", "(1+x)^n"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第88讲 随机事件、频率与概率": {
        "keywords": ["随机事件", "样本空间", "互斥事件", "对立事件",
                      "频率", "概率"],
        "weight": 0.8,
        "anti_keywords": []
    },
    "第89讲 古典概型与概率的基本性质": {
        "keywords": ["古典概型", "等可能", "样本点"],
        "weight": 1.0,
        "anti_keywords": []
    },
    "第90讲 事件的相互独立性、条件概率与全概率公式": {
        "keywords": ["条件概率", "相互独立", "全概率", "贝叶斯",
                      "独立事件"],
        "weight": 1.2,
        "anti_keywords": []
    },
    "第91讲 离散型随机变量的分布列与数字特征": {
        "keywords": ["分布列", "随机变量", "期望", "数学期望",
                      "均值", "方差"],
        "weight": 1.0,
        "anti_keywords": [],
        "require_context": ["概率", "随机"]
    },
    "第92讲 两点分布、二项分布、超几何分布与正态分布": {
        "keywords": ["二项分布", "超几何分布", "正态分布", "两点分布",
                      "B(n,p)", "X~N", "独立重复试验"],
        "weight": 1.3,
        "anti_keywords": []
    },
    "第93讲 概率与统计的综合应用": {
        "keywords": ["概率综合", "决策", "保险"],
        "weight": 0.7,
        "anti_keywords": []
    },
}


# ============================================================
# 2. 文本预处理
# ============================================================

def clean_latex(text: str) -> str:
    """移除 LaTeX 命令，保留数学内容关键词"""
    # 去掉常见LaTeX命令但保留内容
    text = re.sub(r'\\(frac|dfrac|tfrac)\{([^}]*)\}\{([^}]*)\}', r'\2/\3', text)
    text = re.sub(r'\\(overrightarrow|vec|hat)\{([^}]*)\}', r'\2', text)
    text = re.sub(r'\\(text|mathrm|mathbf|mathbb)\{([^}]*)\}', r'\2', text)
    text = re.sub(r'\\(left|right|Big|big|bigg)[|()[\]{}.]?', '', text)
    text = re.sub(r'\\(quad|qquad|,|;|!|\s)', ' ', text)
    text = re.sub(r'\$', '', text)
    text = re.sub(r'\\\\', ' ', text)
    # 保留中文和字母数字
    return text


def extract_text(question: dict) -> str:
    """从题目字典中提取所有文本"""
    parts = []
    if "stem" in question:
        parts.append(question["stem"])
    if "options" in question:
        parts.extend(question["options"])
    if "analysis" in question:
        parts.append(question["analysis"])
    combined = " ".join(parts)
    return clean_latex(combined)


# ============================================================
# 3. 分类引擎
# ============================================================

class MathClassifier:
    def __init__(self, knowledge_tree_path: str):
        with open(knowledge_tree_path, 'r', encoding='utf-8') as f:
            self.knowledge_tree = json.load(f)

        # 构建章节名到编号的映射
        self.chapters = list(self.knowledge_tree.keys())

        # 构建"第N讲"到实际键名的映射 (解决空格等微小差异)
        self.chapter_num_map = {}
        for ch in self.chapters:
            m = re.match(r'(第\d+讲)', ch)
            if m:
                self.chapter_num_map[m.group(1)] = ch

        # 从知识树中提取额外关键词 (题型名中的关键词)
        self.topic_keywords = {}
        for chapter, topics in self.knowledge_tree.items():
            self.topic_keywords[chapter] = []
            for topic in topics:
                # 提取题型名中冒号后面的描述
                if ":" in topic:
                    desc = topic.split(":", 1)[1]
                elif "：" in topic:
                    desc = topic.split("：", 1)[1]
                else:
                    desc = topic
                self.topic_keywords[chapter].append({
                    "name": topic,
                    "desc": desc,
                    "keywords": self._extract_keywords_from_desc(desc)
                })

    def _extract_keywords_from_desc(self, desc: str) -> list:
        """从题型描述中提取关键词"""
        # 按中文逗号、顿号、空格、"的"、"与"、"及"分割
        tokens = re.split(r'[,，、\s/()（）的与及和]+', desc)
        result = [t.strip() for t in tokens if len(t.strip()) >= 2]
        # 也保留原始完整描述作为关键词
        if len(desc.strip()) >= 2:
            result.append(desc.strip())
        return result

    def classify(self, question_text: str, top_n: int = 3) -> dict:
        """
        对题目文本进行分类
        返回: {"chapter": "...", "knowledge_weights": {...}, "scores": [...]}
        """
        if isinstance(question_text, str):
            text_raw = question_text
            text = question_text
        else:
            # 拼接原始文本 (含LaTeX) 用于匹配LaTeX模式
            parts_raw = []
            if "stem" in question_text:
                parts_raw.append(question_text["stem"])
            if "options" in question_text:
                parts_raw.extend(question_text["options"])
            if "analysis" in question_text:
                parts_raw.append(question_text["analysis"])
            text_raw = " ".join(parts_raw)
            text = extract_text(question_text)

        text_clean = clean_latex(text)
        # 同时在原始文本和清洗后文本中搜索
        text_lower = (text_clean + " " + text_raw).lower()

        # 第一层: 章节匹配打分
        chapter_scores = {}

        for chapter, config in CHAPTER_KEYWORDS.items():
            score = 0.0

            # 正向关键词匹配
            for kw in config["keywords"]:
                kw_lower = kw.lower()
                count = text_lower.count(kw_lower)
                if count > 0:
                    # 关键词长度越长，权重越高 (更精确)
                    length_bonus = min(len(kw) / 4, 2.0)
                    score += count * config["weight"] * length_bonus

            # 反向关键词惩罚
            for anti_kw in config.get("anti_keywords", []):
                if anti_kw.lower() in text_lower:
                    score *= 0.3

            # require_all: 必须同时包含所有关键词才有效
            require_all = config.get("require_all", [])
            if require_all:
                if all(kw.lower() in text_lower for kw in require_all):
                    score *= 1.5
                else:
                    score *= 0.2

            # require_context: 至少匹配一个上下文词才有效
            require_ctx = config.get("require_context", [])
            if require_ctx:
                if any(kw.lower() in text_lower for kw in require_ctx):
                    score *= 1.3
                else:
                    score *= 0.5

            # 额外: 知识树中题型关键词匹配
            if chapter in self.topic_keywords:
                for topic_info in self.topic_keywords[chapter]:
                    for kw in topic_info["keywords"]:
                        if len(kw) >= 2 and kw.lower() in text_lower:
                            score += 0.5

            # 特殊规则: 正则模式匹配
            if chapter == "第9讲 指数与指数函数":
                # 匹配指数表达式模式: 数字^{...} 或 数字^数字
                exp_patterns = [
                    r'\d+\^[\{\\]',           # 2^{...} or 2^\...
                    r'\\frac\{.*?\}\)\^\{',    # (frac{...})^{...}
                    r'\^\{-?\d+\.?\d*\}',      # ^{-0.5}, ^{3}
                    r'\^\{\\frac',             # ^{\frac...}
                    r'\^\{\\sqrt',             # ^{\sqrt...}
                    r'\\cdot\s*\d+\^',         # ·2^
                ]
                for pat in exp_patterns:
                    if re.search(pat, text_raw):
                        score += 2.0

            if chapter == "第1讲 集合":
                # 匹配集合符号模式
                set_patterns = [
                    r'\\cup|\\cap|\\subseteq|\\subset|\\varnothing',
                    r'\\in\s*[A-Z]',          # \in A
                    r'[A-Z]\s*=\s*\\?\{',     # A={...}
                    r'集合\s*\$?[A-Z]',        # 集合A
                ]
                for pat in set_patterns:
                    if re.search(pat, text_raw):
                        score += 2.0
                # 容斥原理类: "只...和...", "至少观看"
                rongchi_kws = ["只观看", "只参加", "至少", "恰好", "都参加",
                               "都观看", "韦恩图", "容斥"]
                for kw in rongchi_kws:
                    if kw in text_lower:
                        score += 3.0

            if score > 0:
                chapter_scores[chapter] = score

        if not chapter_scores:
            return {
                "chapter": "未知",
                "knowledge_weights": {},
                "confidence": 0.0,
                "top_matches": []
            }

        # 排序取 top
        sorted_chapters = sorted(chapter_scores.items(), key=lambda x: -x[1])
        best_chapter = sorted_chapters[0][0]
        best_score = sorted_chapters[0][1]

        # 将 CHAPTER_KEYWORDS 键名映射回 knowledge_tree 实际键名
        real_best_chapter = self._resolve_chapter_key(best_chapter)

        # 第二层: 在最佳章节内匹配具体题型
        knowledge_weights = self._match_topics(best_chapter, text_clean)

        # 计算置信度
        total = sum(s for _, s in sorted_chapters)
        confidence = best_score / total if total > 0 else 0

        return {
            "chapter": real_best_chapter,
            "knowledge_weights": knowledge_weights,
            "confidence": round(confidence, 3),
            "top_matches": [
                {"chapter": ch, "score": round(sc, 2)}
                for ch, sc in sorted_chapters[:top_n]
            ]
        }

    def _resolve_chapter_key(self, chapter: str) -> str:
        """将 CHAPTER_KEYWORDS 中的键名解析为 knowledge_tree 中的实际键名"""
        if chapter in self.knowledge_tree:
            return chapter
        # 按"第N讲"编号查找
        m = re.match(r'(第\d+讲)', chapter)
        if m and m.group(1) in self.chapter_num_map:
            return self.chapter_num_map[m.group(1)]
        return chapter

    def _match_topics(self, chapter: str, text: str) -> dict:
        """在指定章节内匹配具体题型"""
        text_lower = text.lower()
        real_chapter = self._resolve_chapter_key(chapter)
        topics = self.knowledge_tree.get(real_chapter, [])
        topic_scores = {}

        for topic in topics:
            # 解析题型名
            if ":" in topic:
                desc = topic.split(":", 1)[1]
            elif "：" in topic:
                desc = topic.split("：", 1)[1]
            else:
                desc = topic

            score = 0.0
            keywords = re.split(r'[,，、\s/()（）]+', desc)
            keywords = [k.strip() for k in keywords if len(k.strip()) >= 2]

            for kw in keywords:
                if kw.lower() in text_lower:
                    score += len(kw)  # 更长的关键词权重更高

            if score > 0:
                topic_scores[topic] = score

        if not topic_scores:
            # 如果没有匹配到具体题型，默认给第一个题型
            if topics:
                return {topics[0]: 1.0}
            return {}

        # 归一化权重，保留 top 3
        sorted_topics = sorted(topic_scores.items(), key=lambda x: -x[1])
        top_topics = sorted_topics[:3]

        # 如果多个题型分数相同（都只匹配了章节通用关键词），只保留第一个
        if len(top_topics) > 1 and top_topics[0][1] == top_topics[-1][1]:
            top_topics = [top_topics[0]]

        total = sum(s for _, s in top_topics)
        weights = {}
        for topic, score in top_topics:
            w = round(score / total, 2)
            if w > 0:
                weights[topic] = w

        # 确保权重和为 1.0
        if weights:
            total_w = sum(weights.values())
            if total_w != 1.0:
                max_topic = max(weights, key=weights.get)
                weights[max_topic] = round(weights[max_topic] + (1.0 - total_w), 2)

        return weights

    def classify_question(self, question: dict) -> dict:
        """对一个完整的题目字典进行分类，返回带 meta 的结果"""
        text = extract_text(question)
        result = self.classify(text)
        return result

    def batch_classify(self, questions: list) -> list:
        """批量分类"""
        results = []
        for q in questions:
            cls_result = self.classify_question(q)
            # 将分类结果写入 meta
            q_copy = json.loads(json.dumps(q))  # deep copy
            if "meta" not in q_copy:
                q_copy["meta"] = {}
            q_copy["meta"]["chapter"] = cls_result["chapter"]
            q_copy["meta"]["knowledge_weights"] = cls_result["knowledge_weights"]
            q_copy["meta"]["classification_confidence"] = cls_result["confidence"]
            results.append(q_copy)
        return results


# ============================================================
# 4. 验证函数: 用已有标注数据测试准确率
# ============================================================

def validate(classifier: MathClassifier, bank_path: str):
    """用 bank_v2.json 验证分类准确率"""
    with open(bank_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    total = 0
    chapter_correct = 0
    topic_partial_correct = 0
    results_detail = []

    for q in questions:
        if "meta" not in q or "chapter" not in q["meta"]:
            continue

        total += 1
        true_chapter = q["meta"]["chapter"]
        true_weights = q["meta"].get("knowledge_weights", {})

        pred = classifier.classify_question(q)
        pred_chapter = pred["chapter"]
        pred_weights = pred["knowledge_weights"]

        # 章节是否正确
        ch_match = (pred_chapter == true_chapter)
        if ch_match:
            chapter_correct += 1

        # 题型是否有重叠
        true_topics = set(true_weights.keys())
        pred_topics = set(pred_weights.keys())
        overlap = true_topics & pred_topics
        if overlap:
            topic_partial_correct += 1

        results_detail.append({
            "id": q.get("id", "?"),
            "true_chapter": true_chapter,
            "pred_chapter": pred_chapter,
            "chapter_match": ch_match,
            "true_topics": list(true_topics),
            "pred_topics": list(pred_topics),
            "topic_overlap": list(overlap),
            "confidence": pred["confidence"]
        })

    print(f"\n{'='*60}")
    print(f"验证结果 (共 {total} 题)")
    print(f"{'='*60}")
    print(f"章节准确率:  {chapter_correct}/{total} = {chapter_correct/total*100:.1f}%")
    print(f"题型部分匹配: {topic_partial_correct}/{total} = {topic_partial_correct/total*100:.1f}%")
    print(f"{'='*60}")

    # 打印错误详情
    errors = [r for r in results_detail if not r["chapter_match"]]
    if errors:
        print(f"\n章节分类错误 ({len(errors)} 题):")
        for e in errors:
            print(f"  [{e['id']}] 真实: {e['true_chapter']}  →  预测: {e['pred_chapter']}  (置信度: {e['confidence']})")

    return results_detail


# ============================================================
# 5. 主程序
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="数学题目自动分类器")
    parser.add_argument("--tree", default="knowledge_tree.json",
                        help="知识树 JSON 文件路径")
    parser.add_argument("--stem", type=str, default=None,
                        help="单题分类: 输入题目文本")
    parser.add_argument("--input", type=str, default=None,
                        help="批量分类: 输入 JSON 文件路径")
    parser.add_argument("--output", type=str, default=None,
                        help="批量分类: 输出 JSON 文件路径")
    parser.add_argument("--validate", type=str, default=None,
                        help="验证模式: 输入已标注的 bank JSON 文件路径")
    parser.add_argument("--interactive", action="store_true",
                        help="交互模式")

    args = parser.parse_args()

    # 找到知识树文件
    tree_path = args.tree
    if not Path(tree_path).exists():
        # 尝试在同目录下查找
        script_dir = Path(__file__).parent
        tree_path = str(script_dir / "knowledge_tree.json")

    classifier = MathClassifier(tree_path)
    print(f"已加载知识树: {len(classifier.chapters)} 个章节")

    # 模式 1: 单题分类
    if args.stem:
        result = classifier.classify(args.stem)
        print(f"\n题目: {args.stem[:80]}...")
        print(f"章节: {result['chapter']}")
        print(f"题型权重: {json.dumps(result['knowledge_weights'], ensure_ascii=False, indent=2)}")
        print(f"置信度: {result['confidence']}")
        print(f"Top 匹配:")
        for m in result['top_matches']:
            print(f"  {m['chapter']}: {m['score']}")
        return

    # 模式 2: 批量分类
    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        results = classifier.batch_classify(questions)
        output_path = args.output or args.input.replace('.json', '_classified.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"已分类 {len(results)} 题，结果保存到: {output_path}")
        return

    # 模式 3: 验证
    if args.validate:
        validate(classifier, args.validate)
        return

    # 模式 4: 交互模式
    if args.interactive:
        print("\n进入交互模式 (输入 'quit' 退出)")
        print("-" * 40)
        while True:
            try:
                stem = input("\n请输入题目: ").strip()
                if stem.lower() in ('quit', 'exit', 'q'):
                    break
                if not stem:
                    continue
                result = classifier.classify(stem)
                print(f"\n  章节: {result['chapter']}")
                print(f"  题型: {json.dumps(result['knowledge_weights'], ensure_ascii=False)}")
                print(f"  置信度: {result['confidence']}")
            except (KeyboardInterrupt, EOFError):
                break
        print("\n再见!")
        return

    # 默认: 显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()
