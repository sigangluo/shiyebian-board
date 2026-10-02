// 「数据概览」的分桶和统计。运行：node --test
const test = require("node:test");
const assert = require("node:assert/strict");
const Stats = require("../site/assets/stats.js");

const regions = [["a", "甲地"], ["b", "乙地"]].map(([key, name]) => ({ key, name }));
const dims = Object.fromEntries(Stats.dims(regions).map((d) => [d.key, d]));
const bucket = (key, j) => dims[key].of(j);

test("学历：按层次分桶，没有写明的归 0", () => {
  assert.equal(bucket("edu", { el: 2 }), "2");
  assert.equal(bucket("edu", { el: 3, ep: true }), "3");
  assert.equal(bucket("edu", {}), "0");
  assert.equal(bucket("edu", { el: null }), "0");
});

test("专业：研究生岗位先看研究生栏，其余先看本科栏", () => {
  assert.equal(bucket("mk", { el: 3, kg: "u", kb: "c" }), "open");
  assert.equal(bucket("mk", { el: 2, kb: "c", kg: "u" }), "limited");
  assert.equal(bucket("mk", { el: 3, kb: "t" }), "limited");     // 研究生栏是空栏，退回本科栏
  assert.equal(bucket("mk", { el: 1 }), "unknown");
});

test("考生类别：限应届 > 限往届 > 限在编 > 不限", () => {
  assert.equal(bucket("cat", { fo: true }), "fo");
  assert.equal(bucket("cat", { pn: true }), "pn");
  assert.equal(bucket("cat", { zb: true }), "zb");
  assert.equal(bucket("cat", {}), "open");
});

test("工作经历：没有字段 = 无要求，null = 年限不明", () => {
  assert.equal(bucket("xp", {}), "0");
  assert.equal(bucket("xp", { xy: null }), "x");
  assert.equal(bucket("xp", { xy: 1 }), "1");
  assert.equal(bucket("xp", { xy: 1.2 }), "2");
  assert.equal(bucket("xp", { xy: 2 }), "2");
  assert.equal(bucket("xp", { xy: 5 }), "3");
});

test("年龄上限的分档边界", () => {
  for (const [amx, want] of [[undefined, "0"], [35, "35"], [36, "38"], [38, "38"], [39, "40"], [40, "40"], [45, "41"]]) assert.equal(bucket("age", { amx }), want, String(amx));
});

test("统计：岗位数、招聘人数按桶累加，空桶保留为 0", () => {
  const jobs = [{ r: "a", n: 2, un: "x" }, { r: "a", n: 3, un: "x" }, { r: "b", n: 1, un: "y" }];
  const rows = Stats.tally(jobs, dims.region);
  assert.deepEqual(rows.map((r) => [r.id, r.jobs, r.heads]), [["a", 2, 5], ["b", 1, 1]]);
  const edu = Stats.tally(jobs, dims.edu);
  assert.equal(edu.length, 5);
  assert.equal(edu.find((r) => r.id === "0").jobs, 3);
  assert.equal(edu.find((r) => r.id === "2").jobs, 0);
});

test("总览：同一地区同名单位只算一个", () => {
  const s = Stats.summary([{ r: "a", n: 2, un: "x" }, { r: "a", n: 3, un: "x" }, { r: "b", n: 1, un: "x" }]);
  assert.deepEqual(s, { jobs: 3, heads: 6, units: 2 });
});

test("每个桶 id 都不重复，且所有维度的桶覆盖分桶函数的输出", () => {
  for (const d of Object.values(dims)) assert.equal(new Set(d.buckets.map(([id]) => id)).size, d.buckets.length, d.key);
});
