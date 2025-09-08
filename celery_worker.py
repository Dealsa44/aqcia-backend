from celery import Celery

celery_app = Celery("worker", broker="redis://localhost:6379/0")

@celery_app.task
def notify_user(email: str, message: str):
    print(f"Notify {email}: {message}")
 
 