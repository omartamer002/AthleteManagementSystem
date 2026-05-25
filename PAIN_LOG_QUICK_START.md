# Quick Start: Pain Log Integration

## What's New

The Performance Intelligence Center now automatically adjusts athlete performance metrics based on recent pain. When an athlete experiences pain, their expected performance and assessment scores are reduced to reflect reality.

## Three Ways to Use It

### 1. **For Frontend Developers** - Use the new API endpoints

```bash
# Get pain-adjusted assessment metrics
curl http://localhost:3000/api/athletes/1/assessments_with_pain/

# Get pain impact summary with recent pain logs
curl http://localhost:3000/api/athletes/1/performance_pain_context/
```

### 2. **For Backend Developers** - Use the service directly

```python
from athletes.pain_adjustment_service import PerformancePainAdjustmentService
from athletes.models import AthleteInfo

athlete = AthleteInfo.objects.get(id=1)

# Get pain impact factor (0.0 = no pain, 1.0 = severe)
pain_data = PerformancePainAdjustmentService.calculate_pain_impact_factor(athlete)

# Apply to a metric
original_squat = 100  # kg
adjusted_squat = PerformancePainAdjustmentService.adjust_performance_metric(
    original_squat, pain_data
)

# Apply to session rating
original_rating = 8.5  # out of 10
adjusted_rating = PerformancePainAdjustmentService.adjust_session_performance_rating(
    original_rating, pain_data
)
```

### 3. **For Coaches** - View in the UI

1. Go to athlete profile
2. Look for performance metrics section
3. If pain is detected, you'll see:
   - ⚠️ Pain warning with % impact
   - Adjusted performance targets
   - Recent pain logs
   - Coaching recommendation (e.g., "Reduce intensity")

---

## How Pain Affects Performance

| Pain Level | Body Impact | Performance Reduction | Coaching Action |
|---|---|---|---|
| **0-2** (None/Minimal) | No effect | 0-5% | Train normally |
| **3-5** (Low) | Minor discomfort | 5-10% | Monitor, continue training |
| **6-7** (Moderate) | Noticeable pain | 15-25% | Reduce volume, maintain technique |
| **8-10** (Severe) | Significant pain | 30-40%+ | Major modifications needed |

---

## Example: Real World Scenario

**Athlete: Sarah (Swimmer)**

**Tuesday - Normal Day**
- No pain logged
- Expected 100m time: 65.0 seconds
- Session rating expectation: 8.0/10

**Wednesday - Pain Detected**
- Logged 6/10 pain in right shoulder
- Pain factor: 15%
- Adjusted expectations:
  - Expected 100m time: 65.0 × 1.15 = 74.8 seconds (1.8s slower)
  - Session rating: 8.0 × 0.85 = 6.8/10
  - Recommendation: "Reduce volume, focus on technique"

**Thursday - Pain Getting Worse**
- Logged 8/10 pain in right shoulder
- Pain factor: 30%  
- New expectations:
  - Expected 100m time: 65.0 × 1.30 = 84.5 seconds (3.8s slower)
  - Session rating: 8.0 × 0.70 = 5.6/10
  - Recommendation: "Major modifications, reduce intensity significantly"

**Friday - Recovery**
- No new pain logged, yesterday's pain impact decays
- Pain factor: 15% (3 days old, fading)
- Gradual return to normal expectations

---

## Key Features Explained

### Pain Recency
Pain from today has 100% impact. This decays linearly over 3 days:
- Today: Full impact
- 1 day ago: 67% impact
- 2 days ago: 33% impact  
- 3+ days ago: Minimal impact

### Multiple Pain Locations
If athlete has pain in multiple areas:
- Each pain contributes to the overall impact factor
- Impact is averaged across all pain logs
- Recommendation considers all affected areas

### Automatic Coaching Guidance
System generates recommendations:
- Low pain: "Normal training OK"
- Moderate pain: "Reduce volume, maintain technique"
- High pain: "Reduce intensity and volume"
- Severe pain: "Major modifications needed, medical evaluation"

---

## Testing It Out

1. **Add Pain to an Athlete**
   - Go to athlete profile
   - Add pain log: "Left Knee, 7/10, Sharp pain"
   - Save

2. **Check the Impact**
   - API: `GET /api/athletes/{id}/performance_pain_context/`
   - Should show ~25% reduction in performance

3. **Generate Adjusted Plan**
   - Use `POST /api/athletes/{id}/generate_workout_plan/`
   - AI will see the pain and auto-regulate the plan
   - Should get modified/lighter workout

---

## Configuration

To customize pain thresholds, edit `pain_adjustment_service.py`:

```python
PAIN_SEVERITY_HIGH = 7        # Change to 8 for stricter threshold
PAIN_SEVERITY_MEDIUM = 4      # Lower to 3 for more sensitivity
REDUCTION_HIGH = 0.40         # Change to 0.50 for 50% max reduction
RECENT_DAYS = 3               # Change to 7 for weekly tracking
```

---

## API Response Examples

### `assessments_with_pain` Response

```json
{
  "categories": [
    {
      "label": "Strength Assessments",
      "metrics": [
        {
          "current": 90.0,
          "original_current": 100.0,
          "pain_adjusted": true,
          "pain_impact_pct": 10.0
        }
      ],
      "pain_context": {
        "impact_factor": 0.10,
        "interpretation": "Minimal - Normal training OK"
      }
    }
  ]
}
```

### `performance_pain_context` Response

```json
{
  "pain_impact": {
    "percentage_reduction": 25.0,
    "interpretation": "High - Reduce intensity and volume"
  },
  "recent_pain_logs": [
    {
      "date": "2026-05-04",
      "body_part": "Right Knee",
      "pain_level": 8
    }
  ],
  "recommendation": "High pain - Modify training intensity..."
}
```

---

## Troubleshooting

**Q: Pain data not showing up?**
A: Check if pain logs were created for the last 3 days. Use:
```python
athlete.pain_logs.filter(date__gte=timezone.now().date() - timedelta(days=3))
```

**Q: Performance not being adjusted?**
A: Make sure you're using `assessments_with_pain` endpoint, not the regular `assessments` endpoint.

**Q: Adjustment seems too aggressive/mild?**
A: Adjust the `REDUCTION_*` constants in `pain_adjustment_service.py`.

---

## Related Files

- **Main Service**: `backend/athletes/pain_adjustment_service.py`
- **API Endpoints**: `backend/athletes/views.py` (lines with `@action(detail=True)`)
- **Documentation**: `PAIN_LOG_INTEGRATION.md`
- **Models**: `backend/athletes/models.py` (PainLog model)

---

## Next Steps

1. ✅ Integration complete
2. 🔄 Test with real athletes and pain data
3. 📊 Monitor how coaches use the feature
4. 🎯 Consider adding body-part specific adjustments
5. 🤖 Explore ML predictions for injury risk

---

**Questions?** Refer to `PAIN_LOG_INTEGRATION.md` for detailed technical documentation.
