from django.db import models

# Create your models here.
from django.db import models
from django.core.validators import FileExtensionValidator, EmailValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User, Group


# Create your models here.

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