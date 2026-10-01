"""「其它条件」自由文本拆解的测试。运行: python3 -m unittest discover -s tests

用例来自深圳、浙江岗位表里真实出现过的写法。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib.conditions import split_conditions


class Split(unittest.TestCase):
    def test_basic(self):
        r = split_conditions("40岁以下；中共党员（含预备党员）；具有2年以上相关工作经历。")
        self.assertEqual((r["age"], r["politics"], r["experience"]), ("40岁以下", "中共党员（含预备党员）", "具有2年以上相关工作经历"))
        self.assertEqual(r["other"], "")

    def test_enumerators_are_stripped(self):
        r = split_conditions("1.40岁以下； 2.中共党员（含预备党员）。")
        self.assertEqual((r["age"], r["politics"]), ("40岁以下", "中共党员（含预备党员）"))
        r = split_conditions("一、45岁以下。 二、具有2年以上相关工作经历。 三、取得医师资格证、医师执业证。")
        self.assertEqual((r["age"], r["experience"], r["certs"]), ("45岁以下", "具有2年以上相关工作经历", "取得医师资格证、医师执业证"))

    def test_relaxed_age(self):
        r = split_conditions("40岁以下；硕士研究生年龄条件放宽到43岁;博士研究生年龄条件放宽到45岁。")
        self.assertEqual((r["age"], r["age_relaxed"], r["age_other"]),
                         ("40岁以下", "硕士研究生年龄条件放宽到43岁", "博士研究生年龄条件放宽到45岁"))

    def test_mixed_clause_is_split_by_comma(self):
        r = split_conditions("中共党员（含预备党员），具有2年以上相关工作经历")
        self.assertEqual((r["politics"], r["experience"]), ("中共党员（含预备党员）", "具有2年以上相关工作经历"))

    def test_diploma_deadline_is_not_a_certificate(self):
        r = split_conditions("应届毕业生取得学历学位证书的时限为2026年10月底前")
        self.assertEqual((r["certs"], r["other"]), ("", ""))
        self.assertIn("学历学位证书", r["soft"])            # 不影响已经毕业的人，但原文保留在 soft 里，详情里能看到
        self.assertEqual(split_conditions("具有执业医师资格")["certs"], "具有执业医师资格")

    def test_soft_requirements_do_not_count(self):
        r = split_conditions("具备较强的文字功底、组织管理、沟通协调和良好的服务意识，工作责任心强；因工作需要，该岗位需经常值班值守")
        self.assertEqual(r["other"], "")
        self.assertNotEqual(r["soft"], "")

    def test_title_and_special_and_trivial(self):
        r = split_conditions("取得相应学位；具有中级及以上职称；限2026年本区服务期满“三支一扶”人员报考。")
        self.assertEqual((r["title"], r["other"]), ("具有中级及以上职称", ""))
        self.assertIn("三支一扶", r["special"])
        self.assertEqual(split_conditions("无")["other"], "")
        r = split_conditions("具有正高职称的年龄放宽到50周岁")             # 这是年龄放宽，不是要求职称
        self.assertEqual((r["title"], r["age_other"]), ("", "具有正高职称的年龄放宽到50周岁"))

    def test_personal_qualities_are_soft(self):
        r = split_conditions("身心健康；服从工作安排；热爱招商引资工作；政治素质高")
        self.assertEqual(r["other"], "")
        self.assertIn("身心健康", r["soft"])

    def test_english_level_is_a_certificate(self):
        self.assertEqual(split_conditions("大学英语六级")["certs"], "大学英语六级")
        self.assertEqual(split_conditions("取得相应学位；大学英语四级以上")["certs"], "大学英语四级以上")

    def test_trivial_clause_inside_a_comma_sentence(self):
        r = split_conditions("取得相应学位，尊重基督教信仰")
        self.assertEqual(r["other"], "尊重基督教信仰")

    def test_title_certificate_is_a_title(self):
        r = split_conditions("具有会计初级及以上职称证书")
        self.assertEqual((r["title"], r["certs"]), ("具有会计初级及以上职称证书", ""))

    def test_unrecognized_stays_in_other(self):
        r = split_conditions("本科专业须为：口腔医学类（B1006）")
        self.assertEqual(r["other"], "本科专业须为：口腔医学类（B1006）")

    def test_preferred_is_not_hard_requirement(self):
        r = split_conditions("有2年以上相关工作经历者优先")
        self.assertEqual((r["experience"], r["other"]), ("", ""))
        self.assertIn("优先", r["soft"])


if __name__ == "__main__":
    unittest.main()
