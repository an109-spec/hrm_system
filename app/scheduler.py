import os
from importlib.util import find_spec

def init_scheduler(app):
    if app.config.get("TESTING", False):
        return

    if find_spec("apscheduler") is None:
        return

    from apscheduler.schedulers.background import BackgroundScheduler
    from app.modules.jobs import register_jobs

    scheduler = BackgroundScheduler()
    register_jobs(scheduler)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler.start()
        app.logger.info("APScheduler started.")