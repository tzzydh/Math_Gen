# 吉林报考数据底座升级记录

日期：2026-04-12

## 本轮完成

- 新增资料库抽取脚本：`scripts/build_jilin_gaokao_json_index.py`
- 从 `资料库` 中标准化抽取吉林核心数据
- 生成吉林 JSON 索引：
  - `data/gaokao/normalized/jilin_library/jilin_major_baselines_2022_2025.json`
  - `data/gaokao/normalized/jilin_library/jilin_school_baselines_2022_2025.json`
  - `data/gaokao/normalized/jilin_library/jilin_enrollment_plans_2022_2025.json`
  - `data/gaokao/normalized/jilin_library/jilin_score_rank_2017_2025.json`
  - `data/gaokao/normalized/jilin_library/jilin_control_lines_2014_2022.json`
  - `data/gaokao/indexes/jilin_library/jilin_school_index.json`
  - `data/gaokao/indexes/jilin_library/jilin_major_index.json`
- 高考推荐引擎优先接入资料库的专业级聚合结果
- 推荐结果新增：
  - `plan_count`
  - `year_span`

## 数据量

- 专业录取线：69502 条
- 院校录取线：13579 条
- 招生计划：76859 条
- 一分一段：12990 条
- 控制线：49 条
- 学校索引：1493 条
- 专业索引：1285 条

## 已验证样例

### 1. 吉林物理类 455 分 / 39104 名 / 电子信息 / 长春

- 推荐数：12
- 扩展池：12
- 结果特征：从原来的稀疏学校池，升级成以吉林本地和周边真实电子信息专业线为主的池子

前 5 项：

1. 吉林工商学院 / 电子信息工程 / 稳档 / 2025-2022
2. 吉林工程技术师范学院 / 电子信息类 / 稳档 / 2022
3. 吉林农业大学 / 电子信息科学与技术 / 稳档 / 2025-2022
4. 吉林建筑大学 / 电子信息工程 / 稳档 / 2025-2022
5. 长春光华学院 / 电子信息工程 / 保档 / 2025-2022

### 2. 吉林物理类 623 分 / 自动换算位次 / 计算机 / 北京杭州

- 自动换算位次：2951
- 推荐数：12
- 结果特征：开始出现更像真实高分段的计算机类学校池

### 3. 吉林历史类 512 分 / 自动换算位次 / 师范 / 省内优先

- 自动换算位次：6954
- 推荐数：12
- 结果特征：推荐集中到长春师范相关方向，更符合地方师范/考编路径

## 当前提升

- 学校推荐不再只依赖 2025 的薄种子池
- 推荐开始具备多年份专业级依据
- 能直接展示“近几年都在招、计划人数大致多少”
- 电子信息、计算机、师范这类方向明显更像真实报考结果

## 下一步

1. 补学校层级、985/211/双一流、公办/民办、中外合作等元数据
2. 把 `00、志愿填报必备资料` 中的院校介绍和专业介绍接入
3. 让结果页展示“推荐依据 / 数据来源 / 近年波动”
4. 把扩展池升级成可筛选的志愿矩阵
