from typing import Dict
from parse import CourseCode, prereqs

THRESHOLD = 0.5


def parse_int(string: str) -> int:
    """
    Like JavaScript `parseInt`, where non-digits after the integer are ignored.
    """
    for i, char in enumerate(string):
        if not char.isdigit():
            index = i
            break
    else:
        index = len(string)
    return int(string[0:index])


course_codes = set(prereqs.keys()) | {
    prerequisite.course_code
    for requirements in prereqs.values()
    for alternatives in requirements
    for prerequisite in alternatives
}
subjects = sorted({subject for subject, _ in course_codes})

for subject in subjects:
    numbers = [number for subj, number in course_codes if subj == subject]
    upper_division = [number for number in numbers if parse_int(number) // 100 == 1]

    for name, numbers in (subject, numbers), (f"{subject} UD", upper_division):
        if len(numbers) <= 1:
            continue
        prereq_freq: Dict[CourseCode, int] = {}
        for number in numbers:
            code = subject, number
            if code in prereqs:
                for alternatives in prereqs[code]:
                    for prereq_code, _ in alternatives:
                        if prereq_code not in prereq_freq:
                            prereq_freq[prereq_code] = 0
                        prereq_freq[prereq_code] += 1
        results = [
            f"{subject} {number} {count / len(numbers) * 100:.2f}%"
            for (subject, number), count in sorted(
                prereq_freq.items(), key=lambda entry: entry[1], reverse=True
            )
            if count / len(numbers) > THRESHOLD
        ]
        print(f"[{name}] {len(numbers)}. {', '.join(results)}")
