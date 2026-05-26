"""
WSGI config for ams_core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import sys

# Add the backend directory to sys.path so Django can resolve 'ams_core' as a module
# This is required for Vercel serverless functions where the entry point
# is backend/ams_core/wsgi.py but Django expects 'ams_core.settings'
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ams_core.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Vercel looks for an 'app' variable as the WSGI handler
app = application
