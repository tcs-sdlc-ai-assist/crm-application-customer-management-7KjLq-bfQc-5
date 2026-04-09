import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_project.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

app = application