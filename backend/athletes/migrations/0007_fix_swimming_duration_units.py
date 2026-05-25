from datetime import timedelta

from django.db import migrations


MINUTE_EVENTS = {'100m', '200m', '400m', '800m', '1500m'}


def _repair_decimal_clock(duration_value):
    if not duration_value:
        return duration_value

    total_seconds = float(duration_value.total_seconds())
    raw = f"{total_seconds:.6f}".rstrip('0').rstrip('.')
    if '.' not in raw:
        return duration_value

    left, right = raw.split('.', 1)
    if not left.isdigit() or not right.isdigit():
        return duration_value

    minutes = int(left)
    seconds = int((right[:2] or '0').ljust(2, '0'))
    hundredths = int((right[2:4] or '0').ljust(2, '0'))
    return timedelta(minutes=minutes, seconds=seconds, milliseconds=hundredths * 10)


def forwards(apps, schema_editor):
    Swimming = apps.get_model('athletes', 'Swimming')

    for record in Swimming.objects.all():
        if record.events not in MINUTE_EVENTS:
            continue

        changed = False

        if record.current_record and record.current_record.total_seconds() < 30:
            record.current_record = _repair_decimal_clock(record.current_record)
            changed = True

        if record.previous_record and record.previous_record.total_seconds() < 30:
            record.previous_record = _repair_decimal_clock(record.previous_record)
            changed = True

        if changed:
            record.expected_record = None
            record.save()


class Migration(migrations.Migration):

    dependencies = [
        ('athletes', '0006_alter_attendancerecord_date'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
