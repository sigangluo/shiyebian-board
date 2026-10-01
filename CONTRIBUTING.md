# 参与贡献

欢迎提交 Issue 和 Pull Request。最有价值的贡献是：**接入新的地区 / 批次**、**修正岗位解析和匹配规则的错误**、**补充测试**。

## 开发环境

- Python 3.9+，Node 18+。
- `pip install -r requirements.txt`
- `python3 scripts/update.py` 抓取数据并生成看板数据，`python3 scripts/serve.py` 在本机预览（不能直接双击 html）。
- 只改代码、不改数据时，不需要抓取数据：`python3 -m unittest discover -s tests` 和 `node --test` 都可以直接运行。

## 提交前

```bash
python3 -m unittest discover -s tests
node --test
```

两个都要通过。CI 会在每次提交时运行同样的测试。

## 需要遵守的约定

完整说明在 [.claude/CLAUDE.md](.claude/CLAUDE.md)，这里列出最容易踩到的几条：

1. **匹配规则有 Python 和 JS 两份，必须一模一样。** 改 `scripts/lib/match.py` 的规则，必须同步改 `site/assets/match.js`（提示文字、判断顺序都要一致），再运行 `python3 tests/make_golden.py` 重新生成交叉测试样例（需要先抓取数据），最后跑 `node --test`。
2. **宁可多放进「待确认」，也不要把可能可报的岗位判为「不符」。**
3. **不替使用者猜。** 没填的条件不参与筛选，只在岗位详情里提示。
4. **岗位表的内容照抄原文，不改写。** 应届身份的规则必须读公告原文，摘录进批次的 `fresh_note`。
5. **只抓官方网站的公开信息。** 批次的 `exam_info`（考试与成绩摘要）同样只依据官方公告和考试大纲，不要照搬培训机构的说法。
6. **界面文字用书面语**，不用「你」等口语；匹配提示（`match.py` / `match.js` 里的文案）同理。
7. **个人条件只存在使用者自己的浏览器里。** 不要在任何会被发布的文件里写入个人条件；`profile.json` 已被 `.gitignore` 忽略，不要提交；测试里的条件请使用虚构的。
8. 前端不拼 `innerHTML`：岗位文字来自第三方网站，只用 `textContent` 渲染。

## 接入新地区

复制 `regions/_template`，实现 `fetch()`，其余文件不用改。步骤、需要抽查的地方见 [.claude/CLAUDE.md](.claude/CLAUDE.md#新增一个地区)。提交时请附上官方公告链接，并在 README 的「已接入的地区」表里补一行。每个批次需要写 `exam_info`（见 `regions/_template`），`python3 -m unittest discover -s tests` 会检查。

## 反馈数据错误

请使用 Issue 模板「岗位信息或匹配结果有误」，附上官方岗位表原文。**请不要在 Issue 里填写真实姓名、证件号等个人信息。**
