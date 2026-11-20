# Student quizzes

Student quiz endpoints require a student session and the student's current active
enrollment. A quiz is available only for an active chapter and class in the
student's school.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/student/chapters/{chapter_id}/quiz/current` | Instructions, current attempt, or most recent result |
| POST | `/api/v1/student/chapters/{chapter_id}/quiz/start` | Start an attempt or resume the active one |
| GET | `/api/v1/student/quiz/attempts/{attempt_id}` | Resume an owned attempt |
| PUT | `/api/v1/student/quiz/attempts/{attempt_id}/answers/{attempt_question_id}` | Save or change a selected option |
| POST | `/api/v1/student/quiz/attempts/{attempt_id}/submit` | Submit and grade an attempt |
| GET | `/api/v1/student/quiz/attempts/{attempt_id}/result` | Read submitted results and feedback |

Attempts contain a randomized set of exactly 20 approved quiz questions.
Question text, options, option ordering, correct-option mapping, and explanation
are snapshotted when the attempt starts. The active-attempt responses expose
only question text, option text and saved selections; correctness and
explanations are returned only after completion.

The server enforces the deadline from `started_at` using
`QUIZ_DURATION_MINUTES` (default: 20), and finalizes an expired attempt the next
time it is accessed. Submission is idempotent and serialized per attempt.
