import os
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from datetime import datetime  # <-- Already imported, just confirming
from sqlalchemy import func

from utils.db import db
from models.attendance import Attendance
from models.user import User
from models.class_model import Class
from utils.auth_middleware import requires_auth, requires_role

teacher_bp = Blueprint('teacher_bp', __name__)

# --- ALLOWED EXTENSIONS (For File Upload) ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ROUTE 1: FILE UPLOAD (Modified) ---
@teacher_bp.route('/upload_class_photo', methods=['POST'])
@requires_auth
@requires_role('teacher')
def upload_class_photo():
    """
    Handles the file upload for a teacher's class photo.
    Saves the file to the UPLOAD_FOLDER with a unique timestamped name.
    """
    if 'class_photo' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['class_photo']

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        
        # --- MODIFICATION START ---
        # Get the original filename to extract the extension
        original_filename = file.filename
        
        # Use os.path.splitext to reliably get the extension (e.g., '.jpg')
        _ , file_extension = os.path.splitext(original_filename)
        
        # Generate a unique timestamp (YYYYMMDD_HHMMSS_microseconds)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Create the new, unique filename
        # We run this final string through secure_filename as a last safety check
        filename = secure_filename(f"{timestamp}{file_extension}")
        # --- MODIFICATION END ---
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        save_path = os.path.join(upload_folder, filename)
        
        try:
            file.save(save_path)
            
            # The JSON response now includes the new unique filename
            return jsonify({
                "message": "File uploaded successfully", 
                "filename": filename,
                "path": f"/uploads/class_images/{filename}"
            }), 200
        
        except Exception as e:
            return jsonify({"error": f"Failed to save file: {str(e)}"}), 500
    else:
        return jsonify({"error": "File type not allowed"}), 400

# --- ROUTE 2: MARK ATTENDANCE (No changes) ---
@teacher_bp.route('/mark-attendance', methods=['POST'])
@requires_auth
@requires_role('teacher')
def mark_attendance():
    """
    Receives attendance data (from face rec) and saves it.
    This route now handles date, calculates absentees, and
    prevents duplicate records (it will update an existing record).
    """
    data = request.json
    
    # 1. Validate required fields
    class_id = data.get('class_id')
    present_student_ids = data.get('present_students', [])
    date_str = data.get('date') # e.g., "2025-11-09"
    image_path = data.get('image_path')
    
    if not class_id or not date_str:
        return jsonify({"error": "Missing 'class_id' or 'date'"}), 400

    try:
        # Convert date string to a Python date object
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    # 2. Get all students for this class
    all_students = User.query.filter_by(class_id=class_id, role='student').all()
    if not all_students:
        return jsonify({"error": "No students found for this class"}), 404

    all_student_ids = {student.id for student in all_students}
    present_set = set(present_student_ids)

    # 3. Calculate absent students (Server-side logic)
    absent_set = all_student_ids - present_set
    
    # 4. Check if a record already exists for this class on this date
    existing_record = Attendance.query.filter(
        Attendance.class_id == class_id,
        func.date(Attendance.date) == target_date
    ).first()

    if existing_record:
        # 5a. UPDATE existing record
        existing_record.present_students = list(present_set)
        existing_record.absent_students = list(absent_set)
        existing_record.image_path = image_path
        
        db.session.commit()
        return jsonify(existing_record.to_json()), 200
    
    else:
        # 5b. CREATE new record
        new_record = Attendance(
            class_id=class_id,
            date=target_date,
            present_students=list(present_set),
            absent_students=list(absent_set),
            image_path=image_path
        )
        
        db.session.add(new_record)
        db.session.commit()
        return jsonify(new_record.to_json()), 201

# --- ROUTE 3: GET REPORTS (No changes) ---
@teacher_bp.route('/class/<int:class_id>/reports', methods=['GET'])
@requires_auth
@requires_role('teacher')
def get_class_reports(class_id):
    """Get attendance reports for a specific class."""
    records = Attendance.query.filter_by(class_id=class_id).order_by(Attendance.date.desc()).limit(30).all()
    
    if not records:
        return jsonify([]), 200
        
    return jsonify([record.to_json() for record in records]), 200