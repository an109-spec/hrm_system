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
        id="attendance_17h_checkout_notification_job",
        func=AttendanceJob.run_17h_notification,
        trigger="cron",
        hour=17,
        minute=0
    )
    scheduler.add_job(
        id="attendance_19h_ot_notification_job",
        func=AttendanceJob.run_19h_ot_notification,
        trigger="cron",
        hour=19,
        minute=0
    )
    scheduler.add_job(
        id="attendance_22h_ot_checkout_notification_job",
        func=AttendanceJob.run_22h_ot_checkout_notification,
        trigger="cron",
        hour=22,
        minute=0
    )
    scheduler.add_job(
        id="notification_cleanup_job",
        func=NotificationJob.cleanup_old_notifications,
        trigger="cron",
        hour=2,
        minute=0
   )
    scheduler.add_job(
        id="overtime_shift_notifications_job",
        func=NotificationJob.push_overtime_shift_notifications,
        trigger="cron",
        minute="*"
    )