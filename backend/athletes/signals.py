from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Owner, Swimming, Fitness
from .services import PredictorService

@receiver(post_save, sender=Owner)
def predict_owner_revenue_on_save(sender, instance, created, **kwargs):
    # Avoid infinite recursion when saving updated prediction
    if kwargs.get('update_fields') and 'expected_revenue' in kwargs.get('update_fields'):
        return
        
    predicted_revenue = PredictorService.predict_business_revenue(instance)
    
    if predicted_revenue is not None:
        instance.expected_revenue = predicted_revenue
        instance.save(update_fields=['expected_revenue'])

@receiver(post_save, sender=Swimming)
def predict_swimming_record_on_save(sender, instance, created, **kwargs):
    if kwargs.get('update_fields') and 'expected_record' in kwargs.get('update_fields'):
        return
        
    predicted_record = PredictorService.predict_athlete_swimming_record(instance)
    
    if predicted_record is not None:
        instance.expected_record = predicted_record
        instance.save(update_fields=['expected_record'])

@receiver(post_save, sender=Fitness)
def predict_fitness_results_on_save(sender, instance, created, **kwargs):
    if kwargs.get('update_fields') and 'expected_fitness_results' in kwargs.get('update_fields'):
        return
        
    predicted_results = PredictorService.predict_json_fitness_results(instance)
    
    if predicted_results:
        instance.expected_fitness_results = predicted_results
        instance.save(update_fields=['expected_fitness_results'])
