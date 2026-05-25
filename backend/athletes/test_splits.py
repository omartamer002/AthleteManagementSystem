import sys
import os
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from athletes.serializers import SwimmingSerializer

data = {
    "athlete": 1,
    "stroke": "Freestyle",
    "events": "1500m",
    "current_record": "15:00.00",
    "splits_data": [
        {"lap_number": 1, "current": "29.8"},
        {"lap_number": 2, "current": "1:02.5"}
    ]
}

serializer = SwimmingSerializer(data=data)
if serializer.is_valid():
    print("VALID:", serializer.validated_data['splits_data'])
else:
    print("INVALID:", serializer.errors)
