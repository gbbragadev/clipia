from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery("clipia", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=50,
    beat_schedule={
        "cleanup-old-jobs": {
            "task": "cleanup_old_jobs",
            "schedule": crontab(hour=4, minute=0),
        },
        "cleanup-orphan-files": {
            "task": "cleanup_orphan_files",
            "schedule": crontab(hour=4, minute=30, day_of_week=0),
        },
        "reconcile-undispatched-job-operations": {
            "task": "reconcile_undispatched_job_operations",
            "schedule": timedelta(minutes=10),
        },
        "drain-refine-balance-outbox": {
            "task": "drain_refine_balance_outbox",
            "schedule": timedelta(minutes=10),
        },
        "reconcile-payment-checkout-dispatches": {
            "task": "reconcile_payment_checkout_dispatches",
            "schedule": timedelta(minutes=5),
        },
        "reconcile-credit-ledger": {
            "task": "reconcile_credit_ledger",
            "schedule": crontab(hour=5, minute=0),
        },
    },
)

celery_app.autodiscover_tasks(["app.worker"])
