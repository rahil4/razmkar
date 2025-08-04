# app/razmkar/routes.py

from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.razmkar.models import Razmkar, RazmkarStatus,RazmkarLog, RazmkarLogType
from app.projects.models import Project
from datetime import datetime
import jdatetime

razmkar_bp = Blueprint('razmkar', __name__, url_prefix='/razmkar')



@razmkar_bp.route('/create', methods=['POST'])
def create_razmkar():
    print('📥 Form data:', request.form)

    # فقط از طریق AJAX اجازه داریم
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return 'روش نامعتبر', 405

    mission = request.form.get('mission')
    note = request.form.get('note')
    due_date_str = request.form.get('due_date')
    status = request.form.get('status', 'pending')
    project_id = request.form.get('project_id')
    parent_id = request.form.get('parent_id')

    if not mission or not project_id:
        return 'ماموریت و شناسه پروژه اجباری هستند', 400

    try:
        # اگر تاریخ وارد شده، آن را از رشته به datetime میلادی تبدیل کن
        due_date = None
        if due_date_str:
            # توجه: کاربر ورودی رو به صورت میلادی وارد کرده
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d')

        status_enum = RazmkarStatus[status]

        new_razmkar = Razmkar(
            mission=mission,
            note=note,
            due_date=due_date,
            status=status_enum,
            project_id=int(project_id),
            parent_id=int(parent_id) if parent_id else None
        )

        db.session.add(new_razmkar)
        db.session.commit()

        return jsonify({'message': 'رزمکار با موفقیت افزوده شد'}), 200

    except ValueError as e:
        return f'خطای مقدار: {e}', 400
    except Exception as e:
        return f'خطای داخلی: {e}', 500


@razmkar_bp.route('/tree/<int:project_id>')
def razmkar_tree(project_id):
    """بازگرداندن HTML ساختار درختی رزمکارها برای پروژه"""
    root_razmkars = Razmkar.query.filter_by(project_id=project_id, parent_id=None).all()
    return render_template('razmkar/_tree.html', razmkars=root_razmkars)




@razmkar_bp.route('/<int:razmkar_id>', methods=['GET', 'POST'])
def razmkar_detail(razmkar_id):
    razmkar = Razmkar.query.get_or_404(razmkar_id)

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        content = request.form.get('content')
        type_ = request.form.get('type')
        created_by = request.form.get('created_by')

        try:
            log_type = RazmkarLogType(type_)
            new_log = RazmkarLog(
                razmkar_id=razmkar.id,
                type=log_type,
                content=content,
                created_by=created_by
            )
            db.session.add(new_log)
            db.session.commit()
            return jsonify({'message': 'لاگ با موفقیت ثبت شد'}), 200

        except ValueError:
            return '❌ نوع لاگ نامعتبر است', 400

        except Exception as e:
            return f'❌ خطای داخلی: {e}', 500

    # GET → نمایش صفحه جزئیات رزمکار
    logs = RazmkarLog.query.filter_by(razmkar_id=razmkar.id).order_by(RazmkarLog.created_at.desc()).all()
    return render_template('razmkar/detail.html', razmkar=razmkar, logs=logs)
