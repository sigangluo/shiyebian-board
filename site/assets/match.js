// 岗位 vs 个人条件的匹配规则。这是 scripts/lib/match.py 里 evaluate() 的 JS 版，两边必须给出一模一样的结果：
//   - 文字解析（学历、专业代码、经历年限、年龄上限、考生类别、户籍写法……）已经在 Python 构建时做完，
//     岗位里带着解析好的字段（格式见 scripts/lib/export.py），这里只做「岗位字段 vs 你的条件」的比较；
//   - 提示文字、判断顺序都和 Python 版逐段对应，改规则要两边一起改；
//   - tests/golden/cases.json 是 Python 版算出的「岗位 + 条件 → 结果」样例，`node --test tests/` 会逐条核对 JS 版。
// 可以在浏览器里用（window.Match），也可以在 Node 里 require（测试用）。
"use strict";
(function () {
  const EDU_LEVEL = { 大专: 1, 本科: 2, 硕士: 3, 博士: 4 };
  const LEVEL_NAME = { 1: "大专", 2: "本科", 3: "硕士研究生", 4: "博士研究生" };
  const LEVEL_COL = { 1: "c", 2: "b", 3: "g", 4: "g" };                 // 大专 / 本科 / 研究生栏的字段后缀：mc kc cc / mb kb cb / mg kg cg
  const REASON_ORDER = ["education", "major", "fresh", "hukou", "experience", "age", "gender", "special", "certs", "title", "politics"];
  const REASON_LABEL = {
    education: "学历不符", major: "专业不符", fresh: "应届 / 往届身份不符", hukou: "户籍不符", experience: "要求工作经历",
    age: "年龄超限", gender: "性别不符", special: "专项招聘 / 编外", certs: "要求资格证书", title: "要求职称", politics: "政治面貌不符",
  };
  const FRESH_VALUES = ["auto", "yes", "no", "maybe"];
  const MAJOR_RANK = { 对口: 0, 不限专业: 1, 需核对: 2, "": 3, 不符: 4 };

  const CODE_PAREN = /[（(]\s*([A-Z]?\d{2,8})\s*[）)]/;
  const CODE_BARE = /[A-Z]\d{2,8}/;

  const has = (text, s) => text.includes(s);
  const g = (x) => String(Number(Number(x).toPrecision(6)));             // 对应 Python 的 f"{x:g}"
  const list = (x) => (Array.isArray(x) ? x : []);

  // ---------- 专业 ----------

  // 岗位某一栏专业要求 -> {blank} / {unlimited} / {codes, text}。col 是 c / b / g。
  function majorReq(job, col) {
    const kind = job["k" + col] || "b";
    if (kind === "b") return { blank: true };
    if (kind === "u") return { unlimited: true };
    return { codes: list(job["c" + col]), text: job["m" + col] || "" };
  }

  function majorFit(req, codes, names, keywords, related) {
    keywords = keywords || [];
    related = related || [];
    if (req.codes && req.codes.length) {
      const digits = (c) => c.replace(/^[A-Z]/, "");          // 浙江只写数字，别的地区带字母，统一成数字再比
      let verdict = "no";
      for (const r0 of req.codes) {
        const r = digits(r0);
        for (const u0 of codes) {
          const u = digits(u0);
          if (u.startsWith(r)) return "match";
          if (r.startsWith(u)) verdict = "check";
        }
      }
      if (verdict === "no") {
        const text = req.text;
        if (names.some((n) => n && has(text, n))) return "check";       // 名称相同、代码不同：多半是两套目录的写法
        for (const seg of text.split(/[；;、，,\n]+/)) {                // 混写：只写名称的那几段
          if (!CODE_PAREN.test(seg) && !CODE_BARE.test(seg)
              && [...names.map((n) => n.slice(0, 3)), ...keywords, ...related].some((x) => x && has(seg, x))) return "check";
        }
      }
      return verdict;
    }
    const text = req.text || "";
    if (names.some((n) => n && has(text, n)) || keywords.some((k) => k && has(text, k))) return "match";
    if (related.some((r) => r && has(text, r)) || names.some((n) => n && has(text, n.slice(0, 3)))) return "check";
    return "no";
  }

  // ---------- 应届身份 ----------

  function freshVerdict(profile, rule) {
    const pf = profile.fresh == null ? "auto" : profile.fresh;
    if (pf === "yes" || pf === "no") return [pf, `按所设定的应届身份（${pf === "yes" ? "应届" : "往届"}）`];
    const gy = profile.graduate_year;
    if (pf === "maybe" || !rule || gy == null) return ["maybe", "是否属于应届取决于当地认定，需查阅公告或咨询招聘单位"];
    const kind = rule.kind, window = rule.window == null ? 2 : rule.window;
    const c = rule.cohort + (rule.closed ? 1 : 0);
    const tail = rule.closed ? `（按已结束的这一批的规则推断，假设下一批规则不变、届别顺延到 ${c} 届）` : "";
    const employed = !!profile.employed_now;
    if (kind === "year") return [gy === c ? "yes" : "no", `该批次按毕业年份判断：应届 = ${c} 年毕业，考生为 ${gy} 年毕业${tail}`];
    if (kind === "year_window") {
      const lo = c - window;
      return [lo <= gy && gy <= c ? "yes" : "no", `该批次应届含 ${lo}–${c} 年毕业，不看是否在职，考生为 ${gy} 年毕业${tail}`];
    }
    if (!(c - window <= gy && gy <= c)) return ["no", `该批次应届限毕业 ${window} 年内（${c - window}–${c} 年毕业），考生为 ${gy} 年毕业${tail}`];
    if (kind === "unemployed") {
      return employed ? ["no", `该批次要求报名时无工作单位，考生目前在职${tail}`]
        : ["yes", `该批次规则：毕业 ${window} 年内且报名时无工作单位，考生符合（报名时仍须无工作单位）${tail}`];
    }
    if (kind === "no_staff_job") {
      return profile.had_staff_job ? ["no", `该批次要求未落实编制内工作，考生有编制内工作经历${tail}`]
        : ["yes", `该批次规则：毕业 ${window} 年内且未落实「编制内」工作，私企工作不影响，考生符合${tail}`];
    }
    if (kind === "unplaced") {
      if (employed) return ["no", `该批次要求非在职，考生目前在职${tail}`];
      if (gy === c || !profile.had_any_job) return ["yes", `该批次规则：非在职的当届毕业生或未落实工作单位的往届毕业生，考生符合${tail}`];
      return ["maybe", `该批次要求往届毕业生「未落实工作单位」，考生入职后又离职，是否属于「落实」公告未说明，需咨询${tail}`];
    }
    throw new Error(`未知的应届规则 kind: ${kind}`);
  }

  // ---------- 综合判断 ----------

  // 返回 {status: ok|check|no, no: [[类别, 说明]], check: [说明], major, lower, fresh_info}
  function evaluate(job, profile, freshRule) {
    const no = [], check = [];
    let majorLabel = "";
    const U = EDU_LEVEL[profile.education];
    const majors = profile.majors || {};
    let verdict = null;                                     // 应届判断只算一次，后面户籍也会用到
    const fresh = () => (verdict = verdict || freshVerdict(profile, freshRule));

    // 学历：决定后面比较哪一栏专业要求
    let useLevel = U;
    if (!job.el) {
      check.push(`学历要求「${job.ed || ""}」写法无法识别，需核对`);
    } else {
      const lv = job.el, plus = !!job.ep;
      if (plus) {
        if (U < lv) no.push(["education", `要求${LEVEL_NAME[lv]}以上，考生为${profile.education}`]);
      } else if (U < lv) {
        no.push(["education", `要求${LEVEL_NAME[lv]}，考生为${profile.education}`]);
      } else if (U > lv) {
        useLevel = lv;                                      // 只要求较低学历：只能用较低学历（及其专业）报考，很多地方不允许
        const low = majors[{ 1: "college", 2: "bachelor" }[lv]] || {};
        if (lv === 1 && !(list(low.codes).length || list(low.names).length)) {
          no.push(["education", `岗位只要求${LEVEL_NAME[lv]}，未填写${LEVEL_NAME[lv]}学历，按无该层次学历处理`]);
        } else {
          check.push(`岗位只要求${LEVEL_NAME[lv]}，考生的最高学历更高，需核实能否以${LEVEL_NAME[lv]}学历（及专业）报考`);
        }
      }
    }

    // 专业
    let skipMajor = false;
    if (job.ei && useLevel >= 3) {
      // 岗位写明「本科专业、研究生专业符合其一即可」：分别按研究生专业、本科专业比一遍，取对口的
      const plain = { ...job, ei: false };                  // 去掉标记，否则会无限递归
      const asGrad = { ...plain, mg: job.mg || job.mb, kg: job.mg ? job.kg : job.kb, cg: job.mg ? job.cg : job.cb };
      const asBach = { ...plain, el: 2, ep: false, ed: "本科", mb: job.mb || job.mg, kb: job.mb ? job.kb : job.kg, cb: job.mb ? job.cb : job.cg };
      const either = [evaluate(asGrad, profile, freshRule), evaluate(asBach, profile, freshRule)];
      let best = either[0];
      for (const e of either) if ((MAJOR_RANK[e.major] ?? 3) < (MAJOR_RANK[best.major] ?? 3)) best = e;
      majorLabel = best.major;
      if (majorLabel === "不符") no.push(["major", "专业要求「本科或研究生专业符合其一」，考生的本科、研究生专业均不在其列"]);
      else if (majorLabel === "需核对") check.push("专业要求「本科或研究生专业符合其一」，考生专业与岗位表的写法不易对应，需核对");
      skipMajor = true;
    }
    const col = LEVEL_COL[useLevel];
    const req = majorReq(job, col);
    const mine = majors[useLevel >= 3 ? "graduate" : useLevel === 2 ? "bachelor" : "college"] || {};
    const codes = list(mine.codes), names = list(mine.names);
    const keywords = list(mine.keywords).length ? list(mine.keywords) : names, related = list(mine.related);
    if (skipMajor) {
      // 已经按「符合其一」处理过
    } else if (req.unlimited) {
      majorLabel = "不限专业";
    } else if (req.blank) {
      const lowerCols = ["b", "c"].filter((c) => job["m" + c]);
      if (!["c", "b", "g"].some((c) => job["m" + c])) {
        majorLabel = "不限专业";
      } else if (useLevel >= 3 && lowerCols.length) {
        // 「本科以上」的岗位只写了一栏专业（本科栏）：研究生能不能用，各地写法不一，先按你的本科专业比一下，提醒核对
        const c = lowerCols[0], k = c === "b" ? "bachelor" : "college";
        const lowReq = majorReq(job, c), low = majors[k] || {};
        const label = c === "b" ? "本科" : "大专";
        if (lowReq.unlimited) {
          majorLabel = "不限专业";
        } else if (list(low.codes).length || list(low.names).length) {
          const fit = majorFit(lowReq, list(low.codes), list(low.names), list(low.keywords).length ? list(low.keywords) : list(low.names), list(low.related));
          majorLabel = fit === "match" ? "对口" : "需核对";
          check.push(`岗位只写了${label}专业要求「${lowReq.text.slice(0, 30)}」，按考生的${label}专业比对：`
            + `${{ match: "对口", check: "可能对口", no: "不对口" }[fit]}；研究生能否按此报考需核对`);
        } else {
          majorLabel = "需核对";
          check.push(`岗位只写了${label}专业要求，未填写${label}专业，无法比对`);
        }
      } else {
        majorLabel = "";
        check.push(`该岗位没有写${LEVEL_NAME[useLevel]}栏的专业要求，需核对`);
      }
    } else if (!codes.length && !names.length) {
      majorLabel = "需核对";
      check.push(`未填写${LEVEL_NAME[useLevel]}专业，无法比对「${req.text.slice(0, 30)}」`);
    } else {
      const fit = majorFit(req, codes, names, keywords, related);
      if (fit === "match") {
        majorLabel = "对口";
      } else if (fit === "check") {
        majorLabel = "需核对";
        check.push(`专业要求「${req.text.slice(0, 40)}」写法特殊或比考生专业更细，需核对`);
      } else {
        majorLabel = "不符";
        no.push(["major", `专业要求「${req.text.slice(0, 40)}」不含考生专业`]);
      }
    }

    // 考生类别（应届 / 往届 / 在编）
    const cat = job.fr || "";
    let freshInfo = "";
    if (job.zb) no.push(["fresh", `考生类别「${cat}」，仅限在编人员报考`]);
    if (job.fo) {
      const [v, note] = fresh();
      freshInfo = note;
      if (v === "no") no.push(["fresh", `限应届毕业生，${note}`]);
      else if (v === "maybe") check.push(`限应届毕业生：${note}`);
    } else if (job.pn) {
      const [v, note] = fresh();
      if (v === "yes") no.push(["fresh", `限往届 / 社会人员，而${note}`]);
      else if (v === "maybe") check.push(`限往届 / 社会人员：${note}`);
    }

    // 工作经历（xy 没有 = 无要求；null = 写了但认不出年限）
    const years = job.xy === undefined ? 0 : job.xy;
    const wm = profile.work_months;
    if (years === null) {
      check.push(`工作经历要求「${(job.xp || "").slice(0, 30)}」无法识别，需核对`);
    } else if (years > 0) {
      if (wm == null) check.push(`要求 ${g(years)} 年工作经历，未填写工作经历月数`);
      else if (wm < years * 12) no.push(["experience", `要求 ${g(years)} 年工作经历，考生有 ${g(wm)} 个月`]);
    }

    // 年龄
    const age = profile.age;
    if (age != null) {
      let mx = job.amx == null ? null : job.amx;
      let relaxed = null;
      if (U >= 3) relaxed = (U === 3 ? job.arx : job.adx) ?? null;
      mx = mx && relaxed ? Math.max(mx, relaxed) : (mx || relaxed || null);
      if (mx !== null && age > mx) no.push(["age", `年龄上限 ${mx} 周岁，考生 ${age} 岁`]);
      else if (mx === null && job.ag) check.push(`年龄要求「${job.ag.slice(0, 20)}」无法识别，需核对`);
    }

    // 性别：只有岗位明确限定了才筛，没填性别时只提醒
    if (job.gd) {
      if (profile.gender == null) check.push(`岗位限${job.gd}性，未填写性别`);
      else if (profile.gender !== job.gd) no.push(["gender", `岗位限${job.gd}性，考生为${profile.gender}性`]);
    }

    // 专项招聘（退役军人、基层服务项目人员、残疾人……）
    if (job.sp && !profile.include_special) no.push(["special", `专项招聘：${job.sp}`]);

    // 资格证书（英语四六级单独处理：六级满足四级；没填英语等级就只提醒，不判不符）
    const held = list(profile.certs);
    const missing = [];
    for (const c of list(job.cl)) {
      if (/英语[四六]级|CET/.test(c)) {
        const need = (has(c, "六级") && U >= 3) || !has(c, "四级") ? 6 : 4;
        const have = profile.english;
        if (have == null) check.push(`要求大学英语${need === 6 ? "六" : "四"}级，未填写英语等级`);
        else if (({ CET4: 4, CET6: 6 }[have] || 0) < need) missing.push(c);
      } else if (!held.some((h) => has(c, h) || has(h, c))) {
        missing.push(c);
      }
    }
    if (missing.length) no.push(["certs", `要求资格证书：${missing.join("、")}`]);

    // 职称
    if (job.ti) no.push(["title", `要求职称：${job.ti}`]);

    // 政治面貌
    const pol = job.po || "", minePol = profile.politics;
    if (pol) {
      if (minePol == null) {
        check.push(`政治面貌要求「${pol}」，未填写政治面貌`);
      } else if ((has(pol, "党员") && !has(minePol, "党员"))
        || (has(pol, "团员") && !has(pol, "党员") && !["党员", "团员"].some((x) => has(minePol, x)))) {
        no.push(["politics", `政治面貌要求「${pol}」，考生为${minePol}`]);
      }
    }

    // 户籍：明确写「限……户籍」「须具有……户籍 / 居住证」的，和你的户籍对不上就是不符；其他写法只提醒
    if (job.ho) {
      const text = job.ho;
      let mineH = profile.hukou == null ? [] : profile.hukou;
      mineH = typeof mineH === "string" ? [mineH] : list(mineH);
      const heldH = [...mineH, ...list(profile.residence)];              // residence：你持有有效居住证的城市
      const explicit = !!job.he, onlyNonfresh = !!job.hn;
      const shown = `户籍要求：${text.slice(0, 50)}（考生户籍：${mineH.join("、") || "未填"}）`;
      if (onlyNonfresh && fresh()[0] === "yes") {
        // 这条只针对非应届，你算应届，不受影响
      } else if (heldH.some((h) => h && has(text, h))) {
        // 户籍 / 居住证对得上
      } else if (explicit && onlyNonfresh && fresh()[0] === "maybe") {
        check.push(shown + "；若考生属于应届则不受此限");
      } else if (explicit) {
        no.push(["hukou", shown]);
      } else {
        check.push(shown);
      }
    }
    if (job.ot) check.push(`其他条件：${job.ot.slice(0, 60)}`);

    const status = no.length ? "no" : check.length ? "check" : "ok";
    return { status, no, check, major: majorLabel, lower: useLevel < U, fresh_info: freshInfo };
  }

  // 被判不符的岗位，按 REASON_ORDER 取第一个类别，用来统计
  function mainReason(no) {
    const kinds = new Set(no.map((x) => x[0]));
    return REASON_ORDER.find((k) => kinds.has(k)) || null;
  }

  // ---------- 批次状态和招聘日历（和 scripts/build.py 里的 batch_status 一致）----------

  function batchStatus(b, today) {
    if (!b.signup_start) return "rolling";
    if (today < b.signup_start) return "upcoming";
    return today <= b.signup_end ? "open" : "closed";
  }

  const iso = (d) => d.toISOString().slice(0, 10);
  function addYears(s, n) {                                  // 2 月 29 日顺延到没有闰日的年份时落在 2 月 28 日
    const [y, m, d] = s.split("-").map(Number);
    const out = new Date(Date.UTC(y + n, m - 1, d));
    if (out.getUTCMonth() !== m - 1) out.setUTCDate(0);
    return iso(out);
  }

  // 已结束的批次：按去年同期推算下一批的报名时间（顺延一年，直到不早于今天）。返回 [start, end] 或 null。只是推算。
  function nextEstimate(b, today) {
    if (!b.signup_start || b.signup_end >= today) return null;
    for (let n = 1; ; n++) {
      const end = addYears(b.signup_end, n);
      if (end >= today) return [addYears(b.signup_start, n), end];
    }
  }

  // 校验并整理个人条件：返回 null 表示还不能筛（没选最高学历）
  function normalizeProfile(p) {
    if (!p || !(p.education in EDU_LEVEL)) return null;
    if (!FRESH_VALUES.includes(p.fresh == null ? "auto" : p.fresh)) return null;
    return p;
  }

  const Match = { evaluate, freshVerdict, majorFit, mainReason, batchStatus, nextEstimate, normalizeProfile,
    REASON_LABEL, REASON_ORDER, EDU_LEVEL, MAJOR_RANK };
  if (typeof module !== "undefined" && module.exports) module.exports = Match;
  else window.Match = Match;
})();
