from datetime import timedelta

from rest_framework import serializers

from .models import AthleteInfo, Owner, Fitness, Swimming, Basketball, Football, CrossFit, AttendanceRecord, InjuryRecord, PainLog

SWIM_SECOND_EVENTS = {'50m'}
SWIM_MINUTE_EVENTS = {'100m', '200m', '400m', '800m', '1500m'}
SWIM_HOUR_EVENTS = {'5km', '10km', '25km'}


def _format_split_timedelta(value):
    if value in (None, ''):
        return None

    total_seconds = value.total_seconds() if hasattr(value, 'total_seconds') else float(value)
    total_seconds = max(0, float(total_seconds))

    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    second_text = f"{seconds:05.2f}"

    if minutes > 0:
        return f"{minutes}:{second_text}"
    return second_text

def _parse_split_duration(value):
    if value in (None, ''):
        return None
    if isinstance(value, timedelta):
        return value

    raw = str(value).strip()
    if raw.lower().endswith('s'):
        raw = raw[:-1].strip()

    if not raw:
        return None

    if ':' in raw:
        parts = raw.split(':')
        try:
            if len(parts) == 2:
                return timedelta(minutes=int(parts[0]), seconds=float(parts[1]))
            elif len(parts) == 3:
                return timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=float(parts[2]))
        except ValueError as exc:
            raise serializers.ValidationError('Invalid split time format.') from exc

    try:
        numeric_value = float(raw)
        return timedelta(seconds=numeric_value)
    except ValueError as exc:
        raise serializers.ValidationError('Invalid split time format.') from exc

def _format_swim_timedelta(value, event_name):
    if value in (None, ''):
        return None

    total_seconds = value.total_seconds() if hasattr(value, 'total_seconds') else float(value)
    total_seconds = max(0, float(total_seconds))

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    second_text = f"{seconds:05.2f}"

    if event_name in SWIM_HOUR_EVENTS:
        return f"{hours}:{minutes:02d}:{second_text}"
    if event_name in SWIM_MINUTE_EVENTS:
        total_minutes = int(total_seconds // 60)
        return f"{total_minutes}:{second_text}"
    return second_text


def _parse_buggy_decimal_clock(text, event_name):
    raw = str(text).strip()
    if '.' not in raw:
        return None

    left, right = raw.split('.', 1)
    if not left.isdigit() or not right.isdigit():
        return None

    if event_name in SWIM_MINUTE_EVENTS:
        minutes = int(left)
        seconds = int((right[:2] or '0').ljust(2, '0'))
        hundredths = int((right[2:4] or '0').ljust(2, '0'))
        return timedelta(minutes=minutes, seconds=seconds, milliseconds=hundredths * 10)

    if event_name in SWIM_HOUR_EVENTS:
        hours = int(left)
        minutes = int((right[:2] or '0').ljust(2, '0'))
        seconds = int((right[2:4] or '0').ljust(2, '0'))
        return timedelta(hours=hours, minutes=minutes, seconds=seconds)

    return None


def _parse_swim_duration(value, event_name):
    if value in (None, ''):
        return None
    if isinstance(value, timedelta):
        return value

    raw = str(value).strip()
    if not raw:
        return None

    if ':' in raw:
        parts = raw.split(':')
        try:
            if event_name in SWIM_HOUR_EVENTS and len(parts) == 3:
                return timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=float(parts[2]))
            if event_name in SWIM_MINUTE_EVENTS and len(parts) == 2:
                return timedelta(minutes=int(parts[0]), seconds=float(parts[1]))
            if event_name in SWIM_SECOND_EVENTS and len(parts) == 1:
                return timedelta(seconds=float(parts[0]))
        except ValueError as exc:
            raise serializers.ValidationError('Invalid swimming time format.') from exc

    decimal_clock = _parse_buggy_decimal_clock(raw, event_name)
    if decimal_clock is not None:
        return decimal_clock

    try:
        numeric_value = float(raw)
    except ValueError as exc:
        raise serializers.ValidationError('Invalid swimming time format.') from exc

    if event_name in SWIM_HOUR_EVENTS:
        return timedelta(hours=numeric_value)
    if event_name in SWIM_MINUTE_EVENTS:
        return timedelta(minutes=numeric_value)
    return timedelta(seconds=numeric_value)

class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = '__all__'


class InjuryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = InjuryRecord
        fields = '__all__'

class PainLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PainLog
        fields = '__all__'


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = '__all__'

class FitnessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fitness
        fields = '__all__'

class SwimmingSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        mutable = data.copy()
        event_name = mutable.get('events')

        if event_name:
            for field_name in ('current_record', 'previous_record', 'expected_record'):
                if field_name in mutable and mutable.get(field_name) not in (None, ''):
                    mutable[field_name] = _parse_swim_duration(mutable.get(field_name), event_name)
            
            # Handle splits_data durations
            splits_data = mutable.get('splits_data')
            if splits_data and isinstance(splits_data, list):
                for split in splits_data:
                    # Auto-calculate expected if missing
                    curr_td = _parse_split_duration(split.get('current'))
                    prev_td = _parse_split_duration(split.get('previous'))
                    exp_val = split.get('expected')

                    if curr_td and (not exp_val or exp_val == ''):
                        if prev_td and prev_td > curr_td:
                            # Use improvement trend: Expected = Current - (Previous - Current)
                            diff = prev_td - curr_td
                            exp_td = curr_td - diff
                        else:
                            # Fallback to 5% improvement
                            exp_td = timedelta(seconds=curr_td.total_seconds() * 0.95)
                        split['expected'] = _format_split_timedelta(exp_td)

                    for field in ('current', 'previous', 'expected'):
                        if field in split and split[field] not in (None, ''):
                            # Normalize split times to formatted strings
                            parsed = _parse_split_duration(split[field])
                            if parsed:
                                split[field] = _format_split_timedelta(parsed)
                mutable['splits_data'] = splits_data

        return super().to_internal_value(mutable)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        event_name = ret.get('events')

        for field_name in ('current_record', 'previous_record', 'expected_record'):
            raw_value = getattr(instance, field_name, None)
            ret[field_name] = _format_swim_timedelta(raw_value, event_name) if raw_value else None

        return ret

    class Meta:
        model = Swimming
        fields = '__all__'

class BasketballSerializer(serializers.ModelSerializer):
    class Meta:
        model = Basketball
        fields = '__all__'

class FootballSerializer(serializers.ModelSerializer):
    class Meta:
        model = Football
        fields = '__all__'

class CrossFitSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrossFit
        fields = '__all__'

class AthleteInfoSerializer(serializers.ModelSerializer):
    fitness_profile = FitnessSerializer(read_only=True)
    swimming_records = SwimmingSerializer(many=True, read_only=True)
    basketball_records = BasketballSerializer(many=True, read_only=True)
    football_records = FootballSerializer(many=True, read_only=True)
    crossfit_records = CrossFitSerializer(many=True, read_only=True)
    attendance_records = AttendanceRecordSerializer(many=True, read_only=True)
    injury_records = InjuryRecordSerializer(many=True, read_only=True)
    pain_logs = PainLogSerializer(many=True, read_only=True)

    class Meta:
        model = AthleteInfo
        fields = [
            'id', 'name', 'age', 'gender', 'height', 'weight', 'body_type', 'date_of_birth', 'academy_since',
            'strengths', 'weaknesses', 'created_at', 'updated_at',
            'is_subscribed', 'subscription_fee', 'subscription_start_date', 'subscription_end_date',
            'fitness_profile', 'swimming_records', 'basketball_records', 
            'football_records', 'crossfit_records', 'attendance_records', 'injury_records', 'pain_logs'
        ]
        read_only_fields = ['academy_since']

    def to_representation(self, instance):
        """
        Overridden to ensure all nested records are properly represented.
        """
        ret = super().to_representation(instance)
        return ret
