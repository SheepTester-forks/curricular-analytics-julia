"""
Outputs a CSV file in Curricular Analytics' curriculum and degree plan formats
from the parsed academic plans and course prerequisites.

Exports:
    `output`, a generator function that takes a major code and optionally a
    college code and yields lines of the CSV file. You can use a for loop on the
    return value to print, write to a file, or store the lines in a string
    variable.
"""

from typing import (
    Dict,
    Generator,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Set,
)
from college_names import college_names
from output_json import Curriculum, CurriculumHash, Item, Term, Requisite

from parse import (
    CourseCode,
    MajorPlans,
    ParsedCourse,
    Prerequisite,
    major_codes,
    prereqs,
)
from parse_course_name import parse_course_name

__all__ = ["MajorOutput"]

INSTITUTION = "University of California, San Diego"
SYSTEM_TYPE = "Quarter"
HEADER = [
    "Course ID",
    "Course Name",
    "Prefix",
    "Number",
    "Prerequisites",
    "Corequisites",
    "Strict-Corequisites",
    "Credit Hours",
    "Institution",
    "Canonical Name",
    "Term",
]
CURRICULUM_COLS = 10
DEGREE_PLAN_COLS = 11

non_course_prereqs: Dict[str, List[CourseCode]] = {
    "SOCI- UD METHODOLOGY": [("SOCI", "60")],
    "TDHD XXX": [("TDTR", "10")],
}


class OutputCourse(NamedTuple):
    """
    A course output by `OutputCourses`. This contains all the fields necessary
    for a course row in a curriculum/degree plan CSV file. This helps reduce
    code repetition between outputting a curriculum vs. a degree plan and a CSV
    vs. JSON file, which each have many similarities.
    """

    course_id: int
    course_title: str
    course_code: CourseCode
    prereq_ids: List[int]
    coreq_ids: List[int]
    units: float
    term: int


class OutputCourses:
    """
    Lists courses in a ready-to-go format for creating a CSV or JSON file.

    Why not return a list directly? This intermediate class allows courses to be
    separated based on whether they're a major or college course because degree
    plan CSVs specifically have a separate section for "Additional Courses."
    Maybe I could've instead output a tuple or something depending on what is
    needed, but in Python it seems easier to me to loop over a list again and
    only yield what is necessary rather than partition a list beforehand.

    `start_id` is the next unassigned ID that can be assigned to additional
    courses.

    `course_ids` is a *clone* of that from `MajorOutput` because degree plan
    additional courses do not share course IDs between each other on Curricular
    Analytics.
    """

    term_names = ["FA", "WI", "SP", "S1"]

    processed_courses: List[ParsedCourse]
    current_id: int
    course_ids: Dict[CourseCode, int]
    duplicate_titles: Dict[str, int]
    claimed_ids: Set[CourseCode]
    year: int

    def __init__(self, parent: "MajorOutput", college: Optional[str]) -> None:
        self.processed_courses = (
            parent.plans.plan(college) if college else parent.curriculum
        )
        self.year = parent.plans.year

        # 3. Assign course IDs
        self.current_id = parent.start_id
        self.course_ids = {**parent.course_ids}
        for course in self.processed_courses:
            if course.course_code and course.course_code not in self.course_ids:
                self.course_ids[course.course_code] = self.current_id
                self.current_id += 1

        # Get duplicate course titles so can start with "GE 1" and so on
        course_titles = [course.course_title for course in self.processed_courses]
        self.duplicate_titles = {
            title: 0
            for i, title in enumerate(course_titles)
            if title in course_titles[0:i]
        }

        # In case there are duplicate courses, only let a course in course_ids
        # get used once
        self.claimed_ids = set(self.course_ids.keys())

    # 4. Get prerequisites
    def _find_prereq(
        self,
        prereq_ids: List[int],
        coreq_ids: List[int],
        alternatives: List[Prerequisite],
        before: int,
    ) -> None:
        """
        Helper method to find prerequisites and corequisites for a course.

        This takes care to prevent backwards prereqs, where a course that could
        satisfy the prerequisites for another course shows up *later* in a plan.
        See #47.

        This also *only* uses the first (i.e. earliest, as
        `self.processed_courses` is chronological) prerequisite found. It
        shouldn't matter too much if there are too many prerequisite arrows, but
        it does affect the complexity score on Curricular Analytics. See #25.

        `prereq_ids` and `coreq_ids` are mutable *references* to a list to which
        prerequisite course IDs are added.

        `before` is the term index of the course in question to prevent a course
        from being marked as a prereq of a past course.
        """
        # Find first processed course whose code is in `alternatives`
        for course in self.processed_courses:
            if course.course_code is None:
                continue
            if course.term >= before:
                return
            for code, concurrent in alternatives:
                if course.course_code == code:
                    (coreq_ids if concurrent else prereq_ids).append(
                        self.course_ids[course.course_code]
                    )
                    return

    def list_courses(
        self, show_major: Optional[bool] = None
    ) -> Generator[OutputCourse, None, None]:
        """
        The methods involved with actually outputting the CSV/JSON file should
        call this method, yielding `OutputCourse`s.

        `show_major` filters courses by whether they're a major or college
        requirement. If `show_major` is None or unspecified, all courses will be
        yielded.
        """
        for course_title, code, units, major_course, term in self.processed_courses:
            if show_major is not None and major_course != show_major:
                continue

            if code in self.claimed_ids:
                course_id = self.course_ids[code]
                self.claimed_ids.remove(code)
            else:
                course_id = self.current_id
                self.current_id += 1

            prereq_ids: List[int] = []
            coreq_ids: List[int] = []
            if course_title in non_course_prereqs:
                for prereq in non_course_prereqs[course_title]:
                    self._find_prereq(
                        prereq_ids,
                        coreq_ids,
                        [Prerequisite(prereq, False)],
                        term,
                    )
            elif code != ("MATH", "18"):
                # Math 18 has no prereqs because it only requires pre-calc,
                # which we assume the student has credit for
                reqs = prereqs(
                    self.term_names[term % 3] + f"{(self.year + term // 3) % 100:02d}"
                )
                if code in reqs:
                    for alternatives in reqs[code]:
                        self._find_prereq(
                            prereq_ids,
                            coreq_ids,
                            alternatives,
                            term,
                        )

            if course_title in self.duplicate_titles:
                self.duplicate_titles[course_title] += 1
                course_title = f"{course_title} {self.duplicate_titles[course_title]}"

            yield OutputCourse(
                course_id,
                course_title,
                code or ("", ""),
                prereq_ids,
                coreq_ids,
                units,
                term,
            )


def rows_to_csv(rows: Iterable[List[str]], columns: int) -> Generator[str, None, None]:
    """
    Converts a list of lists of fields into lines of CSV records. Yields a
    newline-terminated line.

    The return value from `_output_plan` should be passed as the `rows` argument.

    `_output_plan` always outputs a "Term" column because I'm lazy, so this
    function can cut off extra columns or adds empty fields as needed to meet
    the column count.
    """
    for row in rows:
        yield (
            ",".join(
                [
                    '"' + field.replace('"', '""') + '"'
                    if any(c in field for c in ',"\r\n')
                    else field
                    for field in row
                ][:columns]
                + [""] * (columns - len(row))
            )
            + "\n"
        )


class MajorOutput:
    """
    Keeps track of the course IDs used by a curriculum so major courses share
    the same ID across degree plans. Otherwise, if a degree plan uses an ID for
    a different course, it renames courses with that ID in all other degree
    plans and the curriculum in Curricular Analytics.
    """

    plans: MajorPlans
    course_ids: Dict[CourseCode, int]
    curriculum: List[ParsedCourse]
    start_id: int

    def __init__(self, plans: MajorPlans, start_id: int = 1) -> None:
        self.plans = plans
        self.course_ids = {}
        self.curriculum = self.plans.curriculum()
        self.start_id = start_id

        for course in self.curriculum:
            if course.course_code and course.course_code not in self.course_ids:
                self.course_ids[course.course_code] = self.start_id
                self.start_id += 1

    def _output_plan(
        self, college: Optional[str] = None
    ) -> Generator[List[str], None, None]:
        """
        Outputs a curriculum or degree plan in Curricular Analytics' CSV format,
        yielding one row at a time.

        To output a degree plan, specify the college that the degree plan is
        for. If the college isn't specified, then `_output_plan` will output the
        major's curriculum instead.
        """
        major_info = major_codes()[self.plans.major_code]
        yield ["Curriculum", major_info.name]
        if college:
            yield ["Degree Plan", f"{major_info.name}/ {college_names[college]}"]
        yield ["Institution", INSTITUTION]
        # NOTE: Currently just gets the last listed award type (bias towards BS over
        # BA). Will see how to deal with BA vs BS
        # For undeclared majors, there is no award type, so will just use
        # Curricular Analytics' default, BS.
        yield [
            "Degree Type",
            list(major_info.award_types)[-1] if major_info.award_types else "BS",
        ]
        yield ["System Type", SYSTEM_TYPE]
        yield ["CIP", major_info.cip_code]

        processed = OutputCourses(self, college)

        for major_course_section in True, False:
            if not college and not major_course_section:
                break
            yield ["Courses" if major_course_section else "Additional Courses"]
            yield HEADER
            for (
                course_id,
                course_title,
                (subject, number),
                prereq_ids,
                coreq_ids,
                units,
                term,
            ) in processed.list_courses(major_course_section):
                yield [
                    str(course_id),
                    course_title,
                    subject,
                    number,
                    ";".join(map(str, prereq_ids)),
                    ";".join(map(str, coreq_ids)),
                    "",
                    f"{units:g}",  # https://stackoverflow.com/a/2440708
                    "",
                    "",
                    str(term + 1),
                ]

    def output(self, college: Optional[str] = None) -> str:
        """
        A helper function that collects the rows from `_output_plan` into a
        single newline-terminated string with the entire CSV. You'll probably
        want to use this instead of `_output_plan`.
        """
        if college is not None and college not in self.plans:
            raise KeyError(f"No degree plan available for {college}.")
        cols = DEGREE_PLAN_COLS if college else CURRICULUM_COLS
        csv = ""
        for line in rows_to_csv(self._output_plan(college), cols):
            csv += line
        return csv

    def output_json(self, college: Optional[str] = None) -> Curriculum:
        """
        Like `_output_plan`, but outputs a JSON-serializable `Curriculum` object
        instead. This JSON format is what the Curricular Analytics site
        currently uses when you edit or create a curriculum or degree plan with
        a GUI.
        """
        curriculum = Curriculum(
            curriculum_terms=[
                Term(id=i + 1, curriculum_items=[]) for i in range(12 if college else 1)
            ]
        )
        processed = OutputCourses(self, college)
        # Put college courses at the bottom of each quarter, consistent with CSV
        for major_course_section in True, False:
            if not college and not major_course_section:
                break
            for (
                course_id,
                course_title,
                _,
                prereq_ids,
                coreq_ids,
                units,
                term,
            ) in processed.list_courses(major_course_section):
                curriculum["curriculum_terms"][term]["curriculum_items"].append(
                    Item(
                        name=course_title,
                        id=course_id,
                        credits=units,
                        curriculum_requisites=[
                            Requisite(
                                source_id=prereq_id, target_id=course_id, type="prereq"
                            )
                            for prereq_id in prereq_ids
                        ]
                        + [
                            Requisite(
                                source_id=coreq_id, target_id=course_id, type="coreq"
                            )
                            for coreq_id in coreq_ids
                        ],
                    )
                )
        return curriculum

    @classmethod
    def from_json(cls, plans: MajorPlans, json: CurriculumHash) -> "MajorOutput":
        """
        Creates a `MajorOutput` using the same course IDs from an existing
        curriculum or degree plan. This way, modifying a degree plan won't
        inadvertently change the course data of the curriculum on the Curricular
        Analytics website.
        """
        output = MajorOutput(plans)
        output.course_ids = {}
        output.start_id = 1
        for course in json["courses"]:
            parsed = parse_course_name(course["name"])
            if parsed:
                # Assumes lab courses were already split, so won't bother
                # handling has_lab
                subject, number, _ = parsed
                output.course_ids[subject, number] = course["id"]
            if course["id"] + 1 > output.start_id:
                output.start_id = course["id"] + 1
        return output


if __name__ == "__main__":
    import sys
    from parse import major_plans

    _, year, major, college = sys.argv + [""] * (4 - len(sys.argv))
    print(MajorOutput(major_plans(int(year))[major]).output(college or None))
