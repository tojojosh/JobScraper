"""HTML view routes."""
from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    """Main portal page."""
    return render_template('index.html')
