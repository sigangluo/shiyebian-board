// 可搜索、可逐级浏览的选择控件：选中的项显示成标签，可以删。用来选专业、城市、证书——这些选项数量大，普通下拉框难以使用。
//   不输入：先列出分类（学科门类 / 省），点进去逐级选择（门类 → 专业类 → 专业）；输入：在全部选项里按名称、代码、所属分类检索。
// 所有文字用 textContent / 文本节点渲染，不拼 innerHTML。
(function () {
  "use strict";

  const ITEM_PAGE = 8;        // 列表每页的条数（选项行）
  const TILE_PAGE = 36;       // 分类卡片每页的个数：门类、省、专业类都不超过这个数，一般不会翻页
  const LIST_MAX = 380;       // 下拉列表的最大高度
  let uid = 0;

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

  /**
   * opts.root         放这个控件的容器
   * opts.label        给读屏用的名称
   * opts.items        [{ key, label, sub, group, code }]  group 是大类（学科门类 / 省），sub 是小类（专业类）
   * opts.subLevel     true：浏览时多一级（门类 → 专业类 → 专业）；false：门类下直接是专业
   * opts.placeholder  没选任何东西时输入框里的提示
   * opts.multi        默认 true；false 时选一项就替换上一项
   * opts.keepOpen     选完是否保持展开（选证书、城市这种要连选几项的用 true）
   * opts.custom       (文字) => 一项 | null：检索不到时让用户直接添加这段文字（返回自定义项）
   * opts.onChange     选中的项变了（只在用户操作时触发，set() 不触发）
   */
  function create(opts) {
    const id = `pk${++uid}`;
    const items = opts.items;
    const multi = opts.multi !== false;
    const subLevel = !!opts.subLevel;
    const groups = [...new Set(items.filter((i) => i.group).map((i) => i.group))];
    const haystack = new Map(items.map((i) => [i.key, [i.label, i.code, i.sub, i.group].filter(Boolean).join(" ").toLowerCase()]));
    let selected = [], isOpen = false, query = "", path = [], page = 0, active = -1, rows = [];

    const chips = h("span", { class: "pk-chips" });
    const input = h("input", { class: "pk-input", type: "text", role: "combobox", autocomplete: "off", spellcheck: "false",
      "aria-label": opts.label || "", "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": `${id}-list` });
    const box = h("div", { class: "pk-box" }, chips, input);
    const list = h("div", { class: "pk-list", id: `${id}-list`, role: "listbox", hidden: "" });
    const root = opts.root;
    root.classList.add("picker");
    root.replaceChildren(box, list);

    const isOn = (key) => selected.some((s) => s.key === key);
    const q = () => query.trim().toLowerCase();

    function renderChips() {
      chips.replaceChildren(...selected.map((s) => h("span", { class: "chip" + (s.custom ? " custom" : ""), title: s.custom ? "目录中无此项，按名称或代码原样匹配" : (s.label || s.name) },
        h("span", { text: s.label || s.name }),
        h("button", { type: "button", class: "chip-x", "aria-label": `移除 ${s.label || s.name}`, text: "×", "data-key": s.key }))));
      input.placeholder = selected.length ? "继续添加…" : opts.placeholder || "";
    }

    // 检索：名称完全相同 > 名称开头 > 名称包含 > 代码 / 所属分类包含
    function search() {
      const t = q();
      const scored = [];
      for (const i of items) {
        const l = i.label.toLowerCase();
        const s = l === t ? 0 : l.startsWith(t) ? 1 : l.includes(t) ? 2 : haystack.get(i.key).includes(t) ? 3 : 9;
        if (s < 9) scored.push([s, i]);
      }
      return scored.sort((a, b) => a[0] - b[0]).map((x) => x[1]);
    }

    // 一行（可点击）。点击后要做的事写在 data-* 里，由 activate 统一处理
    const row = (cls, data, ...kids) => {
      const el = h("div", { class: `opt ${cls}`.trim(), role: "option", id: `${id}-o${rows.length}`, "aria-selected": cls.includes("on") ? "true" : "false", ...data }, ...kids);
      el.dataset.act = "1";
      rows.push(el);
      return el;
    };
    const itemRow = (i, showPath) => row(isOn(i.key) ? "on" : "", { "data-key": i.key },
      h("span", { class: "o-name", text: i.label }),
      i.code ? h("span", { class: "o-code", text: i.code }) : null,
      showPath && (i.sub || i.group) ? h("span", { class: "o-sub", text: [i.sub, i.group].filter(Boolean).join(" · ") }) : null,
      isOn(i.key) ? h("span", { class: "o-on", text: "已选" }) : null);
    const tile = (name, count, data) => row("tile", data, h("span", { class: "o-name", text: name }), h("span", { class: "o-sub", text: `${count} 项` }));
    const head = (text) => h("div", { class: "pk-head", text });
    // 页码条：‹ 上一页  1 … 4 [5] 6 … 12  下一页 ›  共 N 项
    function pager(pages, total) {
      const nums = [];
      for (let i = 0; i < pages; i++) if (pages <= 7 || i === 0 || i === pages - 1 || Math.abs(i - page) <= 1) nums.push(i);
      const cell = (text, to, cls = "") => h("span", { class: `pg ${cls}`.trim(), "data-page": String(to), role: "button", "aria-label": text, text });
      const parts = [cell("‹ 上一页", page - 1, page === 0 ? "off" : "")];
      let prev = -1;
      for (const i of nums) {
        if (i - prev > 1) parts.push(h("span", { class: "pg gap", text: "…" }));
        parts.push(cell(String(i + 1), i, i === page ? "cur" : ""));
        prev = i;
      }
      parts.push(cell("下一页 ›", page + 1, page === pages - 1 ? "off" : ""), h("span", { class: "pg-total", text: `共 ${total} 项` }));
      return h("div", { class: "pk-pager" }, ...parts);
    }

    function renderList() {
      rows = [];
      const out = [];
      let entries = [], tiles = false, tail = [];
      const query_ = q();
      if (query_) {
        entries = search().map((i) => (() => itemRow(i, true)));
        const extra = opts.custom && !entries.length ? opts.custom(query.trim()) : null;      // 目录里检索不到才提供「直接添加」
        if (extra && !isOn(extra.key)) tail.push(() => row("add", { "data-custom": "1" }, h("span", { class: "o-name", text: `添加「${query.trim()}」` }), h("span", { class: "o-sub", text: "目录中无此项，按输入内容匹配" })));
        else if (!entries.length) out.push(head("未找到匹配项。请更换关键词，或清空输入后按分类浏览"));
      } else if (!groups.length) {
        entries = items.map((i) => () => itemRow(i, false));
      } else if (path.length === 0) {
        out.push(head("可按分类逐级浏览，或输入关键词检索"));
        tiles = true;
        entries = groups.map((g) => () => tile(g, items.filter((i) => i.group === g).length, { "data-group": g }));
      } else {
        const [g, sub] = path;
        out.push(row("back", { "data-back": "1" }, h("span", { class: "o-name", text: path.length === 2 ? `‹ 返回「${g}」` : "‹ 返回全部分类" })));
        out.push(head(path.join(" › ")));
        const inGroup = items.filter((i) => i.group === g);
        if (subLevel && path.length === 1) {                      // 门类下面先列专业类
          tiles = true;
          entries = [...new Set(inGroup.map((i) => i.sub))].map((c) => () => tile(c, inGroup.filter((i) => i.sub === c).length, { "data-sub": c }));
        } else {
          entries = inGroup.filter((i) => !subLevel || i.sub === sub).map((i) => () => itemRow(i, false));
        }
      }
      const size = tiles ? TILE_PAGE : ITEM_PAGE;
      const pages = Math.max(1, Math.ceil(entries.length / size));
      page = Math.min(page, pages - 1);
      const shown = entries.slice(page * size, (page + 1) * size).map((make) => make());
      out.push(tiles ? h("div", { class: "pk-grid" }, ...shown) : shown);
      out.push(tail.map((make) => make()));
      if (pages > 1) out.push(pager(pages, entries.length));
      list.replaceChildren(...out.flat());
      list.scrollTop = 0;
      active = rows.length && query_ ? 0 : -1;
      paintActive(false);
    }

    function goPage(n) {
      page = n;
      renderList();
    }

    function paintActive(scroll) {
      rows.forEach((r, i) => r.classList.toggle("active", i === active));
      if (active >= 0 && rows[active]) {
        input.setAttribute("aria-activedescendant", rows[active].id);
        if (scroll) rows[active].scrollIntoView({ block: "nearest" });
      } else input.removeAttribute("aria-activedescendant");
    }

    // 保证列表完整出现在可视区域内：下方空间不够就把页面往上滚一点，再按剩余空间限制列表高度
    function fit() {
      const vh = window.visualViewport ? window.visualViewport.height : window.innerHeight;
      let space = vh - box.getBoundingClientRect().bottom - 12;
      if (space < 320) {
        window.scrollBy(0, Math.max(0, Math.min(320 - space, box.getBoundingClientRect().top - 60)));
        space = vh - box.getBoundingClientRect().bottom - 12;
      }
      list.style.maxHeight = `${Math.round(Math.max(220, Math.min(LIST_MAX, space)))}px`;
    }

    function openList() {
      if (isOpen) return;
      isOpen = true;
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      fit();
      renderList();
    }
    function closeList() {
      isOpen = false;
      list.hidden = true;
      query = ""; path = []; page = 0; input.value = "";
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }

    function changed() { renderChips(); if (opts.onChange) opts.onChange(selected.slice()); }
    function toggle(item) {
      if (isOn(item.key)) selected = selected.filter((s) => s.key !== item.key);
      else selected = multi ? [...selected, item] : [item];
      query = ""; input.value = ""; page = 0;
      changed();
      if (opts.keepOpen && isOpen) renderList(); else closeList();
    }
    function activate(el) {
      const d = el.dataset;
      if (d.custom) { const it = opts.custom(query.trim()); if (it) toggle(it); return; }
      if (d.key) { const it = items.find((i) => i.key === d.key); if (it) toggle(it); return; }
      if (d.group) path = [d.group];
      else if (d.sub) path = [path[0], d.sub];
      else if (d.back) path = path.slice(0, -1);
      page = 0;
      renderList();
      list.scrollTop = 0;
    }

    // 点列表里的项：用 mousedown 并阻止默认行为，输入框就不会失焦
    list.addEventListener("mousedown", (e) => {
      const pg = e.target.closest(".pg");
      if (pg) { e.preventDefault(); if (pg.dataset.page !== undefined && !pg.classList.contains("off") && !pg.classList.contains("cur")) goPage(Number(pg.dataset.page)); return; }
      const r = e.target.closest(".opt");
      if (r && r.dataset.act) { e.preventDefault(); activate(r); }
      else if (e.target === list) e.preventDefault();
    });
    chips.addEventListener("click", (e) => {
      const b = e.target.closest(".chip-x");
      if (!b) return;
      selected = selected.filter((s) => s.key !== b.dataset.key);
      changed();
      if (isOpen) renderList();
    });
    box.addEventListener("mousedown", (e) => { if (e.target === box || e.target === chips) { e.preventDefault(); input.focus({ preventScroll: true }); openList(); } });
    input.addEventListener("focus", openList);
    input.addEventListener("click", openList);
    input.addEventListener("input", () => { query = input.value; path = []; page = 0; if (!isOpen) openList(); else renderList(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!isOpen) { openList(); return; }
        if (rows.length) { active = (active + (e.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length; paintActive(true); }
      } else if (e.key === "Enter") {
        e.preventDefault();                  // 不要让回车提交表单
        if (isOpen && active >= 0 && rows[active]) activate(rows[active]);
      } else if ((e.key === "PageDown" || e.key === "PageUp") && isOpen) {
        e.preventDefault();
        const to = page + (e.key === "PageDown" ? 1 : -1), pg = list.querySelector(`.pg[data-page="${to}"]`);
        if (pg) goPage(to);
      } else if (e.key === "Escape") {
        if (isOpen) { e.preventDefault(); e.stopPropagation(); closeList(); }
      } else if (e.key === "Backspace" && !input.value && selected.length) {
        selected = selected.slice(0, -1); changed(); if (isOpen) renderList();
      } else if (e.key === "Tab") closeList();
    });
    // 用 composedPath 而不是 contains：点分类会重新渲染列表，被点的那一行此时已经脱离页面，contains 会误判成「点在外面」把列表关掉
    document.addEventListener("mousedown", (e) => { if (isOpen && !e.composedPath().includes(root)) closeList(); });

    renderChips();
    return {
      get: () => selected.slice(),
      set: (arr) => { selected = arr.slice(); renderChips(); if (isOpen) renderList(); },
    };
  }

  window.Picker = { create };
})();
