# pyrefly: ignore [missing-import]
from locust import HttpUser, task, between

class DasherAPIUser(HttpUser):
    # Simulates a user waiting 1 to 5 seconds between tasks
    wait_time = between(1, 5)

    @task(3)
    def get_athletes(self):
        """Simulate a user viewing the athletes list"""
        # The endpoints defined in athletes/urls.py are under /api/
        with self.client.get("/api/athletes/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in [401, 403]:
                # If it's unauthenticated, we still consider it a successful "hit"
                # to the server for load testing purposes, unless we specifically
                # wanted to test only authenticated responses.
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(2)
    def get_fitness_data(self):
        """Simulate a user viewing fitness data"""
        with self.client.get("/api/fitness/", catch_response=True) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(1)
    def get_swimming_data(self):
        """Simulate a user viewing swimming data"""
        with self.client.get("/api/swimming/", catch_response=True) as response:
            if response.status_code in [200, 401, 403]:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")
