// 「我的条件」表单里和选项有关的纯逻辑（不碰 DOM，tests/options.test.js 在 node 里测它）：
// 专业目录 → 选项、选中的专业 → profile 里的 codes / names / keywords / related、工作情况 ↔ 三个布尔值、户籍 ↔ 省 + 市。
// 选项数据在 options.json（scripts/build_options.py 从教育部目录生成）。
(function () {
  "use strict";

  const LEVELS = ["graduate", "bachelor", "college"];
  const PREFIX = { graduate: "A", bachelor: "B", college: "C" };     // 岗位表里的写法：研究生 A0812、本科 B080902（浙江只写数字，比较时会去掉字母）
  const NO_CATEGORY_WORDS = new Set(["交叉学科"]);

  // 专业名称 → 岗位文字里可能出现的简称：计算机科学与技术 → 计算机；软件工程 → 软件；临床医学、汉语言文学保持原样
  function stem(name) {
    let n = String(name || "").replace(/类$/, "");
    if (/(医学|文学)$/.test(n)) return n;
    for (const suf of ["科学与技术", "科学与工程", "与技术", "工程", "科学", "学"]) {
      if (n.endsWith(suf) && n.length - suf.length >= 2) return n.slice(0, -suf.length);
    }
    return n;
  }

  const uniq = (a) => [...new Set(a.filter(Boolean))];

  // 把 options.json 里的数组变成对象：{ level, key, code, name, cat, cls, pro }
  function catalog(opts) {
    const out = {};
    for (const level of LEVELS) {
      out[level] = opts.majors[level].map((r) => ({
        level, key: `${level}:${r[0]}`, code: r[0], name: r[1], cat: r[2],
        cls: level === "graduate" ? "" : r[3], pro: level === "graduate" ? r[3] === 1 : false,
      }));
    }
    return out;
  }

  const codeOf = (level, pick) => (pick.rawCode ? pick.rawCode : pick.code ? PREFIX[level] + pick.code : "");

  // profile 里的 {codes, names} → 选中项。认得出的变成目录里的条目，认不出的（旧版目录的代码、手写的名称）原样保留成自定义项
  function fromProfile(level, spec, cat) {
    const picks = [], seen = new Set();
    const add = (p) => { if (!seen.has(p.key)) { seen.add(p.key); picks.push(p); } };
    const list = (x) => (Array.isArray(x) ? x : x ? [x] : []).map((s) => String(s).trim()).filter(Boolean);
    const entries = cat[level];
    const names = list(spec && spec.names);
    for (const raw of list(spec && spec.codes)) {
      const digits = raw.replace(/^[A-Za-z]/, "");
      const e = entries.find((x) => x.code === digits);
      if (e) add(e);
      else add({ level, key: `custom:${raw.toUpperCase()}`, code: "", rawCode: raw.toUpperCase(), name: raw.toUpperCase(), label: raw.toUpperCase(), custom: true });
    }
    for (const n of names) {
      if (picks.some((p) => p.name === n)) continue;
      const e = entries.find((x) => x.name === n && !x.pro) || entries.find((x) => x.name === n);
      if (e) add(e);
      else add({ level, key: `custom:${n}`, code: "", name: n, label: n, custom: true });
    }
    return picks;
  }

  // 搜不到时用户直接输入的文字：像专业代码的（A081203、0812、080902）按代码，其余按名称
  function customPick(level, text) {
    const t = String(text).trim();
    if (/^[A-Za-z]?\d{2,8}$/.test(t)) {
      const code = PREFIX[level] + t.replace(/^[A-Za-z]/, "");
      return { level, key: `custom:${code}`, code: "", rawCode: code, name: code, label: code, custom: true };
    }
    return { level, key: `custom:${t}`, code: "", name: t, label: t, custom: true };
  }

  // 选中项 → profile 里的 {codes, names}
  function toProfile(level, picks) {
    return {
      codes: uniq(picks.map((p) => codeOf(level, p))),
      names: uniq(picks.filter((p) => !(p.custom && p.rawCode)).map((p) => p.name)),
    };
  }

  // 选中的专业 → 对口关键词 keywords（岗位只写文字时，出现就算对口）和相关词 related（出现算待确认）
  function derive(level, picks, opts) {
    const names = uniq(picks.map((p) => p.name));
    const kws = [], terms = [];
    for (const p of picks) {
      const s = stem(p.name);
      if (s !== p.name && s.length >= 2) kws.push(s);
      if (p.custom || p.rawCode) continue;
      if (p.cls) { const c = stem(p.cls); if (c.length >= 2) kws.push(c); }
      if (level !== "college" && !NO_CATEGORY_WORDS.has(p.cat)) kws.push(...(opts.categoryWords[p.cat] || [p.cat]));
      if (level === "college") continue;
      for (const cl of opts.clusters) {
        if ((cl[level] || []).some((x) => x === p.cat || x === p.code.slice(0, 4))) terms.push(...cl.terms);
      }
    }
    const keywords = uniq(kws).filter((k) => !names.includes(k));
    const related = uniq(terms).filter((t) => !keywords.includes(t) && !names.includes(t));
    return { keywords, related };
  }

  // 工作情况：一个选项对应 employed_now / had_staff_job / had_any_job 三个布尔值。
  // 默认（未填写、旧版 profile 没有这三项）按「尚未工作过」处理：这是应届毕业生最常见的情况，也与 Python 版中未填 = False 一致
  const WORK_STATES = [
    ["none", "尚未工作过（应届毕业生及仅有实习经历者选此项）", { employed_now: false, had_staff_job: false, had_any_job: false }],
    ["left", "有工作经历，目前无工作（企业 / 编外）", { employed_now: false, had_staff_job: false, had_any_job: true }],
    ["working", "目前在职（企业 / 编外，不在编制内）", { employed_now: true, had_staff_job: false, had_any_job: true }],
    ["staff-past", "曾在编制内工作（事业编 / 公务员），现已离职", { employed_now: false, had_staff_job: true, had_any_job: true }],
    ["staff-now", "目前在编制内工作（事业编 / 公务员）", { employed_now: true, had_staff_job: true, had_any_job: true }],
  ];

  function workFlags(state) {
    return { ...(WORK_STATES.find((x) => x[0] === state) || WORK_STATES[0])[2] };
  }
  function workState(p) {
    if (p.had_staff_job) return p.employed_now ? "staff-now" : "staff-past";
    if (p.employed_now) return "working";
    return p.had_any_job ? "left" : "none";
  }

  // 户籍：profile 里是 ["广东", "揭阳"]（也可以只写一个，或带「省」「市」），表单里是省、市两个下拉框
  const shortProvince = (s) => s.replace(/(壮族|回族|维吾尔)?自治区$|特别行政区$|省$|市$/, "");
  function hukouToSelect(hukou, places) {
    const list = (Array.isArray(hukou) ? hukou : hukou ? [hukou] : []).map((s) => String(s).trim()).filter(Boolean);
    let prov = "", city = "";
    const extra = [];
    for (const raw of list) {
      const s = shortProvince(raw), t = s.endsWith("市") ? s.slice(0, -1) : s;
      const pv = places.find(([p]) => p === s);
      if (pv && !prov) { prov = pv[0]; continue; }
      const owner = places.find(([p, cs]) => (!prov || p === prov) && cs.includes(t));
      if (owner && !city) { prov = owner[0]; city = t; continue; }
      extra.push(raw);          // 认不出的写法原样带着，不丢
    }
    return { prov, city, extra };
  }
  const hukouFromSelect = (prov, city, extra) => [prov, city, ...(extra || [])].filter(Boolean);

  // 居住证城市的选项：每个地级市一项，直辖市本身一项
  function placeItems(places) {
    return places.flatMap(([prov, cities]) => (cities.length
      ? cities.map((c) => ({ key: `place:${prov}/${c}`, label: c, sub: prov, group: prov, code: "", value: c }))
      : [{ key: `place:${prov}`, label: prov, sub: "直辖市", group: "直辖市", code: "", value: prov }]));
  }

  // 证书：选项的 tokens 会进 profile.certs（match 用「包含」比较）；profile 里认不出的写法保留成自定义项
  function certsFromProfile(certs, options) {
    const held = (Array.isArray(certs) ? certs : certs ? [certs] : []).map((s) => String(s).trim()).filter(Boolean);
    const picks = [], used = new Set();
    options.forEach((o, i) => {
      if (o.tokens.some((t) => held.includes(t))) { picks.push({ key: `cert:${i}`, label: o.label, tokens: o.tokens }); o.tokens.forEach((t) => used.add(t)); }
    });
    for (const h of held) if (!used.has(h)) picks.push({ key: `custom:${h}`, label: h, tokens: [h], custom: true });
    return picks;
  }
  const certsToProfile = (picks) => uniq(picks.flatMap((p) => p.tokens));

  const Options = { stem, catalog, codeOf, fromProfile, customPick, toProfile, derive, WORK_STATES, workFlags, workState,
    shortProvince, hukouToSelect, hukouFromSelect, placeItems, certsFromProfile, certsToProfile };
  if (typeof module !== "undefined" && module.exports) module.exports = Options;
  else window.Options = Options;
})();
