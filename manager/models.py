from django.db import models
from django.core.validators import FileExtensionValidator, EmailValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from twisted.python.usage import UsageError
from django.contrib.auth.models import User
from users.models import Employee,Company



# Create your models here.
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
    
