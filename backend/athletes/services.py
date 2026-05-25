import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class PredictorService:
    @staticmethod
    def predict_business_revenue(owner_instance):
        from .models import Owner
        
        hist_data = Owner.objects.all().order_by('created_at')
        if hist_data.count() < 2:
            return None
        features = []
        targets = []
        for obj in hist_data:
            features.append([float(obj.athlete_numbers), float(obj.conversion_rate)])
            targets.append(float(obj.total_income))
        X = np.array(features)
        y = np.array(targets)
        try:
            model = LinearRegression()
            model.fit(X, y)
            current_X = np.array([[float(owner_instance.athlete_numbers), float(owner_instance.conversion_rate)]])
            return model.predict(current_X)[0]
        except Exception as e:
            logger.error(f"Error predicting business revenue: {e}")
            return None

    @staticmethod
    def _get_attendance_percentage(athlete_instance):
        from .models import AttendanceRecord
        records = AttendanceRecord.objects.filter(athlete=athlete_instance)
        if not records.exists():
            return 100.0
        attended = records.filter(attended=True).count()
        return (attended / records.count()) * 100.0

    @staticmethod
    def predict_athlete_swimming_record(swimming_instance):
        from .models import Swimming
        attendance_perc = PredictorService._get_attendance_percentage(swimming_instance.athlete)
        hist_data = Swimming.objects.filter(
            athlete=swimming_instance.athlete,
            stroke=swimming_instance.stroke,
            events=swimming_instance.events
        ).order_by('recorded_at')
        if hist_data.count() < 1:
            return None
        if hist_data.count() == 1:
            current_secs = swimming_instance.current_record.total_seconds()
            improvement_factor = 0.02 * (attendance_perc / 100.0)
            return timedelta(seconds=max(1.0, current_secs * (1 - improvement_factor)))
        features = []
        targets = []
        for obj in hist_data:
            if obj.previous_record and obj.current_record:
                features.append([attendance_perc, obj.previous_record.total_seconds()])
                targets.append(obj.current_record.total_seconds())
        if len(features) < 1:
            current_secs = swimming_instance.current_record.total_seconds()
            improvement_factor = 0.02 * (attendance_perc / 100.0)
            return timedelta(seconds=max(1.0, current_secs * (1 - improvement_factor)))
        X = np.array(features)
        y = np.array(targets)
        try:
            model = LinearRegression()
            model.fit(X, y)
            current_features = np.array([[attendance_perc, swimming_instance.current_record.total_seconds()]])
            pred_seconds = max(1.0, model.predict(current_features)[0])
            return timedelta(seconds=pred_seconds)
        except Exception as e:
            logger.error(f"Error predicting swimming record: {e}")
            return None

    @staticmethod
    def predict_json_fitness_results(fitness_instance):
        try:
            prev = fitness_instance.previous_fitness_tests or {}
            curr = fitness_instance.current_fitness_tests or {}
            predicted = {}
            attendance_perc = PredictorService._get_attendance_percentage(fitness_instance.athlete)
            attendance_impact = attendance_perc / 100.0
            for k, curr_v in curr.items():
                if isinstance(curr_v, dict) and curr_v.get('value') is not None:
                    prev_v = prev.get(k) if isinstance(prev.get(k), dict) else {}
                    curr_weight = curr_v.get('value')
                    curr_reps = curr_v.get('reps')
                    unit = curr_v.get('unit')
                    is_rep_count = curr_v.get('measure') == 'rep_count' or unit == 'reps'
                    is_time_seconds = curr_v.get('measure') == 'time_seconds' or unit == 'sec'

                    if isinstance(curr_weight, (int, float)):
                        prev_weight = prev_v.get('value') if isinstance(prev_v.get('value'), (int, float)) else None
                        if prev_weight is not None:
                            delta = curr_weight - prev_weight
                            predicted_weight = curr_weight + (delta * attendance_impact)
                        else:
                            factor = 1 - (0.05 * attendance_impact) if is_time_seconds else 1 + (0.05 * attendance_impact)
                            predicted_weight = curr_weight * factor

                        if is_rep_count:
                            predicted_weight = round(predicted_weight)
                        if is_time_seconds:
                            predicted_weight = max(1, round(predicted_weight))

                        prev_reps = prev_v.get('reps') if isinstance(prev_v.get('reps'), int) else None
                        if isinstance(curr_reps, int):
                            if prev_reps is not None:
                                predicted_reps = int(round(curr_reps + ((curr_reps - prev_reps) * attendance_impact)))
                            else:
                                predicted_reps = curr_reps + 1
                        else:
                            predicted_reps = None

                        predicted[k] = {
                            'value': predicted_weight if is_rep_count else round(predicted_weight, 2),
                            'reps': predicted_reps,
                            'unit': unit or None,
                            **({'measure': curr_v.get('measure')} if curr_v.get('measure') else {}),
                            **({'group': curr_v.get('group')} if curr_v.get('group') else {})
                        }
                    else:
                        predicted[k] = curr_v
                elif isinstance(curr_v, (int, float)):
                    prev_v = prev.get(k)
                    if prev_v is not None and isinstance(prev_v, (int, float)):
                        delta = curr_v - prev_v
                        predicted[k] = curr_v + (delta * attendance_impact)
                    else:
                        predicted[k] = curr_v * (1 + (0.05 * attendance_impact))
                else:
                    predicted[k] = curr_v
            return predicted
        except Exception as e:
            logger.error(f"Error predicting fitness results: {e}")
            return {}


# ════════════════════════════════════════════════════════════════════════════
#  Assessment Insights Service
# ════════════════════════════════════════════════════════════════════════════

class AssessmentInsightsService:
    """
    Parses namespaced assessment JSON keys stored in Fitness.current_fitness_tests,
    applies published norms, auto-calculates derived metrics, and returns
    structured per-category insight objects for charts and the PDF report.

    Namespace convention:  prefix__snake_metric
      mobility__    – Mobility Assessments
      plyometric__  – Plyometric & Power
      strength__    – Strength Assessments
      endurance__   – Muscle Endurance
      aerobic__     – Aerobic & Cardiovascular
      speed__       – Speed & Power Endurance
    """

    NORMS = {
        # Mobility
        'mobility__fms_score':               {'good': 17, 'pass': 14, 'unit': '/21',       'higher_better': True,
                                              'note': 'Score >=14 = minimal injury risk; 3 = perfect on any subtest'},
        'mobility__prone_shoulder_flex_deg': {'good': 170,'pass': 160,'unit': 'deg',        'higher_better': True},
        'mobility__hip_rom_deg':             {'good': 90, 'pass': 75, 'unit': 'deg',        'higher_better': True},
        # Plyometric
        'plyometric__squat_jump_cm':         {'good': 40, 'pass': 30, 'unit': 'cm',         'higher_better': True,
                                              'note': 'Compare to position norms or Z-score'},
        'plyometric__cmj_cm':                {'good': 45, 'pass': 35, 'unit': 'cm',         'higher_better': True},
        'plyometric__depth_jump_cm':         {'good': 40, 'pass': 30, 'unit': 'cm',         'higher_better': True},
        'plyometric__anaerobic_power_w':     {'good': 800,'pass': 600,'unit': 'W',          'higher_better': True,
                                              'note': '6-sec maximal cycling sprint'},
        # Strength
        'strength__1rm_back_squat_kg':       {'good': None,'pass': None,'unit': 'kg',       'higher_better': True,
                                              'note': 'Youth norm: 1.5× body mass'},
        'strength__1rm_bench_press_kg':      {'good': None,'pass': None,'unit': 'kg',       'higher_better': True},
        'strength__1rm_pull_up_kg':          {'good': None,'pass': None,'unit': 'kg',       'higher_better': True},
        'strength__snatch_pct_bw':           {'good': 90, 'pass': 80, 'unit': '% BW',      'higher_better': True,
                                              'note': 'Age 16 norm: 80-90% body mass'},
        'strength__clean_pct_bw':            {'good': 110,'pass': 100,'unit': '% BW',      'higher_better': True,
                                              'note': 'Age 16 norm: 100-110% body mass'},
        # Endurance
        'endurance__6test_battery_score':    {'good': 24, 'pass': 18, 'unit': '/30',        'higher_better': True,
                                              'note': 'Score >=18 required before barbell training'},
        'endurance__mcgill_back_ext_s':      {'good': 150,'pass': 120,'unit': 's',          'higher_better': True,
                                              'note': 'Elite >=150s; Required >=120s'},
        'endurance__mcgill_flexor_hold_s':   {'good': 150,'pass': 120,'unit': 's',          'higher_better': True},
        'endurance__mcgill_side_plank_s':    {'good': 90, 'pass': 60, 'unit': 's',          'higher_better': True,
                                              'note': 'Target up to 90s; R:L ratio within 0.05 of 1.0'},
        # Aerobic
        'aerobic__mas_kmh':                  {'good': 18, 'pass': 14, 'unit': 'km/h',       'higher_better': True,
                                              'note': 'VO2max = 3.5 x MAS'},
        'aerobic__vo2max_ml_kg_min':         {'good': 55, 'pass': 45, 'unit': 'ml/kg/min', 'higher_better': True},
        'aerobic__yoyo_level':               {'good': 17, 'pass': 13, 'unit': 'level',      'higher_better': True},
        'aerobic__hrr_bpm_drop':             {'good': 25, 'pass': 15, 'unit': 'bpm',        'higher_better': True,
                                              'note': 'HR drop 1 min post-exercise; higher = better recovery'},
        # Speed
        'speed__10m_sprint_s':               {'good': 1.70,'pass': 1.90,'unit': 's',        'higher_better': False,
                                              'note': 'Lower time = better acceleration'},
        'speed__20m_sprint_s':               {'good': 2.80,'pass': 3.10,'unit': 's',        'higher_better': False},
        'speed__wingate_peak_power_w':       {'good': 900, 'pass': 650,'unit': 'W',         'higher_better': True,
                                              'note': '30-sec Wingate gold standard for anaerobic capacity'},
        'speed__fatigue_index_pct':          {'good': 15, 'pass': 20, 'unit': '%',          'higher_better': False,
                                              'note': 'High-level target: Fatigue Index < 20%'},
    }

    CATEGORIES = {
        'mobility':   {'label': 'Mobility Assessments',     'color': '#4e73df', 'icon': 'bi-arrows-move'},
        'plyometric': {'label': 'Plyometric & Power',        'color': '#1cc88a', 'icon': 'bi-lightning-charge'},
        'strength':   {'label': 'Strength Assessments',      'color': '#e74a3b', 'icon': 'bi-bar-chart-fill'},
        'endurance':  {'label': 'Muscle Endurance',          'color': '#f6c23e', 'icon': 'bi-activity'},
        'aerobic':    {'label': 'Aerobic & Cardiovascular',  'color': '#36b9cc', 'icon': 'bi-heart-pulse'},
        'speed':      {'label': 'Speed & Power Endurance',   'color': '#fd7e14', 'icon': 'bi-speedometer2'},
    }

    LEGACY_KEY_ALIASES = {
        'bench press': 'strength__1rm_bench_press_kg',
        'bench_press': 'strength__1rm_bench_press_kg',
        '1rm bench press': 'strength__1rm_bench_press_kg',
        'back squat': 'strength__1rm_back_squat_kg',
        'squat': 'strength__1rm_back_squat_kg',
        '1rm back squat': 'strength__1rm_back_squat_kg',
        'pull up': 'strength__1rm_pull_up_kg',
        'pull-up': 'strength__1rm_pull_up_kg',
        '1rm pull up': 'strength__1rm_pull_up_kg',
        '10m sprint': 'speed__10m_sprint_s',
        '20m sprint': 'speed__20m_sprint_s',
        'cmj': 'plyometric__cmj_cm',
        'countermovement jump': 'plyometric__cmj_cm',
        'squat jump': 'plyometric__squat_jump_cm',
        'depth jump': 'plyometric__depth_jump_cm',
        'vo2 max': 'aerobic__vo2max_ml_kg_min',
        'vo2max': 'aerobic__vo2max_ml_kg_min',
        'mas': 'aerobic__mas_kmh',
        'yoyo level': 'aerobic__yoyo_level',
    }

    @staticmethod
    def _get_category(key):
        return key.split('__')[0] if '__' in key else None

    @staticmethod
    def _derive_metrics(tests):
        """Auto-calculate derived metrics (VO2max from MAS, Epley 1RM)."""
        derived = {}
        mas = tests.get('aerobic__mas_kmh')
        if isinstance(mas, (int, float)):
            derived['aerobic__vo2max_ml_kg_min'] = round(3.5 * mas, 1)
        # Epley 1RM for bench press
        bw = tests.get('_epley_bench_weight_kg')
        br = tests.get('_epley_bench_reps')
        if isinstance(bw, (int, float)) and isinstance(br, (int, float)) and br > 1:
            derived['strength__1rm_bench_press_kg'] = round(bw * br * 0.0333 + bw, 1)
        # Epley 1RM for back squat
        sw = tests.get('_epley_squat_weight_kg')
        sr = tests.get('_epley_squat_reps')
        if isinstance(sw, (int, float)) and isinstance(sr, (int, float)) and sr > 1:
            derived['strength__1rm_back_squat_kg'] = round(sw * sr * 0.0333 + sw, 1)
        return derived

    @staticmethod
    def _normalize_tests(tests):
        """
        Flattens mixed legacy/new assessment payloads into a numeric dict keyed by the
        advanced assessment namespace.
        """
        normalized = {}
        if not isinstance(tests, dict):
            return normalized

        for raw_key, raw_value in tests.items():
            if raw_key == 'notes':
                continue

            key = raw_key.strip() if isinstance(raw_key, str) else raw_key
            value = raw_value

            if isinstance(raw_value, dict) and raw_value.get('value') is not None:
                value = raw_value.get('value')

            if not isinstance(value, (int, float)):
                continue

            if isinstance(key, str) and '__' in key:
                normalized[key] = value
                continue

            alias = AssessmentInsightsService.LEGACY_KEY_ALIASES.get(
                str(key).strip().lower().replace('-', ' ')
            )
            if alias:
                normalized[alias] = value

        normalized.update(AssessmentInsightsService._derive_metrics(normalized))
        return normalized

    @staticmethod
    def _status(key, current, norm):
        if current is None:
            return 'no_data'
        good  = norm.get('good')
        pass_ = norm.get('pass')
        hi    = norm.get('higher_better', True)
        beats = (lambda a, b: a >= b) if hi else (lambda a, b: a <= b)
        if good is not None and beats(current, good):
            return 'excellent'
        if pass_ is not None and beats(current, pass_):
            return 'good'
        if pass_ is not None:
            return 'needs_work'
        return 'recorded'

    @staticmethod
    def parse(fitness_instance):
        """
        Returns structured dict keyed by category prefix.
        {
          'mobility': { 'label', 'color', 'icon', 'metrics': [{...}] },
          ...
        }
        """
        curr = AssessmentInsightsService._normalize_tests(fitness_instance.current_fitness_tests or {})
        prev = AssessmentInsightsService._normalize_tests(fitness_instance.previous_fitness_tests or {})
        pred = AssessmentInsightsService._normalize_tests(fitness_instance.expected_fitness_results or {})

        result = {}
        for key, curr_val in curr.items():
            cat = AssessmentInsightsService._get_category(key)
            if cat not in AssessmentInsightsService.CATEGORIES:
                continue
            if not isinstance(curr_val, (int, float)):
                continue

            norm     = AssessmentInsightsService.NORMS.get(key, {'unit': '', 'higher_better': True})
            prev_val = prev.get(key)
            pred_val = pred.get(key)
            if pred_val is None:
                if isinstance(prev_val, (int, float)):
                    pred_val = round(curr_val + (curr_val - prev_val), 2)
                else:
                    factor   = 1.05 if norm.get('higher_better', True) else 0.95
                    pred_val = round(curr_val * factor, 2)

            label = key.split('__', 1)[-1].replace('_', ' ').title()
            metric = {
                'key':           key,
                'label':         label,
                'current':       round(curr_val, 2),
                'previous':      round(prev_val, 2) if isinstance(prev_val, (int, float)) else None,
                'predicted':     round(pred_val, 2),
                'unit':          norm.get('unit', ''),
                'norm_pass':     norm.get('pass'),
                'norm_good':     norm.get('good'),
                'higher_better': norm.get('higher_better', True),
                'status':        AssessmentInsightsService._status(key, curr_val, norm),
                'note':          norm.get('note', ''),
            }
            if cat not in result:
                m = AssessmentInsightsService.CATEGORIES[cat]
                result[cat] = {'label': m['label'], 'color': m['color'], 'icon': m['icon'], 'metrics': []}
            result[cat]['metrics'].append(metric)

        return result

    @staticmethod
    def parse_for_api(fitness_instance):
        """Flat list for JSON API / JS chart consumption."""
        structured = AssessmentInsightsService.parse(fitness_instance)
        return [
            {'category': k, 'label': v['label'], 'color': v['color'],
             'icon': v['icon'], 'metrics': v['metrics']}
            for k, v in structured.items()
        ]
    
    @staticmethod
    def parse_for_api_with_pain_adjustment(fitness_instance):
        """
        Returns assessment insights with pain & biometric-based performance readiness adjustments.
        
        Integrates both pain log and biometric recovery data to dynamically adjust metrics.
        Athletes with high pain, dropped HRV, poor sleep, or high fatigue see reduced
        performance scores to reflect physiological readiness in the Performance Intelligence Center.
        """
        from .pain_adjustment_service import PerformancePainAdjustmentService
        
        # Get base assessment data
        structured = AssessmentInsightsService.parse(fitness_instance)
        categories = [
            {'category': k, 'label': v['label'], 'color': v['color'],
             'icon': v['icon'], 'metrics': v['metrics']}
            for k, v in structured.items()
        ]
        
        # Calculate pain and biometric adjustments
        athlete = fitness_instance.athlete
        pain_adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)
        biometric_adjustment = PerformancePainAdjustmentService.calculate_biometric_readiness(athlete)
        
        # Apply combined readiness reduction factor
        pain_impact = pain_adjustment.get('impact_factor', 0.0)
        bio_impact = biometric_adjustment.get('biometric_impact', 0.0)
        
        combined_reduction_factor = (1.0 - pain_impact) * (1.0 - bio_impact)
        combined_impact_pct = round((1.0 - combined_reduction_factor) * 100, 1)
        
        for category in categories:
            for metric in category['metrics']:
                # Store original values
                metric['original_current'] = metric['current']
                metric['original_predicted'] = metric['predicted']
                
                # Apply combined adjustment
                if combined_impact_pct > 0:
                    metric['current'] = round(metric['current'] * combined_reduction_factor, 2)
                    metric['predicted'] = round(metric['predicted'] * combined_reduction_factor, 2)
                    metric['pain_adjusted'] = True # Kept flag for compatibility
                    metric['combined_adjusted'] = True
                    metric['pain_impact_pct'] = round(pain_impact * 100, 1)
                    metric['bio_impact_pct'] = round(bio_impact * 100, 1)
                    metric['combined_impact_pct'] = combined_impact_pct
        
        # Inject comprehensive performance recovery context into the response
        if categories:
            categories[0]['pain_context'] = {
                'impact_factor': pain_impact,
                'max_pain_level': pain_adjustment['max_pain_level'],
                'avg_pain_level': pain_adjustment['avg_pain_level'],
                'pain_logs_count': pain_adjustment['pain_logs_count'],
                'affected_body_parts': pain_adjustment['affected_body_parts'],
                'recommendation': pain_adjustment['recommendation'],
                'note': f"Performance metrics reduced by {pain_impact*100:.0f}% due to active pain"
            }
            
            categories[0]['biometric_context'] = {
                'biometric_impact': bio_impact,
                'interpretation': biometric_adjustment['interpretation'],
                'acute_hrv': biometric_adjustment['acute_hrv'],
                'chronic_hrv': biometric_adjustment['chronic_hrv'],
                'acute_sleep': biometric_adjustment['acute_sleep'],
                'acute_fatigue': biometric_adjustment['acute_fatigue'],
                'acute_soreness': biometric_adjustment['acute_soreness'],
                'note': f"Performance metrics reduced by {bio_impact*100:.0f}% due to autonomic strain/fatigue"
            }
            
            categories[0]['combined_context'] = {
                'combined_reduction_factor': round(combined_reduction_factor, 3),
                'combined_impact_pct': combined_impact_pct,
                'status': 'Impaired capacity' if combined_impact_pct > 15 else ('Slight capacity reduction' if combined_impact_pct > 5 else 'Cleared at 100% capacity')
            }
        
        return categories
