"""各地表格里的写法 -> 统一写法，让 match.py 只需要认一种。"""


def education_text(edu, degree=""):
    """学历 + 学位 -> 统一写法，match.parse_education 能直接认。

    ('研究生', '硕士及以上') -> '硕士研究生以上'；('研究生', '博士') -> '博士研究生'；
    ('本科及以上', '学士及以上') -> '本科以上'；'大专/高职及以上' -> '大专以上'；'硕士研究生及以上' -> '硕士研究生以上'。
    """
    edu, degree = (edu or "").strip(), (degree or "").strip()
    edu = edu.replace("大专/高职", "大专").replace("及以上", "以上")
    if edu == "研究生":
        if "博士" in degree:
            return "博士研究生"
        if "硕士" in degree:
            return "硕士研究生以上" if "以上" in degree.replace("及以上", "以上") else "硕士研究生"
        return "研究生"
    return edu


def major_columns(major, edu):
    """只有一栏专业的岗位表（上海、江苏、浙江……）：这一栏对所有符合学历的人都适用，所以按岗位的学历要求放进对应的几栏。

    「本科以上」「硕士研究生以上」这类向上兼容的：研究生栏和本科栏都放（match.py 比对研究生栏，只要求较低学历时回退到本科栏）；
    只要求本科（或专科）的：只放本科（或大专）栏；只要求研究生的：只放研究生栏。
    返回可以直接展开成 make_job 参数的 dict。
    """
    major, edu = major or "", edu or ""
    if not major:
        return {}
    if "研究生" in edu or "硕士" in edu or "博士" in edu:
        return {"major_graduate": major}
    if "以上" in edu or "及以上" in edu:
        return {"major_graduate": major, "major_bachelor": major}
    if "专科" in edu or "大专" in edu:
        return {"major_college": major}
    return {"major_bachelor": major}
