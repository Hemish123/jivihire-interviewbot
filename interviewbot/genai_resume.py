import os
import base64
from openai import AzureOpenAI,OpenAI
import re
import json, os


#for production
import subprocess
import tempfile
import os

def convert_webm_to_wav(input_path):
    output_path = input_path.replace(".webm", ".wav")
    command = ["ffmpeg", "-i", input_path, "-ar", "16000", "-ac", "1", output_path, "-y"]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path

def transcribe_audio(audio_file_path):
    """
    Convert audio file to text using OpenAI's Whisper model
    """
    # client = OpenAI(api_key=os.environ['CHATGPT_API_KEY'])
    endpoint = os.getenv("ENDPOINT_URL", "https://jivihireopenai.openai.azure.com/")

    # # # Initialize Azure OpenAI Service client with key-based authentication
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=os.environ['CHATGPT_API_KEY'],
        api_version="2024-05-01-preview",
    )
    
    try:
        #for production
        # ✅ Convert WebM -> WAV
        if audio_file_path.endswith(".webm"):
            audio_file_path = convert_webm_to_wav(audio_file_path)

        with open(audio_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",  # Using Whisper model
                file=audio_file
            )
        return transcription.text
    except Exception as e:
        print(f"Error in audio transcription: {e}")
        return None
    #for production
    finally:
        # Cleanup converted file
        if audio_file_path.endswith(".wav") and os.path.exists(audio_file_path):
            os.remove(audio_file_path)




def evaluate_answer(question: str, answer: str, required_skills: list) -> dict:
    endpoint = os.getenv("ENDPOINT_URL", "https://jivihireopenai.openai.azure.com/")

    # # # Initialize Azure OpenAI Service client with key-based authentication
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=os.environ['CHATGPT_API_KEY'],
        api_version="2024-05-01-preview",
    )
    """
    Sends the interview question and candidate answer to GPT,
    requesting:
      - question_score (0–100)
      - skill_scores dict (skill name -> score)
      - technical_skills_score (0–100)

    Always returns a dict with consistent keys and cleaned values.
    """

    # Convert the required skills list to comma-separated string for the prompt
    skills_list = ", ".join(required_skills)

    # System prompt to instruct GPT
    system = (
        "You are a technical interviewer. Respond ONLY with valid JSON.\n"
        "Format must be:\n"
        "{\n"
        '  "question_score": (integer between 0 and 100),\n'
        '  "technical_skills_score": (integer between 0 and 100),\n'
        '  "skill_scores": {\n'
        '     "Python": 85,\n'
        '     "Django": 90,\n'
        '     ... (one entry per required skill)\n'
        "  }\n"
        "}\n"
        "⚠️ skill_scores must be a dictionary with skill names as keys — not a list or characters.\n"
        "⚠️ Do not split skill names into letters."
    )

    # User prompt with the actual question, answer, and skills to assess
    user = f"""
Question:
{question}

Candidate Answer:
{answer}

Please score each of these skills: {skills_list}.
Also provide an overall "technical_skills_score" based on depth and clarity of technical knowledge.
"""

    # Call GPT
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        temperature=0
    )

    # Extract the raw text response
    text = resp.choices[0].message.content.strip()

    try:
        parsed = json.loads(text)

        # Initialize clean result with defaults
        result = {
            "question_score": 0,
            "skill_scores": {},
            "technical_skills_score": 0
        }

        # Get question_score safely
        if isinstance(parsed.get("question_score"), (int, float)):
            result["question_score"] = parsed["question_score"]

        # Get technical_skills_score safely
        if isinstance(parsed.get("technical_skills_score"), (int, float)):
            result["technical_skills_score"] = parsed["technical_skills_score"]

        # Clean skill_scores
        raw_skills = parsed.get("skill_scores", {})
        clean_skills = {}
        if isinstance(raw_skills, dict):
            for k, v in raw_skills.items():
                # Force key to string, strip whitespace, skip if empty
                k_str = str(k).strip()
                if k_str:
                    # Force value to number, or 0
                    score = float(v) if isinstance(v, (int, float)) else 0
                    clean_skills[k_str] = score

        # If GPT returned nothing, default to all 0s
        if not clean_skills:
            clean_skills = {skill: 0 for skill in required_skills}

        result["skill_scores"] = clean_skills

        return result

    except json.JSONDecodeError:
        # Fallback if GPT did not return JSON
        print("💥 GPT JSON parse error:\n", text)
        return {
            "question_score": 0,
            "skill_scores": {skill: 0 for skill in required_skills},
            "technical_skills_score": 0
        }

# def generate_interview_summary(candidate_name: str, questions: list, required_skills: list) -> str:
#     """
#     Generate a summary of the interview overall performance.
#     """
#     # Build a detailed string with Q&A and scores
#     qna_text = ""
#     for q in questions:
#         qna_text += f"""
# Q: {q['question']}
# A: {q['answer']}
# Score: {q['score']}%
# Technical Skills: {q['technical_skills_score']}%
# """

#         if q["skills"]:
#             skills_str = ", ".join([f"{s}: {v}%" for s, v in q["skills"].items()])
#             qna_text += f"Skill Scores: {skills_str}\n"

#     skills_list = ", ".join(required_skills)

#     system = (
#         "You are a senior interviewer and hiring manager. "
#         "Based on the interview transcript, write a short professional summary assessing the candidate's performance, "
#         "strengths, weaknesses, and fit for the role. Keep it concise (max 200 words)."
#     )

#     user = f"""
# Candidate: {candidate_name}

# Interview Summary Data:
# {qna_text}

# Skills evaluated: {skills_list}

# Please write the interview summary:
# """

#     resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": system},
#             {"role": "user", "content": user}
#         ],
#         temperature=0.3
#     )

#     return resp.choices[0].message.content.strip()

def generate_interview_summary(candidate_name: str, questions: list, required_skills: list) -> str:
    endpoint = os.getenv("ENDPOINT_URL", "https://jivihireopenai.openai.azure.com/")

    # # # Initialize Azure OpenAI Service client with key-based authentication
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=os.environ['CHATGPT_API_KEY'],
        api_version="2024-05-01-preview",
    )
    """
    Generate a 5-bullet summary of the interview covering all aspects: performance, skills, and fit.
    """
    qna_text = ""
    for q in questions:
        qna_text += f"""
Q: {q['question']}
A: {q['answer']}
Score: {q['score']}%
Technical Skills: {q['technical_skills_score']}%
"""
        if q["skills"]:
            skills_str = ", ".join([f"{s}: {v}%" for s, v in q["skills"].items()])
            qna_text += f"Skill Scores: {skills_str}\n"

    skills_list = ", ".join(required_skills)

    # ✅ GPT prompt for 5 bullet points
    system = (
        "You are a senior interviewer. Based on the provided interview data, generate a summary in exactly 5 bullet points. "
        "Cover the candidate's performance, strengths, weaknesses, technical and soft skills, and overall recommendation. "
        "Be concise, avoid repetition, and use professional tone."
    )

    user = f"""
Candidate: {candidate_name}

Interview Summary Data:
{qna_text}

Skills evaluated: {skills_list}

Write 5 bullet points summarizing the interview:
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        temperature=0.3
    )

    return resp.choices[0].message.content.strip()


def generate_questions_from_skills(skills):
    if not skills:
        return []

    # client = OpenAI(api_key=os.environ['CHATGPT_API_KEY'])
    endpoint = os.getenv("ENDPOINT_URL", "https://jivihireopenai.openai.azure.com/")

    # # # Initialize Azure OpenAI Service client with key-based authentication
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=os.environ['CHATGPT_API_KEY'],
        api_version="2024-05-01-preview",
    )
    user_prompt = f"""Generate 5 interview questions based on these skills: {', '.join(skills)}.
    Return a JSON list: {{ "questions": ["q1", "q2", ...] }}"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful technical recruiter."},
                {"role": "user", "content": user_prompt}
            ]
        )
        data = json.loads(resp.choices[0].message.content)
        return data.get("questions", [])[:5]
    except Exception as e:
        print(f"Error generating resume-based questions: {e}")
        return []

def generate_combined_questions_for_skills(designation, skill_levels, n=5):
    """
    Generate exactly `n` interview questions for multiple skills combined.
    skill_levels: [{'skill': 'Python', 'level': 'fresher'}, ...]
    """
    # client = OpenAI(api_key=os.environ['CHATGPT_API_KEY'])
    endpoint = os.getenv("ENDPOINT_URL", "https://jivihireopenai.openai.azure.com/")

    # # # Initialize Azure OpenAI Service client with key-based authentication
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=os.environ['CHATGPT_API_KEY'],
        api_version="2024-05-01-preview",
    )

    # ✅ Create descriptive list for prompt
    skills_desc = ", ".join([f"{s['skill']} ({s['level']} level)" for s in skill_levels])

    user_prompt = (
        f"Generate exactly {n} interview questions for a \"{designation}\" role. "
        f"The questions should cover the following skills and their levels: {skills_desc}. "
        "Distribute questions fairly across skills. Return a JSON list: { \"questions\": [\"q1\", \"q2\", ...] }"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert interviewer."},
                {"role": "user", "content": user_prompt}
            ]
        )
        data = json.loads(resp.choices[0].message.content)
        return data.get("questions", [])[:n]
    except Exception as e:
        print("Error generating combined questions:", e)
        return []
