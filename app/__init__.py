from flask import Flask
from .extensions import db
from app.projects.routes import projects_bp
from app.razmkar.routes import razmkar_bp
from app.dashboard.routes import dashboard_bp
from app.utils.jinja import to_jalali, to_jalali_with_time, to_jalali_detailed
from app.utils.jinja import to_jalali, time_since
from app.utils.jinja import to_jalali, time_since, persian_digits
from app.utils.jinja import highlight_tags

def create_app():
    app = Flask(__name__)
    app.config.from_pyfile('../instance/config.py')

    db.init_app(app)

    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(razmkar_bp)
    app.register_blueprint(dashboard_bp)

    
    app.jinja_env.filters['to_jalali'] = to_jalali
    app.jinja_env.filters['to_jalali_with_time'] = to_jalali_with_time
    app.jinja_env.filters['to_jalali_detailed'] = to_jalali_detailed
    with app.app_context():
        
        db.create_all()


    app.jinja_env.filters['to_jalali'] = to_jalali
    app.jinja_env.filters['time_since'] = time_since


    app.jinja_env.filters['to_jalali'] = to_jalali
    app.jinja_env.filters['time_since'] = time_since
    app.jinja_env.filters['persian_digits'] = persian_digits
    app.jinja_env.filters['to_persian_number'] = persian_digits
    app.jinja_env.filters['highlight_tags'] = highlight_tags

    
        




    return app

