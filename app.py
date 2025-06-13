from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Markup, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from flask_cors import CORS
from werkzeug.utils import secure_filename
from functools import wraps
from custom_filters import register_filters
import tempfile
import pdfkit
from pathlib import Path
import base64
import shutil
from io import BytesIO

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qa-tool.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['ADMIN_PASSWORD'] = 'admin123'  # Change this to a secure password

# Register custom Jinja2 filters
register_filters(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Admin authentication decorator
# def admin_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if not session.get('logged_in'):
#             flash('Please login to access this page', 'warning')
#             return redirect(url_for('login', next=request.url))
#         return f(*args, **kwargs)
#     return decorated_function


# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            # Redirect to public homepage instead of login page
            return redirect(url_for('public_index'))
        return f(*args, **kwargs)
    return decorated_function

# Models
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    categories = db.relationship('Category', backref='project', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_date': self.created_date
        }

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    findings = db.relationship('Finding', backref='category', cascade='all, delete-orphan')


class Finding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20), nullable=False)  # Critical, High, Medium, Low
    level = db.Column(db.String(50))
    status = db.Column(db.String(20), nullable=False)  # Open, In Progress, Closed
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    # Relationship for multiple screenshots
    screenshots = db.relationship('Screenshot', backref='finding', cascade='all, delete-orphan')

    # Return description as safe markup
    @property
    def description_html(self):
        return Markup(self.description) if self.description else ""


# New model for screenshots
class Screenshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255))
    finding_id = db.Column(db.Integer, db.ForeignKey('finding.id'), nullable=False)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid password', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('public_index'))


# Routes
@app.route('/')
@admin_required
def index():
    projects = Project.query.all()
    return render_template('index.html', projects=projects)


# Project routes
@app.route('/project/new', methods=['GET', 'POST'])
@admin_required
def new_project():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']

        project = Project(name=name, description=description)
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('new_project.html')


@app.route('/project/<int:project_id>')
@admin_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template('view_project.html', project=project)


@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        project.name = request.form['name']
        project.description = request.form['description']
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('view_project', project_id=project.id))

    return render_template('edit_project.html', project=project)


@app.route('/project/<int:project_id>/delete', methods=['POST'])
@admin_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('index'))


# Category routes
@app.route('/project/<int:project_id>/category/new', methods=['GET', 'POST'])
@admin_required
def new_category(project_id):
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        name = request.form['name']

        category = Category(name=name, project_id=project.id)
        db.session.add(category)
        db.session.commit()
        flash('Category created successfully!', 'success')
        return redirect(url_for('view_project', project_id=project.id))

    return render_template('new_category.html', project=project)


@app.route('/category/<int:category_id>')
@admin_required
def view_category(category_id):
    category = Category.query.get_or_404(category_id)
    return render_template('view_category.html', category=category)


@app.route('/category/<int:category_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)

    if request.method == 'POST':
        category.name = request.form['name']
        db.session.commit()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('view_category', category_id=category.id))

    return render_template('edit_category.html', category=category)


@app.route('/category/<int:category_id>/delete', methods=['POST'])
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    project_id = category.project_id
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully!', 'success')
    return redirect(url_for('view_project', project_id=project_id))


# Finding routes
@app.route('/category/<int:category_id>/finding/new', methods=['GET', 'POST'])
@admin_required
def new_finding(category_id):
    category = Category.query.get_or_404(category_id)

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        severity = request.form['severity']
        level = request.form['level']
        status = request.form['status']

        finding = Finding(
            title=title,
            description=description,
            severity=severity,
            level=level,
            status=status,
            category_id=category.id
        )
        db.session.add(finding)
        db.session.commit()

        # Process multiple screenshots
        files = request.files.getlist('screenshots')
        captions = request.form.getlist('captions')

        for i, file in enumerate(files):
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{i}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                # Get caption if available
                caption = ""
                if i < len(captions):
                    caption = captions[i]

                screenshot = Screenshot(
                    file_path=f"uploads/{filename}",
                    caption=caption,
                    finding_id=finding.id
                )
                db.session.add(screenshot)

        db.session.commit()
        flash('Finding created successfully!', 'success')
        return redirect(url_for('view_category', category_id=category.id))

    return render_template('new_finding.html', category=category)


@app.route('/finding/<int:finding_id>')
@admin_required
def view_finding(finding_id):
    finding = Finding.query.get_or_404(finding_id)
    return render_template('view_finding.html', finding=finding)


@app.route('/finding/<int:finding_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_finding(finding_id):
    finding = Finding.query.get_or_404(finding_id)

    if request.method == 'POST':
        finding.title = request.form['title']
        finding.description = request.form['description']
        finding.severity = request.form['severity']
        finding.level = request.form['level']
        finding.status = request.form['status']

        # Add category change functionality
        new_category_id = request.form.get('category_id')
        if new_category_id and int(new_category_id) != finding.category_id:
            finding.category_id = int(new_category_id)

        # Process existing screenshots - update captions
        existing_screenshot_ids = request.form.getlist('existing_screenshot_id')
        existing_captions = request.form.getlist('existing_caption')
        screenshots_to_delete = request.form.getlist('delete_screenshot')

        for i, screenshot_id in enumerate(existing_screenshot_ids):
            screenshot = Screenshot.query.get(int(screenshot_id))
            if screenshot:
                if screenshot_id in screenshots_to_delete:
                    # Delete the screenshot file
                    file_path = os.path.join(app.root_path, 'static', screenshot.file_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    db.session.delete(screenshot)
                elif i < len(existing_captions):
                    screenshot.caption = existing_captions[i]

        # Process new screenshots
        files = request.files.getlist('new_screenshots')
        captions = request.form.getlist('new_captions')

        for i, file in enumerate(files):
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{i}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                # Get caption if available
                caption = ""
                if i < len(captions):
                    caption = captions[i]

                screenshot = Screenshot(
                    file_path=f"uploads/{filename}",
                    caption=caption,
                    finding_id=finding.id
                )
                db.session.add(screenshot)

        db.session.commit()
        flash('Finding updated successfully!', 'success')
        return redirect(url_for('view_finding', finding_id=finding.id))

    # Get all categories in the same project as the current finding
    project_id = finding.category.project_id
    categories = Category.query.filter_by(project_id=project_id).all()

    return render_template('edit_finding.html', finding=finding, categories=categories)


@app.route('/finding/<int:finding_id>/delete', methods=['POST'])
@admin_required
def delete_finding(finding_id):
    finding = Finding.query.get_or_404(finding_id)
    category_id = finding.category_id

    # Remove all screenshots
    for screenshot in finding.screenshots:
        file_path = os.path.join(app.root_path, 'static', screenshot.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(finding)
    db.session.commit()
    flash('Finding deleted successfully!', 'success')
    return redirect(url_for('view_category', category_id=category_id))


# Screenshot routes
@app.route('/finding/<int:finding_id>/add_screenshots', methods=['GET', 'POST'])
@admin_required
def add_screenshots(finding_id):
    finding = Finding.query.get_or_404(finding_id)

    if request.method == 'POST':
        files = request.files.getlist('screenshots')
        captions = request.form.getlist('captions')

        for i, file in enumerate(files):
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{i}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                # Get caption if available
                caption = ""
                if i < len(captions):
                    caption = captions[i]

                screenshot = Screenshot(
                    file_path=f"uploads/{filename}",
                    caption=caption,
                    finding_id=finding.id
                )
                db.session.add(screenshot)

        db.session.commit()
        flash('Screenshots added successfully!', 'success')
        return redirect(url_for('view_finding', finding_id=finding.id))

    return render_template('add_screenshots.html', finding=finding)


@app.route('/screenshot/<int:screenshot_id>/delete', methods=['POST'])
@admin_required
def delete_screenshot(screenshot_id):
    screenshot = Screenshot.query.get_or_404(screenshot_id)
    finding_id = screenshot.finding_id

    # Remove screenshot file
    file_path = os.path.join(app.root_path, 'static', screenshot.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(screenshot)
    db.session.commit()
    flash('Screenshot deleted successfully!', 'success')
    return redirect(url_for('view_finding', finding_id=finding_id))


# Public routes for users to view but not edit
@app.route('/public')
def public_index():
    projects = Project.query.all()
    return render_template('public/index.html', projects=projects)


@app.route('/public/project/<int:project_id>')
def public_view_project(project_id):
    project = Project.query.get_or_404(project_id)

    # Pagination setup
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of findings per page

    # Check if a category is selected
    category_id = request.args.get('category_id', type=int)
    selected_category = None

    # Query for findings based on category selection
    if category_id:
        selected_category = Category.query.get_or_404(category_id)
        findings_query = Finding.query.filter_by(category_id=category_id)
    else:
        # Get all findings for this project across all categories
        findings_query = Finding.query.join(Category).filter(Category.project_id == project_id)

    # Order findings by most recent first
    findings_query = findings_query.order_by(Finding.created_date.desc())

    # Apply pagination
    pagination = findings_query.paginate(page=page, per_page=per_page, error_out=False)
    findings = pagination.items

    # Count all findings across all categories in this project
    all_findings_count = Finding.query.join(Category).filter(Category.project_id == project_id).count()

    return render_template(
        'public/view_project.html',
        project=project,
        selected_category=selected_category,
        selected_category_id=category_id,
        findings=findings,
        pagination=pagination,
        all_findings_count=all_findings_count
    )


@app.route('/public/category/<int:category_id>')
def public_view_category(category_id):
    category = Category.query.get_or_404(category_id)
    # Include the project for sidebar navigation
    project = category.project
    return render_template('public/view_category.html', category=category, project=project)


@app.route('/public/finding/<int:finding_id>')
def public_view_finding(finding_id):
    finding = Finding.query.get_or_404(finding_id)
    # Include the category and project for sidebar navigation
    category = finding.category
    project = category.project
    return render_template('public/view_finding.html', finding=finding, category=category, project=project)


# Add a search route for public users
@app.route('/public/search')
def public_search():
    query = request.args.get('q', '')
    if not query:
        return redirect(url_for('public_index'))

    # Search in findings
    findings = Finding.query.filter(
        Finding.title.contains(query) | Finding.description.contains(query)
    ).all()

    # Search in categories
    categories = Category.query.filter(Category.name.contains(query)).all()

    # Search in projects
    projects = Project.query.filter(
        Project.name.contains(query) | Project.description.contains(query)
    ).all()

    # No specific project/category/finding to show in the sidebar for search results
    return render_template(
        'public/search_results.html',
        query=query,
        findings=findings,
        categories=categories,
        projects=projects
    )


from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Markup, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from functools import wraps
from custom_filters import register_filters
import tempfile
import pdfkit
from pathlib import Path
import base64
import shutil
from io import BytesIO
from PIL import Image, ImageEnhance  # Enhanced image processing


# ... [rest of your imports and app setup] ...

@app.route('/project/<int:project_id>/download')
@app.route('/project/<int:project_id>/download/<filter_type>')
@admin_required
def download_project(project_id, filter_type='all'):
    """
    Download project report as PDF

    Args:
        project_id: ID of the project
        filter_type: 'open' for open issues only, 'all' for all issues (default)
    """
    project = Project.query.get_or_404(project_id)

    # Validate filter_type
    if filter_type not in ['open', 'all']:
        filter_type = 'all'

    # Get current date in the format YYYY-MM-DD
    current_date = datetime.now().strftime("%Y-%m-%d")

    with tempfile.TemporaryDirectory() as temp_dir:
        img_dir = Path(temp_dir) / "images"
        img_dir.mkdir(exist_ok=True)

        # Dictionary to track processed screenshots for each finding
        processed_screenshots = {}

        # Process and standardize all screenshots with improved quality
        for category in project.categories:
            for finding in category.findings:
                # Apply filter based on filter_type
                if filter_type == 'open' and finding.status == 'Closed':
                    continue  # Skip closed findings if filtering for open only

                finding_screenshots = []

                # Handle multiple screenshots per finding
                for screenshot in finding.screenshots:
                    source_path = Path(app.root_path) / "static" / screenshot.file_path
                    if source_path.exists():
                        # Generate a unique filename for the processed image
                        processed_filename = f"processed_{screenshot.id}_{Path(screenshot.file_path).name}"
                        dest_path = img_dir / processed_filename

                        # Enhanced image processing with better quality preservation
                        try:
                            # Open image with PIL
                            with Image.open(source_path) as img:
                                # Convert to RGB if needed (handles RGBA, P mode images)
                                if img.mode in ('RGBA', 'P', 'LA'):
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    if img.mode == 'P':
                                        img = img.convert('RGBA')
                                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                                    img = background
                                elif img.mode != 'RGB':
                                    img = img.convert('RGB')

                                # Increased maximum dimensions for better PDF quality
                                max_width = 1200  # Increased from 800
                                max_height = 900  # Increased from 600

                                original_width, original_height = img.size

                                # Only resize if image is significantly larger than max dimensions
                                # Use a higher threshold to preserve more detail
                                if original_width > max_width * 1.2 or original_height > max_height * 1.2:
                                    width_ratio = max_width / original_width
                                    height_ratio = max_height / original_height
                                    ratio = min(width_ratio, height_ratio)

                                    new_width = int(original_width * ratio)
                                    new_height = int(original_height * ratio)

                                    # Use LANCZOS for high-quality downsampling
                                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)

                                    # Apply minimal sharpening only if significantly downsized
                                    if ratio < 0.8:  # Only sharpen if significant downsizing
                                        enhancer = ImageEnhance.Sharpness(resized_img)
                                        final_img = enhancer.enhance(1.1)  # Reduced from 1.2
                                    else:
                                        final_img = resized_img

                                    # Calculate final dimensions
                                    final_width, final_height = new_width, new_height
                                else:
                                    # Don't resize, just optimize
                                    final_img = img
                                    final_width, final_height = original_width, original_height

                                # Save with maximum quality and explicit DPI
                                final_img.save(dest_path, format='JPEG', quality=98, optimize=True, dpi=(300, 300))

                                # Add to tracking dict with relative path
                                relative_path = f"images/{processed_filename}"
                                finding_screenshots.append({
                                    'path': relative_path,
                                    'caption': screenshot.caption or '',
                                    'original_width': original_width,
                                    'original_height': original_height,
                                    'new_width': final_width,
                                    'new_height': final_height
                                })

                        except Exception as e:
                            print(f"Error processing image {source_path}: {e}")
                            # Fallback to copying the original
                            try:
                                shutil.copy(source_path, dest_path)
                            except Exception as copy_error:
                                print(f"Error copying original image {source_path}: {copy_error}")
                                continue

                            # Add to tracking dict with relative path
                            relative_path = f"images/{processed_filename}"
                            finding_screenshots.append({
                                'path': relative_path,
                                'caption': screenshot.caption or '',
                                'original_width': 0,  # Error case
                                'original_height': 0,
                                'new_width': 0,
                                'new_height': 0
                            })

                # Store processed screenshots for this finding
                processed_screenshots[finding.id] = finding_screenshots

        # Add a now() function for templates
        def now():
            return datetime.now()

        # Collect all findings across categories with filtering
        all_findings = []
        for category in project.categories:
            for finding in category.findings:
                # Apply filter based on filter_type
                if filter_type == 'open' and finding.status == 'Closed':
                    continue  # Skip closed findings if filtering for open only

                all_findings.append({'category': category, 'finding': finding})

        # Sort all findings by severity (Critical > High > Medium > Low)
        severity_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
        sorted_findings = sorted(all_findings,
                                 key=lambda x: severity_order.get(x['finding'].severity, 999),
                                 reverse=False)

        # Generate HTML with correct paths to all screenshots
        html_content = render_template(
            'download_project.html',
            project=project,
            base_path=str(Path(temp_dir)),
            processed_screenshots=processed_screenshots,
            sorted_findings=sorted_findings,  # Pass the pre-sorted list
            filter_type=filter_type,  # Pass filter type to template
            now=now
        )

        html_path = Path(temp_dir) / "project_report.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Generate PDF with enhanced quality options
        pdf_buffer = BytesIO()
        pdf_path = Path(temp_dir) / "project_report.pdf"

        # Enhanced PDF generation options for better image quality
        config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
        options = {
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': 'UTF-8',
            'enable-local-file-access': True,

            # Enhanced image quality settings
            'image-quality': 100,
            'image-dpi': 300,
            'disable-smart-shrinking': True,  # Prevents automatic shrinking
            'zoom': 1.0,  # Ensure no scaling

            # Better rendering options
            'print-media-type': True,
            'no-outline': None,
            'enable-forms': None,
            'enable-plugins': None,

            # Quality preservation
            'lowquality': False,  # Ensure high quality
            'load-error-handling': 'ignore',
            'no-stop-slow-scripts': None,

            # Page settings
            'footer-right': '[page] / [topage]',
            'footer-font-size': 8,

            # Additional quality settings
            'minimum-font-size': 8,
            'javascript-delay': 1000,  # Allow time for any JS to complete
        }

        try:
            pdfkit.from_file(str(html_path), str(pdf_path), options, configuration=config)
        except Exception as e:
            print(f"Error generating PDF: {e}")
            # Fallback with simpler options if the enhanced ones fail
            fallback_options = {
                'page-size': 'A4',
                'margin-top': '15mm',
                'margin-right': '15mm',
                'margin-bottom': '15mm',
                'margin-left': '15mm',
                'encoding': 'UTF-8',
                'enable-local-file-access': True,
                'image-quality': 100,
                'image-dpi': 300,
                'print-media-type': True,
                'footer-right': '[page] / [topage]',
                'footer-font-size': 8
            }
            pdfkit.from_file(str(html_path), str(pdf_path), fallback_options, configuration=config)

        # Load PDF into memory and return
        with open(pdf_path, 'rb') as f:
            pdf_buffer.write(f.read())
        pdf_buffer.seek(0)

        # Add date and filter type to the filename
        filter_suffix = "_Open_Issues" if filter_type == 'open' else "_All_Issues"
        filename = f"{project.name}_Quality_Assurance{filter_suffix}_{current_date}.pdf"

        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

# You can reuse this function for public downloads as well
@app.route('/public/project/<int:project_id>/download')
def public_download_project(project_id):
    return download_project(project_id)

# Add this route for admin use
@app.route('/project/<int:project_id>/export')
@admin_required
def export_project(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template('export_project.html', project=project)


# Add this as a public version


@app.route('/public/api/finding/<int:finding_id>')
def api_get_finding(finding_id):
    finding = Finding.query.get_or_404(finding_id)

    # Create a serializable dict of the finding
    result = {
        'id': finding.id,
        'title': finding.title,
        'description': finding.description_html,
        'severity': finding.severity,
        'level': finding.level,
        'status': finding.status,
        'created_date': finding.created_date.strftime("%B %d, %Y at %H:%M"),
        'category_id': finding.category_id,
        'category_name': finding.category.name,  # Add category name
        'screenshots': []
    }

    # Add screenshots
    for screenshot in finding.screenshots:
        result['screenshots'].append({
            'id': screenshot.id,
            'file_path': screenshot.file_path,
            'caption': screenshot.caption
        })

    return result


@app.route('/public/api/update_status/<int:finding_id>', methods=['POST'])
def update_finding_status(finding_id):
    finding = Finding.query.get_or_404(finding_id)

    # Get the new status from the request data
    new_status = request.json.get('status')

    # Validate the status
    if new_status not in ['Open', 'In Progress', 'Closed']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400

    # Update the finding status
    finding.status = new_status
    db.session.commit()

    return jsonify({'success': True, 'message': 'Status updated successfully'})
@app.route('/projects', methods=['GET'])
def projects():
    projects = Project.query.all()
    return jsonify([project.to_dict() for project in projects])
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)