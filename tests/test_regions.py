"""地区配置（META）的格式检查：每个已接入批次都应有 exam_info（考试与成绩摘要），并且格式正确。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib.regions import check_exam_info, discover

GOOD = dict(written="笔试科目", shortlist="入围规则", interview="面试", score="总成绩 = 笔试 × 50% + 面试 × 50%",
            sources=[["招聘公告", "https://example.com/n"]], checked="2026-10-02")


class ExamInfoTest(unittest.TestCase):
    def test_all_batches_have_exam_info(self):
        for r in discover():
            for bk, b in r.meta["batches"].items():
                self.assertIn("exam_info", b, f"{r.key}/{bk} 缺少 exam_info（考试与成绩摘要，见 regions/_template）")
                check_exam_info(f"{r.key}/{bk}", b["exam_info"])

    def test_good(self):
        check_exam_info("x", GOOD)
        check_exam_info("x", {**GOOD, "notes": ["a"], "after": "b", "written_date": "c", "syllabus": [["科目", "内容"]]})

    def test_bad(self):
        bad = [
            {k: v for k, v in GOOD.items() if k != "score"},                 # 缺必填项
            {**GOOD, "written": "  "},                                       # 空白
            {**GOOD, "sources": []},                                         # 没有来源
            {**GOOD, "sources": [["公告", "http://example.com"]]},           # 不是 https
            {**GOOD, "sources": ["https://example.com"]},                    # 格式不对
            {**GOOD, "checked": "昨天"},                                     # 日期格式
            {**GOOD, "notes": "一句话"},                                     # notes 不是列表
            {**GOOD, "notes": [""]},
            {**GOOD, "syllabus": [["只有标题"]]},                              # syllabus 要 [标题, 内容]
            {**GOOD, "syllabus": "一句话"},
            "不是 dict",
        ]
        for info in bad:
            with self.assertRaises(RuntimeError, msg=str(info)[:60]):
                check_exam_info("x", info)


if __name__ == "__main__":
    unittest.main()
