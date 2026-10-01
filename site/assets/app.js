// 事业编岗位看板：纯静态。数据来自 data/index.json 和 data/jobs/*.json（由 scripts/build.py 生成，不含任何个人信息），
// 个人条件在页面上填、只保存在这个浏览器里（localStorage），筛选全部在浏览器里完成（assets/match.js）。
// 岗位的所有文字都来自第三方网站：只用 textContent / 文本节点渲染，不拼 innerHTML；来自数据的链接只接受 https://。
"use strict";

const PAGE = 50;          // 岗位表每页的行数
const STATUS_LABEL = { open: "报名中", upcoming: "即将开始", rolling: "滚动招聘", closed: "已结束（往年参考）" };
const STATUS_RANK = { open: 0, upcoming: 1, rolling: 2, closed: 3 };
const MATCH_LABEL = { ok: "符合", check: "待确认", no: "不符" };
const MATCH_RANK = { ok: 0, check: 1, no: 2 };
const PROFILE_KEY = "shiye.profile.v1";

const $ = (s) => document.querySelector(s);
function h(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}
const safeUrl = (u) => (typeof u === "string" && u.startsWith("https://") ? u : "");
const link = (href, text) => (safeUrl(href) ? h("a", { href, target: "_blank", rel: "noopener noreferrer", text }) : null);
const badge = (cls, text) => h("span", { class: `badge ${cls}`, text });
const pad = (n) => String(n).padStart(2, "0");
// 今天的日期（本地时区）；?date=2026-12-01 可以覆盖，用来看某个日期下的报名状态
const today = new URLSearchParams(location.search).get("date") || (() => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; })();

let index, jobs = [], batchOf = {}, regionOf = {}, order = [], view = [], page = 0;
let profile = null, profileSource = "", extraProfileKeys = {};
const F = { match: "", status: "", major: "", region: "", city: "", fresh: "", lower: "", exam: "", q: "", batch: "" };

// ---------- 个人条件 ----------

const KNOWN = ["education", "majors", "fresh", "graduate_year", "employed_now", "had_staff_job", "had_any_job", "work_months",
  "age", "politics", "hukou", "residence", "english", "certs", "gender", "include_special"];
const csv = (s) => s.split(/[,，、;；\s]+/).filter(Boolean);
const numOrNull = (s) => (s.trim() === "" || Number.isNaN(Number(s)) ? null : Number(s));
const val = (id) => $(id).value.trim();

// 哪些学历要选哪些专业：研究生要选研究生专业，也可以选本科专业（报只要求本科的岗位时用）
const SHOW_LEVEL = {
  graduate: (e) => e === "硕士" || e === "博士",
  bachelor: (e) => e === "本科" || e === "硕士" || e === "博士",
  college: (e) => e === "大专",
};
const HAS_WORK = ["left", "working", "staff-past", "staff-now"];     // 工作过的才需要问累计多久
let opts, cat, hukouExtra = [];
const pick = {};                                                       // 各个选择控件：graduate bachelor college residence cert

function formToProfile() {
  const edu = val("#pEdu");
  const lv = (level, kw, rel) => ({ ...Options.toProfile(level, SHOW_LEVEL[level](edu) ? pick[level].get() : []),
    keywords: SHOW_LEVEL[level](edu) ? csv(val(kw)) : [], related: SHOW_LEVEL[level](edu) ? csv(val(rel)) : [] });
  const majors = { graduate: lv("graduate", "#pGradKw", "#pGradRel"), bachelor: lv("bachelor", "#pBachKw", "#pBachRel") };
  if (SHOW_LEVEL.college(edu) && pick.college.get().length) majors.college = Options.toProfile("college", pick.college.get());
  const work = val("#pWork");
  return {
    ...extraProfileKeys,
    education: edu || null, majors, fresh: val("#pFresh") || "auto", graduate_year: numOrNull(val("#pGradYear")),
    ...Options.workFlags(work),
    work_months: work === "none" ? 0 : numOrNull(val("#pWorkMonths")),
    age: numOrNull(val("#pAge")), politics: val("#pPol") || null,
    hukou: Options.hukouFromSelect(val("#pProv"), val("#pCity"), hukouExtra),
    residence: pick.residence.get().map((p) => p.value), english: val("#pEnglish") || null,
    certs: Options.certsToProfile(pick.cert.get()), gender: val("#pGender") || null, include_special: $("#pSpecial").checked,
  };
}

const fillOptions = (sel, pairs) => sel.replaceChildren(...pairs.map(([v, label]) => h("option", { value: String(v), text: label })));
// 导入的值不在下拉框的选项里（比如年龄 55）：补上这一项，不然会悄悄变成「不填」
function setSelect(sel, v, label) {
  v = v == null ? "" : String(v);
  if (v && ![...sel.options].some((o) => o.value === v)) sel.append(h("option", { value: v, text: label || v }));
  sel.value = v;
}

function fillCities() {
  const prov = val("#pProv"), sel = $("#pCity");
  const cities = (opts.places.find(([p]) => p === prov) || [, []])[1];
  fillOptions(sel, [["", !prov ? "市（请先选省）" : cities.length ? "市（不填）" : "—"], ...cities.map((c) => [c, c])]);
  sel.disabled = !cities.length;
}

// 选专业时自动生成「对口关键词 / 相关词」（只用于岗位只写文字的地区，在「高级设置」里能看到）
function fillTerms(level) {
  const [kw, rel] = level === "graduate" ? ["#pGradKw", "#pGradRel"] : ["#pBachKw", "#pBachRel"];
  const d = Options.derive(level, pick[level].get(), opts);
  $(kw).value = d.keywords.join("，");
  $(rel).value = d.related.join("，");
}

function syncLevels() {
  const edu = val("#pEdu");
  for (const [level, box] of [["graduate", "#gradBox"], ["bachelor", "#bachBox"], ["college", "#collBox"]]) $(box).hidden = !SHOW_LEVEL[level](edu);
  $("#bachLab").textContent = SHOW_LEVEL.graduate(edu) ? "本科专业（选填，用于判断仅要求本科的岗位）" : "本科专业";
  $("#majorNeedEdu").hidden = !!edu;
  $("#majorHint").hidden = !edu;
  for (const label of document.querySelectorAll("#termsSet [data-lv]")) label.hidden = !SHOW_LEVEL[label.dataset.lv](edu);
  $("#termsSet").hidden = !SHOW_LEVEL.graduate(edu) && !SHOW_LEVEL.bachelor(edu);
}
function syncWork() { $("#pWorkMonthsBox").hidden = !HAS_WORK.includes(val("#pWork")); }

function profileToForm(p) {
  const set = (id, v) => { $(id).value = v == null ? "" : v; };
  const m = p.majors || {};
  set("#pEdu", p.education); set("#pFresh", p.fresh || "auto"); set("#pGender", p.gender); set("#pPol", p.politics); set("#pEnglish", p.english);
  setSelect($("#pGradYear"), p.graduate_year, `${p.graduate_year} 年`); setSelect($("#pAge"), p.age, `${p.age} 岁`);
  const work = Options.workState(p);
  set("#pWork", work); set("#pWorkMonths", work === "none" ? "" : p.work_months); syncWork();
  const hk = Options.hukouToSelect(p.hukou, opts.places);
  set("#pProv", hk.prov); fillCities(); set("#pCity", hk.city); hukouExtra = hk.extra;
  for (const level of ["graduate", "bachelor", "college"]) pick[level].set(Options.fromProfile(level, m[level], cat));
  const terms = { graduate: ["#pGradKw", "#pGradRel"], bachelor: ["#pBachKw", "#pBachRel"] };
  for (const [level, [kw, rel]] of Object.entries(terms)) {
    const spec = m[level] || {};
    set(kw, (spec.keywords || []).join("，")); set(rel, (spec.related || []).join("，"));
    if (!$(kw).value && !$(rel).value && pick[level].get().length) fillTerms(level);      // 老的 profile 没有这两项：按选的专业补上
  }
  const res = (Array.isArray(p.residence) ? p.residence : p.residence ? [p.residence] : []).map(String);
  pick.residence.set(res.map((r) => pick.residence.items.find((i) => i.value === r) || { key: `custom:${r}`, label: r, value: r, custom: true }));
  pick.cert.set(Options.certsFromProfile(p.certs, opts.certs));
  $("#pSpecial").checked = !!p.include_special;
  syncLevels();
  extraProfileKeys = Object.fromEntries(Object.entries(p).filter(([k]) => !KNOWN.includes(k) && !k.startsWith("_")));   // 导入的其他字段，导出时原样带上
}

// 把下拉框和选择控件建起来（要在读到 options.json 之后、填表单之前）
function setupOptionControls() {
  const year = Number(today.slice(0, 4));
  fillOptions($("#pGradYear"), [["", "请选择"], ...Array.from({ length: 18 }, (_, i) => [year + 1 - i, `${year + 1 - i} 年`])]);
  fillOptions($("#pAge"), [["", "不填"], ...Array.from({ length: 33 }, (_, i) => [18 + i, `${18 + i} 岁`])]);
  fillOptions($("#pWork"), Options.WORK_STATES.map(([k, label]) => [k, label]));
  fillOptions($("#pProv"), [["", "不填"], ...opts.places.map(([p]) => [p, p])]);
  fillCities();
  for (const level of ["graduate", "bachelor", "college"]) {
    for (const e of cat[level]) {
      e.label = e.pro ? `${e.name}（专业学位）` : e.name;
      e.group = e.cat;
      e.sub = level === "graduate" ? (e.pro ? "专业学位" : "学术学位") : e.cls;
    }
  }
  const major = (level, root, placeholder) => Picker.create({
    root: $(root), label: placeholder, items: cat[level], placeholder, subLevel: level !== "graduate", custom: (t) => Options.customPick(level, t),
    onChange: () => { if (level !== "college") fillTerms(level); changedByUser(); },
  });
  pick.graduate = major("graduate", "#pGradPick", "输入专业名称或代码检索（如 计算机、0812），或按学科门类浏览");
  pick.bachelor = major("bachelor", "#pBachPick", "输入专业名称或代码检索（如 软件、080902），或按学科门类浏览");
  pick.college = major("college", "#pCollPick", "输入专业名称或代码检索，或按专业大类浏览");
  const places = Options.placeItems(opts.places);
  pick.residence = Picker.create({ root: $("#pResPick"), label: "居住证城市", items: places, placeholder: "输入城市名称（如 上海），或按省份浏览", keepOpen: true,
    custom: (t) => ({ key: `custom:${t}`, label: t, value: t, custom: true }), onChange: changedByUser });
  pick.residence.items = places;
  pick.cert = Picker.create({ root: $("#pCertPick"), label: "资格证书", placeholder: "选择或输入证书名称", keepOpen: true,
    items: opts.certs.map((c, i) => ({ key: `cert:${i}`, label: c.label, tokens: c.tokens })),
    custom: (t) => ({ key: `custom:${t}`, label: t, tokens: [t], custom: true }), onChange: changedByUser });
}

function saveProfile(p) {
  try { localStorage.setItem(PROFILE_KEY, JSON.stringify(p)); } catch (e) { /* 存不了（隐私模式等）：只对本次有效 */ }
}
function loadSavedProfile() {
  try { const s = localStorage.getItem(PROFILE_KEY); return s ? JSON.parse(s) : null; } catch (e) { return null; }
}

// ---------- 评估和排序 ----------

function ruleOf(j) {
  const b = batchOf[`${j.r}/${j.b}`];
  return b.fresh_rule ? { ...b.fresh_rule, closed: b.status === "closed" } : null;
}

function evaluateAll() {
  const p = Match.normalizeProfile(profile);
  for (const j of jobs) j._ev = p ? Match.evaluate(j, p, ruleOf(j)) : null;
  order = jobs.slice().sort((a, b) =>
    STATUS_RANK[batchOf[`${a.r}/${a.b}`].status] - STATUS_RANK[batchOf[`${b.r}/${b.b}`].status]
    || (a._ev ? MATCH_RANK[a._ev.status] : 0) - (b._ev ? MATCH_RANK[b._ev.status] : 0)
    || (a._ev ? Match.MAJOR_RANK[a._ev.major] ?? 3 : 0) - (b._ev ? Match.MAJOR_RANK[b._ev.major] ?? 3 : 0)
    || a.ci.localeCompare(b.ci, "zh") || a.id.localeCompare(b.id));
}

const hasProfile = () => !!Match.normalizeProfile(profile);

function changedByUser() { profileSource = ""; applyProfile(true); }

function applyProfile(fromUser) {
  profile = formToProfile();
  if (fromUser) saveProfile(profile);
  evaluateAll();
  page = 0;
  renderAll();
}

// ---------- 筛选和渲染 ----------

// 这个岗位该看哪一栏专业要求：只要求较低学历的，看本科 / 大专栏；否则看研究生栏
function majorText(j) {
  return j._ev && j._ev.lower ? j.mb || j.mc || j.mg || "" : j.mg || j.mb || j.mc || "";
}

function fillSelect(sel, key, options) {
  sel.replaceChildren(...options.map(([v, label]) => h("option", { value: v, text: label })));
  sel.value = F[key];
}
function counts(arr) {
  const m = new Map();
  for (const x of arr) if (x) m.set(x, (m.get(x) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh"));
}

function setupFilters() {
  const bind = (id, key) => $(id).addEventListener("change", (e) => { F[key] = e.target.value; page = 0; render(); });
  for (const [id, key] of [["#fMatch", "match"], ["#fStatus", "status"], ["#fMajor", "major"], ["#fRegion", "region"], ["#fCity", "city"],
    ["#fFresh", "fresh"], ["#fLower", "lower"], ["#fExam", "exam"]]) bind(id, key);
  fillSelect($("#fMatch"), "match", [["", "符合 + 待确认"], ["ok", "仅符合"], ["check", "仅待确认"], ["no", "仅不符"], ["all", "全部"]]);
  fillSelect($("#fStatus"), "status", [["", "全部"], ...Object.entries(STATUS_LABEL)]);
  fillSelect($("#fMajor"), "major", [["", "全部"], ["对口", "对口"], ["不限专业", "不限专业"], ["需核对", "需核对"]]);
  fillSelect($("#fRegion"), "region", [["", "全部"], ...index.regions.map((r) => [r.key, r.name])]);
  fillSelect($("#fCity"), "city", [["", "全部"], ...counts(jobs.map((j) => j.ci)).map(([c, n]) => [c, `${c}（${n}）`])]);
  fillSelect($("#fFresh"), "fresh", [["", "全部"], ["open", "不限（往届可报）"], ["fresh", "限应届"]]);
  fillSelect($("#fLower"), "lower", [["", "全部"], ["0", "以最高学历报考"], ["1", "仅限以较低学历报考"]]);
  fillSelect($("#fExam"), "exam", [["", "全部"], ...counts(jobs.map((j) => j.ex)).map(([c, n]) => [c, `${c}（${n}）`])]);
  $("#fQuery").addEventListener("input", (e) => { F.q = e.target.value.trim(); page = 0; render(); });
  $("#reset").addEventListener("click", () => {
    Object.keys(F).forEach((k) => (F[k] = ""));
    for (const id of ["fMatch", "fStatus", "fMajor", "fRegion", "fCity", "fFresh", "fLower", "fExam"]) $("#" + id).value = "";
    $("#fQuery").value = "";
    page = 0; renderBatches(); render();
  });
}

function pass(j) {
  const b = batchOf[`${j.r}/${j.b}`], ev = j._ev;
  if (ev) {
    if (F.match === "" && ev.status === "no") return false;
    if (F.match === "ok" || F.match === "check" || F.match === "no") { if (ev.status !== F.match) return false; }
  }
  if (F.batch && F.batch !== `${j.r}/${j.b}`) return false;
  if (F.status && b.status !== F.status) return false;
  if (F.major && (!ev || ev.major !== F.major)) return false;
  if (F.region && j.r !== F.region) return false;
  if (F.city && j.ci !== F.city) return false;
  if (F.fresh === "fresh" && !j.fo) return false;
  if (F.fresh === "open" && j.fo) return false;
  if (F.lower && (!ev || String(+ev.lower) !== F.lower)) return false;
  if (F.exam && j.ex !== F.exam) return false;
  if (F.q) {
    const hay = [j.un, j.dp, j.du, j.mg, j.mb, j.mc, j.ci].join("\n");
    if (!F.q.split(/\s+/).every((w) => hay.includes(w))) return false;
  }
  return true;
}

function renderBatches() {
  const box = $("#batches");
  box.replaceChildren();
  for (const r of index.regions) {
    for (const b of r.batches) {
      const key = `${r.key}/${b.key}`;
      const when = b.signup_start ? `报名 ${b.signup_start} 至 ${b.signup_end}` : "无统一报名时间";
      const mine = b.stats ? (b.stats.ok + b.stats.check) : null;
      box.append(h("div", { class: "batch" + (F.batch === key ? " active" : "") },
        h("h3", {}, `${r.name} · ${b.name} `, badge(`b-${b.status}`, STATUS_LABEL[b.status])),
        h("p", { class: "meta", text: `${when}${b.exam ? "　" + b.exam : ""}　公告发布 ${b.published}` }),
        h("p", { class: "meta", text: mine == null ? `岗位表共 ${b.total} 个` : `符合条件 ${mine} 个（符合 + 待确认）/ 岗位表共 ${b.total} 个` }),
        b.next ? h("p", { class: "meta", text: `预计下一批报名：${b.next[0]} 至 ${b.next[1]} 前后（依本年度推算）` }) : null,
        b.fresh_note ? h("details", {}, h("summary", { text: "公告对「应届」的认定" }), h("p", { text: b.fresh_note })) : null,
        h("div", { class: "links" },
          h("button", { type: "button", class: "linkbtn", text: F.batch === key ? "取消仅看本批次" : "仅看本批次",
            onclick: () => { F.batch = F.batch === key ? "" : key; page = 0; renderBatches(); render(); } }),
          link(b.notice_url, "官方公告"),
          h("a", { href: "data/" + b.csv.split("/").map(encodeURIComponent).join("/"), download: "", text: "下载全部岗位 CSV" }))));
    }
  }
}

// 下一批什么时候开：已经在报名 / 即将报名的列真实日期，已结束的按去年同期推算
function renderCalendar() {
  const DAY = 864e5, now = Date.parse(today);
  const items = [];
  for (const r of index.regions) {
    for (const b of r.batches) {
      if (b.status === "open" || b.status === "upcoming") items.push({ r, b, start: b.signup_start, end: b.signup_end, est: false });
      else if (b.next) items.push({ r, b, start: b.next[0], end: b.next[1], est: true });
    }
  }
  items.sort((a, b) => a.start.localeCompare(b.start));
  $("#calendarSec").hidden = items.length === 0;
  $("#calendar").replaceChildren(...items.map(({ r, b, start, end, est }) => {
    const days = Math.round((Date.parse(start) - now) / DAY);
    return h("li", {},
      h("span", { class: "when", text: `${start} 至 ${end}` + (est ? " 前后" : "") }),
      badge(est ? "b-upcoming" : "b-open", est ? "推算" : STATUS_LABEL[b.status]),
      h("span", { text: `${r.name} · ${b.name.replace(/20\d\d年/, "")}` }),
      h("span", { class: "days", text: days > 0 ? `约 ${days} 天后` : "正在报名" }));
  }));
}

function renderProfileInfo() {
  const ok = hasProfile();
  const unset = [];
  if (ok) {
    const p = profile, g = (p.majors || {}).graduate || {}, b = (p.majors || {}).bachelor || {};
    const names = (x) => (x.names || []).join("、");
    const parts = [`最高学历：${p.education}`];
    const majors = [names(g) && `研究生专业：${names(g)}`, names(b) && `本科专业：${names(b)}`].filter(Boolean);
    parts.push(majors.join("；") || "专业未填");
    parts.push({ auto: "应届身份按各批次规则判断", yes: "按应届", no: "按往届", maybe: "应届身份待定" }[p.fresh || "auto"]);
    parts.push(p.work_months ? `工作经历 ${p.work_months} 个月` : "没有工作经历");
    $("#filterText").textContent = parts.join(" · ");
    for (const [key, label] of [["age", "年龄"], ["politics", "政治面貌"], ["gender", "性别"], ["english", "英语等级"]]) if (p[key] == null) unset.push(label);
    if (p.had_any_job && p.work_months == null) unset.push("累计工作月数");
    if (!(p.hukou || []).length) unset.push("户籍");
    if ((p.fresh || "auto") === "auto" && p.graduate_year == null) unset.push("毕业年份（未填写则无法判断各批次的应届规则）");
    if (p.education !== "本科" && !(b.codes || []).length && !(b.names || []).length) unset.push("本科专业");
  }
  $("#filterInfo").hidden = !ok;
  $("#filterUnset").textContent = ok && unset.length ? `尚未填写：${unset.join("、")}。这些项不参与筛选，填写后结果更精确。` : "";
  const out = new Map();
  for (const j of jobs) if (j._ev && j._ev.status === "no") { const k = Match.mainReason(j._ev.no); out.set(k, (out.get(k) || 0) + 1); }
  const total = [...out.values()].reduce((s, n) => s + n, 0);
  $("#filteredOut").textContent = ok && total
    ? `已默认隐藏 ${total} 个明确不符合的岗位：${[...out.entries()].sort((a, b) => b[1] - a[1]).map(([k, n]) => `${Match.REASON_LABEL[k]} ${n}`).join("、")}。在「匹配度」中选择「全部」可查看这些岗位及不符原因。` : "";
  const n = { ok: 0, check: 0 };
  if (ok) for (const j of jobs) if (j._ev && j._ev.status !== "no") n[j._ev.status]++;
  $("#profileStatus").textContent = ok ? `已按所填条件筛选${profileSource ? "（" + profileSource + "）" : ""}：全部批次合计 符合 ${n.ok} · 待确认 ${n.check}` : "请先选择最高学历后开始筛选";
  const live = index.regions.some((r) => r.batches.some((b) => ["open", "upcoming", "rolling"].includes(b.status)));
  const banner = $("#staleBanner");
  banner.hidden = live;
  banner.textContent = "目前收录的批次均已结束报名。以下岗位为往年数据，可供了解各单位的用人情况与条件；下一批公告发布后将更新。";
}

function computeBatchStats() {
  for (const r of index.regions) for (const b of r.batches) b.stats = hasProfile() ? { ok: 0, check: 0, no: 0 } : null;
  if (!hasProfile()) return;
  for (const j of jobs) batchOf[`${j.r}/${j.b}`].stats[j._ev.status]++;
}

function renderAll() {
  computeBatchStats();
  renderProfileInfo();
  renderBatches();
  render();
}

function render() {
  view = order.filter(pass);
  const ok = view.filter((j) => j._ev && j._ev.status === "ok").length, chk = view.filter((j) => j._ev && j._ev.status === "check").length;
  $("#count").textContent = hasProfile() ? `${view.length} 个（符合 ${ok} · 待确认 ${chk}${view.length - ok - chk ? ` · 不符 ${view.length - ok - chk}` : ""}）`
    : `${view.length} 个（未设置条件，显示全部岗位）`;
  const rows = $("#rows");
  const pages = Math.max(1, Math.ceil(view.length / PAGE));
  page = Math.min(page, pages - 1);
  rows.replaceChildren(...view.slice(page * PAGE, (page + 1) * PAGE).map(row));
  $("#empty").hidden = view.length > 0;
  renderPager(pages);
}

// 页码条：‹ 上一页  1 … 4 [5] 6 … 20  下一页 ›，右侧是第几页和总数。只有一页时不显示
function renderPager(pages) {
  const nav = $("#pager");
  nav.hidden = pages <= 1;
  if (pages <= 1) return;
  const go = (n) => () => { page = n; render(); $(".table-wrap").scrollIntoView({ block: "start" }); };
  const btn = (text, n, props = {}) => h("button", { type: "button", text, ...props, ...(props.disabled === undefined ? { onclick: go(n) } : {}) });
  const parts = [btn("‹ 上一页", page - 1, page === 0 ? { disabled: "", class: "pg" } : { class: "pg" })];
  let prev = -1;
  for (let i = 0; i < pages; i++) {
    if (!(pages <= 7 || i === 0 || i === pages - 1 || Math.abs(i - page) <= 2)) continue;
    if (i - prev > 1) parts.push(h("span", { class: "pg-gap", text: "…" }));
    parts.push(btn(String(i + 1), i, i === page ? { class: "pg cur", "aria-current": "page" } : { class: "pg", "aria-label": `第 ${i + 1} 页` }));
    prev = i;
  }
  parts.push(btn("下一页 ›", page + 1, page === pages - 1 ? { disabled: "", class: "pg" } : { class: "pg" }),
    h("span", { class: "pg-info", text: `第 ${page + 1} / ${pages} 页，共 ${view.length} 个，每页 ${PAGE} 个` }));
  nav.replaceChildren(...parts);
}

function row(j) {
  const b = batchOf[`${j.r}/${j.b}`], ev = j._ev;
  const mt = majorText(j);
  const tr = h("tr", { tabindex: "0", role: "button", "aria-label": `查看 ${j.un} 的岗位详情` },
    h("td", {}, h("div", { class: "unit", text: j.un }), h("div", { class: "dept", text: j.dp || "" })),
    h("td", { text: j.ci }),
    h("td", { text: (j.ed || "") + (ev && ev.lower ? "（较低学历）" : "") }),
    h("td", { class: "major-cell" },
      ev && ev.major === "对口" ? badge("b-ok", "对口") : null, ev && ev.major === "对口" ? " " : null,
      h("span", { class: "major", text: mt.length > 70 ? mt.slice(0, 70) + "…" : mt })),
    h("td", { class: "num", text: String(j.n || "") }),
    h("td", { text: j.fr || "" }),
    h("td", {}, ev ? badge(`b-${ev.status}`, MATCH_LABEL[ev.status]) : "—"),
    h("td", {}, badge(`b-${b.status}`, STATUS_LABEL[b.status].replace("（往年参考）", ""))));
  const open = () => showDetail(j);
  tr.addEventListener("click", open);
  tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  return tr;
}

function showDetail(j) {
  const b = batchOf[`${j.r}/${j.b}`], r = regionOf[j.r], ev = j._ev;
  $("#dTitle").textContent = `${j.un}${j.dp ? " · " + j.dp : ""}`;
  const fields = [
    ["城市", j.ci], ["岗位职责", j.du], ["岗位等级", j.gr], ["招聘人数", j.n ? String(j.n) : ""], ["考生类别", j.fr],
    ["学历 / 学位", [j.ed, j.dg].filter(Boolean).join("　")],
    ["专业（研究生）", j.mg], ["专业（本科）", j.mb], ["专业（大专）", j.mc],
    ["年龄", [j.ag, j.ar && `硕士：${j.ar}`].filter(Boolean).join("；")], ["工作经历", j.xp], ["政治面貌", j.po],
    ["资格证书", j.cr], ["职称", j.ti], ["户籍", j.ho], ["专项招聘", j.sp], ["其他条件", j.ot],
    ["考试方式", j.ex], ["岗位代码", j.id], ...(j.x || []),
  ].filter(([, v]) => v);
  const ul = (arr) => h("ul", {}, arr.map((x) => h("li", { text: x })));
  $("#dBody").replaceChildren(...[
    h("p", {}, ev ? badge(`b-${ev.status}`, MATCH_LABEL[ev.status]) : null, ev ? " " : null,
      ev && ev.major ? badge("b-check", `专业${ev.major}`) : null, ev && ev.major ? " " : null, badge(`b-${b.status}`, STATUS_LABEL[b.status])),
    ev && ev.no.length ? h("div", { class: "note note-no" }, "不符合的原因：", ul(ev.no.map((x) => x[1]))) : null,
    ev && ev.check.length ? h("div", { class: "note note-check" }, "需要确认：", ul(ev.check)) : null,
    ev && ev.fresh_info ? h("div", { class: "note note-info" }, "应届判断：" + ev.fresh_info) : null,
    h("dl", {}, fields.flatMap(([k, v]) => [h("dt", { text: k }), h("dd", { text: v })])),
    h("div", { class: "note note-info" },
      `${r.name} · ${b.name}　`, link(j.u || b.notice_url, j.u ? "岗位页面" : "官方公告"),
      b.fresh_note ? h("p", { text: "应届认定：" + b.fresh_note }) : null),
  ].filter(Boolean));     // replaceChildren(null) 会把 "null" 当成文本插进去
  $("#detail").showModal();
}

// ---------- 导出 ----------

function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = h("a", { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportCsv() {
  const cols = [["匹配度", (j) => (j._ev ? MATCH_LABEL[j._ev.status] : "")], ["专业对口", (j) => (j._ev ? j._ev.major : "")],
    ["需要确认 / 不符原因", (j) => (j._ev ? [...j._ev.no.map((x) => x[1]), ...j._ev.check].join("；") : "")],
    ["地区", (j) => regionOf[j.r].name], ["批次", (j) => batchOf[`${j.r}/${j.b}`].name], ["城市", (j) => j.ci], ["招聘单位", (j) => j.un],
    ["工作部门", (j) => j.dp], ["岗位职责", (j) => j.du], ["招聘人数", (j) => j.n], ["考生类别", (j) => j.fr], ["学历", (j) => j.ed],
    ["专业（研究生）", (j) => j.mg], ["专业（本科）", (j) => j.mb], ["年龄", (j) => j.ag], ["工作经历", (j) => j.xp],
    ["其他条件", (j) => j.ot], ["考试方式", (j) => j.ex], ["岗位代码", (j) => j.id], ["官方公告", (j) => j.u || batchOf[`${j.r}/${j.b}`].notice_url]];
  const esc = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
  const lines = [cols.map(([n]) => esc(n)).join(","), ...view.map((j) => cols.map(([, f]) => esc(f(j))).join(","))];
  download(`事业编岗位-${today}.csv`, "﻿" + lines.join("\n"), "text/csv;charset=utf-8");
}

function setupProfileForm() {
  let timer;
  // 选了学历 / 省 / 工作情况，要先更新联动的控件，再重新筛选（控件自己的监听器比表单上的先执行）
  $("#pEdu").addEventListener("change", syncLevels);
  $("#pWork").addEventListener("change", syncWork);
  $("#pProv").addEventListener("change", fillCities);
  $("#profileForm").addEventListener("input", (e) => {
    if (e.target.classList.contains("pk-input")) return;      // 在选择框里打字是搜索，不是改条件
    clearTimeout(timer); timer = setTimeout(() => { profileSource = ""; applyProfile(true); }, 250);
  });
  $("#profileForm").addEventListener("change", (e) => {
    if (e.target.classList.contains("pk-input")) return;
    clearTimeout(timer); profileSource = ""; applyProfile(true);
  });
  $("#pExport").addEventListener("click", () => download("事业编-我的条件.json", JSON.stringify(formToProfile(), null, 2), "application/json"));
  $("#pImport").addEventListener("click", () => $("#pFile").click());
  $("#pFile").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    try {
      const p = JSON.parse(await f.text());
      if (!p || typeof p !== "object" || Array.isArray(p)) throw new Error("不是条件文件");
      profileToForm(p); applyProfile(true); profileSource = "已导入"; renderProfileInfo();
    } catch (err) { alert(`导入失败：${err.message}。请选择本页「导出 JSON」生成的文件或 profile.json。`); }
  });
  $("#pClear").addEventListener("click", () => {
    if (!confirm("确认清空所有已填写的条件？")) return;
    profileToForm({}); extraProfileKeys = {}; profileSource = ""; applyProfile(true);
  });
  $("#pLocal").addEventListener("click", async () => { if (await loadLocalProfile()) { applyProfile(true); profileSource = "来自本机 profile.json"; renderProfileInfo(); } });
}

async function loadLocalProfile() {
  try {
    const res = await fetch("data/profile.local.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    profileToForm(await res.json());
    profileSource = "来自本机 profile.json";
    return true;
  } catch (e) { return false; }
}

// 主题：跟随系统 → 浅色 → 深色 循环。「跟随系统」就是不设 data-theme，由 CSS 的 prefers-color-scheme 决定
const THEMES = [["auto", "◐ 跟随系统"], ["light", "☀ 浅色"], ["dark", "☾ 深色"]];
function setupTheme() {
  const btn = $("#theme"), root = document.documentElement;
  const current = () => (["light", "dark"].includes(root.dataset.theme) ? root.dataset.theme : "auto");
  const paint = () => { btn.textContent = THEMES.find(([k]) => k === current())[1]; };
  btn.addEventListener("click", () => {
    const next = THEMES[(THEMES.findIndex(([k]) => k === current()) + 1) % THEMES.length][0];
    if (next === "auto") delete root.dataset.theme; else root.dataset.theme = next;
    try { next === "auto" ? localStorage.removeItem("theme") : localStorage.setItem("theme", next); } catch (e) { /* 存不了就只对本次有效 */ }
    paint();
  });
  paint();
}

async function getJson(url) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res.json();
}

async function main() {
  setupTheme();
  try {
    [index, opts] = await Promise.all([getJson("data/index.json"), getJson("assets/options.json")]);
    cat = Options.catalog(opts);
    const parts = [];
    let done = 0;
    for (const r of index.regions) for (const b of r.batches) {
      parts.push(getJson("data/" + b.file).then((rows) => { $("#generated").textContent = `加载岗位 ${++done}/${parts.length}…`; return rows; }));
    }
    const all = await Promise.all(parts);
    jobs = all.flat();
    // 导出时空字段是省略的（省体积），这里把显示用的字符串字段补成空串；匹配函数把缺失和空串一样处理，不受影响
    const TEXT_KEYS = ["ci", "un", "dp", "du", "gr", "fr", "ed", "dg", "mc", "mb", "mg", "ag", "ar", "xp", "cr", "ti", "po", "ex", "sp", "ho", "ot", "u"];
    for (const j of jobs) for (const k of TEXT_KEYS) if (j[k] === undefined) j[k] = "";
  } catch (e) {
    const el = $("#error");
    el.hidden = false;
    el.textContent = `读取岗位数据失败（${e.message}）。请先运行 python3 scripts/update.py 生成数据，并通过 python3 scripts/serve.py 打开本页（不支持直接以文件方式打开）。`;
    $("#generated").textContent = "没有数据";
    return;
  }
  for (const r of index.regions) {
    regionOf[r.key] = r;
    for (const b of r.batches) { batchOf[`${r.key}/${b.key}`] = b; b.status = Match.batchStatus(b, today); b.next = Match.nextEstimate(b, today); }
  }
  $("#generated").textContent = `数据日期 ${index.generated}　共 ${jobs.length} 个岗位`;
  setupOptionControls();
  setupProfileForm();
  $("#pLocal").hidden = !index.local_profile;

  // 个人条件：浏览器里保存的优先；没有的话，本机有 profile.json（构建时生成了 profile.local.json）就载入它
  const saved = loadSavedProfile();
  if (saved) { profileToForm(saved); profileSource = ""; }
  else if (index.local_profile) await loadLocalProfile();
  syncLevels(); syncWork();
  profile = formToProfile();
  evaluateAll();

  setupFilters();
  renderCalendar();
  renderAll();
  $("#profileDetails").open = !hasProfile();       // 已经有条件就把表单收起来，没有就展开
  $("#exportCsv").addEventListener("click", exportCsv);
  $("#dClose").addEventListener("click", () => $("#detail").close());
  $("#detail").addEventListener("click", (e) => { if (e.target === $("#detail")) $("#detail").close(); });
}
main();
