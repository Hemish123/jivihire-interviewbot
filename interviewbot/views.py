import requests
import html
import json
from django.views import View
from django.shortcuts import render,get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest,HttpResponse
from .models import InterviewAnswer,InterviewQuestion
from .genai_resume import transcribe_audio,evaluate_answer,generate_interview_summary,generate_questions_from_skills,generate_combined_questions_for_skills
from django.contrib import messages
from manager.models import JobOpening
from candidate.models import Candidate,ResumeAnalysis
# from .utils import transcribe_audio_file
import tempfile
import os
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect


# class InterviewPageView(View):
#     def get(self, request):
#         job_opening_id = request.GET.get("job_opening")
#         candidate_id = request.GET.get("candidate")

#         if not job_opening_id or not candidate_id:
#             return HttpResponseBadRequest("Missing job opening or candidate ID.")

#         job_opening = get_object_or_404(JobOpening, id=job_opening_id)
#         candidate = get_object_or_404(Candidate, id=candidate_id)

#         # Try to get resume analysis if you want
#         resume_analysis = ResumeAnalysis.objects.filter(candidate=candidate, job_opening=job_opening).first()

#         request.session["answers"] = []
#         request.session["current_question"] = None
#         request.session["job_opening_id"] = job_opening.id
#         request.session["candidate_id"] = candidate.id
#         request.session["resume_analysis_id"] = resume_analysis.id if resume_analysis else None

#         return render(request, "interviewbot/interview.html")




# class GetQuestionView(View):
#     def get(self, request):
#         try:
#             if not all(key in request.session for key in ['job_opening_id', 'candidate_id']):
#                 return JsonResponse({"error": "Session data missing"}, status=400)

#             job_opening = get_object_or_404(JobOpening, id=request.session['job_opening_id'])
#             candidate = get_object_or_404(Candidate, id=request.session['candidate_id'])
#             resume_analysis_id = request.session.get('resume_analysis_id')
#             resume_analysis = get_object_or_404(ResumeAnalysis, id=resume_analysis_id) if resume_analysis_id else None

#             previous_answers = request.session.get("answers", [])
#             if not isinstance(previous_answers, list):
#                 previous_answers = []

#             # First question is always fixed
#             if not previous_answers:
#                 question = "Tell me about yourself."
#             else:
#                 question = generate_next_question(job_opening, candidate, resume_analysis, previous_answers)
                
#                 # If we get the completion message, mark as done
#                 if question == "Thank you. The interview questions are complete.":
#                     return JsonResponse({
#                         "question": question,
#                         "done": True
#                     })

#             # Store the current question in session
#             request.session["current_question"] = question
#             request.session.modified = True

#             return JsonResponse({
#                 "question": question,
#                 "done": False
#             })

#         except Exception as e:
#             print(f"Error in GetQuestionView: {str(e)}")
#             return JsonResponse({
#                 "error": str(e),
#                 "done": True
#             }, status=400)

class InstructionPageView(View):
    def get(self, request):
        # Get job and candidate IDs from query params
        job_opening_id = request.GET.get("job_opening")
        candidate_id = request.GET.get("candidate")

        # Store them in session so we don’t lose them
        request.session["job_opening_id"] = job_opening_id
        request.session["candidate_id"] = candidate_id

        return render(request, "interviewbot/instructions.html")

    def post(self, request):
        # When candidate clicks "Next", redirect to interview page
        job_opening_id = request.session.get("job_opening_id")
        candidate_id = request.session.get("candidate_id")

        return redirect(
            f"/interviewbot/start/?job_opening={job_opening_id}&candidate={candidate_id}"
        )

class InterviewPageView(View):
    def get(self, request):
        # Get job opening ID and candidate ID from query parameters
        job_opening_id = request.GET.get("job_opening")
        candidate_id = request.GET.get("candidate")

        # Validate required parameters
        if not job_opening_id or not candidate_id:
            return HttpResponseBadRequest("Missing job opening or candidate ID.")

        # Fetch the JobOpening and Candidate objects
        job_opening = get_object_or_404(JobOpening, id=job_opening_id)
        candidate = get_object_or_404(Candidate, id=candidate_id)

        # Fetch resume analysis for this candidate and job (if any)
        resume_analysis = ResumeAnalysis.objects.filter(candidate=candidate, job_opening=job_opening).first()
        resume_questions = []

        # ✅ If resume analysis exists and contains response_text (skills, etc.)
        if resume_analysis and resume_analysis.response_text:
            # Parse response_text safely (it could be JSON string or dict)
            if isinstance(resume_analysis.response_text, str):
                try:
                    resume_data = json.loads(resume_analysis.response_text)  # Convert JSON string to dict
                except json.JSONDecodeError:
                    resume_data = {}
            else:
                resume_data = resume_analysis.response_text  # Already a dict

            # Extract skills from parsed data
            skills = resume_data.get("skills", [])
            
            # Generate interview questions based on resume skills
            resume_questions = generate_questions_from_skills(skills)

            # Debug logs (can remove in production)
            print("Resume-based skills:", skills)
            print("Generated questions from skills:", resume_questions)

        # ✅ Get job-specific questions that are marked as selected (or auto-selected)
        job_questions = list(
            job_opening.questions.filter(is_selected=True).values_list('text', flat=True)
        )

        # ✅ Combine all questions:
        # 1. A generic intro question
        # 2. Job-specific questions
        # 3. Resume-based questions
        all_questions = ["Tell me about yourself."] + job_questions + resume_questions

        # ✅ Store interview state in session for later use
        request.session["questions"] = all_questions  # List of all questions
        request.session["answers"] = []  # Will store answers during interview
        request.session["current_index"] = 0  # Track which question user is on
        request.session["job_opening_id"] = job_opening.id
        request.session["candidate_id"] = candidate.id
        request.session["resume_analysis_id"] = resume_analysis.id if resume_analysis else None

        # ✅ Render the interview page (questions will be fetched dynamically using GetQuestionView)
        return render(request, "interviewbot/interview.html")


class GetQuestionView(View):
    def get(self, request):
        try:
            # Get the list of all interview questions from session
            questions = request.session.get("questions", [])
            
            # Get the current question index from session
            index = request.session.get("current_index", 0)

            # ✅ If we've shown all questions, end the interview
            if index >= len(questions):
                return JsonResponse({
                    "question": "Thank you. The interview questions are complete.",
                    "done": True
                })

            # ✅ Get the current question based on index
            question = questions[index]

            # ✅ Update session for next request:
            request.session["current_question"] = question  # Store current question
            request.session["current_index"] = index + 1  # Move to next question
            request.session.modified = True  # Mark session as updated

            # ✅ Return current question to frontend
            return JsonResponse({"question": question, "done": False})

        except Exception as e:
            # Handle any unexpected errors
            print(f"Error in GetQuestionView: {str(e)}")
            return JsonResponse({"error": str(e), "done": True}, status=400)



class SubmitAnswerView(View):
    def post(self, request):
        try:
            # ✅ Check if necessary session data exists
            if not all(key in request.session for key in ['job_opening_id', 'candidate_id', 'current_question']):
                return JsonResponse({
                    'error': 'Session data missing',
                    'success': False
                }, status=400)

            # ✅ Get submitted data from the request
            answer = request.POST.get("answer", "").strip()  # Text answer from user
            video_file = request.FILES.get("video")  # Video file (if recorded)
            audio_file = request.FILES.get("audio")  # Audio file (if recorded)
            question = request.session.get("current_question")  # Current question from session

            # ✅ If there is no current question, return an error
            if not question:
                return JsonResponse({
                    'error': 'No current question in session',
                    'success': False
                }, status=400)

            # ✅ Fetch related objects from DB using IDs stored in session
            job_opening = get_object_or_404(JobOpening, id=request.session['job_opening_id'])
            candidate = get_object_or_404(Candidate, id=request.session['candidate_id'])
            resume_analysis_id = request.session.get('resume_analysis_id')
            resume_analysis = get_object_or_404(ResumeAnalysis, id=resume_analysis_id) if resume_analysis_id else None

            # ✅ Initialize transcript for audio (if provided)
            audio_transcript = None
            if audio_file:
                # 🔹 Save uploaded audio file to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp_audio:
                    for chunk in audio_file.chunks():
                        tmp_audio.write(chunk)
                    tmp_audio_path = tmp_audio.name

                # 🔹 Convert audio to text using transcription function
                audio_transcript = transcribe_audio(tmp_audio_path)

                # Clean transcript
                if audio_transcript:
                    audio_transcript = audio_transcript.strip()

                # 🔹 If audio transcript is longer than typed answer, use transcript
                if audio_transcript and len(audio_transcript) > len(answer):
                    answer = audio_transcript

                # 🔹 Delete temporary file
                os.unlink(tmp_audio_path)

            # ✅ Create InterviewAnswer record in DB
            ia = InterviewAnswer.objects.create(
                job_opening=job_opening,
                candidate=candidate,
                resume_analysis=resume_analysis,
                question=question,
                given_answer=answer,
                audio_transcript=audio_transcript,
                is_correct=False,  # Will be updated after evaluation
                video=video_file  # Store uploaded video (if any)
            )

            # ✅ Evaluate the answer using GPT-based service
            eval_data = evaluate_answer(question, answer, job_opening.requiredskills)
            ia.question_score = eval_data.get("question_score")  # Overall score for the answer
            ia.skill_scores = eval_data.get("skill_scores")  # Per-skill breakdown (dict)
            ia.technical_skills_score = eval_data.get("technical_skills_score")  # Overall technical skills score
            ia.save()

            # ✅ Update session answers list for frontend summary
            answers = request.session.get("answers", [])
            answers.append({
                "question": question,
                "answer": answer,
                "question_score": ia.question_score,
                "skill_scores": ia.skill_scores,
                "technical_skills_score": ia.technical_skills_score,
                "audio_transcript": audio_transcript,
                "video_file": video_file.name if video_file else None
            })
            request.session["answers"] = answers
            request.session["current_question"] = None  # Reset current question
            request.session.modified = True  # Mark session as changed

            # ✅ Return success response
            return JsonResponse({
                "done": len(answers) >= 15,  # Interview ends after 15 questions
                "success": True,
                "message": "Answer submitted and evaluated"
            })

        except Exception as e:
            # ✅ Log and return error response in case of unexpected issues
            print("Error in SubmitAnswerView:", e)
            return JsonResponse({"error": str(e), "success": False}, status=400)

class ResetInterviewView(View):
    def post(self, request):
        try:
            # ✅ Flush (clear) the entire session data for the current user.
            # This removes all keys (questions, answers, progress, job_opening_id, etc.)
            # and effectively resets the interview state.
            request.session.flush()

            # ✅ Return a simple success response to indicate session reset completed.
            return HttpResponse("Session reset successful.")

        except Exception as e:
            # ✅ If any error occurs during the session reset process,
            # return an HTTP 400 Bad Request response with the error message.
            return HttpResponseBadRequest("Error: " + str(e))



# class InterviewReportPageView(View):
#     def get(self, request, candidate_id):
#         candidate = get_object_or_404(Candidate, id=candidate_id)
#         answers = InterviewAnswer.objects.filter(candidate=candidate)

#         if not answers.exists():
#             return render(request, "interviewbot/report.html", {
#                 "error": "No answers found for this candidate.",
#                 "candidate": candidate,
#             })

#         skill_totals = {}
#         skill_counts = {}
#         total_question_score = 0
#         total_technical_score = 0
#         question_data = []

#         for ans in answers:
#             q_score = float(ans.question_score or 0)
#             t_score = float(ans.technical_skills_score or 0)
#             total_question_score += q_score
#             total_technical_score += t_score

#             question_data.append({
#                 "question": ans.question,
#                 "answer": ans.given_answer,
#                 "score": q_score,
#                 "technical_skills_score": t_score,
#                 "skills": ans.skill_scores or {}
#             })

#             if ans.skill_scores:
#                 for sk, sc in ans.skill_scores.items():
#                     skill_totals[sk] = skill_totals.get(sk, 0) + sc
#                     skill_counts[sk] = skill_counts.get(sk, 0) + 1

#         skill_averages = {
#             sk: round(skill_totals[sk] / skill_counts[sk], 2)
#             for sk in skill_totals
#         }

#         # Convert to lists for the chart
#         skill_labels = list(skill_averages.keys())
#         skill_values = list(skill_averages.values())

#         if not skill_labels:
#             skill_labels = ["No Data"]
#             skill_values = [0]

#         avg_question_score = round(total_question_score / len(question_data), 2)
#         avg_technical_score = round(total_technical_score / len(question_data), 2)

#         # Generate the summary
#         summary_text = generate_interview_summary(
#             candidate_name=candidate.name,
#             questions=question_data,
#             required_skills=skill_labels
#         )

#         return render(request, "interviewbot/report.html", {
#             "candidate": candidate,
#             "questions": question_data,
#             "skill_labels": skill_labels,
#             "skill_values": skill_values,
#             "average_question_score": avg_question_score,
#             "average_technical_score": avg_technical_score,
#             "summary_text": summary_text,
#         })
    
class InterviewReportPageView(View):
    def get(self, request, candidate_id):
        # ✅ Fetch the candidate or return 404 if not found
        candidate = get_object_or_404(Candidate, id=candidate_id)

        # ✅ Get all interview answers for this candidate in order of submission
        answers = InterviewAnswer.objects.filter(candidate=candidate).order_by("submitted_at")

        # ✅ If no answers exist, show a message
        if not answers.exists():
            return render(request, "interviewbot/report.html", {
                "error": "No answers found for this candidate.",
                "candidate": candidate,
            })

        # ✅ Initialize lists and variables for report data
        job_questions = []       # Stores job-based questions
        resume_questions = []    # Stores resume-based questions
        total_q_score = total_t_score = 0  # Accumulators for average calculation

        # ✅ Dictionaries to calculate per-skill averages
        skill_totals = {}
        skill_counts = {}

        # ✅ Loop through all answers to compute scores and categorize questions
        for ans in answers:
            q_score = float(ans.question_score or 0)           # Question score (default 0 if None)
            t_score = float(ans.technical_skills_score or 0)   # Technical skills score
            total_q_score += q_score
            total_t_score += t_score

            # ✅ Determine the question source:
            # If it's NOT the intro question AND either marked incorrect OR no video uploaded → assume resume-based
            is_resume = "Tell me about yourself" not in ans.question and (ans.is_correct is False or not ans.video)

            # ✅ Collect detailed answer data
            answer_data = {
                "question": ans.question,
                "answer": ans.given_answer,
                "score": q_score,
                "technical_skills_score": t_score,
                "skills": ans.skill_scores or {},    # Skill-wise score breakdown
                "source": "resume" if is_resume else "job"  # Categorization
            }

            # ✅ Add to respective list based on source
            if answer_data["source"] == "resume":
                resume_questions.append(answer_data)
            else:
                job_questions.append(answer_data)

            # ✅ Accumulate skill scores for average calculation
            for skill, score in (ans.skill_scores or {}).items():
                skill_totals[skill] = skill_totals.get(skill, 0) + score
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

        # ✅ Calculate average score per skill
        skill_averages = {
            skill: round(skill_totals[skill] / skill_counts[skill], 2)
            for skill in skill_totals
        }

        # ✅ Prepare skill data for charts (labels & values)
        skill_labels = list(skill_averages.keys()) or ["No Data"]
        skill_values = list(skill_averages.values()) or [0]

        # ✅ Compute overall average scores
        avg_question_score = round(total_q_score / len(answers), 2)
        avg_technical_score = round(total_t_score / len(answers), 2)

        # ✅ Combine all questions for summary generation
        all_questions = job_questions + resume_questions

        # ✅ Generate a summary text using GPT or custom logic
        summary_text = generate_interview_summary(
            candidate_name=candidate.name,
            questions=all_questions,
            required_skills=skill_labels
        )

        # ✅ Render the report page with all computed data
        return render(request, "interviewbot/report.html", {
            "candidate": candidate,
            "questions": all_questions,
            "job_questions": job_questions,
            "resume_questions": resume_questions,
            "skill_labels": skill_labels,
            "skill_values": skill_values,
            "average_question_score": avg_question_score,
            "average_technical_score": avg_technical_score,
            "summary_text": summary_text,
        })

    def get_context_data(self, **kwargs):
        # ✅ Adds extra context for templates
        context = super().get_context_data(**kwargs)
        candidate = get_object_or_404(Candidate, id=self.kwargs["candidate_id"])

        # ✅ Check if interview exists for the candidate
        interview_done = InterviewAnswer.objects.filter(candidate=candidate).exists()
        context["candidate"] = candidate
        context["interview_done"] = interview_done
        return context


class JobOpeningQuestionsView(LoginRequiredMixin, View):
    template_name = "interviewbot/job_opening_questions.html"

    def get(self, request, pk):
        # ✅ Get job by ID, ensure it belongs to the current user's company
        job = get_object_or_404(JobOpening, pk=pk, company=request.user.employee.company)

        # ✅ Render all questions (generated + custom)
        context = {
            'job': job,
            'questions': job.questions.all()  # All questions linked to this job
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        # ✅ Fetch job object
        job = get_object_or_404(JobOpening, pk=pk, company=request.user.employee.company)

        # ✅ Handle custom questions submitted by the recruiter
        custom_questions = request.POST.getlist('custom_questions[]')
        for question in custom_questions:
            if question.strip():
                # ✅ Save custom question to DB
                InterviewQuestion.objects.create(
                    job_opening=job,
                    text=question.strip(),
                    is_selected=True,  # Always selected since no manual selection
                    is_custom=True
                )

        # ✅ Show success message and reload page
        messages.success(request, "Custom interview questions added successfully.")
        return redirect('dashboard')

class JobOpeningSkillSelectView(LoginRequiredMixin, View):
    template_name = "interviewbot/job_opening_skill_select.html"

    def get(self, request, pk):
        # ✅ Get the job for the given primary key, making sure it belongs to the user's company
        job = get_object_or_404(JobOpening, pk=pk, company=request.user.employee.company)

        # ✅ Extract required skills from comma-separated string into list
        skills = job.requiredskills.split(', ') if job.requiredskills else []

        # ✅ Render the template with job and skills list
        return render(request, self.template_name, {'job': job, 'skills': skills})

    def post(self, request, pk):
        # ✅ Fetch the job again during POST to work with it
        job = get_object_or_404(JobOpening, pk=pk, company=request.user.employee.company)

        # ✅ Extract skills again to re-render page with same context in case of error
        skills = job.requiredskills.split(', ') if job.requiredskills else []

        # ✅ Get selected skill names from checkboxes
        selected_skills = request.POST.getlist('skill')  # e.g., ['Python', 'Django']

        skill_levels = []
        for skill in selected_skills:
            # ✅ Get the level for each selected skill using the name 'level_for_<skill>'
            level = request.POST.get(f"level_for_{skill}") or request.POST.get("level")
            if level:
                skill_levels.append({'skill': skill, 'level': level})

        # ❌ If no valid skill + level pair was selected, re-render with error
        if not skill_levels:
            return render(request, self.template_name, {
                'job': job,
                'skills': skills,
                'error': "Please select at least one skill and level to generate questions."
            })

        # ✅ If skill+level pairs exist, call GPT to generate questions for all combined
        questions = generate_combined_questions_for_skills(
            designation=job.designation,
            skill_levels=skill_levels,
            n=5  # total questions only (not 5 per skill)
        )

        # ✅ Save each generated question into the DB
        for q in questions:
            InterviewQuestion.objects.create(
                job_opening=job,
                text=q,
                is_selected=True,
                is_custom=False
            )

        # ✅ Show a success message and redirect to the questions page
        messages.success(request, "Questions generated successfully.")
        return redirect('job-opening-questions', pk=job.pk)
