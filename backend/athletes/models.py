from django.db import models
from django.utils import timezone

class AthleteInfo(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]
    
    name = models.CharField(max_length=255)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    height = models.DecimalField(max_digits=5, decimal_places=2, help_text="Height in cm")
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight in kg")
    body_type = models.CharField(max_length=100)
    date_of_birth = models.DateField(blank=True, null=True)
    academy_since = models.DateField(default=timezone.localdate, editable=False)
    strengths = models.TextField(blank=True, null=True)
    weaknesses = models.TextField(blank=True, null=True)
    is_subscribed = models.BooleanField(default=False)
    subscription_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fee in EGP")
    subscription_start_date = models.DateField(blank=True, null=True)
    subscription_end_date = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class AttendanceRecord(models.Model):
    athlete = models.ForeignKey(AthleteInfo, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.localdate)
    attended = models.BooleanField(default=False)
    performance_rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Rating from 1 to 10")
    coach_notes = models.TextField(null=True, blank=True)
    
    # Biometrics Tracking
    hrv = models.PositiveIntegerField(null=True, blank=True, help_text="Heart Rate Variability (ms)")
    resting_heart_rate = models.PositiveIntegerField(null=True, blank=True, help_text="Resting Heart Rate (bpm)")
    sleep_hours = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Sleep Hours")
    fatigue_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Fatigue Score (1-10, 10 is max fatigue)")
    muscle_soreness = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Muscle Soreness (1-10, 10 is max soreness)")
    workout_completed = models.BooleanField(default=False, help_text="Did the athlete complete their assigned workout for this session?")

    class Meta:
        unique_together = ('athlete', 'date')

    def __str__(self):
        return f"{self.athlete.name} - {self.date} - {'Attended' if self.attended else 'Absent'}"

class InjuryRecord(models.Model):
    SEVERITY_CHOICES = [('Mild', 'Mild'), ('Moderate', 'Moderate'), ('Severe', 'Severe')]
    REHAB_PHASES = [
        ('Acute', 'Acute Phase'),
        ('Mobility', 'Mobility & ROM'),
        ('Load', 'Load Bearing'),
        ('Sport', 'Sport Specific'),
        ('Cleared', 'Cleared for Play')
    ]
    
    athlete = models.ForeignKey(AthleteInfo, on_delete=models.CASCADE, related_name='injury_records')
    is_active = models.BooleanField(default=True, help_text="Current Injury Status (Yes/No)")
    injury_type = models.CharField(max_length=255)
    severity = models.CharField(max_length=50, choices=SEVERITY_CHOICES)
    start_date = models.DateField(default=timezone.localdate)
    expected_recovery_time = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 2 weeks")
    estimated_return_date = models.DateField(blank=True, null=True)
    medical_notes = models.TextField(blank=True, null=True)
    rehab_phase = models.CharField(max_length=50, choices=REHAB_PHASES, default='Acute')
    cleared_to_train = models.BooleanField(default=False)
    cleared_by = models.CharField(max_length=100, blank=True, null=True, help_text="Coach, Doctor, Physio")
    returned_before_recovery = models.BooleanField(default=False)
    
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.athlete.name} - {self.injury_type} ({'Active' if self.is_active else 'Resolved'})"

class PainLog(models.Model):
    athlete = models.ForeignKey(AthleteInfo, on_delete=models.CASCADE, related_name='pain_logs')
    date = models.DateField(default=timezone.localdate)
    body_part = models.CharField(max_length=100)
    pain_level = models.PositiveSmallIntegerField(help_text="Pain Level (1-10)")
    pain_type = models.CharField(max_length=100, help_text="e.g. Sharp, Dull, Aching")
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.athlete.name} - {self.body_part} ({self.pain_level}/10) on {self.date}"

class Owner(models.Model):
    revenue_per_month = models.DecimalField(max_digits=12, decimal_places=2)
    athlete_numbers = models.PositiveIntegerField()
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage of leads becoming members")
    total_income = models.DecimalField(max_digits=12, decimal_places=2)
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Business Snapshot - {self.created_at.strftime('%Y-%m-%d')}"

class Fitness(models.Model):
    athlete = models.OneToOneField(AthleteInfo, on_delete=models.CASCADE, related_name='fitness_profile')
    workout_plan = models.TextField()
    workout_type = models.CharField(max_length=100)
    sessions_per_week = models.PositiveIntegerField()
    
    previous_fitness_tests = models.JSONField(default=dict, blank=True)
    current_fitness_tests = models.JSONField(default=dict, blank=True)
    expected_fitness_results = models.JSONField(default=dict, blank=True)
    
    feedback = models.TextField(blank=True, null=True)
    nutrition_plan = models.TextField(blank=True, null=True)
    fitness_goal = models.TextField(blank=True, null=True)
    inbody_file = models.FileField(upload_to='inbody/', blank=True, null=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Fitness Profile: {self.athlete.name}"

    def calculate_expected_results(self):
        """
        Automated calculation logic:
        For each numerical key in current_fitness_tests:
        - If it exists in previous_fitness_tests: Expected = Current + (Current - Previous)
        - If not: Expected = Current * 1.1 (10% standard growth)
        """
        prev = self.previous_fitness_tests or {}
        curr = self.current_fitness_tests or {}
        expected = {}

        for key, value in curr.items():
            if isinstance(value, dict) and value.get('value') is not None:
                prev_value = prev.get(key) if isinstance(prev.get(key), dict) else {}
                curr_weight = value.get('value')
                curr_reps = value.get('reps')
                unit = value.get('unit')
                is_rep_count = value.get('measure') == 'rep_count' or unit == 'reps'
                is_time_seconds = value.get('measure') == 'time_seconds' or unit == 'sec'

                if isinstance(curr_weight, (int, float)):
                    prev_weight = prev_value.get('value') if isinstance(prev_value.get('value'), (int, float)) else None
                    if prev_weight is not None:
                        expected_weight = curr_weight - (prev_weight - curr_weight) if is_time_seconds else curr_weight + (curr_weight - prev_weight)
                    else:
                        expected_weight = curr_weight * (0.95 if is_time_seconds else 1.1)

                    if is_rep_count:
                        expected_weight = round(expected_weight)
                    if is_time_seconds:
                        expected_weight = max(1, round(expected_weight))

                    if isinstance(curr_reps, int):
                        prev_reps = prev_value.get('reps') if isinstance(prev_value.get('reps'), int) else None
                        expected_reps = curr_reps + (curr_reps - prev_reps) if prev_reps is not None else max(curr_reps + 1, curr_reps)
                    else:
                        expected_reps = None

                    expected[key] = {
                        'value': expected_weight if is_rep_count else round(expected_weight, 2),
                        'reps': expected_reps,
                        'unit': unit or None,
                        **({'measure': value.get('measure')} if value.get('measure') else {}),
                        **({'group': value.get('group')} if value.get('group') else {})
                    }
                else:
                    expected[key] = value
            elif isinstance(value, (int, float)):
                if key in prev and isinstance(prev[key], (int, float)):
                    diff = value - prev[key]
                    expected[key] = value + diff
                else:
                    expected[key] = value * 1.1
            else:
                # Keep non-numerical as is or placeholder
                expected[key] = value

        self.expected_fitness_results = expected
        return expected

    def save(self, *args, **kwargs):
        # Automatically calculate if not manually provided
        if not self.expected_fitness_results or self.expected_fitness_results == {}:
            self.calculate_expected_results()
        super().save(*args, **kwargs)

class Swimming(models.Model):
    athlete = models.ForeignKey(AthleteInfo, on_delete=models.CASCADE, related_name='swimming_records')
    stroke = models.CharField(max_length=100)
    events = models.CharField(max_length=255)
    
    current_record = models.DurationField()
    previous_record = models.DurationField(blank=True, null=True)
    expected_record = models.DurationField(blank=True, null=True)
    swimming_goal = models.TextField(blank=True, null=True)
    
    # Split / Lap Tracking
    total_laps = models.PositiveIntegerField(default=1)
    lap_distance = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. 50m, 25m, 12.5m")
    splits_data = models.JSONField(default=list, blank=True, help_text="List of objects with lap_number, previous, current, expected")
    
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Swimming: {self.athlete.name} - {self.stroke}"

    def calculate_expected_record(self):
        """
        Calculation logic for duration:
        - If Previous > Current (improvement): Expected = Current - (Previous - Current)
        - If not or missing: Expected = Current * 0.95 (5% improvement)
        """
        if not self.current_record:
            return None
            
        if self.previous_record and self.previous_record > self.current_record:
            diff = self.previous_record - self.current_record
            expected = self.current_record - diff
        else:
            # 5% improvement calculation for durations
            total_seconds = self.current_record.total_seconds()
            expected_seconds = total_seconds * 0.95
            from datetime import timedelta
            expected = timedelta(seconds=expected_seconds)
            
        self.expected_record = expected
        return expected

    def save(self, *args, **kwargs):
        if not self.expected_record:
            self.calculate_expected_record()
        super().save(*args, **kwargs)

class Basketball(models.Model):
    athlete = models.ForeignKey(AthleteInfo, on_delete=models.CASCADE, related_name='basketball_records')
    position = models.CharField(max_length=100)
    vertical_jump = models.DecimalField(max_digits=5, decimal_places=2, help_text="Vertical leap in inches")
    
    shooting_stats = models.JSONField(default=dict, blank=True)
    performance_metrics = models.JSONField(default=dict, blank=True)
    current_game_high = models.PositiveIntegerField(help_text="Highest points in a single game")
    expected_performance = models.JSONField(default=dict, blank=True)
    
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Basketball: {self.athlete.name} - {self.position}"

class Football(models.Model):
    athlete = models.ForeignKey(AthleteInfo, on_delete=models.CASCADE, related_name='football_records')
    position = models.CharField(max_length=100)
    
    technical_stats = models.JSONField(default=dict, blank=True)
    physical_data = models.JSONField(default=dict, blank=True)
    match_impact = models.JSONField(default=dict, blank=True)
    expected_growth_trajectory = models.JSONField(default=dict, blank=True)
    
    recorded_at = models.DateTimeField(auto_now_add=True)

class CrossFit(models.Model):
    athlete = models.ForeignKey(AthleteInfo, on_delete=models.CASCADE, related_name='crossfit_records')
    level = models.CharField(max_length=100)
    
    strength_maxes = models.JSONField(default=dict, blank=True)
    benchmark_wods = models.JSONField(default=dict, blank=True)
    gymnastics_proficiency = models.JSONField(default=dict, blank=True)
    expected_pr_projection = models.JSONField(default=dict, blank=True)
    
    recorded_at = models.DateTimeField(auto_now_add=True)
