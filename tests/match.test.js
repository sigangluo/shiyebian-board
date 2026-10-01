// JS 版匹配规则的测试。运行: node --test tests/
//
// 核心是交叉测试：tests/golden/cases.json 里是 Python 版（scripts/lib/match.py）算出的「岗位 + 个人条件 → 结果」，
// JS 版（site/assets/match.js）必须逐条给出一模一样的结果（状态、对口度、全部提示文字）。
// 样例文件由 tests/make_golden.py 生成；改了任何一边的规则都要重新生成并让两边保持一致。
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const Match = require(path.join(__dirname, "..", "site", "assets", "match.js"));
const golden = require("./golden/cases.json");

test("JS 版和 Python 版在全部样例上结果一致", () => {
  let n = 0;
  const bad = [];
  golden.profiles.forEach((profile, pi) => {
    golden.jobs.forEach((job, ji) => {
      const rule = golden.rules[`${job.r}/${job.b}`];
      const got = Match.evaluate(job, profile, rule ? { ...rule, closed: golden.closed_by_profile[pi] } : null);
      const want = golden.expected[pi][ji];
      n++;
      try {
        assert.deepEqual(got, want);
      } catch (e) {
        if (bad.length < 5) bad.push(`条件 ${pi} / 岗位 ${job.r}/${job.b}/${job.id}\n  JS : ${JSON.stringify(got)}\n  Py : ${JSON.stringify(want)}`);
        else bad.push(null);
      }
    });
  });
  assert.equal(bad.length, 0, `${bad.length}/${n} 条不一致，前几条:\n${bad.filter(Boolean).join("\n")}`);
  assert.ok(n > 2000, "样例数量太少");
});

test("样例覆盖了符合、待确认、不符三种结果", () => {
  const seen = new Set(golden.expected.flat().map((e) => e.status));
  assert.deepEqual([...seen].sort(), ["check", "no", "ok"]);
});

test("批次状态", () => {
  const b = { signup_start: "2026-12-01", signup_end: "2026-12-05" };
  assert.equal(Match.batchStatus(b, "2026-11-30"), "upcoming");
  assert.equal(Match.batchStatus(b, "2026-12-01"), "open");
  assert.equal(Match.batchStatus(b, "2026-12-05"), "open");
  assert.equal(Match.batchStatus(b, "2026-12-06"), "closed");
  assert.equal(Match.batchStatus({}, "2026-12-06"), "rolling");
});

test("下一批的推算：顺延一年，直到不早于今天", () => {
  const b = { signup_start: "2025-12-01", signup_end: "2025-12-05" };
  assert.deepEqual(Match.nextEstimate(b, "2026-10-02"), ["2026-12-01", "2026-12-05"]);
  assert.deepEqual(Match.nextEstimate(b, "2027-01-10"), ["2027-12-01", "2027-12-05"]);
  assert.equal(Match.nextEstimate({ ...b, signup_end: "2026-12-05" }, "2026-10-02"), null);      // 还没结束：不推算
  assert.equal(Match.nextEstimate({}, "2026-10-02"), null);                                    // 没有统一报名时间
  const leap = { signup_start: "2024-02-29", signup_end: "2024-03-05" };                        // 闰日顺延到 2 月 28 日
  assert.deepEqual(Match.nextEstimate(leap, "2025-01-01"), ["2025-02-28", "2025-03-05"]);
});

test("应届规则：和 Python 版同样的判断", () => {
  const me = { fresh: "auto", graduate_year: 2026, employed_now: false, had_staff_job: false, had_any_job: true };
  const v = (kind, closed, extra = {}) => Match.freshVerdict({ ...me, ...extra }, { kind, cohort: 2026, window: 2, closed })[0];
  assert.equal(v("no_staff_job", true), "yes");
  assert.equal(v("no_staff_job", true, { had_staff_job: true }), "no");
  assert.equal(v("unemployed", true), "yes");
  assert.equal(v("unemployed", true, { employed_now: true }), "no");
  assert.equal(v("year", false), "yes");
  assert.equal(v("year", true), "no");
  assert.equal(v("unplaced", true), "maybe");
  assert.equal(v("unplaced", true, { had_any_job: false }), "yes");
  assert.equal(v("year", true, { fresh: "yes" }), "yes");
  assert.equal(Match.freshVerdict(me, null)[0], "maybe");
});

test("个人条件的校验", () => {
  assert.equal(Match.normalizeProfile({}), null);
  assert.equal(Match.normalizeProfile({ education: "硕士", fresh: "乱写" }), null);
  assert.ok(Match.normalizeProfile({ education: "硕士" }));
});
