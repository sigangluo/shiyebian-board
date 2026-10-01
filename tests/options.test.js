// 「我的条件」表单的选项逻辑：专业目录 → 对口关键词、工作情况、户籍 ↔ 省市、证书。运行：node --test
const test = require("node:test");
const assert = require("node:assert/strict");
const Options = require("../site/assets/options.js");
const opts = require("../site/assets/options.json");
const cat = Options.catalog(opts);
const entry = (level, code) => cat[level].find((e) => e.code === code);

test("目录：数量和关键条目", () => {
  assert.ok(cat.bachelor.length >= 800 && cat.graduate.length >= 150 && cat.college.length >= 650);
  assert.equal(entry("bachelor", "080902").name, "软件工程");
  assert.equal(entry("bachelor", "080902").cls, "计算机类");
  assert.equal(entry("graduate", "0812").name, "计算机科学与技术");
  assert.equal(entry("graduate", "0854").pro, true);
  assert.equal(new Set(cat.bachelor.map((e) => e.code)).size, cat.bachelor.length);
});

test("stem：名称 → 简称", () => {
  const cases = { 计算机科学与技术: "计算机", 软件工程: "软件", 电子信息工程: "电子信息", 会计学: "会计", 临床医学: "临床医学",
    汉语言文学: "汉语言文学", 计算机类: "计算机", 经济学类: "经济", 法学: "法学", 数学: "数学", 数据科学与大数据技术: "数据科学与大数据技术" };
  for (const [name, want] of Object.entries(cases)) assert.equal(Options.stem(name), want, name);
});

test("derive：计算机硕士（研究生 + 本科）", () => {
  const g = Options.derive("graduate", [entry("graduate", "0812")], opts);
  assert.deepEqual(g.keywords.slice(0, 1), ["计算机"]);
  for (const k of ["工学", "理工", "工科"]) assert.ok(g.keywords.includes(k), k);
  for (const r of ["软件", "信息", "电子", "网络", "数据", "通信", "人工智能", "自动化"]) assert.ok(g.related.includes(r), r);
  assert.ok(!g.related.includes("计算机"), "关键词不重复放进相关词");
  const b = Options.derive("bachelor", [entry("bachelor", "080902")], opts);
  assert.ok(b.keywords.includes("计算机") && b.keywords.includes("软件") && b.keywords.includes("工学"));
  assert.ok(b.related.includes("数据"));
});

test("derive：不在任何关联组里的专业只有名称和门类词；自定义项只用名称", () => {
  const d = Options.derive("bachelor", [entry("bachelor", "010101")], opts);   // 哲学
  assert.deepEqual(d, { keywords: [], related: [] });                           // 名称本身已经够了
  const e = Options.derive("bachelor", [entry("bachelor", "020101")], opts);    // 经济学：在「经济金融财会」组
  assert.deepEqual(e.keywords, ["经济"]);     // 名称「经济学」本身就匹配，不重复放进关键词
  assert.ok(e.related.includes("金融") && !e.related.includes("经济"));
  const c = Options.derive("graduate", [Options.customPick("graduate", "软件工程专业")], opts);
  assert.deepEqual(c.keywords, []);
  assert.deepEqual(c.related, []);
  assert.deepEqual(Options.derive("graduate", [Options.customPick("graduate", "电气工程")], opts).keywords, ["电气"]);
});

test("profile ↔ 选中项：往返不丢", () => {
  const spec = { codes: ["A0812", "A0854"], names: ["计算机科学与技术", "电子信息"] };
  const picks = Options.fromProfile("graduate", spec, cat);
  assert.deepEqual(picks.map((p) => p.code), ["0812", "0854"]);
  assert.deepEqual(Options.toProfile("graduate", picks), spec);
  // 只有名称：按名称找；认不出的代码原样保留
  const p2 = Options.fromProfile("graduate", { codes: ["A081203"], names: ["计算机"] }, cat);
  assert.deepEqual(Options.toProfile("graduate", p2), { codes: ["A081203"], names: ["计算机"] });
  const p3 = Options.fromProfile("bachelor", { codes: ["B080902"], names: [] }, cat);
  assert.deepEqual(Options.toProfile("bachelor", p3), { codes: ["B080902"], names: ["软件工程"] });
  assert.deepEqual(Options.toProfile("bachelor", Options.fromProfile("bachelor", undefined, cat)), { codes: [], names: [] });
});

test("customPick：像代码的按代码，其余按名称", () => {
  assert.equal(Options.customPick("graduate", "081203").rawCode, "A081203");
  assert.equal(Options.customPick("bachelor", "b080902").rawCode, "B080902");
  const n = Options.customPick("graduate", "计算机应用技术");
  assert.equal(n.rawCode, undefined);
  assert.equal(n.name, "计算机应用技术");
});

test("工作情况：五种状态往返；什么都没填就是还没工作过", () => {
  for (const [state] of Options.WORK_STATES) assert.equal(Options.workState(Options.workFlags(state)), state);
  assert.equal(Options.workState({}), "none");
  assert.equal(Options.workState({ employed_now: null, had_staff_job: null, had_any_job: null }), "none");
  assert.deepEqual(Options.workFlags(""), { employed_now: false, had_staff_job: false, had_any_job: false });
  assert.equal(Options.workState({ had_any_job: true }), "left");
});

test("户籍 ↔ 省 + 市", () => {
  const P = opts.places;
  assert.deepEqual(Options.hukouToSelect(["广东", "汕头"], P), { prov: "广东", city: "汕头", extra: [] });
  assert.deepEqual(Options.hukouToSelect("汕头", P), { prov: "广东", city: "汕头", extra: [] });
  assert.deepEqual(Options.hukouToSelect(["广东省", "深圳市"], P), { prov: "广东", city: "深圳", extra: [] });
  assert.deepEqual(Options.hukouToSelect(["上海"], P), { prov: "上海", city: "", extra: [] });
  assert.deepEqual(Options.hukouToSelect(["吉林", "吉林"], P), { prov: "吉林", city: "吉林", extra: [] });
  assert.deepEqual(Options.hukouToSelect(["火星"], P), { prov: "", city: "", extra: ["火星"] });
  assert.deepEqual(Options.hukouFromSelect("广东", "汕头", []), ["广东", "汕头"]);
  assert.deepEqual(Options.hukouFromSelect("", "", ["火星"]), ["火星"]);
});

test("证书：选项 ↔ tokens，认不出的保留", () => {
  const picks = Options.certsFromProfile(["教师资格", "软考", "计算机技术与软件", "六西格玛"], opts.certs);
  assert.deepEqual(picks.map((p) => p.label), ["教师资格证", "计算机技术与软件资格（软考）", "六西格玛"]);
  assert.deepEqual(Options.certsToProfile(picks), ["教师资格", "软考", "计算机技术与软件", "六西格玛"]);
  assert.deepEqual(Options.certsFromProfile([], opts.certs), []);
});

test("居住证城市选项：直辖市一项，其余按地级市", () => {
  const items = Options.placeItems(opts.places);
  assert.ok(items.some((i) => i.value === "上海" && i.group === "直辖市"));
  assert.ok(items.some((i) => i.value === "深圳" && i.sub === "广东"));
  assert.equal(new Set(items.map((i) => i.key)).size, items.length);
});
