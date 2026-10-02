# 事业编岗位看板

各地人社部门公布的事业单位招聘岗位表 → `data/<地区>/<批次>.csv`（保留原文）→ `build.py` 导出全部岗位（原文 + 解析好的字段）→ `site/` 看板在**浏览器里**按访问者填的个人条件筛选。README 见 [../README.md](../README.md)。

**地区不是固定的。** 后续会陆续接入新地区，所以任何脚本、页面、文档里都不要写死地区名或数量；地区列表唯一的来源是 `regions/` 目录。

## 目录

```
regions/<key>/fetch.py   每个地区只有这一个文件：META（元信息 + 批次）+ fetch()（下载并解析岗位表）。自动发现
regions/_template/       新增地区的模板（下划线开头的目录不会被当成地区）
scripts/update.py        入口：并行抓取 + 合并
scripts/fetch_region.py  抓取单个地区 → 校验 → 写 data/<key>/<批次>.csv
scripts/build.py         data/*/*.csv → site/data（全部岗位，**不筛选**；有 profile.json 时只打印摘要并生成仅限本机的 profile.local.json）
scripts/publish.py       用 build.py --public 构建到临时目录，检查不含个人条件，再发布到 gh-pages
site/prep.html           备考指南（流程、各批次考试与成绩摘要、复习和面试建议）；assets/prep.js 渲染批次部分，assets/exam.js 是摘要的共用渲染
scripts/lib/             schema.py（统一岗位格式）、match.py（Python 版匹配规则）、export.py（导出成前端格式 + 解析字段）、conditions.py（拆「其它条件」）、normalize.py（统一写法）、xlsx.py、http.py、regions.py（自动发现）
site/assets/match.js     JS 版匹配规则（浏览器里用）；assets/app.js 是界面；picker.js 可搜索的选择控件；options.js 表单选项逻辑（纯函数，node 测试）；options.json 选项数据（scripts/build_options.py 从教育部目录生成，已提交）
tests/golden/cases.json  Python 版算出的「岗位 + 条件 → 结果」样例，JS 测试逐条核对
profile.json             可选，个人条件，只在本机，已被 .gitignore；profile.example.json 是模板
raw/                     下载的岗位表原件（不进 git）
site/                    静态看板；site/data/ 全是生成物，不要手改
```

## 设计要点（改之前先读）

- **服务端（构建时）不筛选，个人条件只在浏览器里。** 公开站点包含全部岗位；访问者在「我的条件」表单里填条件，存在 localStorage，筛选在 `site/assets/match.js` 里完成，没有任何数据上传。**绝不能把个人条件写进公开发布的文件**：`build.py --public` 不读 `profile.json`，`publish.py` 还会检查发布目录。
- **解析和比较分开，匹配规则有两份。** 文字解析（学历、专业代码、经历年限、年龄上限、考生类别、户籍写法……）只在 Python 里做，结果由 `lib/export.py` 导出成岗位上的字段（字段说明在该文件开头）；`match.js` 只做「岗位字段 vs 你的条件」的比较，是 `match.py` 里 `evaluate()` 的逐段移植，**提示文字、判断顺序必须一致**。改规则要两边一起改，然后 `python3 tests/make_golden.py` 重新生成交叉测试样例，再 `node --test` 核对（样例里有 2940 条，一个字的提示差异都会报错）。加新的解析字段：先在 `export.py` 导出，再让 `match.py` 和 `match.js` 都用它。
- **三档：ok / check / no。** 宁可多放进 check，也不要把可能能报的判成 no（no 默认不出现在看板里，用户看不到就没法纠错）。页面上「匹配度」选「全部」可以看到 no 和原因，调试规则时用。
- **没填的条件不参与筛选**（`age`、`politics`、`hukou`、本科专业……），只在页面的「尚未填写」里提示。不要替用户猜。唯一的默认值是工作情况：「尚未工作过」（看板的使用者包括没有任何工作经历的应届毕业生，Python 版里没填 = False 也是这个意思）。
- **条件表单以选择为主，不让用户手填代码**：专业从官方目录里搜索 / 按门类选（`picker.js`），选中后由 `options.js` 的 `derive` 生成对口关键词 / 相关词（关联组在 `build_options.py` 的 `CLUSTERS`，改它不需要联网）；户籍是省 + 市下拉；证书是常见项 + 允许自填。profile 的格式不变，所以 profile.json、导入导出和 Python 版都不受影响。
- **界面文字用书面语**：不用「你」这类口语，指代使用者时写「考生」或用「所填……」「未填写」等中性说法；匹配提示（match.py / match.js 里的 check / no 文案）也一样，两边要同步改，再 `python3 tests/make_golden.py` 重新生成样例。
- **应届身份各地口径不同**，必须从公告 / 报考指南里**读原文**，摘录进批次的 `fresh_note`（**只放官方原文的内容，不写任何自己的判断或推断**，如「所以按应届处理」「公告没写……」「判断标准是……」；出处写进 `fresh_src`，如「招聘公告」「公告附件3《…》第 1 问」，页面会显示成「依据：…」，必须是核对过的真实条款），再把规则写成批次的 `fresh_rule`（`kind`：`year` 按毕业年份 / `year_window` 毕业 N 年内都算应届、不看是否在职 / `unemployed` 毕业 N 年内且报名时无工作单位 / `no_staff_job` 毕业 N 年内且未落实编制内工作 / `unplaced` 非在职且未落实工作单位；`cohort` 是该批次应届对应的毕业年份）。`fresh_verdict` 用它结合个人条件里的 `graduate_year`、`employed_now`、`had_staff_job`、`had_any_job` 推断用户在该批次算不算应届；已结束的批次假设下一批规则不变、届别顺延一年。公告没写清楚的情形（如入职过又离职算不算「落实」）返回 `maybe`，不要替用户拍板。读不到原文就不要写 `fresh_rule`（不写就是 `maybe`）。个人条件里 `fresh` 设成 `yes/no/maybe` 可以覆盖推断。批次的 `fresh_rule` 会导出给前端，已结束的批次由前端按今天的日期加 `closed` 标记。
- **岗位表的格式千差万别**：表头层数不同（`read_sheets(header_rows=…)`）、合并单元格只有第一行有值（要向下填充，见 jiangsu）、`.xls` 和 `.xlsx` 都有、专业有的带代码（A0812 / 0812 / 08）有的只有文字。**专业只有一栏的表**用 `normalize.major_columns` 按学历要求放进对应的栏；只有文字的靠个人条件里的 `keywords / related` 匹配。「其它条件」写成一段话的，用 `conditions.split_conditions` 拆成年龄、政治面貌、经历、证书、职称、专项、户籍，认不出来的留在 `other`（宁可多提醒）。
- **新接一个地区后，一定要抽查**：对着原岗位表看几个岗位的字段是否对；把被判「不符」的计算机相关岗位拉出来看原因是否站得住（页面上「匹配度」选「全部」，或用 profile.json 跑 Python 版）。这样找出过证书误判、专业放错栏、合并单元格等一批问题。
- **只要求较低学历的岗位**（如硕士看到「本科」岗位）：只能以较低学历及其专业报考，很多地方不允许，所以一律「待确认」并标 `lo`。
- **专业按代码前缀比对**：岗位写 A08 涵盖 A0812 → 符合；岗位写得比用户更细（A081201）→ 待确认；只有名称又对不上 → 待确认，不判不符。
- **批次有状态**：有 `signup_start/end` 就按**今天的日期**（前端在浏览器里算，不是构建日期）算报名中 / 即将开始 / 已结束；没有就是滚动招聘。已结束的批次保留，作往年参考，并按去年同期推算下一批。
- **只抓官方网站的公开信息**，岗位要求照抄原文，不改写。
- **每个批次都要写 `exam_info`（考试与成绩摘要）**：笔试科目 / 时间、入围面试规则、面试、总成绩计算、体检至聘用、需要留意的事项，加上 `sources`（官方页面，https）和 `checked`（核对日期）。**只依据官方公告 / 大纲原文**；公告没写的写「公告未写明」，不要用第三方培训机构的说法补（它们常把往年的题型当成官方口径）。格式由 `lib/regions.py` 的 `check_exam_info` 校验，`tests/test_regions.py` 要求所有批次都有。内容会显示在批次卡片（`assets/exam.js`）和备考指南 `site/prep.html`。
- **备考指南 `prep.html` 里不写地区名**：各批次的考试差异全部来自 `exam_info`，页面运行时从 `data/index.json` 渲染；静态正文只写各地共通的流程和**标明「非官方」的一般性建议**。新增地区时不需要改这个页面。

## 用户说「更新一下数据」时

```bash
python3 scripts/update.py        # 并行抓取所有地区 + 合并
```

1. **看输出**：每个地区应该显示「完成」。任何一个「失败」都会中止且不合并，按提示 `--only <key>` 重抓，再 `update.py --build-only`。
2. **核对数量**：出现 `⚠ 岗位数 A -> B，减少超过 30%` 多半是抓取不全，不要直接接受，先重跑那个地区。
3. **看有没有新批次**：各地官网的招聘栏目（`META["list_url"]`）有没有发布新公告。新批次要手动加进 `META["batches"]`（见下）。
4. **本地预览**：`python3 scripts/serve.py`。不能直接双击 html（`fetch` 会被 file:// 拦住）。
5. 告诉用户：各批次岗位数、有没有 ⚠，以及哪些批次正在报名或即将报名。

**发布**（`python3 scripts/publish.py`，默认只构建和检查）：属于对外发布，**得到用户确认后**才加 `--push`。强制推送会覆盖线上内容，提交作者用本仓库 `git config` 里的公开身份（GitHub noreply 邮箱），不要用内网 / 公司邮箱。也不要自动 commit，除非用户明确要求。

改了规则后跑两套测试：`python3 -m unittest discover -s tests` 和 `node --test`。

## 新增一个批次

同一地区的新公告：在 `regions/<key>/fetch.py` 的 `META["batches"]` 加一项（key 要稳定，如 `2027-jizhong`）：公告页 `notice_url`、岗位表 `table_url`、`published`、`signup_start/end`、`min_jobs`、`fresh_note`。岗位表的列名如果变了，更新该文件的 `COLUMNS`；`read_sheets` 找不到表头会直接报错，不会悄悄漏数据。

## 新增一个地区

1. `cp -r regions/_template regions/<key>`，`<key>` 用拼音小写（同时是 `data/<key>/` 的目录名）。
2. 找到官方公告和岗位表。多数是公告页 + xlsx 附件：用 `lib.http.download` 下载（会检查文件头，防止把 200 状态的错误页当岗位表），`lib.xlsx.read_sheets` 读。网页里的岗位列表就用 requests，**抓不全就抛异常**，不要返回半截数据。
3. `fetch()` 返回 `make_job(...)` 的列表（字段说明见 `scripts/lib/schema.py`），各列保留原文。各地岗位表多出来的列放 `extra`。
4. 把公告 / 指南里对「应届」的定义摘进 `fresh_note`，并写 `fresh_src`（出处）。读原文，别凭印象，也不要加自己的解读；公告里没有的话（如「私企不算」「限本市户籍不能报」）不能写。
5. `python3 scripts/update.py --only <key>`，抽查结果：对着原岗位表核对几个岗位的学历、专业、考生类别。
6. 各地的字段口径不一样（有的有户籍、有的没有，有的专业用代码、有的只有名称）。如果现有字段表达不了，先扩 `schema.py` 和 `match.py`，并补测试，不要给某个地区开特例。

## 站点

- 纯静态，没有构建步骤、没有第三方依赖、不请求外部资源。地区、批次从 `data/index.json` 读，岗位从 `data/jobs/*.json` 读，前端没有任何地区名。岗位导出时空字段是省略的，加载后 `app.js` 把显示用的字符串字段补成空串（否则 `undefined` 会被渲染成文字或让排序报错）。
- 岗位文字都来自第三方站点：前端**只用 `textContent` / 文本节点渲染**，不拼 `innerHTML`；来自数据的链接只接受 `https://`。
- `replaceChildren(...)` 的参数里不能有 `null`（会渲染出 "null" 文字），先 `.filter(Boolean)`。
- 个人条件只存在 localStorage（key `shiye.profile.v1`）；读写都包在 try/catch 里，存不了就只对本次有效。导入导出的 JSON 和 `profile.json` 是同一个格式（未知字段原样保留）。
- 改了 `site/` 之后用 Playwright 在真实浏览器里验证：加载、填条件、筛选数字和 Python 版对得上、无控制台报错。
