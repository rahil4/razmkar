# app/razmkar/routes.py

from flask import Blueprint, request, jsonify, render_template,current_app, send_from_directory
from app.extensions import db
from app.razmkar.models import Razmkar, RazmkarStatus,RazmkarLog, RazmkarLogType
from app.projects.models import Project
from datetime import datetime
import jdatetime
import os, uuid
from werkzeug.utils import secure_filename



razmkar_bp = Blueprint('razmkar', __name__, url_prefix='/razmkar')

# ----- helpers (module-level) -----
def _allowed_file(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return ext in allowed

def _ensure_upload_root():
    upload_root = current_app.config.get('UPLOAD_FOLDER')
    if not upload_root:
        # fallback اگر در config ست نشده بود
        upload_root = os.path.join(current_app.instance_path, 'uploads')
        current_app.config['UPLOAD_FOLDER'] = upload_root
    os.makedirs(upload_root, exist_ok=True)
    return upload_root
# -----------------------------------


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

    if new_status not in RazmkarStatus.__members__:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400

    task.status = RazmkarStatus[new_status]  # ← این خط تغییر کرد
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


import shutil

@razmkar_bp.route('/<int:razmkar_id>/delete', methods=['POST'])
def delete_razmkar(razmkar_id):
    razmkar = Razmkar.query.get_or_404(razmkar_id)

    # پاکسازی دایرکتوری آپلود این رزمکار (اختیاری)
    try:
        upload_root = _ensure_upload_root()
        task_dir = os.path.join(upload_root, 'razmkar', str(razmkar_id))
        if os.path.isdir(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
    except Exception:
        # اگر حذف پوشه شکست خورد، ادامه می‌دهیم
        pass

    db.session.delete(razmkar)
    db.session.commit()
    return jsonify({'message': 'ماموریت حذف شد'})






    


@razmkar_bp.route('/<int:razmkar_id>/add-log', methods=['POST'])
def add_log(razmkar_id):
    # فقط از طریق AJAX مجاز
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'message': 'درخواست نامعتبر است'}), 400

    content = request.form.get('content')  # می‌تواند خالی باشد اگر فایل هست
    type_ = request.form.get('type')       # مثل note/action/... یا file_upload
    created_by = request.form.get('created_by')
    file_obj = request.files.get('file')

    # اگر نه محتوا هست نه فایل، خطا
    if (not content or content.strip() == '') and (not file_obj or file_obj.filename.strip() == ''):
        return jsonify({'message': 'حداقل یکی از «متن لاگ» یا «فایل» لازم است'}), 400

    # اعتبارسنجی نوع (اگر نیامده و فایل هست، بعداً تبدیلش می‌کنیم؛ ولی فعلاً بررسی شود)
    try:
        if type_:
            log_type = RazmkarLogType[type_]
        else:
            # اگر نوع نیامده و فایل هست، بعداً file_upload می‌کنیم؛ فعلاً placeholder:
            log_type = RazmkarLogType.note
    except Exception:
        return jsonify({'message': '❌ نوع لاگ نامعتبر است'}), 400

    # اگر فایل آمده و پسوند مجاز نیست
    if file_obj and file_obj.filename and not _allowed_file(file_obj.filename):
        return jsonify({'message': '❌ فرمت فایل مجاز نیست'}), 400

    try:
        # مرحله 1: ساخت لاگ اولیه (بدون file_path) تا id ایجاد شود
        new_log = RazmkarLog(
            razmkar_id=razmkar_id,
            type=log_type,
            content=content,
            created_by=created_by
        )
        db.session.add(new_log)
        db.session.commit()

        # مرحله 2: اگر فایل داریم، ذخیره و ثبت file_path
        if file_obj and file_obj.filename:
            upload_root = _ensure_upload_root()
            # مسیر ذخیره: uploads/razmkar/<razmkar_id>/logs/<log_id>/
            target_dir = os.path.join(upload_root, 'razmkar', str(razmkar_id), 'logs', str(new_log.id))
            os.makedirs(target_dir, exist_ok=True)

            original = secure_filename(file_obj.filename)
            ext = original.rsplit('.', 1)[1].lower() if '.' in original else ''
            stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

            abs_path = os.path.join(target_dir, stored)
            file_obj.save(abs_path)

            # مسیر نسبی نسبت به UPLOAD_FOLDER در DB نگه می‌داریم
            rel_path = os.path.relpath(abs_path, upload_root)
            new_log.file_path = rel_path

            # اگر نوع چیز دیگری بود و فایل داریم، به file_upload تغییر دهیم (طبق نیاز تو)
            if new_log.type != RazmkarLogType.file_upload:
                new_log.type = RazmkarLogType.file_upload

            db.session.commit()

        return jsonify({'message': '✅ لاگ با موفقیت ثبت شد', 'log_id': new_log.id}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'❌ خطای داخلی: {str(e)}'}), 500



@razmkar_bp.route('/log/<int:log_id>/upload-file', methods=['POST'])
def upload_file_for_log(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'message': 'درخواست نامعتبر'}), 400

    lg = RazmkarLog.query.get_or_404(log_id)
    file_obj = request.files.get('file')
    if not file_obj or not file_obj.filename:
        return jsonify({'message': 'فایلی انتخاب نشده است'}), 400
    if not _allowed_file(file_obj.filename):
        return jsonify({'message': '❌ فرمت فایل مجاز نیست'}), 400

    try:
        upload_root = _ensure_upload_root()
        target_dir = os.path.join(upload_root, 'razmkar', str(lg.razmkar_id), 'logs', str(lg.id))
        os.makedirs(target_dir, exist_ok=True)

        # اگر قبلاً فایل داشت، حذف شود
        if lg.file_path:
            old_abs = os.path.join(upload_root, lg.file_path)
            if os.path.exists(old_abs):
                try: os.remove(old_abs)
                except: pass

        original = secure_filename(file_obj.filename)
        ext = original.rsplit('.', 1)[1].lower() if '.' in original else ''
        stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        abs_path = os.path.join(target_dir, stored)
        file_obj.save(abs_path)

        lg.file_path = os.path.relpath(abs_path, upload_root)
        if lg.type != RazmkarLogType.file_upload:
            lg.type = RazmkarLogType.file_upload

        db.session.commit()
        return jsonify({'message': '✅ فایل بارگذاری شد'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'❌ خطا در آپلود: {str(e)}'}), 500



@razmkar_bp.route('/log/<int:log_id>/download', methods=['GET'])
def download_log_file(log_id):
    lg = RazmkarLog.query.get_or_404(log_id)
    if not lg.file_path:
        return jsonify({'message': '❌ فایلی برای این لاگ ثبت نشده است'}), 404

    upload_root = _ensure_upload_root()
    abs_path = os.path.join(upload_root, lg.file_path)
    if not os.path.exists(abs_path):
        return jsonify({'message': '❌ فایل یافت نشد'}), 404

    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    # اگر نام دانلود خاص می‌خواهی، می‌توانی از محتوای content استخراج کنی
    return send_from_directory(directory=directory, path=filename, as_attachment=True)


@razmkar_bp.route('/log/<int:log_id>/delete-file', methods=['POST'])
def delete_log_file(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'message': 'درخواست نامعتبر'}), 400

    lg = RazmkarLog.query.get_or_404(log_id)
    if not lg.file_path:
        return jsonify({'message': 'فایلی برای حذف وجود ندارد'}), 400

    upload_root = _ensure_upload_root()
    abs_path = os.path.join(upload_root, lg.file_path)

    try:
        if os.path.exists(abs_path):
            os.remove(abs_path)
        lg.file_path = None
        db.session.commit()
        return jsonify({'message': '🗑️ فایل حذف شد'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'❌ خطا در حذف فایل: {str(e)}'}), 500


@razmkar_bp.route('/log/<int:log_id>/edit', methods=['POST'])
def edit_log(log_id):
    log = RazmkarLog.query.get_or_404(log_id)
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'message': 'درخواست نامعتبر'}), 400

    try:
        log.content = request.form.get('content')
        log.created_by = request.form.get('created_by')
        type_in = request.form.get('type')
        if type_in:
            log.type = RazmkarLogType(type_in)

        # --- پشتیبانی از فایل در ویرایش (اختیاری)
        file_obj = request.files.get('file')
        if file_obj and file_obj.filename:
            if not _allowed_file(file_obj.filename):
                return jsonify({'message': '❌ فرمت فایل مجاز نیست'}), 400

            upload_root = _ensure_upload_root()
            target_dir = os.path.join(upload_root, 'razmkar', str(log.razmkar_id), 'logs', str(log.id))
            os.makedirs(target_dir, exist_ok=True)

            # حذف فایل قبلی
            if log.file_path:
                old_abs = os.path.join(upload_root, log.file_path)
                if os.path.exists(old_abs):
                    try: os.remove(old_abs)
                    except: pass

            original = secure_filename(file_obj.filename)
            ext = original.rsplit('.', 1)[1].lower() if '.' in original else ''
            stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
            abs_path = os.path.join(target_dir, stored)
            file_obj.save(abs_path)
            log.file_path = os.path.relpath(abs_path, upload_root)

            if log.type != RazmkarLogType.file_upload:
                log.type = RazmkarLogType.file_upload

        db.session.commit()
        return jsonify({'message': '✅ لاگ با موفقیت ویرایش شد'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'❌ خطا: {str(e)}'}), 500

@razmkar_bp.route('/log/<int:log_id>/delete', methods=['POST'])
def delete_log(log_id):
    # فقط Ajax
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'message': 'درخواست نامعتبر'}), 400

    lg = RazmkarLog.query.get_or_404(log_id)

    # حذف فایل روی دیسک اگر وجود دارد
    try:
        if lg.file_path:
            upload_root = _ensure_upload_root()
            abs_path = os.path.join(upload_root, lg.file_path)
            if os.path.exists(abs_path):
                try:
                    os.remove(abs_path)
                except Exception:
                    # حتی اگر حذف فایل شکست خورد، ادامه می‌دهیم تا رکورد DB پاک شود
                    pass

        db.session.delete(lg)
        db.session.commit()
        return jsonify({'message': '🗑 لاگ حذف شد'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'❌ خطا در حذف لاگ: {str(e)}'}), 500
