from flask import Blueprint, render_template, redirect, url_for, request, flash
from .models import Project, ProjectStatus, ProjectLog, LogType
from app.extensions import db
from app.razmkar.models import Razmkar
from flask import Blueprint, render_template, request, jsonify


projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/', methods=["GET", "POST"])
def list_projects():
    if request.method == "POST":
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            client_name = request.form.get('client_name')
            goal = request.form.get('goal')
            status_value = request.form.get('status', 'draft')

            try:
                status_enum = ProjectStatus[status_value]
            except KeyError:
                return "وضعیت نامعتبر است", 400

            if not client_name or not goal:
                return "همه فیلدها اجباری هستند", 400

            new_project = Project(client_name=client_name, goal=goal, status=status_enum)
            db.session.add(new_project)
            db.session.commit()
            return "OK", 200

        return "Method Not Allowed", 405

    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('projects/list.html', projects=projects)


@projects_bp.route('/<int:project_id>', methods=['GET', 'POST'])
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        note = request.form.get('note')
        type_ = request.form.get('type')
        created_by = request.form.get('created_by')

        print("📥 مقادیر دریافتی از فرم:")
        print("note:", note)
        print("type:", type_)
        print("created_by:", created_by)

        try:
            log_type = LogType(type_)  # ← تبدیل به Enum معتبر

            log = ProjectLog(
                project_id=project.id,
                note=note,
                type=log_type,
                created_by=created_by
            )
            db.session.add(log)
            db.session.commit()

            print("✅ لاگ با موفقیت ذخیره شد:", log)
            return 'OK', 200

        except ValueError:
            print("❌ مقدار type نامعتبر بود:", type_)
            return 'نوع لاگ نامعتبر است', 400

        except Exception as e:
            print("❌ خطا هنگام ذخیره لاگ:", e)
            return 'خطای داخلی سرور', 500

    return render_template('projects/detail.html', project=project)


@projects_bp.route('/<int:project_id>/delete', methods=['POST', 'DELETE'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    try:
        ProjectLog.query.filter_by(project_id=project.id).delete()
        db.session.delete(project)
        db.session.commit()
        flash(f'پروژه "{project.goal}" با موفقیت حذف شد!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('خطا در حذف پروژه رخ داد. لطفاً دوباره تلاش کنید.', 'danger')
    
    return redirect(url_for('projects.list_projects'))


@projects_bp.route('/create', methods=['GET', 'POST'])
def create_project():
    if request.method == "POST":
        client_name = request.form.get('client_name')
        goal = request.form.get('goal')
        status_value = request.form.get('status', 'draft')

        try:
            status_enum = ProjectStatus[status_value]
        except KeyError:
            flash("وضعیت نامعتبر است", "danger")
            return redirect(url_for('projects.create_project'))

        if not client_name or not goal:
            flash("همه فیلدها الزامی هستند", "warning")
            return redirect(url_for('projects.create_project'))

        new_project = Project(client_name=client_name, goal=goal, status=status_enum)
        db.session.add(new_project)
        db.session.commit()
        flash("پروژه با موفقیت ایجاد شد", "success")
        return redirect(url_for('projects.project_detail', project_id=new_project.id))

    return render_template("projects/create.html")

@projects_bp.route('/<int:project_id>/edit', methods=['POST'])
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    project.client_name = request.form.get('client_name')
    project.goal = request.form.get('goal')
    project.status = ProjectStatus[request.form.get('status')]
    db.session.commit()

    return jsonify({"message": "✅ پروژه با موفقیت ویرایش شد"})


@projects_bp.route('/<int:project_id>/add-log', methods=['POST'])
def add_project_log(project_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    note = request.form.get("note")
    created_by = request.form.get("created_by")
    type_ = request.form.get("type")

    if not note or not type_:
        return "مقدارهای لازم وارد نشده", 400

    try:
        type_enum = LogType[type_]  # ← حالا "note" یا "action" را قبول می‌کند

        new_log = ProjectLog(
            project_id=project_id,
            note=note,
            created_by=created_by,
            type=type_enum
        )
        db.session.add(new_log)
        db.session.commit()

        return jsonify({"message": "لاگ با موفقیت ثبت شد"})
    
    except ValueError:
        return "❌ نوع لاگ نامعتبر است", 400

    except Exception as e:
        print("❌ خطا در افزودن لاگ پروژه:", e)
        return f"خطای سرور: {e}", 500


@projects_bp.route('/log/<int:log_id>')
def get_log(log_id):
    log = ProjectLog.query.get_or_404(log_id)
    return jsonify({
        "note": log.note,
        "created_by": log.created_by,
        "type": log.type.name
    })


@projects_bp.route('/log/<int:log_id>/edit', methods=['POST'])
def edit_log(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    log = ProjectLog.query.get_or_404(log_id)

    note = request.form.get("note")
    created_by = request.form.get("created_by")
    type_ = request.form.get("type")

    if not note or not type_:
        return "❌ اطلاعات ناقص", 400

    try:
        log.note = note
        log.created_by = created_by
        log.type = LogType[type_]
        db.session.commit()
        return jsonify({"message": "ویرایش شد"})
    except Exception as e:
        return f"❌ خطا: {e}", 500


@projects_bp.route('/log/<int:log_id>/delete', methods=['POST'])
def delete_log(log_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return "⛔ درخواست نامعتبر", 400

    log = ProjectLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return jsonify({"message": "حذف شد"})
