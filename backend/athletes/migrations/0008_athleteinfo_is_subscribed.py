from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('athletes', '0007_fix_swimming_duration_units'),
    ]

    operations = [
        migrations.AddField(
            model_name='athleteinfo',
            name='is_subscribed',
            field=models.BooleanField(default=False),
        ),
    ]
