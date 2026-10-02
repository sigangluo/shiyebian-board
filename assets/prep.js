// 备考指南页：各批次的「考试与成绩」和官方信息渠道，数据来自 data/index.json（和看板首页同一份），页面里不写任何地区名。
"use strict";

const STATUS_LABEL = { open: "报名中", upcoming: "即将开始", rolling: "滚动招聘", closed: "已结束（往年参考）" };
const $ = (s) => document.querySelector(s);
function h(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}
const link = (href, text) => (typeof href === "string" && href.startsWith("https://")
  ? h("a", { href, target: "_blank", rel: "noopener noreferrer", text }) : h("span", { text }));
const pad = (n) => String(n).padStart(2, "0");
const today = new URLSearchParams(location.search).get("date") || (() => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; })();

async function main() {
  let index;
  try {
    const res = await fetch("data/index.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    index = await res.json();
  } catch (e) {
    const el = $("#error");
    el.hidden = false;
    el.textContent = `读取批次数据失败（${e.message}）。请通过 python3 scripts/serve.py 打开本页（不支持直接以文件方式打开）。`;
    $("#examCards").replaceChildren();
    return;
  }
  const cards = [], sources = [];
  for (const r of index.regions) {
    for (const b of r.batches) {
      const status = Match.batchStatus(b, today);
      if (b.exam_info) {
        cards.push(h("article", { class: "exam-card" },
          h("h3", {}, `${r.name} · ${b.name} `, h("span", { class: `badge b-${status}`, text: STATUS_LABEL[status] })),
          ExamInfo.node(b.exam_info)));
      }
    }
    sources.push(h("li", {}, `${r.name}：`, link(r.list_url, "官方招聘栏目"),
      r.batches.flatMap((b) => [" · ", link(b.notice_url, `${b.name}公告`)])));
  }
  $("#examCards").replaceChildren(...(cards.length ? cards : [h("p", { class: "muted", text: "收录的批次暂无考试与成绩摘要。" })]));
  $("#sources").replaceChildren(...sources);
}
main();
