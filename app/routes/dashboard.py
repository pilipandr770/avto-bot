from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..models import PostingLog
from ..extensions import db
from datetime import datetime, timedelta

bp = Blueprint('dashboard', __name__, url_prefix='')


@bp.route('/')
@login_required
def index():
    settings = current_user.settings
    
    # Paginate logs
    page = request.args.get('page', 1, type=int)
    logs_pagination = PostingLog.query.filter_by(user_id=current_user.id).order_by(PostingLog.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    logs = logs_pagination.items
    
    # Calculate stats
    total_logs = PostingLog.query.filter_by(user_id=current_user.id).count()
    sent_count = PostingLog.query.filter_by(user_id=current_user.id, sent_to_channel=True).count()
    error_count = PostingLog.query.filter_by(user_id=current_user.id, sent_to_channel=False).count()
    last_week = PostingLog.query.filter(PostingLog.user_id==current_user.id, PostingLog.created_at >= datetime.utcnow() - timedelta(days=7)).count()
    
    stats = {
        'total': total_logs,
        'sent': sent_count,
        'errors': error_count,
        'last_week': last_week
    }
    
    return render_template('dashboard/index.html', settings=settings, logs=logs, stats=stats, pagination=logs_pagination)


@bp.route('/logs')
@login_required
def logs():
    logs = PostingLog.query.filter_by(user_id=current_user.id).order_by(PostingLog.created_at.desc()).all()
    return render_template('dashboard/logs.html', logs=logs)
