"""
Pain Log Adjustment Service
============================
Integrates pain log data into Performance Intelligence Center calculations.
Adjusts performance metrics based on recent pain levels to reflect real-world 
athletic performance impact.

The service:
1. Collects recent pain logs for an athlete
2. Calculates pain impact factor (0.0 - 1.0) based on pain severity & recency
3. Adjusts performance metrics, session ratings, and assessment scores accordingly
4. Provides pain context for reports and API responses
"""

from datetime import timedelta
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class PerformancePainAdjustmentService:
    """
    Calculates and applies pain-based performance adjustments.
    
    Pain Impact Calculation:
    - Recent high pain (level 7+) significantly reduces performance (up to 40%)
    - Moderate pain (level 4-6) has medium impact (up to 20%)
    - Low pain (level 1-3) has minimal impact (up to 5%)
    - Recency matters: pain from past 3 days has full impact, older pain decays
    """
    
    # Pain level severity thresholds
    PAIN_SEVERITY_HIGH = 7      # 7-10: Major impact
    PAIN_SEVERITY_MEDIUM = 4    # 4-6: Moderate impact  
    PAIN_SEVERITY_LOW = 1       # 1-3: Minor impact
    
    # Maximum performance reduction factors
    REDUCTION_HIGH = 0.40       # 40% reduction for high pain
    REDUCTION_MEDIUM = 0.20     # 20% reduction for medium pain
    REDUCTION_LOW = 0.05        # 5% reduction for low pain
    
    # Time windows (in days)
    RECENT_DAYS = 3             # Pain within this window has full impact
    
    @staticmethod
    def get_recent_pain_logs(athlete, days=3):
        """Get pain logs from the last N days."""
        from .models import PainLog
        cutoff_date = timezone.now().date() - timedelta(days=days)
        return athlete.pain_logs.filter(date__gte=cutoff_date).order_by('-date')
    
    @staticmethod
    def calculate_pain_impact_factor(athlete, reference_date=None):
        """
        Calculate overall pain impact factor (0.0 = no pain, 1.0 = severe pain).
        
        Returns dict with:
        {
            'impact_factor': 0.0-1.0,  # Multiplier for performance reduction
            'reduction_factor': 0.0-1.0,  # What to multiply performance by (1 - impact_factor)
            'max_pain_level': int,  # Highest pain level in recent logs
            'avg_pain_level': float,  # Average pain level
            'pain_logs_count': int,  # Number of recent pain logs
            'affected_body_parts': list,  # Body parts with pain
            'recommendation': str,  # Coaching recommendation
        }
        """
        if reference_date is None:
            reference_date = timezone.now().date()
        
        recent_pains = PerformancePainAdjustmentService.get_recent_pain_logs(
            athlete, days=PerformancePainAdjustmentService.RECENT_DAYS
        )
        
        if not recent_pains.exists():
            return {
                'impact_factor': 0.0,
                'reduction_factor': 1.0,
                'max_pain_level': 0,
                'avg_pain_level': 0.0,
                'pain_logs_count': 0,
                'affected_body_parts': [],
                'recommendation': 'No recent pain - Athlete ready for full training',
            }
        
        pain_levels = list(recent_pains.values_list('pain_level', flat=True))
        max_pain = max(pain_levels) if pain_levels else 0
        avg_pain = sum(pain_levels) / len(pain_levels) if pain_levels else 0
        
        body_parts = list(set(recent_pains.values_list('body_part', flat=True)))
        
        # Calculate individual log impacts with severity weighting and recency decay
        individual_impacts = []
        for pain in recent_pains:
            days_ago = (reference_date - pain.date).days
            if days_ago < 0:
                days_ago = 0
            
            # Full impact for today (0 days), linear decay to 0 over RECENT_DAYS
            recency_factor = max(0.0, 1.0 - (days_ago / PerformancePainAdjustmentService.RECENT_DAYS))
            
            # Severity factor (non-linear interpolation for realistic performance impact)
            if pain.pain_level >= PerformancePainAdjustmentService.PAIN_SEVERITY_HIGH:
                # High Pain (7-10): 20% to 40% reduction
                pain_ratio = min(1.0, (pain.pain_level - 7) / 3.0)
                severity_impact = PerformancePainAdjustmentService.REDUCTION_HIGH * (0.5 + 0.5 * pain_ratio)
            elif pain.pain_level >= PerformancePainAdjustmentService.PAIN_SEVERITY_MEDIUM:
                # Medium Pain (4-6): 5% to 20% reduction
                pain_ratio = (pain.pain_level - 4) / 2.0
                severity_impact = PerformancePainAdjustmentService.REDUCTION_MEDIUM * (0.25 + 0.75 * pain_ratio)
            elif pain.pain_level >= PerformancePainAdjustmentService.PAIN_SEVERITY_LOW:
                # Low Pain (1-3): 1% to 5% reduction
                pain_ratio = (pain.pain_level - 1) / 2.0
                severity_impact = PerformancePainAdjustmentService.REDUCTION_LOW * (0.2 + 0.8 * pain_ratio)
            else:
                severity_impact = 0.0
            
            individual_impacts.append(severity_impact * recency_factor)
        
        # Compounding Dominance Model: Peak pain dominates, secondary symptoms compound by 15%
        if individual_impacts:
            max_impact = max(individual_impacts)
            secondary_sum = sum(val for val in individual_impacts if val != max_impact)
            # Handle duplicate max values if any
            max_count = individual_impacts.count(max_impact)
            if max_count > 1:
                secondary_sum += max_impact * (max_count - 1)
            
            # Capped at 50% max performance reduction for an athlete cleared to train
            overall_impact = min(0.50, max_impact + 0.15 * secondary_sum)
        else:
            overall_impact = 0.0
        
        # Generate recommendation
        if max_pain >= 8:
            recommendation = 'Significant pain detected - Recommend rest and medical evaluation'
        elif max_pain >= 7:
            recommendation = 'High pain level - Modify training intensity and focus on affected areas'
        elif max_pain >= 5:
            recommendation = 'Moderate pain - Reduce volume, maintain technique work'
        elif max_pain >= 3:
            recommendation = 'Minor pain - Continue normal training with monitoring'
        else:
            recommendation = 'Minimal pain - Athlete cleared for full training'
        
        return {
            'impact_factor': round(overall_impact, 3),
            'reduction_factor': round(1.0 - overall_impact, 3),
            'max_pain_level': max_pain,
            'avg_pain_level': round(avg_pain, 1),
            'pain_logs_count': recent_pains.count(),
            'affected_body_parts': body_parts,
            'recommendation': recommendation,
        }
    
    @staticmethod
    def adjust_performance_metric(value, pain_adjustment):
        """
        Apply pain adjustment to a performance metric.
        
        Args:
            value: The original metric value (int or float)
            pain_adjustment: dict from calculate_pain_impact_factor()
            
        Returns:
            Adjusted metric value (same type as input)
        """
        if value is None or not isinstance(value, (int, float)):
            return value
        
        reduction_factor = pain_adjustment.get('reduction_factor', 1.0)
        adjusted = value * reduction_factor
        
        # Preserve type
        if isinstance(value, int):
            return int(round(adjusted))
        return round(adjusted, 2)
    
    @staticmethod
    def adjust_session_performance_rating(rating, pain_adjustment):
        """
        Adjust session performance rating (1-10 scale) based on pain.
        
        Args:
            rating: Original performance rating (1-10)
            pain_adjustment: dict from calculate_pain_impact_factor()
            
        Returns:
            Adjusted rating (1-10, capped at minimum of 1)
        """
        if rating is None or not isinstance(rating, (int, float)):
            return rating
        
        reduction = pain_adjustment.get('impact_factor', 0.0)
        # Calculate point deduction from the 10-point scale
        points_lost = 9 * reduction  # Max 9 points lost on 10-point scale
        adjusted = max(1, rating - points_lost)
        
        return round(adjusted, 1)
    
    @staticmethod
    def adjust_assessment_metrics(categories_data, pain_adjustment):
        """
        Adjust assessment metrics (mobility, strength, etc.) based on pain.
        
        Args:
            categories_data: Output from AssessmentInsightsService.parse_for_api()
            pain_adjustment: dict from calculate_pain_impact_factor()
            
        Returns:
            Modified categories_data with adjusted metrics and pain context
        """
        if not categories_data or not isinstance(categories_data, list):
            return categories_data
        
        reduction_factor = pain_adjustment.get('reduction_factor', 1.0)
        
        # Adjust all current/predicted metrics
        for category in categories_data:
            if 'metrics' in category and isinstance(category['metrics'], list):
                for metric in category['metrics']:
                    # Adjust current value
                    if metric.get('current') is not None:
                        metric['current_adjusted'] = round(
                            metric['current'] * reduction_factor, 2
                        )
                        metric['pain_adjusted'] = True
                    
                    # Adjust predicted value
                    if metric.get('predicted') is not None:
                        metric['predicted_adjusted'] = round(
                            metric['predicted'] * reduction_factor, 2
                        )
                    
                    # Add adjustment note if significant pain
                    if pain_adjustment.get('impact_factor', 0) > 0.1:
                        metric['adjustment_note'] = (
                            f"Current pain reduces this metric by {pain_adjustment['impact_factor']*100:.0f}%"
                        )
        
        return categories_data
    
    @staticmethod
    def get_performance_context(athlete):
        """
        Get comprehensive performance context including pain impact.
        
        Returns a dict suitable for API responses and reports with:
        - Pain data
        - Performance adjustments
        - Coaching recommendations
        """
        pain_data = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)
        
        return {
            'pain_metrics': pain_data,
            'performance_notes': [
                f"Recent pain logs: {pain_data['pain_logs_count']}",
                f"Maximum pain level: {pain_data['max_pain_level']}/10",
                f"Average pain level: {pain_data['avg_pain_level']}/10",
                f"Affected areas: {', '.join(pain_data['affected_body_parts']) or 'None'}",
                f"Performance impact: {pain_data['impact_factor']*100:.0f}% reduction",
                f"Recommendation: {pain_data['recommendation']}",
            ] if pain_data['pain_logs_count'] > 0 else [],
        }
    
    @staticmethod
    def adjust_predicted_performance(fitness_instance, pain_adjustment):
        """
        Apply pain adjustment to predicted/expected fitness results.
        Pain may reduce expected improvement trajectories.
        
        Args:
            fitness_instance: Fitness model instance
            pain_adjustment: dict from calculate_pain_impact_factor()
            
        Returns:
            Adjusted expected_fitness_results dict
        """
        if not fitness_instance.expected_fitness_results:
            return {}
        
        expected = fitness_instance.expected_fitness_results.copy() if isinstance(
            fitness_instance.expected_fitness_results, dict
        ) else {}
        
        adjusted = {}
        reduction_factor = pain_adjustment.get('reduction_factor', 1.0)
        
        for key, value in expected.items():
            if isinstance(value, dict) and value.get('value') is not None:
                adjusted[key] = value.copy()
                adjusted[key]['value'] = round(
                    adjusted[key]['value'] * reduction_factor, 2
                )
                adjusted[key]['pain_adjusted'] = True
            elif isinstance(value, (int, float)):
                adjusted[key] = round(value * reduction_factor, 2)
            else:
                adjusted[key] = value
        
        return adjusted

    @staticmethod
    def calculate_biometric_readiness(athlete, reference_date=None):
        """
        Calculate subjective & objective biometric readiness factor (0.0 = fully recovered, 1.0 = highly fatigued/deprived).
        
        Evaluates last 3 days (acute) vs last 14 days (chronic) for HRV and RHR,
        and direct subjective limits for sleep, fatigue, and soreness.
        """
        from django.utils import timezone
        from datetime import timedelta

        if reference_date is None:
            reference_date = timezone.now().date()
            
        # Get attendances in last 14 days
        cutoff_date = reference_date - timedelta(days=14)
        attendances = list(athlete.attendance_records.filter(date__gte=cutoff_date, date__lte=reference_date).order_by('-date'))
        
        if not attendances:
            return {
                'biometric_impact': 0.0,
                'biometric_reduction_factor': 1.0,
                'hrv_impact': 0.0,
                'rhr_impact': 0.0,
                'sleep_impact': 0.0,
                'fatigue_impact': 0.0,
                'soreness_impact': 0.0,
                'acute_hrv': 0.0,
                'chronic_hrv': 0.0,
                'acute_rhr': 0.0,
                'chronic_rhr': 0.0,
                'acute_sleep': 8.0,
                'acute_fatigue': 0.0,
                'acute_soreness': 0.0,
                'interpretation': 'Optimal recovery state'
            }
            
        acute_att = attendances[:3]
        chronic_att = attendances
        
        # 1. HRV drop
        hrv_acute_list = [a.hrv for a in acute_att if a.hrv is not None]
        hrv_chronic_list = [a.hrv for a in chronic_att if a.hrv is not None]
        avg_hrv_acute = sum(hrv_acute_list) / len(hrv_acute_list) if hrv_acute_list else 0.0
        avg_hrv_chronic = sum(hrv_chronic_list) / len(hrv_chronic_list) if hrv_chronic_list else 0.0
        
        hrv_impact = 0.0
        if avg_hrv_chronic > 0 and avg_hrv_acute < avg_hrv_chronic:
            hrv_drop_pct = (avg_hrv_chronic - avg_hrv_acute) / avg_hrv_chronic
            if hrv_drop_pct > 0.10: # >10% drop
                hrv_impact = min(0.15, hrv_drop_pct * 0.5)
                
        # 2. RHR rise
        rhr_acute_list = [a.resting_heart_rate for a in acute_att if a.resting_heart_rate is not None]
        rhr_chronic_list = [a.resting_heart_rate for a in chronic_att if a.resting_heart_rate is not None]
        avg_rhr_acute = sum(rhr_acute_list) / len(rhr_acute_list) if rhr_acute_list else 0.0
        avg_rhr_chronic = sum(rhr_chronic_list) / len(rhr_chronic_list) if rhr_chronic_list else 0.0
        
        rhr_impact = 0.0
        if avg_rhr_chronic > 0 and avg_rhr_acute > avg_rhr_chronic + 5:
            rhr_rise = avg_rhr_acute - (avg_rhr_chronic + 5)
            rhr_impact = min(0.10, rhr_rise * 0.02)
            
        # 3. Sleep restriction
        sleep_acute_list = [float(a.sleep_hours) for a in acute_att if a.sleep_hours is not None]
        avg_sleep_acute = sum(sleep_acute_list) / len(sleep_acute_list) if sleep_acute_list else 8.0
        
        sleep_impact = 0.0
        if avg_sleep_acute < 7.0:
            sleep_deficit = 7.0 - avg_sleep_acute
            sleep_impact = min(0.12, sleep_deficit * 0.03)
            
        # 4. Fatigue spike
        fatigue_acute_list = [a.fatigue_score for a in acute_att if a.fatigue_score is not None]
        avg_fatigue_acute = sum(fatigue_acute_list) / len(fatigue_acute_list) if fatigue_acute_list else 0.0
        
        fatigue_impact = 0.0
        if avg_fatigue_acute > 6.0:
            fatigue_impact = min(0.10, (avg_fatigue_acute - 6.0) * 0.025)
            
        # 5. Soreness spike
        soreness_acute_list = [a.muscle_soreness for a in acute_att if a.muscle_soreness is not None]
        avg_soreness_acute = sum(soreness_acute_list) / len(soreness_acute_list) if soreness_acute_list else 0.0
        
        soreness_impact = 0.0
        if avg_soreness_acute > 6.0:
            soreness_impact = min(0.08, (avg_soreness_acute - 6.0) * 0.02)
            
        # Sum of impacts capped at 25% max autonomic/biometric performance drop
        biometric_impact = min(0.25, hrv_impact + rhr_impact + sleep_impact + fatigue_impact + soreness_impact)
        
        interpretation = (
            'Severe sympathetic strain - Limit load significantly' if biometric_impact > 0.18
            else 'Moderate fatigue - Auto-regulate volume' if biometric_impact > 0.08
            else 'Mild autonomic stress - Monitor recovery' if biometric_impact > 0.03
            else 'Optimal recovery state'
        )
        
        return {
            'biometric_impact': round(biometric_impact, 3),
            'biometric_reduction_factor': round(1.0 - biometric_impact, 3),
            'hrv_impact': round(hrv_impact, 3),
            'rhr_impact': round(rhr_impact, 3),
            'sleep_impact': round(sleep_impact, 3),
            'fatigue_impact': round(fatigue_impact, 3),
            'soreness_impact': round(soreness_impact, 3),
            'acute_hrv': round(avg_hrv_acute, 1),
            'chronic_hrv': round(avg_hrv_chronic, 1),
            'acute_rhr': round(avg_rhr_acute, 1),
            'chronic_rhr': round(avg_rhr_chronic, 1),
            'acute_sleep': round(avg_sleep_acute, 1),
            'acute_fatigue': round(avg_fatigue_acute, 1),
            'acute_soreness': round(avg_soreness_acute, 1),
            'interpretation': interpretation
        }
