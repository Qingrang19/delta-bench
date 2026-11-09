# delta-bench

![delta-bench 标识](assets/logo.svg)

**为 EIT（电阻抗成像）数值流水线提供可解释、离线、可接入 CI 的 CSV 回归门禁。**

把已确认的基线输出与候选输出按唯一键对齐，显式选择数值列，得到机器 JSON 和无需网络的 HTML 报告。示例全部为合成数据，不含真实患者或设备数据。本工具只比较输出，不执行 EIT 重建、不评价临床有效性。

## 快速运行

Python 3.10+，运行及测试仅使用标准库，不需要 pip 安装。进入项目根目录：

```sh
mkdir -p reports
python -m delta_bench examples/baseline.csv examples/candidate-pass.csv \
  --key frame --columns conductivity,residual --atol 0.0001 --rtol 0.001 \
  --json reports/pass.json --html reports/pass.html
# 退出码 0：通过

python -m delta_bench examples/baseline.csv examples/candidate-fail.csv \
  --key frame --columns conductivity,residual --atol 0.0001 --rtol 0.001 \
  --json reports/fail.json --html reports/fail.html
# 退出码 1：超差、缺行或新增行

python -m unittest discover -s tests -v
```

直接在浏览器打开 `reports/pass.html` 或 `reports/fail.html`。报告没有脚本、外部字体、CDN 或遥测。stdout 始终是 JSON；`--json` / `--html` 额外写入本地文件。父目录须已存在，已有报告文件会覆盖，但禁止覆盖输入或让两个报告共用同一路径。

## 判定与指标

对每个共有键、每个选定列，以基线值 b 和候选值 c 计算：

- 差异 d = |c − b|。
- 容差 t = atol + rtol × |b|；**d ≤ t 通过**，等号包含在内。
- 相对容差只相对基线，不相对候选，也不取两者最大值，因此比较有方向性。
- 默认 atol = rtol = 0，意味着严格浮点数值相等。基线为零时只靠绝对容差。
- 每列 MAE = Σd / n，RMSE = sqrt(Σd² / n)，最大差异 = max(d)。所有指标包含共有键中的通过与失败单元格，不包括无匹配键。
- 超差明细记录键、列、两值、差异及实际容差；缺失与新增键分别列出。
- 任意超差、缺失键、新增键或零共有键导致整体失败。零共有键的列指标为 JSON null，列 passed 为 false。
- 浮点运算使用 Python binary64。CSV 文本 `1` 与 `1.0` 数值相等。容差应按物理单位、噪声与科学验证结果设置，而不是只为让 CI 通过。

## 数据契约

CSV 使用逗号分隔、UTF-8（兼容 BOM），第一行为非空且不重复的列名。键按原始字符串精确匹配，顺序无关，键必须非空且唯一；不会自动去掉键的前后空格。`--columns` 接受以逗号分隔的列名，必须唯一且不含键列；两份文件都必须包含它们。未选择的辅助列不比较，额外辅助列允许存在。

拒绝：空数据、重复键、重复列名、行宽不一致、缺少所选列、非数字或非有限数值（NaN/±Inf）、负或非有限容差。没有配对的行也必须满足所选数值列契约。差值或容差运算超出浮点范围同样拒绝。

## CLI 与 CI

| 退出码 | 意义 | 建议 |
| --- | --- | --- |
| 0 | 全部通过 | 允许流水线继续 |
| 1 | 有效输入但回归失败 | 检查明细，不应自动替换基线 |
| 2 | 输入、参数或报告写入错误 | 修复输入或环境后重跑 |

无效输入时 stderr 输出错误 JSON（argparse 参数语法错误使用其标准错误文本）。报告只在有效比较后产生，不应依赖旧文件作为当前结果；报告写入不是多文件原子事务，任一写失败必须按退出码 2 处理。建议 CI 每次使用新的输出目录并保存 stdout、stderr 及退出码。

JSON `schema_version: 1` 包含 passed、基线/候选路径、容差、行数、missing_rows、additional_rows、columns（各列统计）、mismatches（全部超差项）。列表顺序确定：键按字符串排序，列按 CLI 选择顺序输出。

## 架构

```text
delta_bench/core.py       CSV 校验、键对齐、容差与指标
           /report.py    HTML 转义和离线报告
           /__main__.py  CLI、文件写入、CI 退出码
tests/test_delta.py      标准库 unittest，包含错误及边界覆盖
examples/                三份合成 EIT 数值快照
assets/logo.svg          双轨信号 / 三角比较门标识
```

没有运行时第三方依赖；模块可直接导入 `delta_bench.core.compare` 做本地集成。核心逻辑不依赖报告 UI。

## 安全、范围与限制

- 全量载入内存，复杂度大致 O(行数 × 选定列数)，排序另加 O(行数 log 行数)；不适合无限流或超大数据。报告包含全部超差，可能较大。
- 不做单位转换、插值、模糊键匹配、统计显著性检验或临床诊断。请先对齐物理量和坐标系。
- 明细会包含原始键与选定数值，HTML/JSON 是数据副本，分享前检查隐私。HTML 对输入字符串转义，但这不等于匿名化。
- 不监听端口、不联网、不上传、不自动更新基线、不运行候选程序。

## 验证

```sh
python -m unittest discover -s tests -v
python -m compileall -q delta_bench
```

包含键对齐、组合容差、基线方向性、指标、非有限值、重复键、畸形 CSV、HTML 注入转义、输出保护及 CLI 报告测试。示例 smoke 的 0/1 退出码需分别验证，失败例本身不是测试失败。
