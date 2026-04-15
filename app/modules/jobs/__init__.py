from .attendance_job import AttendanceJob
from .notification_job import NotificationJob


def register_jobs(scheduler):
    """
    Gắn job vào scheduler (APScheduler / Celery beat)
    """
    scheduler.add_job(
        id="attendance_daily_job",
        func=AttendanceJob.run_daily,
        trigger="cron",
        hour=23,
        minute=59
    )

    scheduler.add_job(
        id="notification_cleanup_job",
        func=NotificationJob.cleanup_old_notifications,
        trigger="cron",
        hour=2,
        minute=0
    )