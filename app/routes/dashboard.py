from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import PostingLog
from ..extensions import db

bp = Blueprint('dashboard', __name__, url_prefix='')


@bp.route('/')
@login_required
def index():
    settings = current_user.settings
    logs = PostingLog.query.filter_by(user_id=current_user.id).order_by(PostingLog.created_at.desc()).limit(20).all()
    return render_template('dashboard/index.html', settings=settings, logs=logs)


@bp.route('/logs')
@login_required
def logs():
    logs = PostingLog.query.filter_by(user_id=current_user.id).order_by(PostingLog.created_at.desc()).all()
    return render_template('dashboard/logs.html', logs=logs)
