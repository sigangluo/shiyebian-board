"""岗位导出（前端用的紧凑格式）的测试。运行: python3 -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib.export import export_job
from lib.schema import make_job


def job(**kw):
    base = dict(id="1", batch="b", unit="某单位", city="上海市", education="本科以上")
    base.update(kw)
    return make_job(**base)


class Export(unittest.TestCase):
    def test_parsed_fields(self):
        e = export_job(job(major_graduate="计算机科学与技术(A0812)", major_bachelor="计算机类（B0809）", experience="2年以上相关工作经历",
                           age="18-38周岁", age_relaxed="放宽到40周岁", fresh="非应届毕业生", hukou="限上海户籍",
                           duty="需入住女生宿舍", certs="教师资格、软考", extra={"（放宽年龄）博士研究生年龄要求": "放宽到45周岁"}), "shanghai")
        self.assertEqual((e["el"], e["ep"]), (2, True))
        self.assertEqual((e["kg"], e["cg"], e["kb"], e["cb"]), ("c", ["A0812"], "c", ["B0809"]))
        self.assertEqual((e["xy"], e["amx"], e["arx"], e["adx"]), (2.0, 38, 40, 45))
        self.assertEqual((e["pn"], e.get("fo"), e["he"], e["gd"]), (True, None, True, "女"))
        self.assertEqual(e["cl"], ["教师资格", "软考"])
        self.assertEqual((e["r"], e["ci"]), ("shanghai", "上海"))            # 城市去掉「市」

    def test_empty_fields_are_omitted(self):
        e = export_job(job(), "x")
        for k in ("dp", "du", "mg", "kg", "cg", "xy", "gd", "cl", "ei", "zb", "pn", "fo", "he", "hn", "arx", "adx"):
            self.assertNotIn(k, e, k)
        for k in ("id", "r", "b", "n"):
            self.assertIn(k, e)

    def test_unparsable_experience_is_kept_as_null(self):
        e = export_job(job(experience="有相关工作经历"), "x")
        self.assertIn("xy", e)
        self.assertIsNone(e["xy"])                                          # 前端据此提示「无法识别」，和「没有要求」区分开

    def test_major_kinds(self):
        e = export_job(job(major_graduate="不限", major_bachelor="计算机、通信工程等相关专业"), "x")
        self.assertEqual((e["kg"], e["kb"]), ("u", "t"))
        self.assertNotIn("cb", e)

    def test_either_major_and_fresh_flags(self):
        e = export_job(job(fresh="2026年毕业生", extra={"专业口径": "本科或研究生符合其一"}), "x")
        self.assertTrue(e["ei"] and e["fo"])
        e = export_job(job(fresh="机关事业单位正式在编人员"), "x")
        self.assertTrue(e["zb"])


if __name__ == "__main__":
    unittest.main()
