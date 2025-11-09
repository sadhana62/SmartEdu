import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_migrate import Migrate
# JWTManager import removed
from config import Config
from utils.db import db 

def create_app():
    """
    Application Factory Function.
    """
    # 1. Initialize Flask App
    app = Flask(__name__)
    app.config.from_object(Config)

    # 2. Initialize Extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    # CORS: Allow all origins for API routes during development
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    # JWT initialization removed

    # 3. Create Upload Directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 4. Register Blueprints
    # Imports are placed here to avoid circular dependencies
    from routes.admin_routes import admin_bp
    from routes.auth_routes import auth_bp
    from routes.teacher_routes import teacher_bp
    from routes.student_routes import student_bp
    from routes.facerec_routes import facerec_bp

    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(teacher_bp, url_prefix='/api/teacher')
    app.register_blueprint(student_bp, url_prefix='/api/students')
    app.register_blueprint(facerec_bp, url_prefix='/api/facerec')

    # 5. Define Global Routes
    @app.route('/uploads/class_images/<filename>')
    def uploaded_file(filename):
        """Route to serve uploaded class images."""
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    @app.route('/api/health')
    def health_check():
        """Simple health check endpoint."""
        return jsonify({"status": "healthy", "message": "SmartEdu backend is running!"})

    # 6. Database Setup & Seeding
    # We use app_context() so we can access current_app and db methods
    with app.app_context():
        # Import models here so recognized by SQLAlchemy before create_all
        from models import user, attendance, subject, student_profile, teacher_profile
        from models.class_model import Class

        # Create tables if they don't exist
        db.create_all()

        # Seed data if the User table is empty
        if user.User.query.count() == 0:
            print("Database is empty, seeding with default data...")
            try:
                # Create a default Teacher
                teacher1 = user.User(name='Dr. Alan Grant', email='alan@smartedu.com', role='teacher', password='password123')
                db.session.add(teacher1)
                
                # Create a default Admin
                admin1 = user.User(name='Admin User', email='admin@smartedu.com', role='admin', password='adminpass')
                db.session.add(admin1)
                
                # Commit first to generate IDs for teacher/admin
                db.session.commit()
                
                # Create a default Class (assigned to the teacher)
                class1 = Class(name='Class 10-A', teacher_id=teacher1.id, timetable={})
                db.session.add(class1)
                db.session.commit()
                
                # Create a default Student (assigned to the class)
                student1 = user.User(name='Ian Malcolm', email='ian@smartedu.com', role='student', class_id=class1.id, password='studentpass')
                db.session.add(student1)
                db.session.commit()
                
                print("Database seeded successfully.")
            except Exception as e:
                db.session.rollback()
                print(f"Error seeding database: {e}")

    return app

if __name__ == '__main__':
    app = create_app()
    # Run the app on port 5000 in debug mode
    app.run(debug=True, port=5000)