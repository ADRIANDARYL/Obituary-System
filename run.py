from app import app
from models import db
from models.user import User
from werkzeug.security import generate_password_hash

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
        # Create admin user if not exists
        admin_user = User.query.filter_by(username="admin").first()
        if not admin_user:
            admin = User(
                username="admin",
                password=generate_password_hash("admin123"),
                role="admin",
                is_approved=True
            )
            db.session.add(admin)
            db.session.commit()
            print("=" * 50)
            print("Admin user created!")
            print("Username: admin")
            print("Password: admin123")
            print("=" * 50)
        else:
            print("Admin user already exists")
    
    print("\n" + "=" * 50)
    print("Starting Flask server...")
    print("Access at: http://127.0.0.1:5000")
    print("=" * 50 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)