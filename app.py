from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db
from models.user import User
from models.obituary import Obituary
from config import Config
import os
import uuid
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
from flask import send_from_directory

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_only():
    return current_user.is_authenticated and current_user.role == "admin"

def allowed_file(filename):
    """Check if file has allowed extension"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "danger")
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(password)
        
        new_user = User(
            username=username,
            password=hashed_pw,
            role="user",
            is_approved=False
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful! Wait for admin approval.", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route("/")
def home():
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            if not user.is_approved:
                flash("Account not approved by admin. Please wait.", "danger")
                return redirect(url_for('login'))
            
            login_user(user)
            session["role"] = user.role
            
            if user.role == "admin":
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for('dashboard'))
        
        flash("Invalid username or password", "danger")
        return redirect(url_for('login'))
    
    return render_template("login.html")

@app.route("/admin")
@login_required
def admin_panel():
    if not admin_only():
        flash("Admin access required", "danger")
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template("admin.html", users=users)

@app.route("/approve_user/<int:user_id>")
@login_required
def approve_user(user_id):
    if not admin_only():
        flash("Admin access required", "danger")
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"User '{user.username}' approved successfully", "success")
    return redirect(url_for('admin_panel'))

@app.route("/reject_user/<int:user_id>")
@login_required
def reject_user(user_id):
    if not admin_only():
        flash("Admin access required", "danger")
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' rejected and deleted", "warning")
    return redirect(url_for('admin_panel'))

@app.route("/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    if not admin_only():
        flash("Admin access required", "danger")
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        flash("You cannot delete your own account", "danger")
        return redirect(url_for('admin_panel'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f"User '{user.username}' deleted", "warning")
    return redirect(url_for('admin_panel'))

@app.route("/add_user", methods=["POST"])
@login_required
def add_user():
    if not admin_only():
        flash("Admin access required", "danger")
        return redirect(url_for('dashboard'))
    
    username = request.form.get("username")
    password = request.form.get("password")
    
    # Check if user already exists
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash(f"Username '{username}' already exists! Please choose a different username.", "danger")
        return redirect(url_for('admin_panel'))
    
    # Check if password is empty
    if not password:
        flash("Password cannot be empty", "danger")
        return redirect(url_for('admin_panel'))
    
    hashed_pw = generate_password_hash(password)
    
    new_user = User(
        username=username,
        password=hashed_pw,
        role="user",
        is_approved=True
    )
    
    db.session.add(new_user)
    db.session.commit()
    flash(f"User '{username}' added successfully", "success")
    return redirect(url_for('admin_panel'))

@app.route("/dashboard")
@login_required
def dashboard():
    count = Obituary.query.count()
    # Get 5 most recent records (ordered by ID descending = newest first)
    recent_records = Obituary.query.order_by(Obituary.id.desc()).limit(5).all()
    return render_template("dashboard.html", count=count, records=recent_records)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        name = request.form.get("name")
        dob = request.form.get("dob")
        dod = request.form.get("dod")
        bio = request.form.get("bio")
        funeral = request.form.get("funeral")
        photo = request.files.get("photo")
        
        filename = None
        if photo and photo.filename and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            # Add unique prefix to avoid overwrites
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
            filename = unique_filename
        elif photo and photo.filename:
            flash("Invalid file type. Allowed: png, jpg, jpeg, gif, webp", "warning")
        
        obituary = Obituary(
            full_name=name,
            date_of_birth=dob,
            date_of_death=dod,
            biography=bio,
            funeral_details=funeral,
            photo=filename
        )
        
        db.session.add(obituary)
        db.session.commit()
        flash("Record added successfully", "success")
        return redirect(url_for('records'))
    
    return render_template("add_obituary.html")

@app.route("/records")
@login_required
def records():
    records = Obituary.query.all()
    return render_template("records.html", records=records)

@app.route("/view/<int:id>")
@login_required
def view_obituary(id):
    record = Obituary.query.get_or_404(id)
    return render_template("view_obituary.html", record=record)

@app.route("/delete/<int:id>")
@login_required
def delete(id):
    record = Obituary.query.get_or_404(id)
    
    # Delete associated photo if exists
    if record.photo:
        photo_path = os.path.join(app.config["UPLOAD_FOLDER"], record.photo)
        if os.path.exists(photo_path):
            os.remove(photo_path)
    
    db.session.delete(record)
    db.session.commit()
    flash("Record deleted", "warning")
    return redirect(url_for('records'))

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    record = Obituary.query.get_or_404(id)
    
    if request.method == "POST":
        record.full_name = request.form.get("name")
        record.date_of_birth = request.form.get("dob")
        record.date_of_death = request.form.get("dod")
        record.biography = request.form.get("bio")
        record.funeral_details = request.form.get("funeral")
        
        # Handle photo update
        photo = request.files.get("photo")
        if photo and photo.filename and allowed_file(photo.filename):
            # Delete old photo
            if record.photo:
                old_photo_path = os.path.join(app.config["UPLOAD_FOLDER"], record.photo)
                if os.path.exists(old_photo_path):
                    os.remove(old_photo_path)
            
            filename = secure_filename(photo.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
            record.photo = unique_filename
        
        db.session.commit()
        flash("Record updated successfully", "success")
        return redirect(url_for('records'))
    
    return render_template("edit_obituary.html", record=record)

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    records = []
    search_term = ""
    
    if request.method == "POST":
        search_term = request.form.get("name", "")
        if search_term:
            records = Obituary.query.filter(
                Obituary.full_name.contains(search_term)
            ).all()
            flash(f"Found {len(records)} record(s)", "info")
    
    return render_template("search.html", records=records, search_term=search_term)

@app.route("/pdf/<int:id>")
@login_required
def generate_pdf(id):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import tempfile
    from PIL import Image as PILImage
    
    try:
        record = Obituary.query.get_or_404(id)
        
        # Create temporary file
        fd, filename = tempfile.mkstemp(suffix='.pdf', prefix=f'obituary_{id}_')
        os.close(fd)
        
        # Create PDF document
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2980b9'),
            spaceAfter=10,
            alignment=TA_LEFT
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12
        )
        
        # Title
        story.append(Paragraph(f"Obituary: {record.full_name}", title_style))
        story.append(Spacer(1, 0.2 * inch))
        
        # ===== PHOTO SECTION =====
        if record.photo:
            # Find the photo file
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], record.photo)
            
            # Also check in static/uploads if needed
            if not os.path.exists(photo_path):
                photo_path = os.path.join('static', 'uploads', record.photo)
            
            if os.path.exists(photo_path):
                try:
                    # Open and resize image
                    img = PILImage.open(photo_path)
                    
                    # Calculate aspect ratio
                    img_width, img_height = img.size
                    max_width = 2 * inch
                    max_height = 2.5 * inch
                    
                    # Resize maintaining aspect ratio
                    ratio = min(max_width / img_width, max_height / img_height)
                    new_width = img_width * ratio
                    new_height = img_height * ratio
                    
                    # Add image to PDF
                    story.append(Spacer(1, 0.2 * inch))
                    
                    # Create a centered table for the image
                    image_table_data = [[Image(photo_path, width=new_width, height=new_height)]]
                    image_table = Table(image_table_data, colWidths=[6 * inch])
                    image_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    story.append(image_table)
                    story.append(Spacer(1, 0.3 * inch))
                    
                except Exception as e:
                    # If image fails to load, show error message
                    story.append(Paragraph(f"<i>[Photo could not be loaded: {str(e)}]</i>", normal_style))
                    story.append(Spacer(1, 0.2 * inch))
            else:
                story.append(Paragraph("<i>[Photo file not found on server]</i>", normal_style))
                story.append(Spacer(1, 0.2 * inch))
        
        # ===== DETAILS TABLE =====
        data = [
            ["Full Name:", record.full_name or "Not specified"],
            ["Date of Birth:", record.date_of_birth or "Not specified"],
            ["Date of Death:", record.date_of_death or "Not specified"],
        ]
        
        table = Table(data, colWidths=[1.8 * inch, 4.2 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.3 * inch))
        
        # ===== BIOGRAPHY =====
        if record.biography:
            story.append(Paragraph("Biography", heading_style))
            # Replace newlines with HTML line breaks
            bio_text = record.biography.replace('\n', '<br/>').replace('\r', '<br/>')
            story.append(Paragraph(bio_text, normal_style))
            story.append(Spacer(1, 0.2 * inch))
        
        # ===== FUNERAL DETAILS =====
        if record.funeral_details:
            story.append(Paragraph("Funeral / Memorial Details", heading_style))
            funeral_text = record.funeral_details.replace('\n', '<br/>').replace('\r', '<br/>')
            story.append(Paragraph(funeral_text, normal_style))
            story.append(Spacer(1, 0.2 * inch))
        
        # ===== FOOTER =====
        from datetime import datetime
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph(f"Generated by Digital Obituary Management System (DOMS) on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Send file and cleanup
        from flask import after_this_request
        
        @after_this_request
        def cleanup(response):
            try:
                os.remove(filename)
            except Exception:
                pass
            return response
        
        safe_name = "".join(c for c in record.full_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        return send_file(
            filename, 
            as_attachment=True, 
            download_name=f"obituary_{safe_name}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "danger")
        return redirect(url_for('records'))
    
    
@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for('login'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        
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
    
    # IMPORTANT: This line MUST be OUTSIDE the 'with' block
    print("\n" + "=" * 50)
    print("Starting Flask server...")
    print("Access at: http://127.0.0.1:5000")
    print("=" * 50 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)