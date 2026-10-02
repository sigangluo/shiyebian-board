// 「数据概览」的纯逻辑（不碰 DOM，tests/stats.test.js 在 node 里测它）：把岗位按几个维度分桶、统计岗位数和招聘人数。
// 分桶只用 export.py 已经解析好的字段（el 学历层次、kc/kb/kg 专业类型、zb/pn/fo 考生类别、xy 经历年限、amx 年龄上限），不另写文字解析。
(function () {
  "use strict";

  // 专业要求看哪一栏：研究生层次的岗位先看研究生栏，其余先看本科栏（和 app.js 的 majorText 一致）
  function majorKind(j) {
    const cols = j.el >= 3 ? [j.kg, j.kb, j.kc] : [j.kb, j.kc, j.kg];
    const k = cols.find(Boolean);
    return k === "u" ? "open" : k ? "limited" : "unknown";
  }

  const bucketBy = (pairs, fn) => ({ buckets: pairs, of: fn });

  const STATIC = [
    { key: "edu", title: "学历要求", note: "按岗位写明的学历层次，「本科及以上」「本科」都算本科",
      ...bucketBy([["1", "大专"], ["2", "本科"], ["3", "硕士研究生"], ["4", "博士研究生"], ["0", "未写明"]], (j) => String(j.el || 0)) },
    { key: "mk", title: "专业要求", note: "「不限」指专业栏写明不限；其余写了专业代码或专业名称的都算限定专业",
      ...bucketBy([["open", "专业不限"], ["limited", "限定专业"], ["unknown", "未写明"]], majorKind) },
    { key: "cat", title: "考生类别", note: "来自岗位表的「考生类别」或「招聘对象」",
      ...bucketBy([["fo", "限应届毕业生"], ["pn", "限往届 / 社会人员"], ["zb", "限在编人员"], ["open", "不限"]],
        (j) => (j.fo ? "fo" : j.pn ? "pn" : j.zb ? "zb" : "open")) },
    { key: "xp", title: "工作经历要求", note: "年限取岗位表里的最低要求；写了要求但认不出年限的归「年限不明」",
      ...bucketBy([["0", "无要求"], ["1", "1 年及以下"], ["2", "2 年"], ["3", "3 年及以上"], ["x", "年限不明"]],
        (j) => (j.xy === undefined || j.xy === 0 ? "0" : j.xy === null ? "x" : j.xy <= 1 ? "1" : j.xy <= 2 ? "2" : "3")) },
    { key: "age", title: "年龄上限", note: "取岗位表里的基本年龄上限，不含硕士、博士的放宽",
      ...bucketBy([["35", "35 岁及以下"], ["38", "36–38 岁"], ["40", "39–40 岁"], ["41", "41 岁及以上"], ["0", "未写明"]],
        (j) => (!j.amx ? "0" : j.amx <= 35 ? "35" : j.amx <= 38 ? "38" : j.amx <= 40 ? "40" : "41")) },
  ];

  // 全部维度；地区的桶来自 index.json 的 regions，所以由调用方传进来
  function dims(regions) {
    const region = { key: "region", title: "地区", note: "", ...bucketBy(regions.map((r) => [r.key, r.name]), (j) => j.r) };
    return [region, ...STATIC];
  }

  const heads = (j) => j.n || 0;

  // 某个维度的统计：每个桶的岗位数和招聘人数，按桶的固定顺序；没有岗位的桶也保留（值为 0），前端自己决定是否隐藏
  function tally(jobs, dim) {
    const rows = dim.buckets.map(([id, label]) => ({ id, label, jobs: 0, heads: 0 }));
    const at = new Map(rows.map((r) => [r.id, r]));
    for (const j of jobs) {
      const r = at.get(dim.of(j));
      if (r) { r.jobs++; r.heads += heads(j); }
    }
    return rows;
  }

  // 总览：岗位数、招聘人数、涉及单位数
  function summary(jobs) {
    const units = new Set();
    let n = 0;
    for (const j of jobs) { n += heads(j); units.add(`${j.r}|${j.un}`); }
    return { jobs: jobs.length, heads: n, units: units.size };
  }

  const Stats = { dims, tally, summary, majorKind };
  if (typeof module !== "undefined" && module.exports) module.exports = Stats;
  else window.Stats = Stats;
})();
