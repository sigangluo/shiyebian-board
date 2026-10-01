"""读岗位表 Excel（.xlsx 和旧的 .xls 都行）：每个 sheet 找到表头行，返回 [(sheet 名, [{列名: 值}, ...])]。

各地岗位表的 sheet 数量、表头位置、列名都不一样，所以这里只做通用的部分：
用「必须出现的列名」定位表头（前几行里找），空行跳过，列名去掉空白和换行。解析成标准字段由各地区的 fetch.py 做。
有的岗位表表头占两行（上一行是大类、下一行是具体列名，如深圳），用 header_rows=2：每一列取各行里「最下面那个非空的名字」。
"""
import re
from pathlib import Path

from .http import FetchError


def clean(v):
    """单元格 -> 字符串或 None。去掉首尾空白；连续的空行压成一个换行。"""
    if v is None:
        return None
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    s = re.sub(r"\n\s*\n+", "\n", str(v).replace("\r", "")).strip()
    return s or None


def _sheets(path):
    """统一成 ([(sheet 名, 行的迭代器)], 需要关闭的 workbook 或 None)。.xls 用 xlrd，.xlsx 用 openpyxl。"""
    if Path(path).suffix.lower() == ".xls":
        import xlrd
        wb = xlrd.open_workbook(str(path))
        return [(ws.name, (ws.row_values(i) for i in range(ws.nrows))) for ws in wb.sheets()], None
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    return [(ws.title, ws.iter_rows(values_only=True)) for ws in wb.worksheets], wb


def _header_name(cell):
    return re.sub(r"\s+", "", clean(cell) or "")


def read_sheets(path, require, scan=8, skip_sheets=(), header_rows=1):
    """读 path 里所有 sheet。

    require:     表头必须包含的列名（如 ("岗位代码", "招聘单位")），用来定位表头，也用来发现岗位表格式变了。
    header_rows: 表头占几行。
    没找到表头的 sheet：如果有数据就抛 FetchError（岗位表变了，不能悄悄漏掉），完全空的 sheet 跳过。
    """
    sheets, wb = _sheets(path)
    out = []
    for title, rows in sheets:
        if title in skip_sheets:
            continue
        rows = iter(rows)
        head = []                                   # 预读的前几行，原样保留（表头之后的行还要当数据用）
        for _ in range(scan + header_rows):
            row = next(rows, None)
            if row is None:
                break
            head.append(list(row))
        header, start = None, None
        for i in range(min(scan, len(head))):
            block = head[i:i + header_rows]
            width = max(len(r) for r in block)
            names = [next((n for n in (_header_name(r[c]) for r in reversed(block) if c < len(r)) if n), "")
                     for c in range(width)]
            if all(r in names for r in require):
                header, start = names, i + header_rows
                break
        if header is None:
            if any(any(_header_name(c) for c in r) for r in head) and len(head) >= scan:
                raise FetchError(f"sheet「{title}」前 {scan} 行里找不到包含 {list(require)} 的表头，岗位表格式可能变了")
            continue
        data = []
        for row in [*head[start:], *rows]:
            rec = {h: clean(c) for h, c in zip(header, row) if h}
            if rec.get(require[0]):           # 第一个必需列为空的行（空行、页脚备注）直接跳过
                data.append(rec)
        out.append((title, data))
    if wb is not None:
        wb.close()
    if not out:
        raise FetchError(f"{path} 里没有任何 sheet 含有 {list(require)} 这些列")
    return out
