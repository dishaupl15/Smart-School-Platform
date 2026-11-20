from fastapi import APIRouter

from app.api.v1.routes.admin import router as admin_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.questions import question_stats, router as questions_router
from app.api.v1.routes.student import router as student_router
from app.api.v1.routes.student_quiz import router as student_quiz_router
from app.api.v1.routes.teacher import router as teacher_router
from app.schemas.question_bank import QuestionStats

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin management"])
api_router.include_router(questions_router, prefix="/admin/questions", tags=["question bank"])
api_router.include_router(student_router, prefix="/student", tags=["student portal"])
api_router.include_router(student_quiz_router, prefix="/student", tags=["student quizzes"])
api_router.include_router(teacher_router, prefix="/teacher", tags=["teacher portal"])
api_router.add_api_route(
    "/admin/question-bank/stats",
    question_stats,
    methods=["GET"],
    response_model=QuestionStats,
    tags=["question bank"],
    include_in_schema=False,
)
api_router.include_router(health_router, prefix="/health", tags=["health"])
