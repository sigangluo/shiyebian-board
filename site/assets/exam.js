// 批次的「考试与成绩」摘要（exam_info，来自各地官方公告，由 regions/<地区>/fetch.py 的 META 提供）的渲染，看板和备考指南共用。
// 文字都来自配置文件，仍然只用 textContent 渲染；链接只接受 https://。
(function () {
  "use strict";

  const ROWS = [["written_date", "笔试时间"], ["written", "笔试"], ["shortlist", "入围面试"], ["interview", "面试"], ["score", "总成绩"], ["after", "体检至聘用"]];

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

  function node(e) {
    const rows = ROWS.filter(([k]) => e[k]);
    const links = (e.sources || []).filter(([, u]) => typeof u === "string" && u.startsWith("https://"))
      .flatMap(([t, u], i) => [i ? " · " : null, h("a", { href: u, target: "_blank", rel: "noopener noreferrer", text: t })]);
    const syl = (e.syllabus || []).filter((x) => Array.isArray(x) && x.length === 2);
    return h("div", { class: "exam" },
      h("dl", {}, rows.flatMap(([k, label]) => [h("dt", { text: label }), h("dd", { text: e[k] })])),
      syl.length ? h("div", { class: "exam-syllabus" }, h("p", { text: "笔试内容（依据考试大纲）" }),
        h("ul", {}, syl.map(([t, c]) => h("li", {}, h("b", { text: t }), "：", c)))) : null,
      (e.notes || []).length ? h("div", { class: "exam-notes" }, h("p", { text: "需要留意" }), h("ul", {}, e.notes.map((n) => h("li", { text: n })))) : null,
      h("p", { class: "exam-src" }, "依据：", links, e.checked ? `（对照公告原文核对于 ${e.checked}，以当年公告为准）` : ""));
  }

  window.ExamInfo = { node };
})();
