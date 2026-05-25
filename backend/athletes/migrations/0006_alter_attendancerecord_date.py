from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('athletes', '0005_attendancerecord_coach_notes_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendancerecord',
            name='date',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
    ]
