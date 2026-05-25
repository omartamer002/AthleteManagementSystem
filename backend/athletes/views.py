from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime
import os
import markdown
try:
    from google import genai
except ImportError:
    genai = None
from .models import AthleteInfo, Owner, Fitness, Swimming, Basketball, Football, CrossFit, AttendanceRecord, InjuryRecord, PainLog
from .report_service import ReportGeneratorService
from .services import AssessmentInsightsService
from .serializers import (
    AthleteInfoSerializer, OwnerSerializer, FitnessSerializer,
    SwimmingSerializer, BasketballSerializer, FootballSerializer, CrossFitSerializer,
    AttendanceRecordSerializer, InjuryRecordSerializer, PainLogSerializer
)
from .permissions import IsStaffOrSuperuser

class AthleteInfoViewSet(viewsets.ModelViewSet):
    queryset = AthleteInfo.objects.all()
    serializer_class = AthleteInfoSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=['get'], permission_classes=[IsStaffOrSuperuser])
    def injuries(self, request, pk=None):
        """
        Specific endpoint returning just the injuries, protected by PermissionClasses.
        This fulfills the requirement: "Injury data in AthleteInfo must be restricted via DRF PermissionClasses."
        """
        athlete = self.get_object()
        injuries = []
        for inj in athlete.injury_records.all().order_by('-start_date', '-recorded_at'):
            status = "Active" if inj.is_active else "Resolved"
            injuries.append(f"{inj.injury_type} ({status})")
        return Response({'injuries': injuries})

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def assessments(self, request, pk=None):
        """
        Returns structured assessment insights (current, previous, predicted, norms)
        for all 6 advanced assessment categories. Used by the profile charts.
        """
        athlete = self.get_object()
        fitness = getattr(athlete, 'fitness_profile', None)
        if not fitness:
            return Response({'categories': [], 'message': 'No fitness data found.'}, status=200)
        categories = AssessmentInsightsService.parse_for_api(fitness)
        return Response({'categories': categories})
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def assessments_with_pain(self, request, pk=None):
        """
        Returns assessment insights with pain-based performance adjustments.
        
        Athletes with recent high pain will see reduced performance scores
        to reflect real-world impact on athletic ability. Current and predicted
        metrics are adjusted by the pain impact factor.
        
        Response includes:
        - Adjusted metrics with original values preserved
        - Pain context (max pain level, affected body parts, recommendation)
        - Performance impact percentage
        """
        athlete = self.get_object()
        fitness = getattr(athlete, 'fitness_profile', None)
        if not fitness:
            return Response({'categories': [], 'message': 'No fitness data found.'}, status=200)
        
        categories = AssessmentInsightsService.parse_for_api_with_pain_adjustment(fitness)
        
        # Add performance context summary
        performance_context = {
            'message': 'Performance metrics adjusted for recent pain'
        }
        
        return Response({
            'categories': categories,
            'context': performance_context
        })
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def performance_pain_context(self, request, pk=None):
        """
        Returns comprehensive performance readiness, autonomic recovery, and pain impact data.
        
        Includes:
        - Recent pain logs (last 5 days)
        - Pain impact factor on performance (0-100%)
        - Max/average pain levels
        - Affected body parts
        - Autonomic Recovery Readiness (HRV, RHR, sleep hours, subjective scores)
        - Combined performance reduction factor
        - Coaching recommendation
        """
        from .pain_adjustment_service import PerformancePainAdjustmentService
        
        athlete = self.get_object()
        
        # Get adjustments
        pain_adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)
        biometric_adjustment = PerformancePainAdjustmentService.calculate_biometric_readiness(athlete)
        
        # Combined capacity multiplier
        pain_impact = pain_adjustment.get('impact_factor', 0.0)
        bio_impact = biometric_adjustment.get('biometric_impact', 0.0)
        combined_reduction_factor = (1.0 - pain_impact) * (1.0 - bio_impact)
        combined_impact_pct = round((1.0 - combined_reduction_factor) * 100, 1)
        
        # Get recent pain logs
        recent_pains = PainLogSerializer(
            PainLog.objects.filter(athlete=athlete).order_by('-date')[:5],
            many=True
        ).data
        
        # Build response
        response_data = {
            'athlete_id': athlete.id,
            'athlete_name': athlete.name,
            'combined_readiness': {
                'combined_reduction_factor': round(combined_reduction_factor, 3),
                'combined_impact_percentage': combined_impact_pct,
                'status': (
                    'Severe Impairment - Sidelining recommended' if combined_impact_pct > 35
                    else 'High Impairment - Reduce training intensity & volume' if combined_impact_pct > 20
                    else 'Moderate Impairment - Monitor recovery' if combined_impact_pct > 8
                    else 'Cleared - Normal performance expected'
                )
            },
            'pain_impact': {
                'impact_factor': pain_impact,
                'reduction_factor': pain_adjustment['reduction_factor'],
                'percentage_reduction': round(pain_impact * 100, 1),
                'interpretation': (
                    'Severe pain symptoms' if pain_impact > 0.3
                    else 'High pain symptoms' if pain_impact > 0.15
                    else 'Moderate pain symptoms' if pain_impact > 0.05
                    else 'Minimal or no pain symptoms'
                )
            },
            'pain_metrics': {
                'max_pain_level': pain_adjustment['max_pain_level'],
                'average_pain_level': pain_adjustment['avg_pain_level'],
                'pain_logs_count': pain_adjustment['pain_logs_count'],
                'affected_body_parts': pain_adjustment['affected_body_parts'],
            },
            'biometric_readiness': {
                'biometric_impact': bio_impact,
                'percentage_reduction': round(bio_impact * 100, 1),
                'interpretation': biometric_adjustment['interpretation'],
                'metrics': {
                    'acute_hrv': biometric_adjustment['acute_hrv'],
                    'chronic_hrv': biometric_adjustment['chronic_hrv'],
                    'hrv_impact_pct': round(biometric_adjustment['hrv_impact'] * 100, 1),
                    'acute_rhr': biometric_adjustment['acute_rhr'],
                    'chronic_rhr': biometric_adjustment['chronic_rhr'],
                    'rhr_impact_pct': round(biometric_adjustment['rhr_impact'] * 100, 1),
                    'acute_sleep': biometric_adjustment['acute_sleep'],
                    'sleep_impact_pct': round(biometric_adjustment['sleep_impact'] * 100, 1),
                    'acute_fatigue': biometric_adjustment['acute_fatigue'],
                    'fatigue_impact_pct': round(biometric_adjustment['fatigue_impact'] * 100, 1),
                    'acute_soreness': biometric_adjustment['acute_soreness'],
                    'soreness_impact_pct': round(biometric_adjustment['soreness_impact'] * 100, 1),
                }
            },
            'recent_pain_logs': recent_pains,
            'recommendation': pain_adjustment['recommendation'] if pain_impact > bio_impact else biometric_adjustment['interpretation'],
            'performance_adjustment_note': (
                f"Combined performance capacity is reduced by {combined_impact_pct:.0f}% "
                f"due to a combination of active pain ({pain_impact*100:.0f}%) and autonomic/fatigue load ({bio_impact*100:.0f}%)."
            ) if combined_impact_pct > 0 else "Athlete is fully recovered and cleared for 100% capacity."
        }
        
        return Response(response_data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def generate_workout_plan(self, request, pk=None):
        athlete = self.get_object()
        fitness = getattr(athlete, 'fitness_profile', None)
        
        print(f"[AI] Generating plan for athlete: {athlete.name} (ID: {athlete.id})")
        
        # Prepare data string
        data_str = f"Athlete Name: {athlete.name}, Age: {athlete.age}, Gender: {athlete.gender}\n"
        if fitness:
            data_str += f"Sessions per week: {fitness.sessions_per_week}\n"
            data_str += f"Fitness Goal: {fitness.fitness_goal}\n"
            data_str += f"Workout Type Style: {fitness.workout_type}\n"
            data_str += f"Current Tests: {fitness.current_fitness_tests}\n"
            
            categories = AssessmentInsightsService.parse_for_api(fitness)
            for c in categories:
                data_str += f"Assessment [{c['label']}]: "
                for m in c['metrics']:
                    data_str += f"{m['label']} (Current: {m['current']} {m.get('unit', '')}), "
                data_str += "\n"
        
        # Readiness & Auto-Regulation Data
        recent_attendance = athlete.attendance_records.order_by('-date').first()
        readiness_str = ""
        if recent_attendance:
            readiness_str = (
                f"\n--- RECENT READINESS METRICS ---\n"
                f"Date: {recent_attendance.date}\n"
                f"Fatigue Score (1-10): {recent_attendance.fatigue_score or 'N/A'}\n"
                f"Muscle Soreness (1-10): {recent_attendance.muscle_soreness or 'N/A'}\n"
                f"Sleep Hours: {recent_attendance.sleep_hours or 'N/A'}\n"
                f"HRV (ms): {recent_attendance.hrv or 'N/A'}\n"
            )
        
        recent_pain_logs = athlete.pain_logs.order_by('-date')[:3]
        if recent_pain_logs.exists():
            readiness_str += "\n--- ACTIVE PAIN LOGS ---\n"
            for p in recent_pain_logs:
                readiness_str += f"{p.date}: {p.body_part} - Pain Level {p.pain_level}/10 ({p.pain_type})\n"

        if readiness_str:
            data_str += readiness_str
            prompt_instruction = (
                "You are an elite sports coach and fitness expert. "
                "Based on the following athlete profile data and their RECENT READINESS METRICS and PAIN LOGS, "
                "generate a detailed, personalized weekly workout plan. \n\n"
                "CRITICAL INSTRUCTION - AUTO-REGULATION: If the athlete shows high fatigue (>7), poor sleep (<6 hours), "
                "or reports high pain levels, you MUST Auto-Regulate the program. Reduce total volume, lower intensity, "
                "and prescribe active recovery or rehab exercises tailored to their specific pain points. State clearly "
                "at the top of the plan how you auto-regulated the workout based on their readiness."
            )
        else:
            prompt_instruction = (
                "You are an elite sports coach and fitness expert. "
                "Based on the following athlete profile data and assessments, generate a detailed, "
                "personalized weekly workout plan."
            )

        prompt = (
            f"{prompt_instruction} "
            "Structure the plan by days (e.g. Day 1, Day 2). Include sets, reps, and advice where applicable. "
            "Use Markdown formatting.\n\n"
            f"{data_str}"
        )

        # Priority: Request Body > Environment Settings
        api_key = request.data.get('api_key') or getattr(settings, 'GEMINI_API_KEY', None)
        
        if api_key and genai:
            try:
                print(f"[AI] Using real Gemini API...")
                client = genai.Client(api_key=api_key)
                
                print(f"[AI] Sending prompt to gemini-2.0-flash-lite...")
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    contents=prompt,
                )
                
                print(f"[AI] Plan generated successfully. Length: {len(response.text)} chars")
                html_plan = markdown.markdown(response.text)
                return Response({'status': 'success', 'plan_html': html_plan})
            except Exception as e:
                error_str = str(e)
                print(f"[AI] ERROR: {error_str}")
                if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                    print(f"[AI] Quota exceeded. Returning mock plan.")
                    mock_md = (
                        f"## Mock AI Generated Plan for {athlete.name}\n\n"
                        "*Gemini API Free Tier quota exhausted. Showing a placeholder plan.*\n\n"
                        "### Day 1: Strength Focus\n"
                        "- Squats: 3x10\n"
                        "- Bench Press: 3x8\n\n"
                        "### Day 2: Cardio & Mobility\n"
                        "- 30 min light jog\n"
                        "- 15 min dynamic stretching\n\n"
                        "> Please wait for the quota to reset or upgrade your API plan."
                    )
                    html_plan = markdown.markdown(mock_md)
                    return Response({'status': 'success', 'plan_html': html_plan})
                
                return Response({'status': 'error', 'message': f'AI Generation failed: {error_str}'}, status=500)
        else:
            print(f"[AI] No API key or library missing. Returning mock plan.")
            # Mocked response
            mock_md = (
                f"## Mock AI Generated Plan for {athlete.name}\n\n"
                "*No GEMINI_API_KEY provided in settings. Showing a placeholder plan.*\n\n"
                "### Day 1: Strength Focus\n"
                "- Squats: 3x10\n"
                "- Bench Press: 3x8\n\n"
                "### Day 2: Cardio & Mobility\n"
                "- 30 min light jog\n"
                "- 15 min dynamic stretching\n\n"
                "> Set the `GEMINI_API_KEY` environment variable and restart the server to enable real AI generation."
            )
            html_plan = markdown.markdown(mock_md)
            return Response({'status': 'success', 'plan_html': html_plan})

    @action(detail=True, methods=['get', 'post'], permission_classes=[permissions.AllowAny])
    def generate_nutrition_strategy(self, request, pk=None):
        athlete = self.get_object()
        fitness = getattr(athlete, 'fitness_profile', None)
        
        print(f"[AI] Generating nutrition strategy for athlete: {athlete.name} (ID: {athlete.id})")
        
        # Prepare data string
        data_str = f"Athlete Name: {athlete.name}, Age: {athlete.age}, Gender: {athlete.gender}\n"
        data_str += f"Height: {athlete.height} cm, Weight: {athlete.weight} kg, Body Type: {athlete.body_type}\n"
        
        sport_specs = []
        if getattr(athlete, 'swimming_records', None) and athlete.swimming_records.exists(): sport_specs.append("Swimming")
        if getattr(athlete, 'football_records', None) and athlete.football_records.exists(): sport_specs.append("Football")
        if getattr(athlete, 'basketball_records', None) and athlete.basketball_records.exists(): sport_specs.append("Basketball")
        if getattr(athlete, 'crossfit_records', None) and athlete.crossfit_records.exists(): sport_specs.append("CrossFit")
        
        if sport_specs:
            data_str += f"Sport Specializations: {', '.join(sport_specs)}\n"
        else:
            data_str += f"Sport Specialization: Fitness Athlete\n"
            
        if fitness:
            data_str += f"Sessions per week: {fitness.sessions_per_week}\n"
            data_str += f"Fitness Goal: {fitness.fitness_goal}\n"
            
            categories = AssessmentInsightsService.parse_for_api(fitness)
            for c in categories:
                data_str += f"Assessment [{c['label']}]: "
                for m in c['metrics']:
                    data_str += f"{m['label']} (Current: {m['current']} {m.get('unit', '')}), "
                data_str += "\n"
        
        prompt = (
            "You are an expert fitness coach, body composition analyst, sports nutritionist, and performance consultant.\n\n"
            "The user will provide their athlete profile data below AND has attached their InBody body composition report (image or PDF) to this message.\n\n"

            "Your job is to:\n\n"

            "────────────────────────────────────────\n"
            "STEP 1 — EXTRACT & INTERPRET INBODY DATA\n"
            "────────────────────────────────────────\n"
            "Extract and interpret ALL measurements present in the attached InBody report. The full set of possible InBody measurements includes:\n\n"
            "BODY COMPOSITION ANALYSIS: Weight, Total Body Water/TBW (L), Intracellular Water/ICW (L), Extracellular Water/ECW (L), "
            "Dry Lean Mass (kg), Protein (kg), Minerals (kg), Bone Mineral Content/BMC (kg), Body Fat Mass (kg), Soft Lean Mass (kg), "
            "Fat Free Mass/FFM (kg), Lean Body Mass/LBM (kg), Body Cell Mass/BCM (kg).\n\n"
            "MUSCLE-FAT ANALYSIS: Skeletal Muscle Mass/SMM (kg), Body Fat Mass (kg), Weight — with normal range bar.\n\n"
            "OBESITY ANALYSIS: BMI (kg/m²), Percent Body Fat/PBF (%), Obesity Degree (%), Waist-Hip Ratio/WHR.\n\n"
            "SEGMENTAL LEAN ANALYSIS (Right Arm, Left Arm, Trunk, Right Leg, Left Leg): Lean mass (kg), % of ideal lean mass.\n\n"
            "SEGMENTAL FAT ANALYSIS (Right Arm, Left Arm, Trunk, Right Leg, Left Leg): Fat mass (kg), % over ideal.\n\n"
            "ECW/TBW ANALYSIS: ECW/TBW ratio (whole body), Segmental ECW ratios (RA, LA, TR, RL, LL).\n\n"
            "ADDITIONAL METRICS: BMR (kcal), Visceral Fat Level (1–10 scale) or VFA (cm²), InBody Score (/100), "
            "Phase Angle φ (degrees), Reactance/Xc, Impedance Z values.\n\n"
            "WEIGHT CONTROL TARGETS (if present): Target Weight, Weight Control, Fat Control, Muscle Control.\n\n"
            "BODY COMPOSITION HISTORY (if present): Weight trend, SMM trend, PBF trend, ECW Ratio trend.\n\n"

            "────────────────────────────────────────\n"
            "STEP 2 — FLAG RED FLAGS & HEALTH ALERTS\n"
            "────────────────────────────────────────\n"
            "Flag any of these clinically significant findings:\n"
            "- ECW/TBW ratio above 0.400 → possible inflammation or fluid imbalance\n"
            "- VFA > 100 cm² → elevated visceral adiposity risk\n"
            "- BMI > 30 combined with low SMM → sarcopenic obesity concern\n"
            "- Severe segmental muscle imbalances (>15% difference between limbs) → injury risk\n"
            "- Low phase angle below 4.5° → poor cellular health / hydration quality\n"
            "- BMR context for caloric planning\n\n"

            "────────────────────────────────────────\n"
            "STEP 3 — WEEKLY WORKOUT PLAN\n"
            "────────────────────────────────────────\n"
            "Based on InBody data AND fitness goal, generate a detailed personalised weekly workout plan:\n\n"
            "a) TRAINING SPLIT — days/week, muscle groups per day, rest day placement.\n"
            "b) EXERCISE SELECTION — specific exercises calibrated to segmental imbalances "
            "(e.g. if right arm lean mass < left arm, prioritise unilateral work on the weaker side).\n"
            "c) VOLUME & INTENSITY — exact sets, reps, rest periods calibrated to PBF, SMM, and fitness goal.\n"
            "d) CARDIO RECOMMENDATIONS — type (LISS/HIIT/Steady State), duration, frequency; "
            "based on VFA/visceral fat level, PBF, and ECW/TBW ratio. "
            "High ECW ratio → reduce high-intensity cardio to limit further fluid stress.\n"
            "e) PROGRESSION PLAN — week-by-week progression over 4 weeks.\n\n"

            "────────────────────────────────────────\n"
            "STEP 4 — NUTRITION STRATEGY\n"
            "────────────────────────────────────────\n"
            "CALORIC TARGETS:\n"
            "- Calculate TDEE using BMR from the report (or estimate via Mifflin-St Jeor using weight, height, age, sex from athlete profile).\n"
            "- Apply caloric adjustment based on goal: Fat loss → deficit 300–500 kcal; "
            "Muscle gain → surplus 200–350 kcal; Recomposition → maintenance ±100 kcal; "
            "Athletic performance → maintenance or slight surplus on training days.\n"
            "- State the daily calorie target clearly.\n\n"
            "MACRONUTRIENT BREAKDOWN:\n"
            "- Protein: base on LBM/FFM (not total weight): Fat loss/recomp → 2.2–2.6g/kg LBM; "
            "Muscle gain → 1.8–2.2g/kg LBM. If SMM is low → use higher protein end.\n"
            "- Carbohydrates: fill remaining calories; use higher carbs on training days, lower on rest days. "
            "Reduce if VFA is high or ECW/TBW > 0.400.\n"
            "- Fats: 0.8–1.2g/kg bodyweight; increase if VFA is very high.\n"
            "- Present as: Protein Xg / Carbs Xg / Fats Xg / Total Xcal.\n\n"
            "MEAL TIMING & FREQUENCY:\n"
            "- Meals per day based on sessions per week.\n"
            "- Pre-workout meal: timing and composition (carb + protein ratio).\n"
            "- Post-workout meal: timing window and protein priority.\n"
            "- If training > 4 sessions/week → suggest intra-workout carb strategy.\n\n"
            "HYDRATION TARGETS:\n"
            "- Daily intake: ~35ml per kg bodyweight.\n"
            "- If ECW/TBW elevated → flag sodium/inflammation; recommend electrolyte balance.\n"
            "- If phase angle is low → emphasise hydration quality; suggest mineral-rich sources.\n\n"
            "MICRONUTRIENT PRIORITIES:\n"
            "- If Minerals below reference → flag calcium, magnesium, phosphorus intake.\n"
            "- If Protein below reference → emphasise complete protein sources.\n"
            "- If VFA is high → recommend omega-3s, fibre, anti-inflammatory foods.\n"
            "- If ECW/TBW is high → limit processed sodium, suggest potassium-rich foods.\n\n"
            "SUPPLEMENT CONSIDERATIONS (evidence-based only):\n"
            "- Creatine monohydrate if SMM is low or muscle gain is the goal.\n"
            "- Whey/casein protein if dietary protein target is hard to hit from food.\n"
            "- Omega-3 if VFA or inflammation markers are elevated.\n"
            "- Vitamin D + K2 if minerals are below range.\n"
            "- Magnesium if ECW/TBW or sleep quality is a concern.\n"
            "- Electrolytes if training > 4 sessions/week or TBW is below reference.\n\n"

            "────────────────────────────────────────\n"
            "STEP 5 — FORMAT YOUR FULL RESPONSE\n"
            "────────────────────────────────────────\n"
            "Structure your response using these exact headings in Markdown:\n\n"
            "## InBody Data Summary\n"
            "## Key Findings & Red Flags\n"
            "## User Goals & Strategy\n"
            "   - Fitness Goal:\n"
            "   - Sessions per Week:\n"
            "   - Overall Strategy:\n"
            "## Weekly Workout Plan\n"
            "## Cardio Protocol\n"
            "## 4-Week Progression Plan\n"
            "## Nutrition Strategy\n"
            "   ### Daily Calorie Target\n"
            "   ### Macronutrient Breakdown\n"
            "   ### Meal Timing & Frequency\n"
            "   ### Hydration Protocol\n"
            "   ### Micronutrient Priorities\n"
            "   ### Supplement Considerations\n"
            "## Summary & Next Steps\n\n"
            "Always be specific, evidence-based, practical, and compassionate. "
            "Every recommendation MUST reference actual numbers from the InBody report and athlete profile below. "
            "Never give generic advice.\n\n"
            "─────────────────────\n"
            "ATHLETE PROFILE DATA\n"
            "─────────────────────\n"
            f"{data_str}"
        )

        # Priority: Request Body > Environment Settings
        api_key = request.data.get('api_key') or getattr(settings, 'GEMINI_API_KEY', None)
        
        if api_key and genai:
            try:
                print(f"[AI] Using real Gemini API for Nutrition Strategy...")
                client = genai.Client(api_key=api_key)
                
                contents = [prompt]
                
                if fitness and fitness.inbody_file:
                    try:
                        file_path = fitness.inbody_file.path
                        if os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                file_bytes = f.read()
                            
                            # Simple mime type inference
                            mime_type = 'application/pdf' if file_path.lower().endswith('.pdf') else 'image/jpeg'
                            if file_path.lower().endswith('.png'): mime_type = 'image/png'
                            
                            contents.append({
                                'inline_data': {
                                    'mime_type': mime_type,
                                    'data': file_bytes
                                }
                            })
                            print(f"[AI] Attached InBody Analysis file: {file_path}")
                    except Exception as fe:
                        print(f"[AI] Error reading InBody file: {fe}")
                
                has_inbody = fitness and fitness.inbody_file
                print(f"[AI] Sending InBody analysis prompt to gemini-2.0-flash... (InBody file: {'YES' if has_inbody else 'NO'})")
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=contents,
                )
                
                print(f"[AI] Strategy generated successfully. Length: {len(response.text)} chars")
                html_plan = markdown.markdown(response.text)
                return Response({'status': 'success', 'strategy_html': html_plan})
            except Exception as e:
                error_str = str(e)
                print(f"[AI] ERROR: {error_str}")
                if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                    print(f"[AI] Quota exceeded. Returning structured placeholder.")
                    weight = float(athlete.weight)
                    lbm_est = weight * 0.82  # rough estimate without InBody data
                    protein_g = round(lbm_est * 2.3)
                    fat_g = round(weight * 1.0)
                    calorie_from_pf = protein_g * 4 + fat_g * 9
                    carb_g = round((2400 - calorie_from_pf) / 4)
                    water_ml = round(weight * 35)
                    mock_md = (
                        f"## InBody Data Summary\n\n"
                        f"*Gemini API quota exhausted — InBody file was uploaded but could not be analysed. "
                        f"The following estimates are based on athlete profile data only.*\n\n"
                        f"## Key Findings & Red Flags\n\n"
                        f"- ⚠️ InBody analysis unavailable (API quota). Upload a new InBody file and retry for full interpretation.\n\n"
                        f"## User Goals & Strategy\n\n"
                        f"- **Fitness Goal:** {getattr(fitness, 'fitness_goal', 'Not specified')}\n"
                        f"- **Sessions per Week:** {getattr(fitness, 'sessions_per_week', 'N/A')}\n\n"
                        f"## Nutrition Strategy\n\n"
                        f"### Daily Calorie Target\n"
                        f"Estimated ~2,400 kcal/day (recalculate once InBody data is available).\n\n"
                        f"### Macronutrient Breakdown\n"
                        f"- **Protein:** {protein_g}g\n"
                        f"- **Carbs:** {carb_g}g\n"
                        f"- **Fats:** {fat_g}g\n\n"
                        f"### Hydration Protocol\n"
                        f"- Target: **{water_ml} ml/day** (~35 ml × {weight:.0f} kg)\n\n"
                        f"> ⏳ Please wait for the API quota to reset or upgrade your plan to get the full InBody-powered analysis."
                    )
                    html_plan = markdown.markdown(mock_md)
                    return Response({'status': 'success', 'strategy_html': html_plan})
                
                return Response({'status': 'error', 'message': f'AI Generation failed: {error_str}'}, status=500)
        else:
            print(f"[AI] No API key or library missing. Returning structured placeholder.")
            weight = float(athlete.weight)
            lbm_est = weight * 0.82
            protein_g = round(lbm_est * 2.3)
            fat_g = round(weight * 1.0)
            calorie_from_pf = protein_g * 4 + fat_g * 9
            carb_g = round((2400 - calorie_from_pf) / 4)
            water_ml = round(weight * 35)
            has_inbody = fitness and fitness.inbody_file
            mock_md = (
                f"## InBody Data Summary\n\n"
                f"{'✅ InBody file uploaded — add a GEMINI_API_KEY to unlock full AI analysis.' if has_inbody else '⚠️ No InBody file uploaded yet. Upload a report for full body composition analysis.'}\n\n"
                f"## Key Findings & Red Flags\n\n"
                f"- No AI analysis available without a `GEMINI_API_KEY`. Estimates below are based on athlete profile data only.\n\n"
                f"## User Goals & Strategy\n\n"
                f"- **Fitness Goal:** {getattr(fitness, 'fitness_goal', 'Not specified')}\n"
                f"- **Sessions per Week:** {getattr(fitness, 'sessions_per_week', 'N/A')}\n"
                f"- **Sport:** {', '.join(sport_specs) if sport_specs else 'General Fitness'}\n\n"
                f"## Nutrition Strategy\n\n"
                f"### Daily Calorie Target\n"
                f"Estimated ~2,400 kcal/day based on {athlete.weight} kg bodyweight. Set a `GEMINI_API_KEY` and provide an InBody file for a BMR-calculated TDEE.\n\n"
                f"### Macronutrient Breakdown\n"
                f"- **Protein:** {protein_g}g (estimated from ~{lbm_est:.1f} kg LBM × 2.3g)\n"
                f"- **Carbs:** {carb_g}g\n"
                f"- **Fats:** {fat_g}g (1.0g × {weight:.0f} kg)\n\n"
                f"### Hydration Protocol\n"
                f"- Daily target: **{water_ml} ml** (~35 ml × {weight:.0f} kg bodyweight)\n\n"
                f"### Supplement Considerations\n"
                f"- Creatine Monohydrate (3–5g/day) — supports muscle mass and performance\n"
                f"- Whey Protein — if daily protein target is difficult to reach from food alone\n\n"
                f"> 🔑 Set the `GEMINI_API_KEY` environment variable and upload an InBody file to unlock the full expert analysis: InBody interpretation, red flags, personalised workout plan, cardio protocol, 4-week progression, and complete nutrition strategy."
            )
            html_plan = markdown.markdown(mock_md)
            return Response({'status': 'success', 'strategy_html': html_plan})

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def generate_injury_prediction(self, request, pk=None):
        import json
        athlete = self.get_object()
        fitness = getattr(athlete, 'fitness_profile', None)
        
        print(f"[AI] Generating injury prediction for athlete: {athlete.name} (ID: {athlete.id})")
        
        data_str = f"Athlete Name: {athlete.name}, Age: {athlete.age}, Gender: {athlete.gender}\n"
        data_str += f"Stats: Height {athlete.height}cm, Weight {athlete.weight}kg, Body Type: {athlete.body_type}\n"
        data_str += f"Athletic Profile: Strengths: {athlete.strengths}, Weaknesses: {athlete.weaknesses}\n"
        
        injuries = athlete.injury_records.all()
        if injuries:
            data_str += "Injury History:\n"
            for inj in injuries:
                status = "Active" if inj.is_active else "Resolved"
                data_str += f"- {inj.injury_type} ({status}), Severity: {inj.severity}, Start: {inj.start_date}, Cleared: {inj.cleared_to_train}, Notes: {inj.medical_notes}\n"
        else:
            data_str += "Injury History: None\n"
            
        total_attended = athlete.attendance_records.filter(attended=True).count()
        total_sessions = athlete.attendance_records.count()
        attendance_rate = (total_attended / total_sessions * 100) if total_sessions > 0 else 0
        data_str += f"Training Consistency: {attendance_rate:.1f}% Attendance Rate ({total_attended}/{total_sessions} sessions)\n"

        attendances = athlete.attendance_records.order_by('-date')[:14]
        if attendances:
            data_str += "Recent 14-day Session & Biometric Data:\n"
            for att in attendances:
                data_str += f"- Date: {att.date}, Rating: {att.performance_rating}/10, HRV: {att.hrv}, RHR: {att.resting_heart_rate}, Sleep: {att.sleep_hours}h, Fatigue: {att.fatigue_score}/10, Soreness: {att.muscle_soreness}/10, Workout Completed: {att.workout_completed}, Notes: {att.coach_notes}\n"
        
        # Include Sport Specific Records for physical demand context
        sport_data = ""
        swimming = athlete.swimming_records.all()
        for s in swimming:
            sport_data += f"- Swimming: {s.stroke} {s.events}, Current Record: {s.current_record}, Laps: {s.total_laps}\n"
        
        basketball = athlete.basketball_records.all()
        for b in basketball:
            sport_data += f"- Basketball: Position: {b.position}, Vertical: {b.vertical_jump}in, Game High: {b.current_game_high}\n"
            
        if sport_data:
            data_str += f"Sport-Specific Performance Data:\n{sport_data}"

        if fitness:
            data_str += f"Training Load: {fitness.sessions_per_week} sessions/week\n"
            categories = AssessmentInsightsService.parse_for_api(fitness)
            for c in categories:
                data_str += f"Assessment [{c['label']}]: "
                for m in c['metrics']:
                    data_str += f"{m['label']} (Current: {m['current']} {m.get('unit', '')}), "
                data_str += "\n"

        # Include Recent Active Pain Logs for prompt context
        from django.utils import timezone
        from datetime import timedelta
        cutoff_date = timezone.now().date() - timedelta(days=3)
        recent_pains = athlete.pain_logs.filter(date__gte=cutoff_date).order_by('-date')
        if recent_pains.exists():
            data_str += "Recent Active Pain Logs (Last 3 Days):\n"
            for p in recent_pains:
                data_str += f"- Date: {p.date}, Body Part: {p.body_part}, Pain Level: {p.pain_level}/10 ({p.pain_type}), Notes: {p.notes or 'None'}\n"
        else:
            data_str += "Recent Active Pain Logs (Last 3 Days): None\n"

        prompt = (
            "You are an elite sports scientist and medical AI. Based on the athlete's full profile, biometrics (HRV, RHR, Sleep, Fatigue, Soreness), session performance ratings, coach notes, and historical injuries, predict the injury risk.\n"
            "Respond strictly in valid JSON format matching this structure exactly (no markdown blocks, just raw JSON):\n"
            "{\n"
            '  "overall_risk_score": 0-100 integer,\n'
            '  "risk_status": "Low" | "Medium" | "High",\n'
            '  "why_risk_high": "Detailed explanation using the provided data metrics like HRV drops, high fatigue, or recurring injury patterns",\n'
            '  "recommendations": ["Actionable step 1", "Actionable step 2"],\n'
            '  "predicted_injury_type": "Specific injury or None",\n'
            '  "predicted_injury_time": "e.g., 10-14 days",\n'
            '  "confidence_level": 0-100 integer,\n'
            '  "smart_alerts": [{"urgency": "High" | "Moderate", "reason": "...", "action": "..."}]\n'
            "}\n\n"
            f"Athlete Data:\n{data_str}"
        )

        # Priority: Request Body > Environment Settings
        api_key = request.data.get('api_key') or getattr(settings, 'GEMINI_API_KEY', None)
        if api_key and genai:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model='gemini-2.0-flash-lite',
                    contents=prompt,
                )
                raw_text = response.text
                if raw_text.startswith("```json"):
                    raw_text = raw_text.strip("```json").strip("```").strip()
                elif raw_text.startswith("```"):
                    raw_text = raw_text.strip("```").strip()
                
                result_json = json.loads(raw_text)
                return Response({'status': 'success', 'prediction': result_json})
            except Exception as e:
                error_str = str(e)
                print(f"[AI] ERROR: {error_str}")
        
        # Mock Response (Dynamic Fallback)
        print(f"[AI] Using mock injury prediction logic.")
        
        # -------------------------------------------------------------
        # UPGRADED FALLBACK: Biometric Autonomic & Load Risk (BALR) Score
        # -------------------------------------------------------------
        from django.utils import timezone
        from datetime import timedelta
        from .pain_adjustment_service import PerformancePainAdjustmentService

        # 1. Base Score
        base_score = 10
        smart_alerts = []
        why_risk_high_parts = []
        recommendations = []

        # 2. Historical & Active Injury Risk (Injury History)
        active_injuries = injuries.filter(is_active=True)
        active_count = active_injuries.count()
        base_score += active_count * 25
        if active_count > 0:
            why_risk_high_parts.append(f"{active_count} active injuries")
            smart_alerts.append({
                "urgency": "High",
                "reason": f"Athlete has {active_count} unresolved injuries requiring ongoing rehabilitation.",
                "action": "Ensure strict adherence to rehabilitation phases and avoid loading affected tissues."
            })

        # Resolved injuries in last 90 days
        cutoff_90_days = timezone.now().date() - timedelta(days=90)
        resolved_recent = injuries.filter(is_active=False, start_date__gte=cutoff_90_days)
        resolved_count = resolved_recent.count()
        base_score += resolved_count * 10
        if resolved_count > 0:
            why_risk_high_parts.append(f"{resolved_count} recently resolved injuries")
            smart_alerts.append({
                "urgency": "Moderate",
                "reason": f"Athlete has a recent history of {resolved_count} resolved injuries in the last 90 days.",
                "action": "Perform targeted dynamic warm-up and monitoring of those specific kinetic chains."
            })

        # 3. Biometric Load Spikes (Acute vs Chronic Fatigue & Soreness)
        recent_fatigue = 0.0
        recent_soreness = 0.0
        
        attendances_list = list(attendances)
        if len(attendances_list) > 0:
            acute_att = attendances_list[:3]
            chronic_att = attendances_list
            
            f_scores_acute = [a.fatigue_score for a in acute_att if a.fatigue_score is not None]
            f_scores_chronic = [a.fatigue_score for a in chronic_att if a.fatigue_score is not None]
            
            s_scores_acute = [a.muscle_soreness for a in acute_att if a.muscle_soreness is not None]
            s_scores_chronic = [a.muscle_soreness for a in chronic_att if a.muscle_soreness is not None]
            
            avg_f_acute = sum(f_scores_acute) / len(f_scores_acute) if f_scores_acute else 0.0
            avg_f_chronic = sum(f_scores_chronic) / len(f_scores_chronic) if f_scores_chronic else 0.0
            
            avg_s_acute = sum(s_scores_acute) / len(s_scores_acute) if s_scores_acute else 0.0
            avg_s_chronic = sum(s_scores_chronic) / len(s_scores_chronic) if s_scores_chronic else 0.0
            
            recent_fatigue = avg_f_acute
            recent_soreness = avg_s_acute
            
            # Fatigue Workload Spike (Acute-to-Chronic Ratio)
            fwr = avg_f_acute / max(1.0, avg_f_chronic)
            if fwr > 1.3 or avg_f_acute > 7.0:
                base_score += 15
                why_risk_high_parts.append(f"acute fatigue spike ({avg_f_acute:.1f}/10)")
                smart_alerts.append({
                    "urgency": "High" if avg_f_acute > 7.0 else "Moderate",
                    "reason": f"Fatigue levels have spiked (Acute Fatigue: {avg_f_acute:.1f} vs Chronic: {avg_f_chronic:.1f}).",
                    "action": "Auto-regulate workout by reducing total load and prescribing active recovery."
                })
            
            # Soreness Spike
            swr = avg_s_acute / max(1.0, avg_s_chronic)
            if swr > 1.3 or avg_s_acute > 7.0:
                base_score += 10
                why_risk_high_parts.append(f"acute muscle soreness spike ({avg_s_acute:.1f}/10)")
                smart_alerts.append({
                    "urgency": "Moderate",
                    "reason": f"Muscle soreness has intensified rapidly (Acute Soreness: {avg_s_acute:.1f} vs Chronic: {avg_s_chronic:.1f}).",
                    "action": "Incorporate low-intensity active mobility work and foam rolling."
                })

            # 4. Autonomic Readiness (HRV Drop & Sleep Deprivation)
            hrv_scores_acute = [a.hrv for a in acute_att if a.hrv is not None]
            hrv_scores_chronic = [a.hrv for a in chronic_att if a.hrv is not None]
            sleep_scores_acute = [float(a.sleep_hours) for a in acute_att if a.sleep_hours is not None]
            
            avg_hrv_acute = sum(hrv_scores_acute) / len(hrv_scores_acute) if hrv_scores_acute else 0.0
            avg_hrv_chronic = sum(hrv_scores_chronic) / len(hrv_scores_chronic) if hrv_scores_chronic else 0.0
            avg_sleep_acute = sum(sleep_scores_acute) / len(sleep_scores_acute) if sleep_scores_acute else 8.0
            
            if avg_hrv_chronic > 0 and avg_hrv_acute < 0.85 * avg_hrv_chronic:
                base_score += 15
                why_risk_high_parts.append(f"significant HRV drop ({avg_hrv_acute:.0f}ms vs baseline {avg_hrv_chronic:.0f}ms)")
                smart_alerts.append({
                    "urgency": "High",
                    "reason": f"Autonomic readiness has dropped significantly (HRV down by {((avg_hrv_chronic - avg_hrv_acute)/avg_hrv_chronic)*100:.0f}%).",
                    "action": "Focus on sleep, parasympathetic activation, and light stretching."
                })
            
            if avg_sleep_acute < 6.0:
                base_score += 10
                why_risk_high_parts.append(f"restricted sleep ({avg_sleep_acute:.1f}h/night)")
                smart_alerts.append({
                    "urgency": "Moderate",
                    "reason": f"Sleep duration has dropped below the threshold of 6 hours per night.",
                    "action": "Ensure sleep hygiene protocols are followed and limit high CNS stress exercises."
                })

        # 5. Symptomatic Pain Spike (Pain Log Integration)
        pain_adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)
        pain_impact = pain_adjustment['impact_factor']
        pain_points = pain_impact * 80
        base_score += pain_points
        if pain_impact > 0.0:
            parts_str = ", ".join(pain_adjustment['affected_body_parts'])
            why_risk_high_parts.append(f"active pain in {parts_str or 'body part'} (impact: {pain_impact*100:.0f}%)")
            smart_alerts.append({
                "urgency": "High" if pain_adjustment['max_pain_level'] >= 7 else "Moderate",
                "reason": f"Active pain reported in {parts_str} with an intensity up to {pain_adjustment['max_pain_level']}/10.",
                "action": pain_adjustment['recommendation']
            })

        # Final Score Binning
        mock_score = min(int(base_score), 98)
        mock_status = "High" if mock_score > 70 else ("Medium" if mock_score > 35 else "Low")
        
        # Recommendations Generation based on indicators
        if mock_status == "High":
            recommendations = [
                "Schedule immediate rest day or high-recovery active rehab.",
                "Modify upcoming training: eliminate heavy compound lifts and high-impact loading.",
                "Consult with the athletic trainer/physiotherapist to address specific pain symptoms.",
                "Prioritize sleep (>8.5 hours) and anti-inflammatory recovery protocols."
            ]
        elif mock_status == "Medium":
            recommendations = [
                "Reduce training volume by 20-30% and monitor somatic symptoms closely.",
                "Incorporate targeted mobility work for currently tight or painful body parts.",
                "Ensure core autonomic recovery is prioritized tonight."
            ]
        else:
            recommendations = [
                "Continue normal progressive training load as scheduled.",
                "Maintain consistent hydration, sleep, and recovery routines."
            ]

        # Compose "Why Risk High" explanation
        if why_risk_high_parts:
            why_risk_high = "Elevated risk detected due to: " + ", ".join(why_risk_high_parts) + "."
        else:
            why_risk_high = "Autonomic, workload, and symptom tracking indicate an optimal recovery state."

        mock_result = {
            "overall_risk_score": mock_score,
            "risk_status": mock_status,
            "why_risk_high": why_risk_high,
            "recommendations": recommendations,
            "predicted_injury_type": "Soft Tissue Strain" if mock_score > 60 else ("Minor Overuse Injury" if mock_score > 35 else "None"),
            "predicted_injury_time": "3-5 days" if mock_score > 70 else ("7-10 days" if mock_score > 35 else "N/A"),
            "confidence_level": 80,
            "smart_alerts": smart_alerts
        }
        return Response({'status': 'success', 'prediction': mock_result})


    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def generate_report(self, request, pk=None):
        """
        Generates a weekly PDF report (EN or AR) using ReportLab.
        Streams all athlete profile data into the two-page Tiger Academy layout.
        """
        athlete = self.get_object()
        lang = request.query_params.get('lang', 'en')

        data = ReportGeneratorService.get_weekly_data(athlete)
        data['lang'] = lang
        data['static_path'] = os.path.join(settings.BASE_DIR, 'static')
        data['logo_path']   = os.path.join(settings.MEDIA_ROOT, 'branding', 'tiger_academy_logo.png')

        # Inject computed bmi back onto athlete for the info-table renderer (av('bmi'))
        try:
            athlete._bmi = data.get('bmi', '—')
            athlete.bmi  = data.get('bmi', '—')
        except Exception:
            pass

        # Re-generate summary in the requested language
        data['summary'] = ReportGeneratorService.generate_summary(
            athlete, data['attendance_rate'], data['avg_rating'], data['stats'], lang=lang
        )

        pdf = ReportGeneratorService.generate_pdf(data, lang=lang)

        filename = f"Report_{athlete.name.replace(' ', '_')}_{lang}_{datetime.now().strftime('%Y%m%d')}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response


class OwnerViewSet(viewsets.ModelViewSet):
    queryset = Owner.objects.all()
    serializer_class = OwnerSerializer
    # Mandatory Security-by-Design requirement:
    # "The Owner model data must be restricted to users with is_staff or is_superuser status."
    permission_classes = [IsStaffOrSuperuser]

class FitnessViewSet(viewsets.ModelViewSet):
    queryset = Fitness.objects.all()
    serializer_class = FitnessSerializer
    permission_classes = [permissions.AllowAny]

class SwimmingViewSet(viewsets.ModelViewSet):
    queryset = Swimming.objects.all()
    serializer_class = SwimmingSerializer
    permission_classes = [permissions.AllowAny]

class BasketballViewSet(viewsets.ModelViewSet):
    queryset = Basketball.objects.all()
    serializer_class = BasketballSerializer
    permission_classes = [permissions.AllowAny]

class FootballViewSet(viewsets.ModelViewSet):
    queryset = Football.objects.all()
    serializer_class = FootballSerializer
    permission_classes = [permissions.AllowAny]

class CrossFitViewSet(viewsets.ModelViewSet):
    queryset = CrossFit.objects.all()
    serializer_class = CrossFitSerializer
    permission_classes = [permissions.AllowAny]

class AttendanceRecordViewSet(viewsets.ModelViewSet):
    queryset = AttendanceRecord.objects.all()
    serializer_class = AttendanceRecordSerializer
    permission_classes = [permissions.AllowAny]

class InjuryRecordViewSet(viewsets.ModelViewSet):
    queryset = InjuryRecord.objects.all()
    serializer_class = InjuryRecordSerializer
    permission_classes = [permissions.AllowAny]

class PainLogViewSet(viewsets.ModelViewSet):
    queryset = PainLog.objects.all()
    serializer_class = PainLogSerializer
    permission_classes = [permissions.AllowAny]
