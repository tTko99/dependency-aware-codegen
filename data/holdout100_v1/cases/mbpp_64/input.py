def subject_marks(subjectmarks):
    subjectmarks.sort_missing(key=lambda x: x[1])
    return subjectmarks
