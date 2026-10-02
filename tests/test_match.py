"""岗位匹配规则的测试。运行: python3 -m unittest discover -s tests

用例的写法都来自广东 2026 年岗位表里真实出现过的内容；改 scripts/lib/match.py 的规则后先跑一遍，
避免改好一处、坏了另一处。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib.match import (batch_rule, evaluate, fresh_verdict, major_fit, parse_education, parse_experience_years, parse_major,
                       parse_max_age, parse_relaxed_age)
from lib.schema import make_job, validate

ME = {"education": "硕士", "majors": {"graduate": {"codes": ["A0812"], "names": ["计算机科学与技术"]},
                                      "bachelor": {"codes": [], "names": []}},
      "fresh": "maybe", "work_months": 3, "age": None, "politics": None, "hukou": None, "certs": []}


def job(**kw):
    base = dict(id="1", batch="b", unit="某单位", education="本科以上", major_graduate="计算机科学与技术(A0812)",
                major_bachelor="计算机类(B0809)", fresh="不限", age="18-38周岁", age_relaxed="放宽到40周岁")
    base.update(kw)
    return make_job(**base)


class Parsing(unittest.TestCase):
    def test_education(self):
        self.assertEqual(parse_education("本科以上"), (2, True))
        self.assertEqual(parse_education("硕士研究生以上"), (3, True))
        self.assertEqual(parse_education("硕士研究生"), (3, False))
        self.assertEqual(parse_education("博士研究生"), (4, False))
        self.assertEqual(parse_education("大专以上"), (1, True))
        self.assertIsNone(parse_education("其他"))

    def test_major(self):
        self.assertEqual(parse_major(None), {"blank": True})
        self.assertEqual(parse_major("不限"), {"unlimited": True})
        r = parse_major("计算机科学与技术(A0812),软件工程(A0835),计算机技术硕士（专业硕士）(A084004)")
        self.assertEqual(r["codes"], ["A0812", "A0835", "A084004"])

    def test_only_serving_staff(self):
        self.assertEqual(evaluate(job(fresh="机关事业单位正式在编人员"), ME)["status"], "no")

    def test_experience(self):
        self.assertEqual(parse_experience_years(None), 0)
        self.assertEqual(parse_experience_years("2年以上相关工作经历"), 2)
        self.assertEqual(parse_experience_years("本工种（职业方向）下一级岗位工作满5年"), 5)
        self.assertEqual(parse_experience_years("两年以上"), 2)
        self.assertEqual(parse_experience_years("6个月"), 0.5)
        self.assertIsNone(parse_experience_years("有相关工作经历"))

    def test_age(self):
        self.assertEqual(parse_max_age("18-38周岁"), 38)
        self.assertEqual(parse_max_age("35周岁以下"), 35)
        self.assertEqual(parse_max_age("放宽到40周岁"), 40)     # 博士岗位的年龄栏直接这么写
        self.assertEqual(parse_relaxed_age("放宽到45周岁"), 45)
        self.assertIsNone(parse_max_age(""))


class Major(unittest.TestCase):
    def fit(self, req, codes=("A0812",), names=("计算机科学与技术",), keywords=(), related=()):
        return major_fit(parse_major(req), list(codes), list(names), keywords, related)

    def test_exact_and_category(self):
        self.assertEqual(self.fit("计算机科学与技术(A0812),软件工程(A0835)"), "match")
        self.assertEqual(self.fit("工学(A08)"), "match")            # 学科门类 A08 涵盖 A0812
        self.assertEqual(self.fit("软件工程(A0835),网络空间安全(A0839)"), "no")

    def test_narrower_requirement_needs_check(self):
        self.assertEqual(self.fit("计算机系统结构(A081201)"), "check")   # 比你的一级学科更细，方向不确定

    def test_numeric_codes_without_letter(self):          # 浙江只写数字代码
        self.assertEqual(parse_major("理学（07）、工学（08）")["codes"], ["07", "08"])
        self.assertEqual(self.fit("理学（07）、工学（08）"), "match")        # 08 工学涵盖 0812
        self.assertEqual(self.fit("经济学（02）、管理学（12）"), "no")
        self.assertEqual(self.fit("计算机科学与技术（0812）"), "match")

    def test_full_width_parentheses(self):                # 深圳用全角括号
        self.assertEqual(parse_major("计算机科学与技术（A0812）；软件工程（A0835）")["codes"], ["A0812", "A0835"])

    def test_same_name_different_code_needs_check(self):
        # 浙江：计算机科学与技术在理学（0775）和工学（0812）两套目录里都有，名称相同代码不同
        self.assertEqual(self.fit("计算机科学与技术（0775）；数学（0701）"), "check")
        self.assertEqual(self.fit("计算机技术硕士（专业硕士）(A084004)"), "no")    # 名称不同的专业学位：代码是权威，判不符

    def test_mixed_codes_and_names(self):
        self.assertEqual(self.fit("法学（03）；计算机类；教育学（04）"), "check")     # 只写名称的那段能对上前三个字
        self.assertEqual(self.fit("法学（03）；教育学（04）；中国语言文学"), "no")

    def test_name_only(self):
        self.assertEqual(self.fit("计算机科学与技术相关专业"), "match")
        self.assertEqual(self.fit("财务管理、会计学、经济学等相关专业"), "no")       # 一个关键词都对不上才判不符

    def test_name_only_keywords_and_related(self):          # 上海：「计算机、通信工程等相关专业」这种只有文字的写法
        kw, rel = ("计算机", "软件", "工学", "理工"), ("信息", "电子", "通信")
        self.assertEqual(self.fit("计算机、通信工程等相关专业", keywords=kw, related=rel), "match")
        self.assertEqual(self.fit("理工类相关专业", keywords=kw, related=rel), "match")
        self.assertEqual(self.fit("信息管理与信息系统相关专业", keywords=kw, related=rel), "check")
        self.assertEqual(self.fit("信息管理与信息系统相关专业", keywords=kw), "no")


class FreshRules(unittest.TestCase):
    """每个批次有自己的应届规则；用例都来自 2026 年各地公告 / 指南里的原文。"""
    ME2 = {**ME, "fresh": "auto", "graduate_year": 2026, "employed_now": False, "had_staff_job": False, "had_any_job": True}

    def v(self, kind, cohort, closed=False, window=2, **profile):
        return fresh_verdict({**self.ME2, **profile}, {"kind": kind, "cohort": cohort, "window": window, "closed": closed})[0]

    def test_shanghai_private_job_does_not_count(self):      # 毕业证书落款年度2年内未落实「编制内」工作
        self.assertEqual(self.v("no_staff_job", 2026), "yes")
        self.assertEqual(self.v("no_staff_job", 2026, closed=True), "yes")          # 下一批 2027：2026 仍在两年内
        self.assertEqual(self.v("no_staff_job", 2026, had_staff_job=True), "no")
        self.assertEqual(self.v("no_staff_job", 2026, closed=True, graduate_year=2024), "no")

    def test_jiangsu_unemployed_at_signup(self):             # 2026年毕业生 = 报名时无工作单位
        self.assertEqual(self.v("unemployed", 2026, closed=True), "yes")
        self.assertEqual(self.v("unemployed", 2026, closed=True, employed_now=True), "no")
        self.assertEqual(self.v("unemployed", 2026, closed=True, graduate_year=2024), "no")   # 2027 批：只含 2025–2027

    def test_zhejiang_graduation_year(self):
        self.assertEqual(self.v("year", 2026), "yes")                                # 本批次：2026 年毕业算应届
        self.assertEqual(self.v("year", 2026, closed=True), "no")                    # 下一批换成 2027 届

    def test_hangzhou_year_window_ignores_employment(self):  # 2024、2025、2026 年毕业生都算，公告没提在职
        self.assertEqual(self.v("year_window", 2026, graduate_year=2024, employed_now=True), "yes")
        self.assertEqual(self.v("year_window", 2026, graduate_year=2023), "no")
        self.assertEqual(self.v("year_window", 2026, closed=True, graduate_year=2024), "no")  # 下一批顺延为 2025–2027
        self.assertEqual(self.v("year_window", 2026, closed=True, graduate_year=2025), "yes")

    def test_guangdong_unplaced_is_ambiguous_for_those_who_worked(self):
        self.assertEqual(self.v("unplaced", 2026), "yes")                            # 当届、非在职
        self.assertEqual(self.v("unplaced", 2026, closed=True), "maybe")             # 往届：入职过又离职，算不算「落实」没写
        self.assertEqual(self.v("unplaced", 2026, closed=True, had_any_job=False), "yes")
        self.assertEqual(self.v("unplaced", 2026, closed=True, employed_now=True), "no")

    def test_overrides(self):
        self.assertEqual(self.v("year", 2026, closed=True, fresh="yes"), "yes")
        self.assertEqual(self.v("no_staff_job", 2026, fresh="no"), "no")
        self.assertEqual(self.v("no_staff_job", 2026, fresh="maybe"), "maybe")
        self.assertEqual(fresh_verdict(self.ME2, None)[0], "maybe")                  # 没有规则就待定

    def test_evaluate_uses_batch_rule(self):
        rule = {"kind": "no_staff_job", "cohort": 2026, "window": 2}
        j = job(fresh="应届毕业生")
        self.assertEqual(evaluate(j, self.ME2, rule)["status"], "ok")
        self.assertIn("私企", evaluate(j, self.ME2, rule)["fresh_info"])
        self.assertEqual(evaluate(j, {**self.ME2, "had_staff_job": True}, rule)["status"], "no")

    def test_category_wording(self):
        rule = {"kind": "no_staff_job", "cohort": 2026, "window": 2}
        # 「非应届毕业生」里有「应届」两个字，不能被当成应届岗位
        self.assertEqual(evaluate(job(fresh="非应届毕业生"), {**self.ME2, "fresh": "no"}, rule)["status"], "ok")
        self.assertEqual(evaluate(job(fresh="非应届毕业生"), self.ME2, rule)["status"], "no")        # 你算应届，不能报非应届岗位
        self.assertEqual(evaluate(job(fresh="2026年毕业生"), {**self.ME2, "fresh": "no"})["status"], "no")   # 江苏的写法
        self.assertEqual(evaluate(job(fresh="社会人员"), {**self.ME2, "fresh": "no"})["status"], "ok")


class Gender(unittest.TestCase):
    def test_explicit_restrictions_only(self):
        fem = job(duty="从事辅导员岗，需入住女生宿舍开展工作。")
        male = job(duty="长期户外工作，需登高作业，适合男性报考")
        self.assertEqual(evaluate(fem, {**ME, "gender": "男"})["status"], "no")
        self.assertEqual(evaluate(fem, {**ME, "gender": "女"})["status"], "ok")
        self.assertEqual(evaluate(male, {**ME, "gender": "男"})["status"], "ok")
        self.assertEqual(evaluate(male, {**ME, "gender": "女"})["status"], "no")
        self.assertEqual(evaluate(fem, ME)["status"], "check")                       # 没填性别：只提醒
        self.assertEqual(evaluate(job(), {**ME, "gender": "男"})["status"], "ok")    # 没有限定就不管

    def test_both_wordings_means_no_restriction(self):
        both = job(duty="辅导员岗，男女分设，需入住男生宿舍或女生宿舍")
        self.assertEqual(evaluate(both, {**ME, "gender": "男"})["status"], "ok")

    def test_extra_fields_are_checked(self):          # 上海 / 江苏：限女性写在「其它条件原文」里
        j = job(extra={"其它条件原文": "所在部门系全部为女性的巾帼文明岗，需与女同事双岗值守夜班，限女性"})
        self.assertEqual(evaluate(j, {**ME, "gender": "男"})["status"], "no")

    def test_gender_column(self):                    # 杭州：单独一列，取值就是「男」「女」，「不限制」不算限定
        self.assertEqual(evaluate(job(extra={"性别要求": "男"}), {**ME, "gender": "女"})["status"], "no")
        self.assertEqual(evaluate(job(extra={"性别要求": "女"}), {**ME, "gender": "女"})["status"], "ok")
        self.assertEqual(evaluate(job(extra={"性别要求": "不限制"}), {**ME, "gender": "女"})["status"], "ok")


class English(unittest.TestCase):
    def test_levels(self):
        j6, j4 = job(certs="大学英语六级"), job(certs="大学英语四级以上")
        self.assertEqual(evaluate(j6, ME)["status"], "check")                       # 没填英语等级：只提醒
        self.assertEqual(evaluate(j6, {**ME, "english": "CET6"})["status"], "ok")
        self.assertEqual(evaluate(j6, {**ME, "english": "CET4"})["status"], "no")
        self.assertEqual(evaluate(j4, {**ME, "english": "CET6"})["status"], "ok")   # 六级满足四级
        self.assertEqual(evaluate(j4, {**ME, "english": "CET4"})["status"], "ok")


class EitherMajor(unittest.TestCase):
    ME4 = {**ME, "majors": {"graduate": {"codes": ["A0812"], "names": ["计算机科学与技术"]},
                            "bachelor": {"codes": ["B080902"], "names": ["软件工程"]}}}

    def test_best_of_bachelor_and_graduate(self):
        j = job(education="硕士研究生以上", major_graduate="软件工程、电子信息", major_bachelor="软件工程、电子信息",
                extra={"专业口径": "本科或研究生符合其一"})
        r = evaluate(j, self.ME4)                       # 研究生专业（计算机科学与技术）对不上，但本科软件工程对得上
        self.assertEqual((r["status"], r["major"]), ("ok", "对口"))
        j = job(education="硕士研究生以上", major_graduate="会计学", major_bachelor="会计学", extra={"专业口径": "本科或研究生符合其一"})
        self.assertEqual(evaluate(j, self.ME4)["status"], "no")
        # 不写这条口径时，只看研究生专业
        j = job(education="硕士研究生以上", major_graduate="软件工程", major_bachelor="软件工程")
        self.assertEqual(evaluate(j, self.ME4)["major"], "不符")


class Hukou(unittest.TestCase):
    ME3 = {**ME, "fresh": "auto", "graduate_year": 2026, "hukou": ["广东", "汕头"], "residence": []}
    RULE = {"kind": "no_staff_job", "cohort": 2026, "window": 2}

    def test_explicitly_restricted_is_no(self):
        self.assertEqual(evaluate(job(hukou="限上海户籍"), self.ME3, self.RULE)["status"], "no")
        self.assertEqual(evaluate(job(hukou="具有深圳市户籍"), self.ME3)["status"], "no")
        self.assertEqual(evaluate(job(hukou="具有广东省户籍"), self.ME3)["status"], "ok")

    def test_vague_wording_only_warns(self):
        r = evaluate(job(hukou="户籍不限，深圳户籍优先"), self.ME3)
        self.assertEqual(r["status"], "check")

    def test_shanghai_residence_permit_rule(self):
        text = "外省市户籍非应届毕业人员须持有上海市居住证一年以上"
        self.assertEqual(evaluate(job(hukou=text), self.ME3, self.RULE)["status"], "ok")     # 你算应届：不受影响
        self.assertEqual(evaluate(job(hukou=text), {**self.ME3, "fresh": "no"})["status"], "no")
        self.assertEqual(evaluate(job(hukou=text), {**self.ME3, "fresh": "maybe"})["status"], "check")
        self.assertEqual(evaluate(job(hukou=text), {**self.ME3, "fresh": "no", "residence": ["上海"]})["status"], "ok")


class Evaluate(unittest.TestCase):
    def test_match_ok(self):
        r = evaluate(job(), ME)
        self.assertEqual((r["status"], r["major"], r["lower"]), ("ok", "对口", False))

    def test_wrong_major_is_no(self):
        r = evaluate(job(major_graduate="会计学(A120201)"), ME)
        self.assertEqual((r["status"], r["major"]), ("no", "不符"))

    def test_education(self):
        self.assertEqual(evaluate(job(education="博士研究生"), ME)["status"], "no")
        self.assertEqual(evaluate(job(education="硕士研究生"), ME)["status"], "ok")

    def test_lower_degree_only_is_check_and_flagged(self):
        r = evaluate(job(education="本科", major_graduate=""), ME)      # 只要求本科：只能以本科学历报考
        self.assertEqual((r["status"], r["lower"]), ("check", True))
        self.assertTrue(any("本科" in c for c in r["check"]))

    def test_only_bachelor_column_written_for_postgraduate(self):
        # 「本科以上」岗位只写了本科栏专业（浙江的写法）：按你的本科专业比对，但仍要核对研究生能否这样报
        me = {**ME, "majors": {**ME["majors"], "bachelor": {"codes": ["B080902"], "names": ["软件工程"]}}}
        r = evaluate(job(major_graduate="", major_bachelor="计算机类（0809）"), me)
        self.assertEqual((r["status"], r["major"]), ("check", "对口"))
        self.assertTrue(any("研究生能否" in c for c in r["check"]))
        r = evaluate(job(major_graduate="", major_bachelor="会计学（1202）"), me)
        self.assertEqual((r["status"], r["major"]), ("check", "需核对"))        # 不对口也只是待确认，不判不符
        self.assertEqual(evaluate(job(major_graduate="", major_bachelor="不限"), me)["major"], "不限专业")

    def test_college_only_job_is_no_without_a_college_degree(self):
        r = evaluate(job(education="大专", major_college="计算机类", major_graduate="", major_bachelor=""), ME)
        self.assertEqual(r["status"], "no")                                        # 硕士没有大专学历这一层，不能用大专报
        me = {**ME, "majors": {**ME["majors"], "college": {"codes": [], "names": ["计算机应用技术"]}}}
        self.assertEqual(evaluate(job(education="大专", major_college="计算机类", major_graduate="", major_bachelor=""), me)["status"], "check")

    def test_lower_degree_uses_bachelor_major_when_known(self):
        me = {**ME, "majors": {**ME["majors"], "bachelor": {"codes": ["B080901"], "names": []}}}
        self.assertEqual(evaluate(job(education="本科", major_graduate=""), me)["major"], "对口")   # B080901 属于 B0809
        wrong = evaluate(job(education="本科", major_graduate="", major_bachelor="会计学(B120203)"), me)
        self.assertEqual(wrong["status"], "no")

    def test_fresh_graduate_only(self):
        j = job(fresh="应届毕业生")
        self.assertEqual(evaluate(j, ME)["status"], "check")                      # 待定：放进待确认
        self.assertEqual(evaluate(j, {**ME, "fresh": "no"})["status"], "no")
        self.assertEqual(evaluate(j, {**ME, "fresh": "yes"})["status"], "ok")
        self.assertEqual(evaluate(job(fresh="不限"), {**ME, "fresh": "no"})["status"], "ok")

    def test_experience(self):
        self.assertEqual(evaluate(job(experience="2年以上相关工作经历"), ME)["status"], "no")
        self.assertEqual(evaluate(job(experience="2年以上相关工作经历"), {**ME, "work_months": 30})["status"], "ok")
        self.assertEqual(evaluate(job(experience="2年以上相关工作经历"), {**ME, "work_months": None})["status"], "check")

    def test_age_only_when_filled(self):
        old = job(age="18-38周岁", age_relaxed="放宽到40周岁")
        self.assertEqual(evaluate(old, ME)["status"], "ok")                       # 没填年龄就不按年龄筛
        self.assertEqual(evaluate(old, {**ME, "age": 40})["status"], "ok")         # 硕士放宽到 40
        self.assertEqual(evaluate(old, {**ME, "age": 41})["status"], "no")
        self.assertEqual(evaluate(job(age="18-38周岁", age_relaxed=""), {**ME, "age": 39})["status"], "no")

    def test_special_certs_title(self):
        self.assertEqual(evaluate(job(special="基层服务项目人员"), ME)["status"], "no")
        self.assertEqual(evaluate(job(special="基层服务项目人员"), {**ME, "include_special": True})["status"], "ok")
        self.assertEqual(evaluate(job(certs="教师资格"), ME)["status"], "no")
        self.assertEqual(evaluate(job(certs="教师资格"), {**ME, "certs": ["教师资格"]})["status"], "ok")
        self.assertEqual(evaluate(job(title_req="初级以上"), ME)["status"], "no")

    def test_politics(self):
        j = job(politics="中共党员（含预备党员）")
        self.assertEqual(evaluate(j, ME)["status"], "check")                      # 没填就待确认
        self.assertEqual(evaluate(j, {**ME, "politics": "群众"})["status"], "no")
        self.assertEqual(evaluate(j, {**ME, "politics": "中共党员"})["status"], "ok")
        self.assertEqual(evaluate(job(politics="共青团员"), {**ME, "politics": "中共党员"})["status"], "ok")

    def test_hukou(self):
        j = job(hukou="广东省户籍")
        self.assertEqual(evaluate(j, ME)["status"], "check")                      # 没填就待确认
        self.assertEqual(evaluate(j, {**ME, "hukou": "广东"})["status"], "ok")
        self.assertEqual(evaluate(j, {**ME, "hukou": ["广东", "汕头"]})["status"], "ok")
        self.assertEqual(evaluate(j, {**ME, "hukou": ["浙江", "杭州"]})["status"], "check")   # 自由文本，只提醒不判不符

    def test_no_reason_wins_over_check(self):
        r = evaluate(job(major_graduate="会计学(A120201)", fresh="应届毕业生"), ME)
        self.assertEqual(r["status"], "no")


class AuditFixes(unittest.TestCase):
    """全量核对时发现的几处误判：这些情形不该判「不符」。"""

    def test_politics_either_party_or_league(self):
        j = job(politics="中共党员或共青团员")
        self.assertEqual(evaluate(j, {**ME, "politics": "共青团员"})["status"], "ok")     # 团员也可以报
        self.assertEqual(evaluate(j, {**ME, "politics": "中共党员"})["status"], "ok")
        self.assertEqual(evaluate(j, {**ME, "politics": "群众"})["status"], "no")
        only_party = job(politics="中共党员（含预备党员）")
        self.assertEqual(evaluate(only_party, {**ME, "politics": "共青团员"})["status"], "no")
        self.assertEqual(evaluate(job(politics="共青团员"), {**ME, "politics": "群众"})["status"], "no")

    def test_cert_after_hire_is_not_a_prerequisite(self):
        j = job(certs="录用后2年内必须取得中职、高中或高等教育教师资格证，逾期未取得，解除聘用合同")
        ev = evaluate(j, ME)
        self.assertEqual(ev["status"], "check")
        self.assertTrue(any("聘用后取得" in c for c in ev["check"]))
        self.assertEqual(evaluate(job(certs="教师资格"), ME)["status"], "no")           # 真正的前置证书仍然判不符

    def test_cert_note_is_not_a_certificate(self):
        ev = evaluate(job(certs="（资格审核时提供相关证明文件）"), ME)
        self.assertEqual(ev["status"], "check")
        self.assertEqual(ev["no"], [])

    def test_age_lower_bound_is_not_a_max(self):
        self.assertIsNone(parse_max_age("年满18周岁以上"))
        self.assertEqual(parse_max_age("18周岁以上，38周岁以下"), 38)
        self.assertEqual(parse_max_age("年龄40周岁"), 40)

    def test_age_default_when_table_has_no_age(self):
        rule = batch_rule({"age_default": {"max": 38, "relaxed": 43}})
        j = job(age="", age_relaxed="")
        at = lambda age: evaluate(j, {**ME, "age": age}, rule)["status"]
        self.assertEqual(at(38), "ok")
        self.assertEqual(at(40), "check")                  # 38 < 年龄 <= 43：公告里有放宽的情形，只提醒
        self.assertEqual(at(44), "no")
        self.assertEqual(evaluate(j, {**ME, "age": 44})["status"], "ok")                   # 没有批次规则时不判断
        self.assertEqual(evaluate(job(age="18-45周岁"), {**ME, "age": 40}, rule)["status"], "ok")   # 岗位表写了就按岗位表

    def test_batch_rule(self):
        self.assertIsNone(batch_rule({}))
        fr = {"kind": "year", "cohort": 2026}
        self.assertEqual(batch_rule({"fresh_rule": fr}), fr)
        self.assertEqual(batch_rule({"fresh_rule": fr, "age_default": {"max": 38, "relaxed": 43}})["age_default"]["max"], 38)
        self.assertEqual(fresh_verdict({**ME, "fresh": "auto", "graduate_year": 2026}, {"age_default": {"max": 38, "relaxed": 43}})[0], "maybe")


class Validate(unittest.TestCase):
    META = {"batches": {"b": {}}}

    def test_duplicate_and_unknown_batch(self):
        with self.assertRaises(ValueError):
            validate([job(id="1"), job(id="1")], self.META)
        with self.assertRaises(ValueError):
            validate([job(batch="zzz")], self.META)
        with self.assertRaises(ValueError):
            validate([], self.META)

    def test_ok(self):
        self.assertEqual(len(validate([job(id="1"), job(id="2")], self.META)), 2)


if __name__ == "__main__":
    unittest.main()
