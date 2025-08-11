from django.urls import path
from .views import InterviewPageView, GetQuestionView, SubmitAnswerView,ResetInterviewView,InterviewReportPageView,JobOpeningQuestionsView,JobOpeningSkillSelectView

urlpatterns = [
    path('', InterviewPageView.as_view(), name='interview'),
    path('get-question/', GetQuestionView.as_view(), name='get_question'),
    path('submit-answer/', SubmitAnswerView.as_view(), name='submit_answer'),
    path('reset/', ResetInterviewView.as_view(), name='reset_interview'),
    path("interviewbot/report-page/<int:candidate_id>/", InterviewReportPageView.as_view(), name="interview-report-page"),
    path('job-opening/<int:pk>/questions/', JobOpeningQuestionsView.as_view(), name='job-opening-questions'),
    path('job-opening/<int:pk>/generate/', JobOpeningSkillSelectView.as_view(), name='job-opening-generate'),

]
