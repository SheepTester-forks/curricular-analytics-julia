from difflib import SequenceMatcher
import json
from sys import argv, stdout
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from college_names import college_names
from curricula_index import urls
from departments import departments, dept_schools

from parse import RawCourse, major_codes, major_plans, read_csv_from


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"


def display_term(term: int) -> str:
    return f"Y{term // 4 + 1} {['FA', 'WI', 'SP', 'SU'][term % 4]}"


class DiffResults(NamedTuple):
    added: List[RawCourse]
    removed: List[RawCourse]
    changed: List[Tuple[RawCourse, RawCourse]]
    old_units: float
    new_units: float

    def print(self) -> None:
        for course in self.removed:
            print(f"{Colors.RED}- {course.course_title}{Colors.RESET}")
        for old, new in self.changed:
            print(
                "* "
                + (
                    f"{Colors.YELLOW}{old.course_title} → {new.course_title}{Colors.RESET}"
                    if old.course_title != new.course_title
                    else new.course_title
                )
                + (
                    f" · {Colors.YELLOW}{old.units} → {new.units}{Colors.RESET} units"
                    if old.units != new.units
                    else ""
                )
                + (
                    f" · term {Colors.YELLOW}{display_term(old.term)} → {display_term(new.term)}{Colors.RESET}"
                    if old.term != new.term
                    else ""
                )
                + (
                    f" · {Colors.YELLOW}{old.type} → {new.type}{Colors.RESET}"
                    if old.type != new.type
                    else ""
                )
                + (
                    f" · {Colors.YELLOW}{'now' if new.overlaps_ge else 'no longer'}{Colors.RESET} overlaps GE"
                    if old.overlaps_ge != new.overlaps_ge
                    else ""
                )
            )
        for course in self.added:
            print(f"{Colors.GREEN}+ {course.course_title}{Colors.RESET}")

    def to_json(self):
        changes: Dict[str, List[Any]] = {"changes": []}
        for course in self.removed:
            changes["changes"].append(
                {
                    "type": "removed",
                    "course": course.course_title,
                    "units": course.units,
                    "term": course.term,
                }
            )
        for old, new in self.changed:
            course_changes = {}
            if old.course_title != new.course_title:
                course_changes["title"] = [old.course_title, new.course_title]
            if old.units != new.units:
                course_changes["units"] = [old.units, new.units]
            if old.term != new.term:
                course_changes["term"] = [old.term, new.term]
            if old.type != new.type:
                course_changes["type"] = [old.type, new.type]
            if old.overlaps_ge != new.overlaps_ge:
                course_changes["overlap"] = [old.overlaps_ge, new.overlaps_ge]
            changes["changes"].append(
                {
                    "type": "changed",
                    "course": new.course_title,
                    "changes": course_changes,
                }
            )
        for course in self.added:
            changes["changes"].append(
                {
                    "type": "added",
                    "course": course.course_title,
                    "units": course.units,
                    "term": course.term,
                }
            )
        if self.old_units != self.new_units:
            changes["units"] = [self.old_units, self.new_units]
        return changes


def similarity(a: str, b: str) -> float:
    # https://stackoverflow.com/a/17388505
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def diff(old: List[RawCourse], new: List[RawCourse]) -> DiffResults:
    old_only = old.copy()
    new_only = new.copy()
    for course in old:
        if course in new_only:
            old_only.remove(course)
            new_only.remove(course)
    changed: List[Tuple[RawCourse, RawCourse]] = []

    # Prioritize matching courses with the same course title
    for course in old_only.copy():
        for other in new_only:
            if course.course_title.lower() == other.course_title.lower():
                old_only.remove(course)
                new_only.remove(other)
                changed.append((course, other))
                break
    # Match courses based on similarity
    for course in old_only.copy():
        max_similarity = 0
        most_similar: Optional[RawCourse] = None
        for other in new_only:
            sim = similarity(course.course_title, other.course_title)
            if sim > max_similarity:
                max_similarity = sim
                most_similar = other
        if most_similar and max_similarity >= 0.5:
            old_only.remove(course)
            new_only.remove(most_similar)
            changed.append((course, most_similar))

    return DiffResults(
        new_only,
        old_only,
        changed,
        sum(course.units for course in old),
        sum(course.units for course in new),
    )


def print_major_changes(major: str, college: str) -> None:
    for year in range(2015, 2022):
        if (
            major not in major_plans(year)
            or major not in major_plans(year + 1)
            or college not in major_plans(year)[major].colleges
            or college not in major_plans(year + 1)[major].colleges
        ):
            continue
        differences = diff(
            major_plans(year)[major].raw_plans[college],
            major_plans(year + 1)[major].raw_plans[college],
        )
        # https://stackoverflow.com/a/8337012
        print(
            f"{Colors.BOLD}{year + 1} changes{Colors.RESET}"
            + (
                f" {Colors.CYAN}({differences.new_units - differences.old_units:+g} → {differences.new_units:g} units){Colors.RESET}"
                if differences.old_units != differences.new_units
                else ""
            )
        )
        differences.print()


def diff_all() -> None:
    complexities: Dict[Tuple[int, str, str], float] = {}
    for (year, major, college, complexity, *_,) in read_csv_from(
        "./files/metrics_fa12.csv", "julia Metrics.jl"
    )[1:]:
        complexities[int(year), major, college] = float(complexity)

    def diff_major(major: str, college: str):
        years: List[Any] = []
        for year in range(2015, 2022):
            if (
                major not in major_plans(year)
                or major not in major_plans(year + 1)
                or college not in major_plans(year)[major].colleges
                or college not in major_plans(year + 1)[major].colleges
            ):
                continue
            differences = diff(
                major_plans(year)[major].raw_plans[college],
                major_plans(year + 1)[major].raw_plans[college],
            )
            years.append(
                {
                    **differences.to_json(),
                    "year": year + 1,
                    "url": urls[year + 1, major],
                    "complexity": [
                        complexities[year, major, college],
                        complexities[year + 1, major, college],
                    ],
                }
            )
        return years

    majors_by_dept: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for year in range(2015, 2023):
        for major_code in major_plans(year).keys():
            major = f"{major_code} {major_codes()[major_code].name}"
            department = departments[major_codes()[major_code].department]
            school = dept_schools.get(major_codes()[major_code].department) or ""
            if school not in majors_by_dept:
                majors_by_dept[school] = {}
            if department not in majors_by_dept[school]:
                majors_by_dept[school][department] = {}
            if major not in majors_by_dept[school][department]:
                majors_by_dept[school][department][major] = {}
            for college_code, college_name in college_names.items():
                output = diff_major(major_code, college_code)
                if output:
                    first_year: int = output[0]["year"]
                    majors_by_dept[school][department][major][college_name] = {
                        "changes": output,
                        "first": {
                            "year": first_year,
                            "url": urls[first_year, major_code],
                        },
                    }
    json.dump(majors_by_dept, stdout)


if __name__ == "__main__":
    # https://stackoverflow.com/questions/287871/how-do-i-print-colored-text-to-the-terminal#comment113206663_21786287
    import os

    # Enable ANSI colours on Windows
    if os.name == "nt":
        os.system("color")

    if len(argv) < 3:
        diff_all()
    else:
        print_major_changes(*argv[1:3])