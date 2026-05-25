import sys
import os
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from athletes.serializers import SwimmingSerializer
from datetime import timedelta

data = {
    "athlete": 1,
    "stroke": "Freestyle",
    "events": "100m",
    "current_record": "1:00.00",
    "splits_data": [
        {"lap_number": 1, "current": "29.0", "previous": "30.0"},
        {"lap_number": 2, "current": "31.0"}
    ]
}

serializer = SwimmingSerializer(data=data)
if serializer.is_valid():
    print("VALID SPLITS:", serializer.validated_data['splits_data'])
else:
    print("INVALID:", serializer.errors)
