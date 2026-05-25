from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('athletes', '0008_athleteinfo_is_subscribed'),
    ]

    operations = [
        migrations.AddField(
            model_name='athleteinfo',
            name='subscription_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='athleteinfo',
            name='subscription_start_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
