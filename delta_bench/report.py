"""Offline HTML report. All data is escaped, including JSON."""
import html
import json


def render_html(result):
    e = lambda value: html.escape(str(value), quote=True)
    status = 'PASS' if result['passed'] else 'FAIL'
    rows = ''.join('<tr>' + ''.join(f'<td>{e(v)}</td>' for v in
                   [name, stats['count'], stats['mae'], stats['rmse'],
                    stats['max_difference'], stats['mismatches']]) + '</tr>'
                   for name, stats in result['columns'].items())
    detail = e(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>delta-bench · {status}</title><style>
body{{font:16px system-ui;background:#101e29;color:#e8f4f2;margin:3rem auto;max-width:1100px;padding:0 1rem}}
h1{{color:#62e3bf}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:.8rem;border-bottom:1px solid #456}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#172c39;padding:1rem}}.summary{{font-size:1.2rem}}
</style><h1>Δ delta-bench / {status}</h1><p class="summary">已比较 {result['compared_rows']} 行 · 缺失 {len(result['missing_rows'])} 行 · 新增 {len(result['additional_rows'])} 行</p>
<p>判定：|candidate − baseline| ≤ atol + rtol × |baseline|。指标只覆盖双方共有键。</p>
<table><thead><tr><th>列</th><th>行数</th><th>MAE</th><th>RMSE</th><th>最大差异</th><th>超差数</th></tr></thead><tbody>{rows}</tbody></table>
<h2>完整机器报告</h2><pre>{detail}</pre></html>'''
