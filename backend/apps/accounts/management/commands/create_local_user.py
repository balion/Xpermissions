import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Create a local user account with a usable password. '
        'Intended for CLI-only use — the UI does not expose local user creation.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email address (used as login)')
        parser.add_argument('--username', type=str, help='Username (unique identifier)')
        parser.add_argument('--first-name', dest='first_name', type=str, default='')
        parser.add_argument('--last-name', dest='last_name', type=str, default='')
        parser.add_argument('--password', type=str, help='Password (omit to prompt interactively)')
        parser.add_argument(
            '--superuser', action='store_true',
            help='Grant is_superuser + is_staff (full Django admin access)',
        )
        parser.add_argument(
            '--status', type=str, default='active',
            choices=['active', 'pending', 'locked'],
        )

    def handle(self, *args, **options):
        from apps.accounts.models import User

        email = options['email'] or input('Email: ').strip()
        username = options['username'] or input('Username: ').strip()
        first_name = options['first_name'] or input('First name (optional, Enter to skip): ').strip()
        last_name = options['last_name'] or input('Last name (optional, Enter to skip): ').strip()

        if not email or not username:
            self.stderr.write(self.style.ERROR('Email and username are required.'))
            return

        if User.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f'A user with email {email!r} already exists.'))
            return

        if User.objects.filter(username=username).exists():
            self.stderr.write(self.style.ERROR(f'A user with username {username!r} already exists.'))
            return

        password = options['password'] or self._prompt_password()
        if not password:
            return

        is_superuser = options['superuser']
        user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            status=options['status'],
            is_active=True,
            is_staff=is_superuser,
            is_superuser=is_superuser,
        )
        user.set_password(password)
        user.save()

        label = 'Superuser' if is_superuser else 'User'
        self.stdout.write(self.style.SUCCESS(f'{label} {email!r} created successfully.'))

    def _prompt_password(self) -> str:
        while True:
            password = getpass.getpass('Password: ')
            confirm = getpass.getpass('Confirm password: ')
            if password != confirm:
                self.stderr.write('Passwords do not match. Try again.\n')
                continue
            try:
                validate_password(password)
            except ValidationError as exc:
                for msg in exc.messages:
                    self.stderr.write(f'  {msg}')
                self.stderr.write('Try again.\n')
                continue
            return password
