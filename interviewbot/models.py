from django.db import models
from django.db.models import JSONField
from django.core.validators import FileExtensionValidator, EmailValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User,AbstractUser


class Company(models.Model):
    name = models.CharField(max_length=255)
    website = models.URLField(max_length=100, blank=True)
    description = models.TextField(null=True, blank=True)
    joined = models.DateTimeField(default=timezone.now)
    created_by = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, related_name='company')

    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)
    location = models.CharField(max_length=400, blank=True)
    email = models.EmailField(validators=[EmailValidator], unique=True)
    contact = models.CharField(max_length=12, blank=True)
    website = models.URLField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)


    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.email = self.email.lower()  # Convert email to lowercase
        super().save(*args, **kwargs)

def exempt_zero(value):
    if value == 0:
        raise ValidationError(
            ('Please enter a value greater than 0'),
            params={'value': value},
        )


class Company(models.Model):
    name = models.CharField(max_length=255)
    website = models.URLField(max_length=100, blank=True)
    description = models.TextField(null=True, blank=True)
    joined = models.DateTimeField(default=timezone.now)
    created_by = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, related_name='company')

    def __str__(self):
        return self.name
    
class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee')  # Link to User model
    contact = models.CharField(max_length=12, unique=True, blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='employees', null=True)
    joined = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.user.username

class JobOpening(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    designation = models.CharField(max_length=255)
    openings = models.PositiveIntegerField(validators=[exempt_zero])
    requiredskills = models.TextField(blank=True)
    min_experience = models.PositiveIntegerField(default=0)
    max_experience = models.PositiveIntegerField(default=1)
    education = models.CharField(max_length=255, default="graduate", blank=True)
    jobdescription = models.FileField(blank=True, upload_to='jd/',
                                     validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc', 'txt'],
                                                                        message='Select pdf, docx, doc or txt files only')])
    budget = models.FloatField(default=0)
    job_type = models.CharField(max_length=50,blank=True, choices=[('Contractual', 'Contractual'),
                                                        ('Permanent', 'Permanent')])
    job_mode = models.CharField(max_length=50,blank=True, choices=[('Office', 'Office'),
                                                        ('Remote', 'Remote'),
                                                        ('Hybrid', 'Hybrid')])
    updated_on = models.DateTimeField(default=timezone.now)
    jd_content = models.TextField(blank=True)
    assignemployee = models.ManyToManyField(Employee)
    # assignemployee = models.ForeignKey(Employee, on_delete=models.CASCADE)  # ForeignKey to Employee
    content_type = models.CharField(blank=True, max_length=10, choices=[('file', 'File'), ('text', 'Text')])  # Choice for content type
    active = models.BooleanField(default=True)
    expires = models.IntegerField(default=21)
    skills_criteria = models.IntegerField(default=50)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, default="1", related_name='jobopening')

    HIRING_FOR_CHOICES = [
        ('self', 'Hiring for self'),
        ('client', 'Hiring for client'),
    ]
    hiring_for = models.CharField(max_length=10, choices=HIRING_FOR_CHOICES, default='self')


    def __str__(self):
        return self.designation

    @property
    def expiration_date(self):
        """Calculate the expiration date based on created_date and expires."""
        return self.updated_on + timezone.timedelta(days=self.expires)

    @property
    def days_remaining(self):
        """Calculate the number of days remaining until expiration."""
        remaining = ((self.expiration_date - timezone.now()).days) + 1
        return max(remaining, 0)  # Return 0 if already expired

    @property
    def is_expired(self):
        """Check if the job opening is expired."""
        if hasattr(self, 'request') and self.request.user.is_authenticated and self.request.user.employee.company.name == "JMS Advisory":
            return False

        return timezone.now() > self.expiration_date

    class Meta:
        ordering = ['-updated_on']

class Candidate(models.Model):
    job_openings = models.ManyToManyField(JobOpening, blank=True, null=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(validators=[EmailValidator])
    contact = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    linkedin = models.URLField(max_length=255, blank=True, null=True)
    github = models.URLField(max_length=255, blank=True, null=True)
    portfolio = models.URLField(max_length=255, blank=True, null=True)
    blog = models.URLField(max_length=255, blank=True, null=True)
    education = models.CharField(max_length=255)
    experience = models.PositiveIntegerField(blank=True, default=0)
    current_designation = models.CharField(max_length=255, blank=True, null=True)
    current_organization = models.CharField(max_length=255, blank=True, null=True)
    current_ctc = models.FloatField(max_length=255, blank=True, default=0)
    current_ctc_ih = models.FloatField(max_length=255, blank=True, default=0)


    expected_ctc = models.FloatField(max_length=255, blank=True, default=0)
    expected_ctc_ih = models.FloatField(max_length=255, blank=True, default=0)
    offer_in_hand = models.FloatField(max_length=255, blank=True, default=0)
    notice_period = models.PositiveIntegerField(blank=True, default=0)
    reason_for_change = models.CharField(max_length=500, blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    upload_resume = models.FileField(upload_to='resumes/', null=True,
                                     validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc'],
                                                                        message='Select pdf, docx or doc files only')])
    filename = models.CharField(max_length=255, blank=True)
    text_content = models.TextField(default='')
    updated = models.DateTimeField(default=timezone.now)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='candidates', null=True)
    is_new = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.email = self.email.lower()  # Convert email to lowercase
        if self.upload_resume:
            # Extract the original filename
            self.filename = self.upload_resume.name
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class ResumeAnalysis(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="analysis")
    job_opening = models.ForeignKey(JobOpening, on_delete=models.CASCADE, null=True)
    response_text = models.JSONField(null=True)

class InterviewAnswer(models.Model):
    job_opening = models.ForeignKey(JobOpening, on_delete=models.CASCADE, null=True, blank=True)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="interview_answers", null=True, blank=True)
    resume_analysis = models.ForeignKey(ResumeAnalysis, on_delete=models.SET_NULL, null=True, blank=True, related_name="interview_answers")
    question = models.TextField()
    given_answer = models.TextField()
    audio_transcript = models.TextField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    video = models.FileField(upload_to='interviews/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    # Scores generated by GPT
    question_score = models.DecimalField(null=True, blank=True, max_digits=5, decimal_places=2)
    skill_scores = JSONField(null=True, blank=True)  # e.g., {"Communication": 80, "Problem Solving": 70}
    technical_skills_score = models.DecimalField(             # <--- New field added
        null=True, blank=True, max_digits=5, decimal_places=2,
        help_text="Score (0–100) representing overall technical skill demonstrated."
    )
    source = models.CharField(max_length=20, choices=[('job', 'Job'), ('resume', 'Resume')], default='job')


class InterviewQuestion(models.Model):
    job_opening = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    is_selected = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)  # <-- Track recruiter-created ones
    created_at = models.DateTimeField(auto_now_add=True)
