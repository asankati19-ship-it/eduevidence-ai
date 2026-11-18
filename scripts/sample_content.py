"""Original synthetic course material authored for Project 022."""

SAMPLES = [
    {
        "course_id": 1, "code": "PY-101", "filename": "Python Programming Course Handbook.pdf",
        "pages": [
            ("Course overview", "Purpose and learning outcomes", [
                "Python Programming is a six-week foundation course for new programmers. Learners write and debug small command-line programs, organize code into reusable functions, and read structured files.",
                "By the end of the course, learners can test functions, handle exceptions, and explain their design decisions in a code review.",
                "The course uses the Python standard library and the LMS practice workspace. The course notebook contains examples and extension exercises.",
            ]),
            ("Modules and weekly practice", "A six-week learning sequence", [
                "Weeks 1 and 2 cover variables, control flow, strings, lists, dictionaries, and the interactive Python shell.",
                "Weeks 3 and 4 cover functions, modules, files, exceptions, and debugging. Week 5 introduces unit tests and code review.",
                "Week 6 is the capstone workshop. Learners bring a working prototype and receive feedback on testing and readability.",
            ]),
            ("Assessment and submission", "What to upload and where", [
                "Graded labs account for 60% of the course mark. The capstone project accounts for 40% of the course mark.",
                "Submit each lab through the LMS Assessments area as a ZIP archive containing Python source files and a short README. A successful submission generates an LMS receipt.",
                "Upload the capstone to the Capstone submission slot. Include your Python source, test files, and instructions for running the project.",
            ]),
            ("Completion requirements", "The conditions for course completion", [
                "To complete the Python Programming course, submit all four graded labs, achieve at least 70% overall, and earn a Pass on the capstone project.",
                "The overall mark and capstone Pass are evaluated separately. A capstone resubmission is available once after written feedback.",
                "The completion record appears in the LMS Results area after the course coordinator verifies the conditions.",
            ]),
        ],
    },
    {
        "course_id": 2, "code": "AI-201", "filename": "AI and Machine Learning Course Guide.pdf",
        "pages": [
            ("Course overview", "Learning objectives and prerequisites", [
                "AI and Machine Learning is an eight-week applied course. Learners prepare a small dataset, train baseline models, evaluate results, and explain limitations.",
                "Before starting, learners should understand Python functions and basic descriptive statistics. The course provides starter notebooks and synthetic datasets.",
                "The learning resources include a glossary, weekly notebook walkthroughs, and an evaluation checklist.",
            ]),
            ("Modules and workshops", "The applied machine learning sequence", [
                "Modules cover dataset preparation, classification, regression, validation, and responsible model reporting.",
                "For classification workshops, compare a logistic regression baseline with a decision tree. Report precision, recall, and the confusion matrix.",
                "Use the LMS workshop notebooks. Each notebook includes a runnable starter and a short reflection prompt.",
            ]),
            ("Assessment and capstone", "Grading and report contents", [
                "The AI and Machine Learning final mark consists of two quizzes worth 20% combined, a modeling notebook worth 35%, and a capstone report worth 45%.",
                "The capstone report must include the dataset description, a baseline model, validation results, and a discussion of limitations.",
                "Submit the modeling notebook as an IPYNB file and the capstone report as a PDF in separate LMS Assessments slots.",
            ]),
        ],
    },
    {
        "course_id": 3, "code": "LMS-001", "filename": "LMS Assessment and Attendance Policy.pdf",
        "pages": [
            ("Assessment submissions", "Receipts and late work", [
                "Submit graded work through the assessment slot listed in the LMS. Keep the timestamped submission receipt as proof of delivery.",
                "For assignments marked eligible for late submission, a learner may submit up to 48 hours after the deadline. The penalty is 10 percentage points per 24-hour period or part thereof.",
                "If the LMS is unavailable, contact course support and include the error details before the deadline where possible.",
            ]),
            ("Attendance requirements", "Live sessions and recorded participation", [
                "Learners must attend at least 75% of scheduled live sessions. A live session counts when the learner is present for at least half of its scheduled duration.",
                "Watching a recording does not count toward live attendance. A learner may request a documented accommodation from course support.",
                "Attendance records appear in the LMS Attendance area within two working days of a session.",
            ]),
            ("Assessment review and support", "How to request a review", [
                "Request an assessment review in the LMS Support area within five working days after the grade is released.",
                "Include the assessment name, the rubric criterion, and a short explanation of the issue. The support team acknowledges the request in the LMS.",
                "Requests for general learning support can be submitted in the same area using the Course Support category.",
            ]),
        ],
    },
]

