from flask import Flask, render_template, request, redirect, session, flash, url_for
import mysql.connector
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "twice"

UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.jinja_env.globals.update(zip=zip)


def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT")),
        ssl_ca=os.environ.get("SSL_CA_PATH")
    )

@app.route('/')
def home():
    if 'email' in session:
        if session['role'] == 'admin':
            return redirect('/admin_dashboard')
        else:
            return redirect('/user_dashboard')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['email'] = user['email']
            session['username'] = user['username']
            session['role'] = user['role']
            session['profile_pic'] = user.get('profile_pic', 'default.jpg')

            if user['role'] == 'admin':
                return redirect('/admin_dashboard')
            else:
                return redirect('/user_dashboard')
        else:
            flash("Invalid email or password", "danger")
            return redirect('/login')

    return render_template("login.html")


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "POST":
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect('/signup')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Email already exists!", "warning")
            cursor.close()
            conn.close()
            return redirect('/signup')


        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
            (username, email, password, 'user')
        )
        conn.commit()

        cursor.execute(
            """
            INSERT INTO members (first_name, last_name, email, status)
            VALUES (%s, %s, %s, %s)
            """,
            (username, '', email, 'Active') 
        )
        conn.commit()

        cursor.close()
        conn.close()

        flash("Account created successfully! You are now also added as a member.", "success")
        return redirect('/login')

    return render_template("signup.html")

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'email' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT SUM(amount) AS total_tithes FROM tithes")
    total_tithes = cursor.fetchone()['total_tithes'] or 0

    cursor.execute("SELECT SUM(amount) AS total_expenses FROM expenses")
    total_expenses = cursor.fetchone()['total_expenses'] or 0

    expenses_percentage = (total_expenses / (total_tithes + total_expenses) * 100) if (total_tithes + total_expenses) > 0 else 0

    filter_type = request.args.get('type')
    selected_date = request.args.get('date')
    filter_target = request.args.get('filter')

    filtered_tithes = None
    filtered_expenses = None

    if selected_date and filter_target:
        if filter_target == 'tithes':
            if filter_type == 'day':
                cursor.execute("SELECT SUM(amount) AS total FROM tithes WHERE DATE(date) = %s", (selected_date,))
            elif filter_type == 'month':
                cursor.execute("SELECT SUM(amount) AS total FROM tithes WHERE MONTH(date) = MONTH(%s) AND YEAR(date) = YEAR(%s)", (selected_date, selected_date))
            elif filter_type == 'year':
                cursor.execute("SELECT SUM(amount) AS total FROM tithes WHERE YEAR(date) = YEAR(%s)", (selected_date,))
            filtered_tithes = cursor.fetchone()['total'] or 0

        elif filter_target == 'expenses':
            if filter_type == 'day':
                cursor.execute("SELECT SUM(amount) AS total FROM expenses WHERE DATE(date) = %s", (selected_date,))
            elif filter_type == 'month':
                cursor.execute("SELECT SUM(amount) AS total FROM expenses WHERE MONTH(date) = MONTH(%s) AND YEAR(date) = YEAR(%s)", (selected_date, selected_date))
            elif filter_type == 'year':
                cursor.execute("SELECT SUM(amount) AS total FROM expenses WHERE YEAR(date) = YEAR(%s)", (selected_date,))
            filtered_expenses = cursor.fetchone()['total'] or 0

    cursor.execute("""
        SELECT event_id, event_name, event_date, description, location 
        FROM events 
        WHERE event_date >= CURDATE() 
        ORDER BY event_date ASC
    """)
    upcoming_events = cursor.fetchall()

    cursor.execute("""
        SELECT event_id, event_name, event_date, description, location 
        FROM events 
        WHERE event_date < CURDATE() 
        ORDER BY event_date DESC
    """)
    past_events = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS ongoing FROM events WHERE event_date >= CURDATE()")
    ongoing_events = cursor.fetchone()['ongoing']

    cursor.execute("SELECT COUNT(*) AS completed FROM events WHERE event_date < CURDATE()")
    completed_events = cursor.fetchone()['completed']

    cursor.execute("SELECT COUNT(*) AS total_members FROM members")
    total_members = cursor.fetchone()['total_members']

    cursor.execute("SELECT COUNT(*) AS total_lifegroups FROM lifegroups")
    total_lifegroups = cursor.fetchone()['total_lifegroups']

    cursor.execute("SELECT COUNT(*) AS total_ministries FROM ministries")
    total_ministries = cursor.fetchone()['total_ministries']

    cursor.execute("""
        SELECT event_id AS id, event_name AS title, description, event_date AS date, 'event' AS type FROM events
        UNION ALL
        SELECT ministry_id AS id, ministry_name AS title, '' AS description, NULL AS date, 'ministry' AS type FROM ministries
        UNION ALL
        SELECT lifegroup_id AS id, lifegroup_name AS title, '' AS description, NULL AS date, 'lifegroup' AS type FROM lifegroups
        ORDER BY date DESC
        LIMIT 10
    """)
    announcements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        username=session['username'],
        email=session['email'],
        total_tithes=total_tithes,
        total_expenses=total_expenses,
        expenses_percentage=expenses_percentage,
        ongoing_events=ongoing_events,
        completed_events=completed_events,
        total_members=total_members,
        total_lifegroups=total_lifegroups,
        total_ministries=total_ministries,
        upcoming_events=upcoming_events,
        past_events=past_events,
        announcements=announcements,
        filtered_tithes=filtered_tithes,
        filtered_expenses=filtered_expenses,
        selected_date=selected_date,
        filter_type=filter_type
    )

@app.route('/logout')
def logout():
    session.clear()  # clears all session data
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('login'))


from datetime import datetime, timedelta, time  # Make sure these are imported

@app.route("/view_user_event/<int:event_id>")
def view_user_event(event_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()
    cursor.close()
    conn.close()

    if not event:
        flash("Event not found.", "danger")
        return redirect(url_for("user_dashboard"))

    # Format event_time safely
    ev_time = event.get('event_time')
    if ev_time:
        # MySQL TIME is often returned as timedelta
        if isinstance(ev_time, timedelta):
            total_seconds = ev_time.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            event_time_obj = time(hour=hours, minute=minutes, second=seconds)
        else:
            event_time_obj = ev_time  # already a time object
        event['event_time_formatted'] = event_time_obj.strftime("%I:%M %p")
    else:
        event['event_time_formatted'] = None

    # Make sure the template can show the correct image
    event['image_url'] = event['image_url'] if event['image_url'] else None

    return render_template("view_user_event.html", event=event)



from flask import Flask, render_template, session, redirect, url_for, flash
from datetime import datetime, timedelta

@app.route("/user_dashboard")
def user_dashboard():
    if "email" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user info
    cursor.execute("SELECT * FROM members WHERE email = %s", (session["email"],))
    user = cursor.fetchone()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("login"))

    profile_pic = user['profile_pic'] if user.get('profile_pic') else 'default.jpg'

    # Fetch ministries of the user
    cursor.execute("""
        SELECT m.ministry_id, m.ministry_name
        FROM ministries m
        JOIN member_ministries mm ON m.ministry_id = mm.ministry_id
        WHERE mm.member_id = %s
        ORDER BY m.ministry_name
    """, (user['member_id'],))
    ministries = cursor.fetchall()
    ministry_data = {
        'ministry_ids': [m['ministry_id'] for m in ministries],
        'ministry_names': [m['ministry_name'] for m in ministries]
    } if ministries else None

    # Fetch life groups of the user
    cursor.execute("""
        SELECT l.lifegroup_id, l.lifegroup_name
        FROM lifegroups l
        JOIN member_lifegroups ml ON l.lifegroup_id = ml.lifegroup_id
        WHERE ml.member_id = %s
        ORDER BY l.lifegroup_name
    """, (user['member_id'],))
    lifegroups = cursor.fetchall()
    lifegroup_data = {
        'lifegroup_ids': [l['lifegroup_id'] for l in lifegroups],
        'lifegroup_names': [l['lifegroup_name'] for l in lifegroups]
    } if lifegroups else None

    # Fetch upcoming and past events
    cursor.execute("SELECT * FROM events ORDER BY event_date, event_time")
    events = cursor.fetchall()
    upcoming_events = []
    past_events = []

    now = datetime.now()
    for event in events:
        # Format event_time properly
        event_time = event.get('event_time')
        if event_time:
            if isinstance(event_time, timedelta):  # MySQL TIME returns timedelta
                total_seconds = int(event_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                dt = datetime(1, 1, 1, hours, minutes)
                event['event_time_formatted'] = dt.strftime('%I:%M %p')
            elif isinstance(event_time, str):
                event['event_time_formatted'] = datetime.strptime(event_time, '%H:%M:%S').strftime('%I:%M %p')
        else:
            event['event_time_formatted'] = None

        # Split upcoming and past
        if event['event_date'] >= now.date():
            upcoming_events.append(event)
        else:
            past_events.append(event)

    cursor.close()
    conn.close()

    return render_template(
        "user_dashboard.html",
        user=user,
        username=f"{user['first_name']} {user['last_name']}",
        profile_pic=profile_pic,
        ministry=ministry_data,
        lifegroup=lifegroup_data,
        upcoming_events=upcoming_events,
        past_events=past_events
    )

@app.route('/all_ministries')
def all_ministries():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM ministries")
    ministries = cursor.fetchall()

    cursor.close()
    conn.close()

    # Pass profile_pic from session (or default if not set)
    profile_pic = session.get('profile_pic', 'default-profile.png')
    
    return render_template('all_ministries.html', ministries=ministries, profile_pic=profile_pic)


@app.context_processor
def inject_profile_pic():
    return dict(profile_pic=session.get('profile_pic', 'default-profile.png'))


@app.route('/ministry/<int:ministry_id>')
def user_view_ministry(ministry_id):
    if 'email' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch ministry details
    cursor.execute("""
        SELECT ministry_id, ministry_name, description, schedule
        FROM ministries
        WHERE ministry_id = %s
    """, (ministry_id,))
    ministry = cursor.fetchone()

    # Fetch current user details
    cursor.execute("""
        SELECT * FROM users WHERE email = %s
    """, (session['email'],))
    user = cursor.fetchone()

    cursor.close()
    conn.close()
    
    if not ministry:
        flash("Ministry not found", "danger")
        return redirect('/all_ministries')
    
    return render_template('user_view_ministry.html', ministry=ministry, user=user)



@app.route('/all_lifegroups')
def all_lifegroups():
    if 'email' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT lifegroup_id, lifegroup_name FROM lifegroups ORDER BY lifegroup_name")
    lifegroups = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Get profile picture from session, fallback to default
    profile_pic = session.get('profile_pic', 'default-profile.png')
    
    return render_template('all_lifegroups.html', lifegroups=lifegroups, profile_pic=profile_pic)


@app.route('/view_lifegroup/<int:lifegroup_id>')
def view_lifegroup(lifegroup_id):
    if 'email' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM lifegroups WHERE lifegroup_id = %s", (lifegroup_id,))
    lifegroup = cursor.fetchone()
    cursor.close()
    conn.close()

    if not lifegroup:
        flash("Life Group not found", "danger")
        return redirect('/all_lifegroups')
    
    # Pass profile_pic to template
    profile_pic = session.get('profile_pic', 'default-profile.png')
    return render_template('user_view_lifegroup.html', lifegroup=lifegroup, profile_pic=profile_pic)



@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user info
    cursor.execute("SELECT * FROM users WHERE email=%s", (session['email'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        new_password = request.form.get('password')

        # Handle profile picture
        file = request.files.get('profile_pic')
        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
        else:
            filename = user.get('profile_pic')  # keep old picture or None

        # Update database
        cursor.execute("""
            UPDATE users
            SET username=%s, email=%s, password=%s, profile_pic=%s
            WHERE email=%s
        """, (new_username, new_email, new_password, filename, session['email']))
        conn.commit()

        # Update session
        session['email'] = new_email
        session['profile_pic'] = filename

        flash("Profile updated successfully!", "success")
        return redirect(url_for('update_profile'))

    cursor.close()
    conn.close()
    return render_template('update_profile.html', user=user)



from flask import send_from_directory

import os
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

from flask import Flask, render_template, request, redirect, url_for, flash

@app.route("/admin/users")
def view_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, username, email, role, password FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("admin_users.html", users=users)


@app.route("/admin/add_user", methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
            (username, email, password, role)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("User added successfully!", "success")
        return redirect(url_for("view_users"))

    return render_template("add_user.html")


@app.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if request.method == "POST":
        username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        password = request.form.get('password')

        if password:
            cursor.execute(
                "UPDATE users SET username=%s, email=%s, role=%s, password=%s WHERE id=%s",
                (username, email, role, password, user_id)
            )
        else:
            cursor.execute(
                "UPDATE users SET username=%s, email=%s, role=%s WHERE id=%s",
                (username, email, role, user_id)
            )

        conn.commit()
        cursor.close()
        conn.close()

        flash("User updated successfully!", "success")
        return redirect(url_for("view_users"))

    cursor.close()
    conn.close()
    return render_template("edit_user.html", user=user)


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("User deleted successfully!", "success")
    return redirect(url_for("view_users"))



@app.route("/admin/add_members", methods=["GET", "POST"])
def add_members():
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM lifegroups ORDER BY lifegroup_name ASC")
    lifegroups = cursor.fetchall()

    cursor.execute("SELECT * FROM ministries ORDER BY ministry_name ASC")
    ministries = cursor.fetchall()

    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        gender = request.form["gender"]
        birth_date = request.form.get("birth_date")
        marital_status = request.form.get("marital_status")
        contact_number = request.form.get("contact_number")
        email = request.form.get("email")
        address = request.form.get("address")
        status = request.form["status"]
        notes = request.form.get("notes")

        lifegroup_ids = request.form.getlist("lifegroup_ids")
        ministry_ids = request.form.getlist("ministry_ids")

        profile_pic = "default.jpg"
        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join("static/uploads", filename)
                file.save(filepath)
                profile_pic = filename

        cursor.execute("""
            INSERT INTO members (first_name, last_name, gender, birth_date, marital_status,
                                 contact_number, email, address, status, notes, profile_pic)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (first_name, last_name, gender, birth_date, marital_status,
              contact_number, email, address, status, notes, profile_pic))
        conn.commit()

        member_id = cursor.lastrowid

        for lg_id in lifegroup_ids:
            cursor.execute("INSERT INTO member_lifegroups (member_id, lifegroup_id) VALUES (%s, %s)",
                           (member_id, lg_id))

        for m_id in ministry_ids:
            cursor.execute("INSERT INTO member_ministries (member_id, ministry_id) VALUES (%s, %s)",
                           (member_id, m_id))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Member added successfully!", "success")
        return redirect(url_for("view_members"))

    cursor.close()
    conn.close()
    return render_template("add_members.html", lifegroups=lifegroups, ministries=ministries)

@app.route("/admin/members")
@app.route("/admin/members/<int:member_id>")
def view_members(member_id=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if member_id:
        cursor.execute("""
            SELECT 
                m.member_id,
                m.first_name,
                m.last_name,
                m.gender,
                m.birth_date,
                m.marital_status,
                m.contact_number,
                m.email,
                m.address,
                m.status,
                m.notes,
                m.profile_pic,
                GROUP_CONCAT(DISTINCT mn.ministry_name SEPARATOR ', ') AS ministries,
                GROUP_CONCAT(DISTINCT mn.ministry_id SEPARATOR ',') AS ministry_ids,
                GROUP_CONCAT(DISTINCT lg.lifegroup_name SEPARATOR ', ') AS lifegroups,
                GROUP_CONCAT(DISTINCT lg.lifegroup_id SEPARATOR ',') AS lifegroup_ids
            FROM members AS m
            LEFT JOIN member_ministries AS mm ON m.member_id = mm.member_id
            LEFT JOIN ministries AS mn ON mm.ministry_id = mn.ministry_id
            LEFT JOIN member_lifegroups AS ml ON m.member_id = ml.member_id
            LEFT JOIN lifegroups AS lg ON ml.lifegroup_id = lg.lifegroup_id
            WHERE m.member_id = %s
            GROUP BY m.member_id
        """, (member_id,))
        member = cursor.fetchone()
        members = [member] if member else []
    else:
        # Fetch all members
        cursor.execute("""
            SELECT 
                m.member_id,
                m.first_name,
                m.last_name,
                m.gender,
                m.birth_date,
                m.marital_status,
                m.contact_number,
                m.email,
                m.address,
                m.status,
                m.notes,
                m.profile_pic,
                GROUP_CONCAT(DISTINCT mn.ministry_name SEPARATOR ', ') AS ministries,
                GROUP_CONCAT(DISTINCT mn.ministry_id SEPARATOR ',') AS ministry_ids,
                GROUP_CONCAT(DISTINCT lg.lifegroup_name SEPARATOR ', ') AS lifegroups,
                GROUP_CONCAT(DISTINCT lg.lifegroup_id SEPARATOR ',') AS lifegroup_ids
            FROM members AS m
            LEFT JOIN member_ministries AS mm ON m.member_id = mm.member_id
            LEFT JOIN ministries AS mn ON mm.ministry_id = mn.ministry_id
            LEFT JOIN member_lifegroups AS ml ON m.member_id = ml.member_id
            LEFT JOIN lifegroups AS lg ON ml.lifegroup_id = lg.lifegroup_id
            GROUP BY m.member_id
            ORDER BY m.member_id DESC
        """)
        members = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("view_members.html", members=members, member_id=member_id)



@app.route("/edit_member/<int:member_id>", methods=["GET", "POST"])
def edit_member(member_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch member details
    cursor.execute("SELECT * FROM members WHERE member_id = %s", (member_id,))
    member = cursor.fetchone()

    if not member:
        cursor.close()
        conn.close()
        flash("Member not found.", "danger")
        return redirect(url_for("view_members"))

    # Fetch ministries and lifegroups
    cursor.execute("SELECT * FROM ministries ORDER BY ministry_name")
    ministries = cursor.fetchall()

    cursor.execute("SELECT * FROM lifegroups ORDER BY lifegroup_name")
    lifegroups = cursor.fetchall()

    # Get current selections
    cursor.execute("SELECT ministry_id FROM member_ministries WHERE member_id = %s", (member_id,))
    member_ministries = [row["ministry_id"] for row in cursor.fetchall()]

    cursor.execute("SELECT lifegroup_id FROM member_lifegroups WHERE member_id = %s", (member_id,))
    member_lifegroups = [row["lifegroup_id"] for row in cursor.fetchall()]

    if request.method == "POST":
        # Basic member info
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        gender = request.form["gender"]
        birth_date = request.form.get("birth_date")
        marital_status = request.form.get("marital_status")
        contact_number = request.form["contact_number"]
        email = request.form["email"]
        address = request.form.get("address")
        status = request.form["status"]
        notes = request.form.get("notes")

        # Update member info
        cursor.execute("""
            UPDATE members 
            SET first_name=%s, last_name=%s, gender=%s, birth_date=%s, marital_status=%s,
                contact_number=%s, email=%s, address=%s, status=%s, notes=%s
            WHERE member_id=%s
        """, (first_name, last_name, gender, birth_date, marital_status,
              contact_number, email, address, status, notes, member_id))

        # Handle profile picture
        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                filepath = os.path.join("static/uploads", filename)
                file.save(filepath)
                # Update profile_pic in DB
                cursor.execute("UPDATE members SET profile_pic=%s WHERE member_id=%s", (filename, member_id))

        # Update ministries
        cursor.execute("DELETE FROM member_ministries WHERE member_id=%s", (member_id,))
        for mid in request.form.getlist("ministries"):
            cursor.execute("INSERT INTO member_ministries (member_id, ministry_id) VALUES (%s, %s)", (member_id, mid))

        # Update lifegroups
        cursor.execute("DELETE FROM member_lifegroups WHERE member_id=%s", (member_id,))
        for lid in request.form.getlist("lifegroups"):
            cursor.execute("INSERT INTO member_lifegroups (member_id, lifegroup_id) VALUES (%s, %s)", (member_id, lid))

        conn.commit()
        flash("Member updated successfully!", "success")
        return redirect(url_for("view_members"))

    cursor.close()
    conn.close()

    return render_template(
        "edit_member.html",
        member=member,
        ministries=ministries,
        lifegroups=lifegroups,
        member_ministries=member_ministries,
        member_lifegroups=member_lifegroups
    )

@app.route("/delete_member/<int:member_id>")
def delete_member(member_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM members WHERE member_id = %s", (member_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Member deleted successfully!", "success")
    return redirect(url_for("view_members"))


@app.route('/member_profile/<int:member_id>')
def member_profile(member_id):
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch member info
    cursor.execute('SELECT * FROM members WHERE member_id = %s', (member_id,))
    member = cursor.fetchone()
    if not member:
        cursor.close()
        conn.close()
        return "Member not found", 404

    # Fetch lifegroups with leader info
    cursor.execute("""
        SELECT lg.lifegroup_name, lg.lifegroup_id,
               CASE WHEN lg.leader_id = %s THEN 1 ELSE 0 END AS is_leader
        FROM lifegroups lg
        JOIN member_lifegroups mlg ON lg.lifegroup_id = mlg.lifegroup_id
        WHERE mlg.member_id = %s
    """, (member_id, member_id))
    lg_data = cursor.fetchall()
    if lg_data:
        member['lifegroups'] = ', '.join([
            f"{lg['lifegroup_name']} (Leader)" if lg['is_leader'] else lg['lifegroup_name']
            for lg in lg_data
        ])
        member['lifegroup_ids'] = ', '.join([str(lg['lifegroup_id']) for lg in lg_data])
    else:
        member['lifegroups'] = None
        member['lifegroup_ids'] = None

    # Fetch ministries with leader info
    cursor.execute("""
        SELECT m.ministry_name, m.ministry_id,
               CASE WHEN m.leader_id = %s THEN 1 ELSE 0 END AS is_leader
        FROM ministries m
        JOIN member_ministries mm ON m.ministry_id = mm.ministry_id
        WHERE mm.member_id = %s
    """, (member_id, member_id))
    min_data = cursor.fetchall()
    if min_data:
        member['ministries'] = ', '.join([
            f"{m['ministry_name']} (Leader)" if m['is_leader'] else m['ministry_name']
            for m in min_data
        ])
        member['ministry_ids'] = ', '.join([str(m['ministry_id']) for m in min_data])
    else:
        member['ministries'] = None
        member['ministry_ids'] = None

    cursor.close()
    conn.close()

    return render_template('member_profile.html', member=member)




@app.route("/view_ministry_members/<int:ministry_id>")
def view_ministry_members(ministry_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch members
    query = """
        SELECT 
            m.member_id, 
            m.first_name, 
            m.last_name, 
            m.gender, 
            m.contact_number, 
            m.email, 
            m.status, 
            mm.notes
        FROM member_ministries mm
        JOIN members m ON mm.member_id = m.member_id
        WHERE mm.ministry_id = %s
    """
    cursor.execute(query, (ministry_id,))
    members = cursor.fetchall()

    # Fetch ministry details including description
    cursor.execute("SELECT ministry_id, ministry_name, description FROM ministries WHERE ministry_id = %s", (ministry_id,))
    ministry = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("view_ministry_members.html", ministry=ministry, members=members)



@app.route("/admin/delete_member_from_ministry/<int:member_id>/<int:ministry_id>", methods=["POST"])
def delete_member_from_ministry(member_id, ministry_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM member_ministries WHERE member_id=%s AND ministry_id=%s",
            (member_id, ministry_id)
        )
        conn.commit()
        flash("Member removed from ministry successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error removing member: {e}", "danger")
    finally:
        cursor.close()
        conn.close()
    return redirect(request.referrer)


@app.route("/admin/update_member_note/<int:member_id>/<int:ministry_id>", methods=["POST"])
def update_member_note(member_id, ministry_id):
    notes = request.form.get("notes", "")
    conn = get_db_connection()
    cursor = conn.cursor()
 
    cursor.execute(
        "SELECT * FROM member_ministries WHERE member_id=%s AND ministry_id=%s",
        (member_id, ministry_id)
    )
    if cursor.fetchone():
        cursor.execute(
            "UPDATE member_ministries SET notes=%s WHERE member_id=%s AND ministry_id=%s",
            (notes, member_id, ministry_id)
        )
    else:
        cursor.execute(
            "INSERT INTO member_ministries (member_id, ministry_id, notes) VALUES (%s, %s, %s)",
            (member_id, ministry_id, notes)
        )
    
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Member note updated successfully!", "success")
    return redirect(url_for('view_ministry_members', ministry_id=ministry_id))


@app.route("/view_lifegroup_members/<int:lifegroup_id>")
def view_lifegroup_members(lifegroup_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch members
    query = """
        SELECT m.member_id, m.first_name, m.last_name, m.gender, m.contact_number,
               m.email, m.status, ml.notes
        FROM members m
        JOIN member_lifegroups ml ON m.member_id = ml.member_id
        WHERE ml.lifegroup_id = %s
    """
    cursor.execute(query, (lifegroup_id,))
    members = cursor.fetchall()

    # Fetch lifegroup info
    cursor.execute("SELECT * FROM lifegroups WHERE lifegroup_id = %s", (lifegroup_id,))
    lifegroup = cursor.fetchone()  # this is now a dict with all fields

    cursor.close()
    conn.close()

    # Pass the lifegroup object to the template
    return render_template(
        "view_lifegroup_members.html",
        lifegroup=lifegroup,
        members=members
    )



@app.route("/update_lifegroup_member_note/<int:member_id>/<int:lifegroup_id>", methods=["POST"])
def update_lifegroup_member_note(member_id, lifegroup_id):
    note = request.form.get("note", "")
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE member_lifegroups SET notes = %s WHERE member_id = %s AND lifegroup_id = %s",
        (note, member_id, lifegroup_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Note updated successfully!", "success")
    return redirect(url_for("view_lifegroup_members", lifegroup_id=lifegroup_id))


@app.route("/remove_member_from_lifegroup/<int:member_id>/<int:lifegroup_id>", methods=["POST"])
def remove_member_from_lifegroup(member_id, lifegroup_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM member_lifegroups WHERE member_id = %s AND lifegroup_id = %s",
        (member_id, lifegroup_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Member removed from this Life Group successfully!", "success")
    return redirect(url_for("view_lifegroup_members", lifegroup_id=lifegroup_id))



@app.route("/admin_ministries")
def admin_ministries():
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all ministries with their leaders
    cursor.execute("""
        SELECT 
            m.ministry_id, 
            m.ministry_name, 
            m.schedule,
            m.leader_id,
            CONCAT(mem.first_name, ' ', mem.last_name) AS leader_name
        FROM ministries m
        LEFT JOIN members mem ON m.leader_id = mem.member_id
        ORDER BY m.ministry_name
    """)
    ministries = cursor.fetchall()

    # Fetch all members for leader/member selection
    cursor.execute("SELECT member_id, first_name, last_name FROM members ORDER BY first_name ASC")
    members = cursor.fetchall()

    # Fetch assigned members for each ministry
    ministry_member_ids = {}
    for ministry in ministries:
        cursor.execute("SELECT member_id FROM member_ministries WHERE ministry_id=%s", (ministry['ministry_id'],))
        ministry_member_ids[ministry['ministry_id']] = [row['member_id'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template(
        "admin_ministries.html",
        ministries=ministries,
        members=members,
        ministry_member_ids=ministry_member_ids
    )

@app.route('/add_ministry', methods=['GET', 'POST'])
def add_ministry():
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        ministry_name = request.form.get("ministry_name")
        description = request.form.get("description", "")  # New field, optional (defaults to empty string)
        leader_id = request.form.get("leader_id")
        schedule = request.form.get("schedule")
        member_ids = request.form.getlist("member_ids")  # list of selected member IDs

        # Insert ministry (updated to include description)
        cursor.execute("""
            INSERT INTO ministries (ministry_name, description, leader_id, schedule)
            VALUES (%s, %s, %s, %s)
        """, (ministry_name, description, leader_id, schedule))
        ministry_id = cursor.lastrowid

        # Assign members
        for member_id in member_ids:
            cursor.execute(
                "INSERT INTO member_ministries (ministry_id, member_id) VALUES (%s, %s)",
                (ministry_id, member_id)
            )

        conn.commit()
        flash("Ministry added successfully!", "success")
        return redirect(url_for("admin_ministries"))

    # GET request: fetch all members to populate dropdowns
    cursor.execute("SELECT * FROM members")
    members = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("add_ministry.html", members=members, leaders=members)  # leaders list is same as members




@app.route("/admin/edit_ministry/<int:ministry_id>", methods=["POST"])
def edit_ministry(ministry_id):
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    ministry_name = request.form.get("ministry_name")
    description = request.form.get("description")
    leader_id = request.form.get("leader_id")
    schedule = request.form.get("schedule")
    member_ids = request.form.getlist("member_ids")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Update ministry info with description
    cursor.execute("""
        UPDATE ministries
        SET ministry_name=%s, description=%s, leader_id=%s, schedule=%s
        WHERE ministry_id=%s
    """, (ministry_name, description, leader_id, schedule, ministry_id))

    # Clear old members
    cursor.execute("DELETE FROM member_ministries WHERE ministry_id=%s", (ministry_id,))

    # Insert new members
    for member_id in member_ids:
        if member_id:  # skip empty strings
            cursor.execute(
                "INSERT INTO member_ministries (ministry_id, member_id) VALUES (%s, %s)",
                (ministry_id, member_id)
            )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Ministry updated successfully!", "info")
    return redirect(url_for("view_ministry_members", ministry_id=ministry_id))




@app.route("/admin/delete_ministry/<int:ministry_id>")
def delete_ministry(ministry_id):
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete related members first to maintain foreign key integrity
    cursor.execute("DELETE FROM member_ministries WHERE ministry_id = %s", (ministry_id,))

    # Delete the ministry itself
    cursor.execute("DELETE FROM ministries WHERE ministry_id = %s", (ministry_id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Ministry deleted successfully!", "danger")
    return redirect(url_for("admin_ministries"))



# Display all Life Groups
@app.route("/admin/lifegroups")
def admin_lifegroups():
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all lifegroups with their leaders
    cursor.execute("""
        SELECT 
            lg.lifegroup_id, 
            lg.lifegroup_name, 
            lg.schedule,
            lg.description,
            lg.leader_id,
            CONCAT(m.first_name, ' ', m.last_name) AS leader_name
        FROM lifegroups lg
        LEFT JOIN members m ON lg.leader_id = m.member_id
        ORDER BY lg.lifegroup_name
    """)
    lifegroups = cursor.fetchall()

    # Fetch all members for leader/member selection
    cursor.execute("SELECT member_id, first_name, last_name FROM members ORDER BY first_name ASC")
    members = cursor.fetchall()

    # Fetch assigned members for each lifegroup
    lifegroup_member_ids = {}
    for lg in lifegroups:
        cursor.execute("SELECT member_id FROM member_lifegroups WHERE lifegroup_id=%s", (lg['lifegroup_id'],))
        lifegroup_member_ids[lg['lifegroup_id']] = [row['member_id'] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template(
        "admin_lifegroups.html",
        lifegroups=lifegroups,
        members=members,
        lifegroup_member_ids=lifegroup_member_ids
    )
    
@app.route("/admin/lifegroups/add", methods=["POST"])
def add_lifegroup():
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    lifegroup_name = request.form.get("lifegroup_name")
    description = request.form.get("description", "")  # optional
    leader_id = request.form.get("leader_id")
    schedule = request.form.get("schedule")
    member_ids = request.form.getlist("member_ids")  # list of selected member IDs

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Insert new life group
    cursor.execute("""
        INSERT INTO lifegroups (lifegroup_name, description, leader_id, schedule)
        VALUES (%s, %s, %s, %s)
    """, (lifegroup_name, description, leader_id, schedule))
    lifegroup_id = cursor.lastrowid

    # Assign members
    for member_id in member_ids:
        cursor.execute(
            "INSERT INTO member_lifegroups (lifegroup_id, member_id) VALUES (%s, %s)",
            (lifegroup_id, member_id)
        )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Life Group added successfully!", "success")
    return redirect(url_for("admin_lifegroups"))

@app.route("/admin/lifegroups/add", methods=["GET"])
def add_lifegroup_page():
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT member_id, first_name, last_name FROM members ORDER BY first_name ASC")
    members = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("add_lifegroup.html", members=members, leaders=members)


@app.route("/admin/lifegroups/edit/<int:lifegroup_id>", methods=["POST"])
def edit_lifegroup(lifegroup_id):
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    lifegroup_name = request.form.get("lifegroup_name")
    description = request.form.get("description")
    leader_id = request.form.get("leader_id")
    schedule = request.form.get("schedule")
    member_ids = request.form.getlist("member_ids")

    # ✅ Pantay lahat ng nasa loob ng function
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Update Life Group info
    cursor.execute("""
        UPDATE lifegroups
        SET lifegroup_name=%s, description=%s, leader_id=%s, schedule=%s
        WHERE lifegroup_id=%s
    """, (lifegroup_name, description, leader_id, schedule, lifegroup_id))

    # Kunin existing members
    cursor.execute("SELECT member_id FROM member_lifegroups WHERE lifegroup_id=%s", (lifegroup_id,))
    existing_members = {row["member_id"] for row in cursor.fetchall()}

    # Convert to set para madali i‑compare
    new_members = set(member_ids)

    # Idagdag yung bago
    for member_id in new_members - existing_members:
        cursor.execute(
            "INSERT INTO member_lifegroups (lifegroup_id, member_id) VALUES (%s, %s)",
            (lifegroup_id, member_id)
        )

    # Tanggalin lang yung hindi na napili
    for member_id in existing_members - new_members:
        cursor.execute(
            "DELETE FROM member_lifegroups WHERE lifegroup_id=%s AND member_id=%s",
            (lifegroup_id, member_id)
        )

    conn.commit()
    cursor.close()
    conn.close()

    flash("Life Group updated successfully!", "info")
    return redirect(url_for("view_lifegroup_members", lifegroup_id=lifegroup_id))


# Delete Life Group
@app.route("/admin/lifegroups/delete/<int:lifegroup_id>")
def delete_lifegroup(lifegroup_id):
    if "email" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete related members and the lifegroup
    cursor.execute("DELETE FROM member_lifegroups WHERE lifegroup_id=%s", (lifegroup_id,))
    cursor.execute("DELETE FROM lifegroups WHERE lifegroup_id=%s", (lifegroup_id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Life Group deleted successfully!", "danger")
    return redirect(url_for("admin_lifegroups"))


@app.route("/admin/tithes/add", methods=["GET", "POST"])
def add_tithe():
    if request.method == "POST":
        amount = request.form['amount']
        date = request.form['date']
        entered_by = session.get('username') or "Admin"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tithes (amount, date, entered_by) VALUES (%s, %s, %s)",
            (amount, date, entered_by)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Tithe added successfully!", "success")
        return redirect(url_for("view_tithes"))

    return render_template("add_tithe.html")


@app.route("/view_tithes")
def view_tithes():
    if 'email' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    filter_type = request.args.get('filter_type')
    date = request.args.get('date')      # From day selector
    month = request.args.get('month')    # From month selector
    year = request.args.get('year')      # From year input

    tithes = []
    total_filtered = 0

    if filter_type == 'day_month' and date:
        cursor.execute("SELECT * FROM tithes WHERE DATE(date) = %s ORDER BY date DESC", (date,))
        tithes = cursor.fetchall()
        cursor.execute("SELECT SUM(amount) AS total FROM tithes WHERE DATE(date) = %s", (date,))
        total_filtered = cursor.fetchone()['total'] or 0

    elif filter_type == 'day_month' and month:
        cursor.execute("""
            SELECT * FROM tithes 
            WHERE MONTH(date) = MONTH(%s) AND YEAR(date) = YEAR(%s)
            ORDER BY date DESC
        """, (month, month))
        tithes = cursor.fetchall()
        cursor.execute("""
            SELECT SUM(amount) AS total FROM tithes 
            WHERE MONTH(date) = MONTH(%s) AND YEAR(date) = YEAR(%s)
        """, (month, month))
        total_filtered = cursor.fetchone()['total'] or 0

    elif filter_type == 'year' and year:
        cursor.execute("SELECT * FROM tithes WHERE YEAR(date) = %s ORDER BY date DESC", (year,))
        tithes = cursor.fetchall()
        cursor.execute("SELECT SUM(amount) AS total FROM tithes WHERE YEAR(date) = %s", (year,))
        total_filtered = cursor.fetchone()['total'] or 0

    else:
        cursor.execute("SELECT * FROM tithes ORDER BY date DESC")
        tithes = cursor.fetchall()
        cursor.execute("SELECT SUM(amount) AS total FROM tithes")
        total_filtered = cursor.fetchone()['total'] or 0

    cursor.close()
    conn.close()

    return render_template("view_tithes.html", tithes=tithes, total_tithes=total_filtered)



@app.route("/admin/tithes/edit/<int:id>", methods=["GET", "POST"])
def edit_tithe(id):
    if 'role' not in session or session['role'] != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tithes WHERE id = %s", (id,))
    tithe = cursor.fetchone()

    if not tithe:
        flash("Tithe not found.", "danger")
        return redirect(url_for("view_tithes"))

    if request.method == "POST":
        amount = request.form["amount"]
        date = request.form["date"]
        entered_by = request.form["entered_by"]

        cursor.execute(
            "UPDATE tithes SET amount=%s, date=%s, entered_by=%s WHERE id=%s",
            (amount, date, entered_by, id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash(" Tithe updated successfully!", "success")
        return redirect(url_for("view_tithes"))

    cursor.close()
    conn.close()
    return render_template("edit_tithe.html", tithe=tithe)


@app.route("/admin/tithes/delete/<int:id>")
def delete_tithe(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tithes WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash(" Tithe deleted successfully!", "success")
    return redirect(url_for("view_tithes"))

@app.route("/admin/expenses/add", methods=["GET", "POST"])
def add_expense():
    if 'role' not in session or session['role'] != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        amount = request.form["amount"]
        category = request.form["category"]
        description = request.form["description"]
        date_spent = request.form["date_spent"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (amount, category, description, date_spent) VALUES (%s, %s, %s, %s)",
            (amount, category, description, date_spent)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Expense added successfully!", "success")
        return redirect(url_for("view_expenses"))

    return render_template("add_expense.html")

@app.route("/admin/view_expenses")
def view_expenses():
    if 'email' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    filter_type = request.args.get('filter_type')
    date = request.args.get('date')
    month = request.args.get('month')
    year = request.args.get('year')

    query = "SELECT * FROM expenses"
    params = []

    if filter_type == 'day_month':
        if date:  # If day selected
            query += " WHERE DATE(date_spent) = %s"
            params.append(date)
        elif month:  # If month selected
            query += " WHERE MONTH(date_spent) = MONTH(%s) AND YEAR(date_spent) = YEAR(%s)"
            params.extend([month, month])
    elif filter_type == 'year' and year:
        query += " WHERE YEAR(date_spent) = %s"
        params.append(year)

    query += " ORDER BY date_spent DESC"
    cursor.execute(query, tuple(params))
    expenses = cursor.fetchall()

    # Calculate total
    total_query = "SELECT SUM(amount) AS total FROM expenses"
    if filter_type == 'day_month':
        if date:
            total_query += " WHERE DATE(date_spent) = %s"
            cursor.execute(total_query, (date,))
        elif month:
            total_query += " WHERE MONTH(date_spent) = MONTH(%s) AND YEAR(date_spent) = YEAR(%s)"
            cursor.execute(total_query, (month, month))
    elif filter_type == 'year' and year:
        total_query += " WHERE YEAR(date_spent) = %s"
        cursor.execute(total_query, (year,))
    else:
        cursor.execute(total_query)

    total_expenses = cursor.fetchone()['total'] or 0

    cursor.close()
    conn.close()

    return render_template("view_expenses.html", expenses=expenses, total_expenses=total_expenses)




@app.route('/admin/edit_expense/<int:id>', methods=['GET', 'POST'])
def edit_expense(id):
    if 'role' not in session or session['role'] != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM expenses WHERE expense_id = %s", (id,))
    expense = cursor.fetchone()

    if not expense:
        flash("Expense not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('view_expenses'))

    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        description = request.form['description']
        date_spent = request.form['date_spent']
        entered_by = session['username']  

        cursor.execute("""
            UPDATE expenses 
            SET amount=%s, category=%s, description=%s, date_spent=%s, entered_by=%s
            WHERE expense_id=%s
        """, (amount, category, description, date_spent, entered_by, id))
        conn.commit()

        flash("Expense updated successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for('view_expenses'))

    cursor.close()
    conn.close()
    return render_template('edit_expense.html', expense=expense)


@app.route('/admin/delete_expense/<int:id>')
def delete_expense(id):
    if 'role' not in session or session['role'] != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE expense_id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Expense deleted successfully!", "success")
    return redirect(url_for('view_expenses'))
@app.route('/admin/add_event', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        event_name = request.form['event_name']
        event_date = request.form['event_date']
        event_time = request.form['event_time']
        description = request.form['description']
        location = request.form['location']

        # Handle image upload
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_url = filename
            else:
                flash('Invalid file type. Only PNG, JPG, JPEG, GIF allowed.', 'danger')
                return redirect(request.url)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (event_name, event_date, event_time, description, location, image_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (event_name, event_date, event_time, description, location, image_url))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Event added successfully!", "success")
        return redirect(url_for('view_events'))

    return render_template('add_event.html')


# ===================== View Events =====================
@app.route('/admin/view_events')
def view_events():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM events ORDER BY event_date DESC")
    events = cursor.fetchall()
    cursor.close()
    conn.close()

    for ev in events:
        ev_time = ev.get('event_time')
        if isinstance(ev_time, time):
            ev['event_time_formatted'] = ev_time.strftime("%I:%M %p")
        elif isinstance(ev_time, timedelta):
            total_seconds = ev_time.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            t = time(hour=hours, minute=minutes, second=seconds)
            ev['event_time_formatted'] = t.strftime("%I:%M %p")
        else:
            ev['event_time_formatted'] = ""

    return render_template('view_events.html', events=events)


# ===================== Edit Event =====================
@app.route('/admin/edit_event/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        event_name = request.form['event_name']
        event_date = request.form['event_date']
        event_time = request.form['event_time']
        description = request.form['description']
        location = request.form['location']

        # Handle image upload
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                # Delete old image
                cursor.execute("SELECT image_url FROM events WHERE event_id=%s", (event_id,))
                old_image = cursor.fetchone()
                if old_image and old_image['image_url']:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image['image_url'])
                    if os.path.exists(old_path):
                        os.remove(old_path)

                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_url = filename
            else:
                flash('Invalid file type.', 'danger')
                return redirect(request.url)

        # Update database
        if image_url:
            cursor.execute("""
                UPDATE events
                SET event_name=%s, event_date=%s, event_time=%s, description=%s, location=%s, image_url=%s
                WHERE event_id=%s
            """, (event_name, event_date, event_time, description, location, image_url, event_id))
        else:
            cursor.execute("""
                UPDATE events
                SET event_name=%s, event_date=%s, event_time=%s, description=%s, location=%s
                WHERE event_id=%s
            """, (event_name, event_date, event_time, description, location, event_id))

        conn.commit()
        cursor.close()
        conn.close()
        flash("Event updated successfully!", "success")
        return redirect(url_for('view_events'))

    # GET method: fetch event
    cursor.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_event.html', event=event)


# ===================== Delete Event =====================
@app.route('/admin/delete_event/<int:event_id>')
def delete_event(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete associated image file
    cursor.execute("SELECT image_url FROM events WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()
    if event and event[0]:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], event[0])
        if os.path.exists(image_path):
            os.remove(image_path)

    cursor.execute("DELETE FROM events WHERE event_id=%s", (event_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Event deleted successfully!", "danger")
    return redirect(url_for('view_events'))

from datetime import datetime, timedelta, time 
# ===================== Event Detail =====================
@app.route('/event/<int:event_id>')
def event_detail(event_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM events WHERE event_id = %s", (event_id,))
    event = cursor.fetchone()
    cursor.close()
    conn.close()

    if event is None:
        return "Event not found", 404

    if event['event_time']:
        # Convert MySQL TIME (timedelta) to proper time object
        if isinstance(event['event_time'], timedelta):
            total_seconds = event['event_time'].total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            time_obj = time(hour=hours, minute=minutes, second=seconds)
        else:
            time_obj = event['event_time']  # already a time object
        event['event_time_formatted'] = time_obj.strftime('%I:%M %p')
    else:
        event['event_time_formatted'] = ""

    return render_template('event_detail.html', event=event)


if __name__ == "__main__":
    app.run(debug=True)
