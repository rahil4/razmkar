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

    # گرفتن لاگ‌ها
    logs = RazmkarLog.query.filter_by(razmkar_id=razmkar.id).order_by(RazmkarLog.created_at.desc()).all()

    # گرفتن مسیر والدها (breadcrumb)
    def get_razmkar_ancestors(r):
        ancestors = []
        current = r.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    ancestors = get_razmkar_ancestors(razmkar)

    return render_template(
        'razmkar/detail.html',
        razmkar=razmkar,
        logs=logs,
        ancestors=ancestors
    )


@razmkar_bp.route('/<int:task_id>/update_status_ajax', methods=['POST'])
def update_status_ajax(task_id):
    task = Razmkar.query.get_or_404(task_id)
    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ['pending', 'in_progress', 'done', 'cancelled']:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400

    task.status = new_status
    db.session.commit()
    return jsonify({'success': True})

@razmkar_bp.route('/<int:razmkar_id>/edit', methods=['POST'])
def edit_razmkar(razmkar_id):
    razmkar = Razmkar.query.get_or_404(razmkar_id)

    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'message': 'درخواست نامعتبر'}), 400

    # دریافت اطلاعات
    mission = request.form.get('mission')
    note = request.form.get('note')
    due_date = request.form.get('due_date')
    status = request.form.get('status')

    # اعتبارسنجی وضعیت
    if status not in RazmkarStatus.__members__:
        return jsonify({'message': 'وضعیت نامعتبر است'}), 400

    # اعمال تغییرات
    razmkar.mission = mission
    razmkar.note = note

    if due_date:
        try:
            razmkar.due_date = datetime.strptime(due_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'فرمت تاریخ نادرست است'}), 400
    else:
        razmkar.due_date = None

    razmkar.status = RazmkarStatus[status]

    db.session.commit()
    return jsonify({'message': 'ماموریت با موفقیت ویرایش شد'})


@razmkar_bp.route('/<int:razmkar_id>/delete', methods=['POST'])
def delete_razmkar(razmkar_id):
    razmkar = Razmkar.query.get_or_404(razmkar_id)
    db.session.delete(razmkar)
    db.session.commit()
    return jsonify({'message': 'ماموریت حذف شد'})
