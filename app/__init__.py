import os
from flask import Flask
from .config import Config
from .extensions import db, migrate, login_manager, scheduler
from sqlalchemy import event


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Ensure DB schema search_path set for every new connection
    schema = app.config.get("DB_SCHEMA")

    def set_search_path(dbapi_connection, connection_record):
        if schema:
            try:
                cur = dbapi_connection.cursor()
                cur.execute(f"SET search_path TO {schema}, public")
                cur.close()
            except Exception:
                pass

    try:
        engine = db.get_engine(app)
        event.listen(engine, "connect", set_search_path)
    except Exception:
        # if engine isn't available yet, skip attaching listener
        pass

    # Register blueprints
    from .routes.auth import bp as auth_bp
    from .routes.dashboard import bp as dash_bp
    from .routes.settings import bp as settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(settings_bp)

    # Start scheduler
    try:
        scheduler.start()
    except Exception:
        # scheduler may already be running in some environments
        pass
    # schedule check_all_inboxes job using app context
    try:
        from .tasks import check_all_inboxes
        # add job that calls check_all_inboxes with current app
        scheduler.add_job(func=lambda: check_all_inboxes(app), trigger='interval', minutes=3, id='check_all_inboxes', replace_existing=True)
    except Exception:
        pass

    return app


# Import tasks to register job functions
from . import tasks  # noqa: E402
