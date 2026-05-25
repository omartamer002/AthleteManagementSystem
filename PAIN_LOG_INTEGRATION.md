# Pain Log Integration with Performance Intelligence Center

## Overview

This system integrates athlete pain data into the Performance Intelligence Center calculations. When an athlete experiences pain, it automatically reduces their performance metrics to reflect the real-world impact of pain on athletic ability.

**Key Principle**: Pain naturally affects performance. An athlete with high pain levels in recent days should not be expected to achieve the same performance targets as a pain-free athlete.

---

## How It Works

### 1. Pain Data Collection

Pain is logged in the `PainLog` model with:
- **Body Part**: Affected area (e.g., "Left Knee", "Right Shoulder")
- **Pain Level**: 1-10 scale (10 = severe)
- **Pain Type**: Descriptor (e.g., "Sharp", "Dull", "Aching")
- **Date**: When the pain was recorded
- **Notes**: Additional context

### 2. Pain Impact Calculation

The `PerformancePainAdjustmentService` analyzes recent pain logs (last 3 days) and calculates a **pain impact factor** (0.0 to 1.0):

**Severity Thresholds**:
- **High Pain (7-10)**: Up to 40% performance reduction
- **Moderate Pain (4-6)**: Up to 20% performance reduction  
- **Low Pain (1-3)**: Up to 5% performance reduction

**Recency Factor**:
- Pain from today has 100% impact
- Impact decays linearly over 3 days
- Pain older than 3 days has minimal impact

**Example**:
```
Max pain level: 8 (high)
2 days ago: -50% of remaining impact
1 day ago: -75% of remaining impact
Today: -100% of remaining impact
→ Result: ~30% performance reduction
```

### 3. Performance Adjustment

Adjusted metrics = Original metric × (1 - pain impact factor)

**For Session Ratings (1-10 scale)**:
```
Adjusted rating = Original rating - (9 points × pain impact factor)
Min: 1, Max: 10
```

**For Fitness Tests & Advanced Assessments**:
```
Adjusted value = Original value × reduction_factor
```

---

## API Endpoints

### Get Pain-Adjusted Assessments

```bash
GET /api/athletes/{id}/assessments_with_pain/
```

Returns assessment insights with adjusted performance metrics based on recent pain.

**Response Structure**:
```json
{
  "categories": [
    {
      "category": "strength",
      "label": "Strength Assessments",
      "metrics": [
        {
          "key": "strength__1rm_back_squat_kg",
          "label": "1rm Back Squat Kg",
          "current": 90.0,
          "original_current": 100.0,
          "predicted": 95.0,
          "original_predicted": 105.0,
          "pain_adjusted": true,
          "pain_impact_pct": 10.0,
          "adjustment_note": "Current pain reduces this metric by 10%"
        }
      ],
      "pain_context": {
        "impact_factor": 0.1,
        "max_pain_level": 6,
        "avg_pain_level": 5.5,
        "affected_body_parts": ["Right Knee"],
        "recommendation": "Moderate pain - Reduce volume, maintain technique work"
      }
    }
  ]
}
```

### Get Performance Pain Context

```bash
GET /api/athletes/{id}/performance_pain_context/
```

Returns comprehensive pain impact summary including recent pain logs.

**Response**:
```json
{
  "athlete_id": 1,
  "athlete_name": "John Athlete",
  "pain_impact": {
    "impact_factor": 0.25,
    "reduction_factor": 0.75,
    "percentage_reduction": 25.0,
    "interpretation": "High - Reduce intensity and volume"
  },
  "pain_metrics": {
    "max_pain_level": 8,
    "average_pain_level": 6.5,
    "pain_logs_count": 3,
    "affected_body_parts": ["Right Knee", "Left Ankle"]
  },
  "recent_pain_logs": [
    {
      "date": "2026-05-04",
      "body_part": "Right Knee",
      "pain_level": 8,
      "pain_type": "Sharp",
      "notes": "Increased after jump training"
    }
  ],
  "recommendation": "High pain level - Modify training intensity and focus on affected areas",
  "performance_adjustment_note": "Performance metrics are reduced by 25% due to recent pain..."
}
```

---

## Integration Points

### 1. Assessment Insights Service

**Original Method** (no pain adjustment):
```python
categories = AssessmentInsightsService.parse_for_api(fitness)
```

**With Pain Adjustment**:
```python
categories = AssessmentInsightsService.parse_for_api_with_pain_adjustment(fitness)
```

The new method:
- Calculates pain impact factor
- Applies reduction to current & predicted metrics
- Preserves original values for reference
- Adds pain context to response

### 2. Workout Plan Generation

The `generate_workout_plan` endpoint now includes recent pain logs in the AI prompt:

```python
recent_pain_logs = athlete.pain_logs.order_by('-date')[:3]
if recent_pain_logs.exists():
    # Includes pain data in prompt for auto-regulation
    prompt += "--- ACTIVE PAIN LOGS ---\n"
    for p in recent_pain_logs:
        prompt += f"{p.date}: {p.body_part} - Pain Level {p.pain_level}/10\n"
```

The AI then auto-regulates the workout if pain is significant.

### 3. Reports

Pain impact can be included in athlete performance reports:
```python
pain_context = PerformancePainAdjustmentService.get_performance_context(athlete)
# Add to report data for display
```

---

## Usage Examples

### Python/Django

```python
from athletes.pain_adjustment_service import PerformancePainAdjustmentService
from athletes.models import AthleteInfo

athlete = AthleteInfo.objects.get(id=1)

# Get pain impact data
pain_data = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)

print(f"Impact Factor: {pain_data['impact_factor']}")  # 0.0 to 1.0
print(f"Max Pain: {pain_data['max_pain_level']}/10")
print(f"Body Parts: {pain_data['affected_body_parts']}")
print(f"Recommendation: {pain_data['recommendation']}")

# Adjust a performance metric
original_squat = 100
adjusted_squat = PerformancePainAdjustmentService.adjust_performance_metric(
    original_squat, pain_data
)
print(f"Squat: {original_squat}kg → {adjusted_squat}kg (adjusted for pain)")

# Adjust session rating
original_rating = 8.5
adjusted_rating = PerformancePainAdjustmentService.adjust_session_performance_rating(
    original_rating, pain_data
)
print(f"Rating: {original_rating} → {adjusted_rating} (adjusted for pain)")
```

### REST API

```bash
# 1. View pain-adjusted assessments
curl http://localhost:8000/api/athletes/1/assessments_with_pain/

# 2. Get pain context
curl http://localhost:8000/api/athletes/1/performance_pain_context/

# 3. Original assessments (unchanged)
curl http://localhost:8000/api/athletes/1/assessments/
```

### Frontend Integration

```javascript
// Fetch pain-adjusted performance data
fetch('/api/athletes/1/performance_pain_context/')
  .then(r => r.json())
  .then(data => {
    const { pain_impact, recent_pain_logs, recommendation } = data;
    
    if (pain_impact.percentage_reduction > 0) {
      // Show pain warning
      displayAlert(
        `Performance metrics reduced by ${pain_impact.percentage_reduction}% due to pain`,
        recommendation
      );
    }
    
    // Display recent pain logs
    recent_pain_logs.forEach(log => {
      console.log(`${log.body_part}: ${log.pain_level}/10 (${log.pain_type})`);
    });
  });
```

---

## Data Models

### PainLog Model

```python
class PainLog(models.Model):
    athlete = ForeignKey(AthleteInfo, on_delete=CASCADE)
    date = DateField(default=timezone.localdate)
    body_part = CharField(max_length=100)  # e.g. "Left Knee"
    pain_level = PositiveSmallIntegerField()  # 1-10
    pain_type = CharField(max_length=100)  # e.g. "Sharp", "Dull"
    notes = TextField(blank=True, null=True)
    created_at = DateTimeField(auto_now_add=True)
```

---

## Configuration

Key constants in `PerformancePainAdjustmentService`:

```python
PAIN_SEVERITY_HIGH = 7        # 7-10 pain
PAIN_SEVERITY_MEDIUM = 4      # 4-6 pain
PAIN_SEVERITY_LOW = 1         # 1-3 pain

REDUCTION_HIGH = 0.40         # 40% max reduction
REDUCTION_MEDIUM = 0.20       # 20% max reduction
REDUCTION_LOW = 0.05          # 5% max reduction

RECENT_DAYS = 3               # Consider last 3 days
```

To customize, edit `pain_adjustment_service.py` constants.

---

## Performance Interpretation

### Impact Factor Scale

| Impact Factor | Interpretation | Recommendation |
|---|---|---|
| 0.0 - 0.05 | Minimal | Normal training OK |
| 0.05 - 0.15 | Moderate | Monitor closely, reduce volume |
| 0.15 - 0.30 | High | Reduce intensity and volume |
| 0.30+ | Severe | Major modifications needed, medical evaluation |

---

## Example Scenario

**Athlete**: John (Sprinter)

**Day 1**: Logged 5/10 pain in left hamstring
- Impact factor: ~5%
- Performance reduction: ~5%

**Day 2**: Logged 7/10 pain in left hamstring  
- Impact factor: ~25%
- Performance reduction: ~25%
- Expected squat: 100kg → 75kg (adjusted)
- Session rating: 8.5 → 6.3 (adjusted)
- Recommendation: "Reduce intensity and volume"

**Day 3**: Logged 8/10 pain, added right knee pain
- Impact factor: ~35%
- Performance reduction: ~35%  
- Expected squat: 100kg → 65kg (adjusted)
- Session rating: 8.5 → 5.4 (adjusted)
- Recommendation: "Major modifications needed, medical evaluation"

**Day 4**: No pain logged
- Impact decays to 0% over next 3 days
- Full recovery in expected metrics

---

## Monitoring & Alerts

Track pain-related performance changes:

```python
# Get previous week's performance
prev_adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(
    athlete, reference_date - timedelta(days=7)
)

# Get current
curr_adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)

if curr_adjustment['impact_factor'] > 0.2:
    # Alert coach/athlete about significant pain
    send_alert(f"Significant pain detected: {curr_adjustment['recommendation']}")
```

---

## Testing

```python
from django.test import TestCase
from athletes.models import AthleteInfo, PainLog
from athletes.pain_adjustment_service import PerformancePainAdjustmentService
from datetime import timedelta
from django.utils import timezone

class PainAdjustmentTests(TestCase):
    def setUp(self):
        self.athlete = AthleteInfo.objects.create(
            name="Test Athlete",
            age=20,
            gender="M"
        )
    
    def test_no_pain(self):
        result = PerformancePainAdjustmentService.calculate_pain_impact_factor(
            self.athlete
        )
        assert result['impact_factor'] == 0.0
        assert result['reduction_factor'] == 1.0
    
    def test_high_pain(self):
        PainLog.objects.create(
            athlete=self.athlete,
            body_part="Knee",
            pain_level=9,
            date=timezone.now().date()
        )
        result = PerformancePainAdjustmentService.calculate_pain_impact_factor(
            self.athlete
        )
        assert result['impact_factor'] > 0.2
        assert result['max_pain_level'] == 9
    
    def test_adjustment(self):
        pain_data = {'reduction_factor': 0.75}
        adjusted = PerformancePainAdjustmentService.adjust_performance_metric(
            100, pain_data
        )
        assert adjusted == 75
```

---

## Future Enhancements

1. **Body Part Specificity**: Different pain locations affect different movements
2. **Pain Trajectory**: Analyze if pain is improving or worsening
3. **Concurrent Training Load**: Factor in high volume + high pain = greater risk
4. **ML Predictions**: Predict injury risk based on pain patterns
5. **Recovery Tracking**: Monitor how pain responds to interventions
6. **Sport-Specific Impact**: Tailor adjustments for different sports

---

## Support & Debugging

### Check Recent Pain Logs

```python
athlete = AthleteInfo.objects.get(id=1)
print(athlete.pain_logs.order_by('-date')[:5])
```

### Verify Pain Adjustment

```python
from athletes.pain_adjustment_service import PerformancePainAdjustmentService
adjustment = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)
print(adjustment)
```

### Test API Endpoint

```bash
curl -X GET http://localhost:8000/api/athletes/1/performance_pain_context/ \
  -H "Content-Type: application/json"
```

---

## Related Documentation

- [PainLog Model](../models.py)
- [Assessment Insights Service](../services.py)
- [AthleteInfoViewSet](../views.py)
- [Rest Framework Serializers](../serializers.py)
