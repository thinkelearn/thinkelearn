from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Create a superuser with environment variables'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing user and create a new one',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Get credentials from environment variables
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        email = os.environ.get('ADMIN_EMAIL', 'admin@thinkelearn.com')
        password = os.environ.get('ADMIN_PASSWORD', 'defaultpassword123')
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            if options['reset']:
                User.objects.filter(username=username).delete()
                self.stdout.write(
                    self.style.WARNING(f'Deleted existing user "{username}".')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'User "{username}" already exists. Use --reset to recreate.')
                )
                return
        
        # Create superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Superuser "{username}" created successfully with email {email}.')
        )