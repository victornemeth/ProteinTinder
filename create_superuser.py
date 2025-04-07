# create_superuser.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'annotate_app_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username='admin').exists():
    print("Creating superuser 'admin'")
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
else:
    print("Superuser 'admin' already exists")
