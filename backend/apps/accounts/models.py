from django.contrib.auth.models import AbstractUser
from django.db import models

STATUS_ACTIVE = 'active'
STATUS_LOCKED = 'locked'
STATUS_PENDING = 'pending'

STATUS_CHOICES = [
    (STATUS_ACTIVE, 'Active'),
    (STATUS_LOCKED, 'Locked'),
    (STATUS_PENDING, 'Pending'),
]


class User(AbstractUser):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    roles = models.ManyToManyField(
        'roles.Role',
        blank=True,
        related_name='users',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        ordering = ['email']

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def is_active_user(self):
        return self.status == STATUS_ACTIVE

    @property
    def display_name(self):
        full = self.get_full_name()
        return full if full.strip() else self.email
