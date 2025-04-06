from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
import mysql.connector
from flask_sqlalchemy import SQLAlchemy
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session security

# MySQL Connection
def get_db_connection():
    return mysql.connector.connect(
        host="sql301.infinityfree.com",
        user="if0_38685389",
        password="RFJdyZDy6XRgRq",
        database="if0_38685389_hostel_database"
    )

# Route for index page
@app.route('/')
def index():
    return render_template("index.html")

# Route for login
@app.route('/login', methods=['POST'])
def login():
    user_type = request.form['userType']
    username = request.form['username']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor()
    if user_type == "admin":
        cursor.execute("SELECT * FROM admins WHERE name = %s AND password = %s", (username, password))
    else:
        cursor.execute("SELECT * FROM registered_hostellers WHERE username = %s AND password = %s", (username, password))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        session['username'] = username
        session['password'] = password
        session['user_type'] = user_type

        if user_type == "admin":
            return redirect(url_for('admin_interface'))  # Redirect to admin page
        return redirect(url_for('user_dashboard'))  # Redirect to user dashboard
    else:
        return f"<h2>Invalid credentials. Please try again.</h2><br><a href='/'>Go Back</a>"

# Route for admin interface
@app.route('/admin_interface')
def admin_interface():
    if 'username' in session and session['user_type'] == 'admin':
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="hostel_database"
        )
        cursor = connection.cursor()

        # Count total hostellers
        cursor.execute("SELECT COUNT(*) FROM enrolled_hostellers")
        total_hostellers = cursor.fetchone()[0]

        # Count total complaints
        cursor.execute("SELECT COUNT(*) FROM complaints")
        total_complaints = cursor.fetchone()[0]

        # Count total fines
        cursor.execute("SELECT COUNT(*) FROM fines")
        total_fines = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return render_template(
            "admin_interface.html",
            username=session['username'],
            total_hostellers=total_hostellers,
            total_complaints=total_complaints,
            total_fines=total_fines
        )
    return redirect(url_for('index'))


# Route for user dashboard
@app.route('/user_dashboard')
def user_dashboard():
    if 'username' in session and session['user_type'] == 'student':
        return f"<h2>Welcome, {session['username']}!</h2><br><a href='/logout'>Logout</a>"
    return redirect(url_for('index'))

# Route for registration
@app.route('/register', methods=['POST'])
def register():
    student_id = request.form['id']
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if student is enrolled
    cursor.execute("SELECT * FROM enrolled_hostellers WHERE id = %s", (student_id,))
    enrolled_student = cursor.fetchone()

    if enrolled_student:
        try:
            cursor.execute("INSERT INTO registered_hostellers (hosteller_id, username, password, email) VALUES (%s, %s, %s, %s)",
                           (student_id, username, password, email))
            conn.commit()
            message = "Registration Successful!"
        except Exception as e:
            conn.rollback()
            message = f"Error: {e}"
    else:
        message = "Error: Student ID not found in enrolled hostellers."

    cursor.close()
    conn.close()
    return f"<h2>{message}</h2><br><a href='/'>Go Back</a>"

# Route for logout
@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    response = redirect(url_for('index'))  # Redirect to login page
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Route for Hosteller Management page
@app.route('/add_remove_view')
def add_remove_view():
    if 'username' in session and session['user_type'] == 'admin':
        return render_template("addRemoveView.html")
    return redirect(url_for('index'))

# API Routes for Hosteller Management
@app.route('/get_hostellers', methods=['GET'])
def get_hostellers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM enrolled_hostellers")
    hostellers = cursor.fetchall()
    conn.close()
    return jsonify(hostellers)

@app.route('/add_hosteller', methods=['POST'])
def add_hosteller():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO enrolled_hostellers (name, room_no, hostel_name, contact_no, email)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (data['name'], data['room_no'], data['hostel_name'], data['contact_no'], data['email']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Hosteller added successfully'}), 201

@app.route('/delete_hosteller/<int:id>', methods=['DELETE'])
def delete_hosteller(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM enrolled_hostellers WHERE hosteller_id = %s", (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Hosteller deleted successfully'})

# Route to render Charge Fine Page
@app.route('/charge_fine_page')
def charge_fine_page():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch fine rules
    cursor.execute("SELECT rule_id, rule_description, fine_amount FROM fine_rules")
    rules = cursor.fetchall()
    fine_rules = [{"rule_id": row[0], "description": row[1], "fine_amount": row[2]} for row in rules]

    # Fetch hosteller IDs and names
    cursor.execute("SELECT reg_id, username FROM Registered_Hostellers")
    hostellers = cursor.fetchall()
    hosteller_list = [{"reg_id": row[0], "username": row[1]} for row in hostellers]

    conn.close()
    
    return render_template("chargeFine.html", fine_rules=fine_rules, hosteller_list=hosteller_list)

# Handle Fine Charging
@app.route('/charge_fine', methods=['POST'])
def charge_fine():
    hosteller_id = request.form['hostellerId']
    fine_rule_id = request.form['fineRule']

    if not hosteller_id or not fine_rule_id:
        flash("Error: Missing required fields!", "danger")
        return redirect(url_for('charge_fine_page'))  # Redirect to charge fine page

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch fine amount from fine_rules table
    cursor.execute("SELECT fine_amount FROM fine_rules WHERE rule_id = %s", (fine_rule_id,))
    fine_amount = cursor.fetchone()

    if fine_amount:
        fine_amount = fine_amount[0]
        cursor.execute("INSERT INTO fines (hosteller_id, rule_id, amount) VALUES (%s, %s, %s)",
                       (hosteller_id, fine_rule_id, fine_amount))
        conn.commit()
        flash("Fine charged successfully!", "success")
    else:
        flash("Error: Invalid fine rule selected!", "danger")

    cursor.close()
    conn.close()
    return redirect(url_for('charge_fine_page'))  # Redirect back to the charge fine page

# Fine Management Route
@app.route('/fine_management')
def fine_management():
    return render_template("fine_management.html")

from datetime import datetime  # If not already imported

# View & Resolve Complaints (Admin)
@app.route('/view_resolve_complaints')
def view_resolve_complaints():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch pending complaints
    query_pending = """
        SELECT c.complaint_id, c.complaint_text, c.complaint_date, c.status,
               r.username, c.hosteller_id
        FROM Complaints c
        JOIN Registered_Hostellers r ON c.hosteller_id = r.reg_id
        WHERE c.status = 'Pending'
        ORDER BY c.complaint_date DESC
    """
    cursor.execute(query_pending)
    complaints = cursor.fetchall()

    for i, complaint in enumerate(complaints, start=1):
        complaint['serial_no'] = i

    # Fetch resolved complaints
    query_resolved = """
        SELECT rc.complaint_id, rc.complaint_text, rc.resolution_text, rc.resolved_date, rc.status,
               r.username, rc.hosteller_id
        FROM Resolved_Complaints rc
        JOIN Registered_Hostellers r ON rc.hosteller_id = r.reg_id
        ORDER BY rc.resolved_date DESC
    """
    cursor.execute(query_resolved)
    resolved = cursor.fetchall()

    for i, res in enumerate(resolved, start=1):
        res['serial_no'] = i

    cursor.close()
    conn.close()

    return render_template("view_complaints.html", complaints=complaints, resolved=resolved)


# Handle complaint resolution
@app.route('/resolve_complaint', methods=['POST'])
def resolve_complaint():
    complaint_id = request.form['complaint_id']
    hosteller_id = request.form['hosteller_id']
    complaint_text = request.form['complaint_text']
    resolution_text = request.form['resolution_text']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Insert into resolved complaints
    insert_query = """
        INSERT INTO Resolved_Complaints
        (complaint_id, hosteller_id, complaint_text, resolution_text, resolved_date, status)
        VALUES (%s, %s, %s, %s, %s, 'Resolved')
    """
    cursor.execute(insert_query, (
        complaint_id,
        hosteller_id,
        complaint_text,
        resolution_text,
        datetime.now()
    ))

    # Update complaint status
    update_query = "UPDATE Complaints SET status = 'Resolved' WHERE complaint_id = %s"
    cursor.execute(update_query, (complaint_id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash('Complaint resolved successfully.', 'success')
    return redirect(url_for('view_resolve_complaints'))

@app.route('/view_feedbacks')
def view_feedbacks():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT gf.feedback_text, rh.username, rc.complaint_text, rc.resolution_text, rc.resolved_date
        FROM Grievance_Feedback gf
        JOIN Registered_Hostellers rh ON gf.hosteller_id = rh.hosteller_id
        JOIN Resolved_Complaints rc ON gf.complaint_id = rc.complaint_id
        ORDER BY rc.resolved_date DESC
    """
    cursor.execute(query)
    feedbacks = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('feedbacks.html', feedbacks=feedbacks)

@app.route('/view_fines')
def view_fines():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT fr.rule_description, f.amount, f.fine_date, f.status
        FROM Fines f
        JOIN Fine_Rules fr ON f.rule_id = fr.rule_id
        ORDER BY f.fine_date DESC
    """
    cursor.execute(query)
    fines = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("view_fines.html", fines=fines)

@app.route('/download_fine_records_pdf')
def download_fine_records_pdf():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT fr.rule_description, f.amount, f.fine_date, f.status
        FROM Fines f
        JOIN Fine_Rules fr ON f.rule_id = fr.rule_id
        ORDER BY f.fine_date DESC
    """
    cursor.execute(query)
    fines = cursor.fetchall()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 50, "Hostel Fines Report")

    p.setFont("Helvetica", 10)
    y_start = height - 90
    row_height = 20
    col_widths = [200, 100, 100, 100]
    x_positions = [50, 250, 350, 450]
    headers = ["Reason", "Amount (Rupees)", "Date", "Status"]

    def draw_table_header(y):
        p.setFont("Helvetica-Bold", 10)
        for i, header in enumerate(headers):
            p.drawString(x_positions[i] + 5, y + 5, header)
            p.rect(x_positions[i], y, col_widths[i], row_height, stroke=1, fill=0)

    def draw_row(fine, y):
        p.setFont("Helvetica", 10)
        values = [
            fine['rule_description'][:35],
            f"{fine['amount']:.2f}",
            fine['fine_date'].strftime('%Y-%m-%d'),
            fine['status'].capitalize()
        ]
        for i, value in enumerate(values):
            p.drawString(x_positions[i] + 5, y + 5, value)
            p.rect(x_positions[i], y, col_widths[i], row_height, stroke=1, fill=0)

    y = y_start
    draw_table_header(y)
    y -= row_height

    for fine in fines:
        if y < 80:
            p.showPage()
            y = height - 90
            draw_table_header(y)
            y -= row_height
        draw_row(fine, y)
        y -= row_height

    p.save()
    buffer.seek(0)

    cursor.close()
    conn.close()

    return send_file(buffer, as_attachment=True, download_name="Hostel_Fines_Report.pdf", mimetype='application/pdf')

@app.route('/rules')
def view_rules():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Fine_Rules")
    rules = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("fine_rules.html", rules=rules)

@app.route('/add_rule', methods=['POST'])
def add_rule():
    description = request.form['description']
    amount = request.form['amount']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Fine_Rules (rule_description, fine_amount) VALUES (%s, %s)", (description, amount))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/rules')

@app.route('/delete_rule/<int:rule_id>')
def delete_rule(rule_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Fine_Rules WHERE rule_id = %s", (rule_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Rule deleted successfully!')
    return redirect('/rules')

@app.route('/update_rule', methods=['POST'])
def update_rule():
    rule_id = request.form['rule_id']
    description = request.form['description']
    amount = request.form['amount']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Fine_Rules SET rule_description = %s, fine_amount = %s WHERE rule_id = %s",
                   (description, amount, rule_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash('Rule updated successfully!')
    return redirect('/rules')

@app.route('/download_rules_pdf')
def download_rules_pdf():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Fine_Rules")
    rules = cursor.fetchall()
    cursor.close()
    conn.close()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 50, "Hostel Fine Rules")

    headers = ["ID", "Description", "Amount (Rupees)"]
    x_positions = [50, 100, 450]
    row_height = 20
    y = height - 80

    p.setFont("Helvetica-Bold", 10)
    for i, header in enumerate(headers):
        col_width = x_positions[i + 1] - x_positions[i] if i < 2 else 100
        p.rect(x_positions[i], y, col_width, row_height, stroke=1, fill=0)
        p.drawString(x_positions[i] + 5, y + 5, header)
    y -= row_height

    p.setFont("Helvetica", 10)
    for rule in rules:
        if y < 60:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica", 10)

        p.rect(x_positions[0], y, 50, row_height, stroke=1, fill=0)
        p.drawString(x_positions[0] + 5, y + 5, str(rule['rule_id']))

        p.rect(x_positions[1], y, 350, row_height, stroke=1, fill=0)
        desc = rule['rule_description'][:50] + "..." if len(rule['rule_description']) > 50 else rule['rule_description']
        p.drawString(x_positions[1] + 5, y + 5, desc)

        p.rect(x_positions[2], y, 100, row_height, stroke=1, fill=0)
        p.drawString(x_positions[2] + 5, y + 5, f"{rule['fine_amount']:.2f}")

        y -= row_height

    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="Fine_Rules_Report.pdf", mimetype='application/pdf')

# Run Flask App
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002, debug=True)
