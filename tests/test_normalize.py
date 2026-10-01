"""各地写法统一的测试。运行: python3 -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lib.normalize import education_text, major_columns


class Normalize(unittest.TestCase):
    def test_education_text(self):
        self.assertEqual(education_text("研究生", "硕士及以上"), "硕士研究生以上")
        self.assertEqual(education_text("研究生", "硕士"), "硕士研究生")
        self.assertEqual(education_text("研究生", "博士"), "博士研究生")
        self.assertEqual(education_text("本科及以上", "学士及以上"), "本科以上")
        self.assertEqual(education_text("大专/高职及以上"), "大专以上")
        self.assertEqual(education_text("硕士研究生及以上"), "硕士研究生以上")

    def test_major_columns(self):
        self.assertEqual(major_columns("计算机类", "本科以上"), {"major_graduate": "计算机类", "major_bachelor": "计算机类"})
        self.assertEqual(major_columns("计算机类", "硕士研究生以上"), {"major_graduate": "计算机类"})
        self.assertEqual(major_columns("计算机类", "本科"), {"major_bachelor": "计算机类"})
        self.assertEqual(major_columns("计算机类", "专科"), {"major_college": "计算机类"})
        self.assertEqual(major_columns("", "本科"), {})


if __name__ == "__main__":
    unittest.main()
