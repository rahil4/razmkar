from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired
from .models import ProjectStatus, LogType

class ProjectForm(FlaskForm):
    goal = StringField('هدف پروژه', validators=[DataRequired()])
    client_name = StringField('نام کارفرما', validators=[DataRequired()])
    status = SelectField('وضعیت', choices=[(status.value, status.name) for status in ProjectStatus])
    submit = SubmitField('ایجاد')

class LogForm(FlaskForm):
    note = TextAreaField('متن لاگ', validators=[DataRequired()])
    type = SelectField('نوع لاگ', choices=[(t.value, t.name) for t in LogType])
    created_by = StringField('ایجادکننده')
    submit = SubmitField('افزودن لاگ')
