"""
python3 college_ges.py > college_ges.csv
"""

import sys
from college_names import college_codes, college_names
from parse import major_codes, major_plans

html = sys.argv[1] == "html"

all_extra_ge_units = {
    (major_code, college): sum(
        course.units
        for course in plans.plan(college)
        if course.course_title.upper() != "ELECTIVE" and not course.for_major
    )
    for major_code, plans in major_plans(2022).items()
    for college in plans.colleges
}
min_ge = min(units for units in all_extra_ge_units.values() if units > 0)
max_ge = max(all_extra_ge_units.values())
print(f"min={min_ge} max={max_ge}", file=sys.stderr)


class ColorScale:
    # Google Sheets color scale colors
    _GREEN = 87, 187, 138
    _YELLOW = 255, 214, 102
    _RED = 230, 124, 115

    @staticmethod
    def _interpolate(t: float, a: float, b: float) -> str:
        return str(a + (b - a) * t)

    @classmethod
    def color_scale(cls, t: float) -> str:
        # green: rgb(87,187,138)
        # yellow: rgb(255,214,102)
        # red: rgb(230,124,115)
        channels = ",".join(
            cls._interpolate(t * 2, cls._GREEN[i], cls._YELLOW[i])
            if t < 0.5
            else cls._interpolate(t * 2 - 1, cls._YELLOW[i], cls._RED[i])
            for i in range(3)
        )
        return f"rgb({channels})"


if html:
    college_headers = "".join(
        f'<th class="college-header">{college_names[college]}</th>'
        for college in college_codes
    )
    print(
        f'<table><tr class="header"><th class="major">Major</th>{college_headers}</tr>'
    )
else:
    print("Major," + ",".join(college_names[college] for college in college_codes))

sums = {college: 0.0 for college in college_codes}
major_count = 0

for major_code in major_plans(2022).keys():
    if major_code.startswith("UN"):
        continue
    major_count += 1
    if html:
        print('<tr class="row"><th scope="col" class="major">')
        print(
            f'<span class="major-code">{major_code}</span><span class="major-name">: {major_codes()[major_code].name}</span></th>'
        )
    else:
        print(major_code, end="")
    for college in college_codes:
        if (major_code, college) not in all_extra_ge_units:
            if html:
                print("<td></td>")
            else:
                print(",", end="")
            continue
        extra_ge_units = all_extra_ge_units[major_code, college]
        sums[college] += extra_ge_units
        if html:
            color = (
                ColorScale.color_scale((extra_ge_units - min_ge) / (max_ge - min_ge))
                if extra_ge_units >= min_ge
                else "transparent"
            )
            print(f'<td style="--color: {color};">{extra_ge_units: .0f}</td>')
        else:
            print(f",{extra_ge_units}", end="")
    if html:
        print(f"</tr>")
    else:
        print()

if html:
    print('<tr class="average"><th scope="col" class="major">Average</th>')
    for college in college_codes:
        average = sums[college] / major_count
        color = ColorScale.color_scale((average - min_ge) / (max_ge - min_ge))
        print(f'<td style="--color: {color};">{average: .0f}</td>')
    print(f"</tr>")

if html:
    print("</table>")