from django.db import models
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta

# Create your models here.


class ScreeningMetrics(models.Model):
    total_resumes_processed = models.IntegerField(default=0)
    total_screening_time = models.DurationField(default=timedelta())
    for_role = models.CharField(max_length=100)
    date = models.DateField(default=timezone.now)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    # def __str__(self):
    #     return f"Screening Metrics: {self.total_resumes_processed} resumes processed, {self.total_screening_time} total screening time"