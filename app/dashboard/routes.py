# app/dashboard/routes.py
from flask import Blueprint, render_template
from datetime import date, timedelta
from app.razmkar.models import Razmkar, RazmkarStatus
from app.projects.models import Project
from app.extensions import db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    today = date.today()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=6 - today.weekday())

    base_query = Razmkar.query.filter(Razmkar.status != RazmkarStatus.done)

    today_list = base_query.filter(db.func.date(Razmkar.due_date) == today).all()
    tomorrow_list = base_query.filter(db.func.date(Razmkar.due_date) == tomorrow).all()
    week_list = base_query.filter(db.func.date(Razmkar.due_date).between(today, week_end)).all()
    overdue_list = base_query.filter(db.func.date(Razmkar.due_date) < today).all()
    
    # دریافت لیست پروژه‌ها برای modal افزودن سریع
    projects = Project.query.order_by(Project.created_at.desc()).limit(10).all()

    return render_template('dashboard/index.html',
                           today_list=today_list,
                           tomorrow_list=tomorrow_list,
                           week_list=week_list,
                           overdue_list=overdue_list,
                           projects=projects)
