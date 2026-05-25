from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from athletes.models import AthleteInfo, PainLog, InjuryRecord, AttendanceRecord
from athletes.pain_adjustment_service import PerformancePainAdjustmentService
from athletes.views import AthleteInfoViewSet
from rest_framework.test import APIRequestFactory

class PerformancePainAdjustmentTests(TestCase):
    def setUp(self):
        self.athlete = AthleteInfo.objects.create(
            name="Alexander Karelin",
            age=26,
            gender="M",
            height=191.0,
            weight=130.0,
            body_type="Mesomorph"
        )

    def test_zero_pain_impact(self):
        """Assert that an athlete with no recent pain logs has 0.0 impact factor and 1.0 reduction factor."""
        adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(self.athlete)
        self.assertEqual(adjustment['impact_factor'], 0.0)
        self.assertEqual(adjustment['reduction_factor'], 1.0)
        self.assertEqual(adjustment['max_pain_level'], 0)

    def test_single_high_pain_impact(self):
        """Assert that a single active high pain log results in correct severity weighting and recency calculation."""
        PainLog.objects.create(
            athlete=self.athlete,
            body_part="Left Shoulder",
            pain_level=8,
            pain_type="Sharp",
            date=timezone.now().date()
        )
        adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(self.athlete)
        # Severity calculation for High Pain 8: 
        # pain_ratio = (8 - 7)/3 = 0.3333
        # W_j = 0.40 * (0.5 + 0.5 * 0.3333) = 0.2667
        # Since date is today, recency is 1.0. Max impact = 0.267
        self.assertAlmostEqual(adjustment['impact_factor'], 0.267, places=3)
        self.assertAlmostEqual(adjustment['reduction_factor'], 0.733, places=3)
        self.assertEqual(adjustment['max_pain_level'], 8)

    def test_compounding_dominance_multiple_pain_logs(self):
        """Assert that multiple pain logs compound secondary values by 15% instead of averaging them down."""
        # 1. High pain log today (8/10) -> max impact is W_1 * 1.0 = 0.2667
        PainLog.objects.create(
            athlete=self.athlete,
            body_part="Left Knee",
            pain_level=8,
            pain_type="Sharp",
            date=timezone.now().date()
        )
        # 2. Medium pain log today (5/10) -> W_2 = 0.20 * (0.25 + 0.75 * 0.5) = 0.125
        PainLog.objects.create(
            athlete=self.athlete,
            body_part="Right Knee",
            pain_level=5,
            pain_type="Aching",
            date=timezone.now().date()
        )
        
        # Max impact: 0.2667
        # Secondary: 0.125
        # Compound: min(0.50, 0.2667 + 0.15 * 0.125) = 0.2667 + 0.01875 = 0.28545 -> round to 3 decimals: 0.285
        adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(self.athlete)
        self.assertAlmostEqual(adjustment['impact_factor'], 0.285, places=3)
        self.assertEqual(adjustment['max_pain_level'], 8)
        self.assertEqual(adjustment['pain_logs_count'], 2)


class BALRInjuryRiskFallbackTests(TestCase):
    def setUp(self):
        self.athlete = AthleteInfo.objects.create(
            name="Sergey Bubka",
            age=28,
            gender="M",
            height=183.0,
            weight=80.0,
            body_type="Ectomorph"
        )
        
    def test_baseline_risk(self):
        """An athlete with optimal biometrics, no pain, and no injuries should have baseline optimal score."""
        # We need a viewset instance
        viewset = AthleteInfoViewSet()
        
        # Simulate generate_injury_prediction internally
        # Retrieve dependencies
        injuries = self.athlete.injury_records.all()
        attendances = self.athlete.attendance_records.order_by('-date')[:14]
        
        # Mock calculation variables
        base_score = 10
        active_count = injuries.filter(is_active=True).count()
        base_score += active_count * 25
        
        # Pain impact
        pain_adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(self.athlete)
        base_score += pain_adjustment['impact_factor'] * 80
        
        self.assertEqual(base_score, 10.0)

    def test_active_injury_impact(self):
        """Active injuries and pain symptoms must drive the risk score higher."""
        InjuryRecord.objects.create(
            athlete=self.athlete,
            injury_type="Hamstring Strain",
            severity="Moderate",
            is_active=True,
            start_date=timezone.now().date() - timedelta(days=5)
        )
        
        # Add a pain log of 7
        PainLog.objects.create(
            athlete=self.athlete,
            body_part="Right Hamstring",
            pain_level=7,
            pain_type="Dull",
            date=timezone.now().date()
        )
        
        # Retrieve and calculate
        injuries = self.athlete.injury_records.all()
        active_count = injuries.filter(is_active=True).count()
        
        base_score = 10
        base_score += active_count * 25 # +25 points
        
        pain_adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(self.athlete)
        # Severity for 7 High Pain:
        # ratio = 0.0 -> W_j = 0.40 * 0.5 = 0.20. today -> recency 1.0. impact = 0.20
        pain_points = pain_adjustment['impact_factor'] * 80 # +16 points
        base_score += pain_points
        
        self.assertEqual(active_count, 1)
        self.assertEqual(pain_adjustment['impact_factor'], 0.20)
        self.assertEqual(base_score, 51.0) # 10 (base) + 25 (active) + 16 (pain)


class BiometricReadinessTests(TestCase):
    """
    Unit tests for PerformancePainAdjustmentService.calculate_biometric_readiness().
    Verifies that each biometric marker (HRV, RHR, Sleep, Fatigue, Soreness)
    produces correct individual and combined impact factors.
    """
    def setUp(self):
        self.athlete = AthleteInfo.objects.create(
            name="Yusuf Dibaba",
            age=25,
            gender="M",
            height=175.0,
            weight=70.0,
            body_type="Ectomorph"
        )

    def _create_attendance(self, days_ago, hrv=65, rhr=55, sleep=8.0, fatigue=3, soreness=3):
        """Helper to create a backdated attendance record."""
        return AttendanceRecord.objects.create(
            athlete=self.athlete,
            date=timezone.now().date() - timedelta(days=days_ago),
            attended=True,
            hrv=hrv,
            resting_heart_rate=rhr,
            sleep_hours=sleep,
            fatigue_score=fatigue,
            muscle_soreness=soreness,
            performance_rating=8
        )

    def test_zero_impact_with_optimal_biometrics(self):
        """An athlete with optimal HRV, RHR, sleep, fatigue, and soreness should have 0.0 biometric impact."""
        # Create 14 days of healthy attendance with no flags
        for day in range(14):
            self._create_attendance(days_ago=day, hrv=65, rhr=55, sleep=8.0, fatigue=3, soreness=3)

        result = PerformancePainAdjustmentService.calculate_biometric_readiness(self.athlete)
        self.assertEqual(result['biometric_impact'], 0.0)
        self.assertEqual(result['biometric_reduction_factor'], 1.0)
        self.assertEqual(result['interpretation'], 'Optimal recovery state')

    def test_hrv_drop_triggers_impact(self):
        """
        A >10% HRV drop (acute vs chronic) must add a non-zero HRV impact.
        Chronic HRV = 70ms (14-day avg), Acute HRV = 50ms (3-day avg) → 28.6% drop → impact triggered.
        """
        # 11 days of chronic HRV at 70
        for day in range(3, 14):
            self._create_attendance(days_ago=day, hrv=70)
        # 3 acute days at 50 (28.6% drop from chronic)
        for day in range(0, 3):
            self._create_attendance(days_ago=day, hrv=50)

        result = PerformancePainAdjustmentService.calculate_biometric_readiness(self.athlete)
        # Chronic HRV = avg over all 14 records = (70*11 + 50*3) / 14 = (770 + 150) / 14 = 65.714ms
        # Acute HRV = 50ms
        # drop_pct = (65.714 - 50) / 65.714 = 0.2391 → hrv_impact = min(0.15, 0.2391 * 0.5) = 0.120
        self.assertGreater(result['hrv_impact'], 0.0)
        self.assertAlmostEqual(result['hrv_impact'], 0.120, places=3)
        self.assertGreater(result['biometric_impact'], 0.0)
        self.assertEqual(result['acute_hrv'], 50.0)
        self.assertEqual(result['chronic_hrv'], round((70*11 + 50*3) / 14, 1))

    def test_rhr_elevation_triggers_impact(self):
        """
        An RHR rise of >5 bpm above the chronic baseline must trigger RHR impact.
        Chronic RHR = 55 bpm, Acute RHR = 70 bpm → rise of 15 above baseline, threshold 5 → rhr_rise = 10 bpm.
        """
        for day in range(3, 14):
            self._create_attendance(days_ago=day, rhr=55)
        for day in range(0, 3):
            self._create_attendance(days_ago=day, rhr=70)

        result = PerformancePainAdjustmentService.calculate_biometric_readiness(self.athlete)
        # rhr_rise = 70 - (55 + 5) = 10 → rhr_impact = min(0.10, 10 * 0.02) = min(0.10, 0.20) = 0.10
        self.assertAlmostEqual(result['rhr_impact'], 0.10, places=3)
        self.assertEqual(result['acute_rhr'], 70.0)

    def test_sleep_restriction_impact(self):
        """
        An average acute sleep of 5.5h should trigger a sleep_impact.
        sleep_deficit = 7.0 - 5.5 = 1.5 → sleep_impact = min(0.12, 1.5 * 0.03) = 0.045
        """
        for day in range(0, 3):
            self._create_attendance(days_ago=day, sleep=5.5)
        # Add some chronic data to have valid attendance
        for day in range(3, 8):
            self._create_attendance(days_ago=day, sleep=8.0)

        result = PerformancePainAdjustmentService.calculate_biometric_readiness(self.athlete)
        self.assertAlmostEqual(result['sleep_impact'], 0.045, places=3)
        self.assertEqual(result['acute_sleep'], 5.5)

    def test_high_fatigue_impact(self):
        """
        Average fatigue of 8.5 for last 3 days → fatigue_impact = min(0.10, (8.5 - 6.0) * 0.025) = 0.0625.
        """
        for day in range(0, 3):
            self._create_attendance(days_ago=day, fatigue=8)
        # avg = 8.0, 8.0 - 6.0 = 2.0, impact = min(0.10, 2.0 * 0.025) = 0.05
        for day in range(3, 8):
            self._create_attendance(days_ago=day, fatigue=3)

        result = PerformancePainAdjustmentService.calculate_biometric_readiness(self.athlete)
        # avg acute fatigue = 8.0 → impact = min(0.10, (8.0-6.0)*0.025) = 0.05
        self.assertAlmostEqual(result['fatigue_impact'], 0.05, places=3)
        self.assertEqual(result['acute_fatigue'], 8.0)

    def test_high_soreness_impact(self):
        """
        Average soreness of 8.0 for last 3 days → soreness_impact = min(0.08, (8.0 - 6.0) * 0.02) = 0.04.
        """
        for day in range(0, 3):
            self._create_attendance(days_ago=day, soreness=8)
        for day in range(3, 8):
            self._create_attendance(days_ago=day, soreness=3)

        result = PerformancePainAdjustmentService.calculate_biometric_readiness(self.athlete)
        self.assertAlmostEqual(result['soreness_impact'], 0.04, places=3)
        self.assertEqual(result['acute_soreness'], 8.0)

    def test_combined_pain_and_biometric_capacity_multiplier(self):
        """
        Full integration test: combined capacity reduction from pain AND biometric factors
        must match (1 - I_pain) x (1 - I_bio) formula exactly.
        """
        # Seed biometric stress: HRV drop
        for day in range(3, 14):
            self._create_attendance(days_ago=day, hrv=70)
        for day in range(0, 3):
            self._create_attendance(days_ago=day, hrv=50)

        # Add a medium pain log
        PainLog.objects.create(
            athlete=self.athlete,
            body_part="Left Quad",
            pain_level=5,
            pain_type="Aching",
            date=timezone.now().date()
        )

        pain_adj = PerformancePainAdjustmentService.calculate_pain_impact_factor(self.athlete)
        bio_adj = PerformancePainAdjustmentService.calculate_biometric_readiness(self.athlete)

        pain_impact = pain_adj['impact_factor']
        bio_impact = bio_adj['biometric_impact']

        expected_combined_rf = round((1.0 - pain_impact) * (1.0 - bio_impact), 3)
        actual_combined_rf = round(pain_adj['reduction_factor'] * bio_adj['biometric_reduction_factor'], 3)

        self.assertAlmostEqual(expected_combined_rf, actual_combined_rf, places=3)
        self.assertGreater(pain_impact, 0.0)
        self.assertGreater(bio_impact, 0.0)
        # Combined impact must be greater than either alone (multiplicative compounding)
        combined_impact_pct = (1.0 - expected_combined_rf) * 100
        self.assertGreater(combined_impact_pct, pain_impact * 100)
        self.assertGreater(combined_impact_pct, bio_impact * 100)
