"""
ATTENDIFY v2- Student Attendance Management System
Professional Edition | BCA Final Year Project
"""
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, make_response)
from functools import wraps
from datetime import date
import sqlite3, hashlib, csv, io, os

app = Flask(__name__)
app.secret_key = "attendify_v2_bca_2026"
DATABASE = os.path.join("instance", "attendify.db")

# ── DB ───────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def md5(t): return hashlib.md5(t.encode()).hexdigest()

def init_db():
    if os.path.exists(DATABASE): return
    conn = get_db()
    conn.executescript("""
        CREATE TABLE admin(
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstName TEXT NOT NULL, lastName TEXT NOT NULL DEFAULT '',
            emailAddress TEXT NOT NULL UNIQUE, password TEXT NOT NULL
        );
        CREATE TABLE tblterm(
            Id INTEGER PRIMARY KEY AUTOINCREMENT, termName TEXT NOT NULL
        );
        CREATE TABLE tblsessionterm(
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            sessionName TEXT NOT NULL, termId INTEGER NOT NULL,
            isActive INTEGER NOT NULL DEFAULT 0,
            dateCreated TEXT NOT NULL DEFAULT (date('now'))
        );
        CREATE TABLE tblclass(
            Id INTEGER PRIMARY KEY AUTOINCREMENT, className TEXT NOT NULL
        );
        CREATE TABLE tblclassarms(
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            classId INTEGER NOT NULL, classArmName TEXT NOT NULL,
            isAssigned INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE tblclassteacher(
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstName TEXT NOT NULL, lastName TEXT NOT NULL,
            emailAddress TEXT NOT NULL UNIQUE, password TEXT NOT NULL,
            phoneNo TEXT NOT NULL DEFAULT '',
            classId INTEGER, classArmId INTEGER,
            dateCreated TEXT NOT NULL DEFAULT (date('now'))
        );
        CREATE TABLE tblstudents(
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstName TEXT NOT NULL, lastName TEXT NOT NULL,
            otherName TEXT NOT NULL DEFAULT '',
            admissionNumber TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL DEFAULT '12345',
            classId INTEGER, classArmId INTEGER,
            dateCreated TEXT NOT NULL DEFAULT (date('now'))
        );
        CREATE TABLE tblattendance(
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            admissionNo TEXT NOT NULL,
            classId INTEGER NOT NULL, classArmId INTEGER NOT NULL,
            sessionTermId INTEGER NOT NULL,
            status INTEGER NOT NULL DEFAULT 0,
            dateTimeTaken TEXT NOT NULL
        );
    """)
    for t in ['First Term','Second Term','Third Term']:
        conn.execute("INSERT INTO tblterm(termName) VALUES(?)",(t,))
    conn.commit(); conn.close()
    print("✅  Database initialized.")

# ── GUARDS ───────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def d(*a,**k):
        if session.get('role')!='admin':
            flash('Admin login required.','danger')
            return redirect(url_for('login'))
        return f(*a,**k)
    return d

def teacher_required(f):
    @wraps(f)
    def d(*a,**k):
        if session.get('role')!='teacher':
            flash('Teacher login required.','danger')
            return redirect(url_for('login'))
        return f(*a,**k)
    return d

# ── AUTH ─────────────────────────────────────────────────────
@app.route('/', methods=['GET','POST'])
def login():
    if session.get('role')=='admin': return redirect(url_for('admin_dashboard'))
    if session.get('role')=='teacher': return redirect(url_for('teacher_dashboard'))
    if request.method=='POST':
        role=request.form['role']; email=request.form['email'].strip().lower()
        pwd=md5(request.form['password']); db=get_db()
        if role=='admin':
            u=db.execute("SELECT * FROM admin WHERE emailAddress=? AND password=?",(email,pwd)).fetchone()
            if u:
                session.update(role='admin',uid=u['Id'],name=u['firstName'])
                db.close(); return redirect(url_for('admin_dashboard'))
        elif role=='teacher':
            u=db.execute("SELECT * FROM tblclassteacher WHERE emailAddress=? AND password=?",(email,pwd)).fetchone()
            if u:
                session.update(role='teacher',uid=u['Id'],
                    name=u['firstName']+' '+u['lastName'],
                    classId=u['classId'],classArmId=u['classArmId'])
                db.close(); return redirect(url_for('teacher_dashboard'))
        db.close(); flash('Invalid email or password!','danger')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        role=request.form['role']
        fn=request.form['firstName'].strip()
        ln=request.form['lastName'].strip()
        email=request.form['email'].strip().lower()
        pwd=request.form['password']; pwd2=request.form['password2']
        if pwd!=pwd2:
            flash('Passwords do not match!','danger')
            return redirect(url_for('register'))
        if len(pwd)<6:
            flash('Password must be at least 6 characters!','danger')
            return redirect(url_for('register'))
        db=get_db(); h=md5(pwd)
        if role=='admin':
            if db.execute("SELECT Id FROM admin WHERE emailAddress=?",(email,)).fetchone():
                flash('Email already registered!','danger')
                db.close(); return redirect(url_for('register'))
            db.execute("INSERT INTO admin(firstName,lastName,emailAddress,password) VALUES(?,?,?,?)",(fn,ln,email,h))
            db.commit(); db.close()
            flash('Admin account created! Please login.','success')
            return redirect(url_for('login'))
        elif role=='teacher':
            if db.execute("SELECT Id FROM tblclassteacher WHERE emailAddress=?",(email,)).fetchone():
                flash('Email already registered!','danger')
                db.close(); return redirect(url_for('register'))
            db.execute("""INSERT INTO tblclassteacher
                (firstName,lastName,emailAddress,password,phoneNo,classId,classArmId)
                VALUES(?,?,?,?,?,?,?)""",
                (fn,ln,email,h,request.form.get('phone',''),
                 request.form.get('classId') or None,
                 request.form.get('classArmId') or None))
            db.commit(); db.close()
            flash('Teacher account created! Please login.','success')
            return redirect(url_for('login'))
    db=get_db()
    classes=db.execute("SELECT * FROM tblclass").fetchall()
    arms=db.execute("SELECT ca.*,c.className FROM tblclassarms ca JOIN tblclass c ON c.Id=ca.classId").fetchall()
    db.close()
    return render_template('register.html',classes=classes,arms=arms)

@app.route('/logout')
def logout():
    session.clear(); flash('Logged out successfully.','success')
    return redirect(url_for('login'))

# ── AJAX ─────────────────────────────────────────────────────
@app.route('/ajax/arms/<int:cid>')
def ajax_arms(cid):
    db=get_db()
    arms=db.execute("SELECT Id,classArmName FROM tblclassarms WHERE classId=?",(cid,)).fetchall()
    db.close()
    return jsonify([{'id':a['Id'],'name':a['classArmName']} for a in arms])

# ── ADMIN DASHBOARD ──────────────────────────────────────────
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db=get_db()
    stats=dict(
        students=db.execute("SELECT COUNT(*) FROM tblstudents").fetchone()[0],
        teachers=db.execute("SELECT COUNT(*) FROM tblclassteacher").fetchone()[0],
        classes=db.execute("SELECT COUNT(*) FROM tblclass").fetchone()[0],
        arms=db.execute("SELECT COUNT(*) FROM tblclassarms").fetchone()[0],
        sessions=db.execute("SELECT COUNT(*) FROM tblsessionterm").fetchone()[0],
        attendance=db.execute("SELECT COUNT(*) FROM tblattendance").fetchone()[0],
    )
    # Chart data: attendance per class
    chart_data=db.execute("""
        SELECT c.className,
            SUM(CASE WHEN a.status=1 THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN a.status=0 THEN 1 ELSE 0 END) as absent
        FROM tblattendance a JOIN tblclass c ON c.Id=a.classId
        GROUP BY a.classId
    """).fetchall()
    # Low attendance students (<75%)
    low_att=db.execute("""
        SELECT s.firstName,s.lastName,s.admissionNumber,
            c.className,ca.classArmName,
            COUNT(a.Id) as total,
            SUM(CASE WHEN a.status=1 THEN 1 ELSE 0 END) as present,
            ROUND(SUM(CASE WHEN a.status=1 THEN 1.0 ELSE 0 END)/COUNT(a.Id)*100,1) as pct
        FROM tblstudents s
        JOIN tblclass c ON c.Id=s.classId
        JOIN tblclassarms ca ON ca.Id=s.classArmId
        JOIN tblattendance a ON a.admissionNo=s.admissionNumber
        GROUP BY s.admissionNumber
        HAVING pct < 75.0
        ORDER BY pct ASC LIMIT 10
    """).fetchall()
    db.close()
    return render_template('admin/dashboard.html',stats=stats,
                           chart_data=chart_data,low_att=low_att)

# ── ADMIN CLASSES ────────────────────────────────────────────
@app.route('/admin/classes',methods=['GET','POST'])
@admin_required
def admin_classes():
    db=get_db()
    if request.method=='POST':
        a=request.form.get('action')
        if a=='add':
            if db.execute("SELECT Id FROM tblclass WHERE className=?",(request.form['className'].strip(),)).fetchone():
                flash('This class already exists!','danger')
            else:
                db.execute("INSERT INTO tblclass(className) VALUES(?)",(request.form['className'].strip(),))
                db.commit(); flash('Class added successfully!','success')
        elif a=='delete':
            db.execute("DELETE FROM tblclass WHERE Id=?",(request.form['id'],))
            db.commit(); flash('Class deleted.','success')
        elif a=='edit':
            db.execute("UPDATE tblclass SET className=? WHERE Id=?",(request.form['className'].strip(),request.form['id']))
            db.commit(); flash('Class updated successfully!','success')
        db.close(); return redirect(url_for('admin_classes'))
    classes=db.execute("SELECT * FROM tblclass").fetchall()
    db.close()
    return render_template('admin/classes.html',classes=classes)

# ── ADMIN ARMS ───────────────────────────────────────────────
@app.route('/admin/arms',methods=['GET','POST'])
@admin_required
def admin_arms():
    db=get_db()
    if request.method=='POST':
        a=request.form.get('action')
        if a=='add':
            if db.execute("SELECT Id FROM tblclassarms WHERE classId=? AND classArmName=?",(request.form['classId'],request.form['armName'].strip())).fetchone():
                flash('This division already exists!','danger')
            else:
                db.execute("INSERT INTO tblclassarms(classId,classArmName,isAssigned) VALUES(?,?,1)",(request.form['classId'],request.form['armName'].strip()))
                db.commit(); flash('Division added successfully!','success')
        elif a=='delete':
            db.execute("DELETE FROM tblclassarms WHERE Id=?",(request.form['id'],))
            db.commit(); flash('Division deleted.','success')
        db.close(); return redirect(url_for('admin_arms'))
    arms=db.execute("SELECT ca.*,c.className FROM tblclassarms ca JOIN tblclass c ON c.Id=ca.classId").fetchall()
    classes=db.execute("SELECT * FROM tblclass").fetchall()
    db.close()
    return render_template('admin/arms.html',arms=arms,classes=classes)

# ── ADMIN TEACHERS ───────────────────────────────────────────
@app.route('/admin/teachers',methods=['GET','POST'])
@admin_required
def admin_teachers():
    db=get_db()
    if request.method=='POST':
        a=request.form.get('action')
        if a=='add':
            if db.execute("SELECT Id FROM tblclassteacher WHERE emailAddress=?",(request.form['email'].strip().lower(),)).fetchone():
                flash('Email already registered!','danger')
            else:
                db.execute("""INSERT INTO tblclassteacher(firstName,lastName,emailAddress,password,phoneNo,classId,classArmId)
                    VALUES(?,?,?,?,?,?,?)""",(request.form['firstName'],request.form['lastName'],
                    request.form['email'].strip().lower(),md5(request.form['password']),
                    request.form['phone'],request.form['classId'],request.form['classArmId']))
                db.commit(); flash('Teacher added successfully!','success')
        elif a=='delete':
            db.execute("DELETE FROM tblclassteacher WHERE Id=?",(request.form['id'],))
            db.commit(); flash('Teacher deleted.','success')
        elif a=='assign':
            db.execute("UPDATE tblclassteacher SET classId=?,classArmId=? WHERE Id=?",(request.form['classId'],request.form['classArmId'],request.form['id']))
            db.commit(); flash('Class assigned successfully!','success')
        db.close(); return redirect(url_for('admin_teachers'))
    teachers=db.execute("""SELECT t.*,c.className,ca.classArmName FROM tblclassteacher t
        LEFT JOIN tblclass c ON c.Id=t.classId LEFT JOIN tblclassarms ca ON ca.Id=t.classArmId ORDER BY t.firstName""").fetchall()
    classes=db.execute("SELECT * FROM tblclass").fetchall()
    arms=db.execute("SELECT ca.*,c.className FROM tblclassarms ca JOIN tblclass c ON c.Id=ca.classId").fetchall()
    db.close()
    return render_template('admin/teachers.html',teachers=teachers,classes=classes,arms=arms)

# ── ADMIN STUDENTS ───────────────────────────────────────────
@app.route('/admin/students',methods=['GET','POST'])
@admin_required
def admin_students():
    db=get_db()
    if request.method=='POST':
        a=request.form.get('action')
        if a=='add':
            if db.execute("SELECT Id FROM tblstudents WHERE admissionNumber=?",(request.form['admNo'],)).fetchone():
                flash('Admission number already exists!','danger')
            else:
                db.execute("""INSERT INTO tblstudents(firstName,lastName,otherName,admissionNumber,password,classId,classArmId)
                    VALUES(?,?,?,?,?,?,?)""",(request.form['firstName'],request.form['lastName'],
                    request.form.get('otherName',''),request.form['admNo'],'12345',
                    request.form['classId'],request.form['classArmId']))
                db.commit(); flash('Student added successfully!','success')
        elif a=='delete':
            db.execute("DELETE FROM tblstudents WHERE Id=?",(request.form['id'],))
            db.commit(); flash('Student deleted.','success')
        db.close(); return redirect(url_for('admin_students'))
    students=db.execute("""SELECT s.*,c.className,ca.classArmName FROM tblstudents s
        LEFT JOIN tblclass c ON c.Id=s.classId LEFT JOIN tblclassarms ca ON ca.Id=s.classArmId
        ORDER BY s.classId,s.classArmId,s.firstName""").fetchall()
    classes=db.execute("SELECT * FROM tblclass").fetchall()
    arms=db.execute("SELECT ca.*,c.className FROM tblclassarms ca JOIN tblclass c ON c.Id=ca.classId").fetchall()
    db.close()
    return render_template('admin/students.html',students=students,classes=classes,arms=arms)

# ── ADMIN SESSIONS ───────────────────────────────────────────
@app.route('/admin/sessions',methods=['GET','POST'])
@admin_required
def admin_sessions():
    db=get_db()
    if request.method=='POST':
        a=request.form.get('action')
        if a=='add':
            db.execute("INSERT INTO tblsessionterm(sessionName,termId,isActive) VALUES(?,?,0)",(request.form['sessionName'],request.form['termId']))
            db.commit(); flash('Session added successfully!','success')
        elif a=='activate':
            db.execute("UPDATE tblsessionterm SET isActive=0")
            db.execute("UPDATE tblsessionterm SET isActive=1 WHERE Id=?",(request.form['id'],))
            db.commit(); flash('Session activated successfully!','success')
        elif a=='deactivate':
            db.execute("UPDATE tblsessionterm SET isActive=0 WHERE Id=?",(request.form['id'],))
            db.commit(); flash('Session deactivated.','success')
        elif a=='delete':
            db.execute("DELETE FROM tblsessionterm WHERE Id=?",(request.form['id'],))
            db.commit(); flash('Session deleted.','success')
        db.close(); return redirect(url_for('admin_sessions'))
    sessions=db.execute("SELECT st.*,t.termName FROM tblsessionterm st JOIN tblterm t ON t.Id=st.termId").fetchall()
    terms=db.execute("SELECT * FROM tblterm").fetchall()
    db.close()
    return render_template('admin/sessions.html',sessions=sessions,terms=terms)

# ── TEACHER DASHBOARD ────────────────────────────────────────
@app.route('/teacher/dashboard')
@teacher_required
def teacher_dashboard():
    db=get_db(); cid=session.get('classId'); aid=session.get('classArmId')
    class_info=None; total=0; present_today=0; today=date.today().isoformat()
    att_summary=[]; low_students=[]
    if cid and aid:
        class_info=db.execute("""SELECT c.className,ca.classArmName FROM tblclassteacher t
            JOIN tblclass c ON c.Id=t.classId JOIN tblclassarms ca ON ca.Id=t.classArmId WHERE t.Id=?""",(session['uid'],)).fetchone()
        total=db.execute("SELECT COUNT(*) FROM tblstudents WHERE classId=? AND classArmId=?",(cid,aid)).fetchone()[0]
        present_today=db.execute("SELECT COUNT(*) FROM tblattendance WHERE classId=? AND classArmId=? AND dateTimeTaken=? AND status=1",(cid,aid,today)).fetchone()[0]
        # Attendance % per student
        att_summary=db.execute("""
            SELECT s.firstName,s.lastName,s.admissionNumber,
                COUNT(a.Id) as total_days,
                SUM(CASE WHEN a.status=1 THEN 1 ELSE 0 END) as present_days,
                ROUND(SUM(CASE WHEN a.status=1 THEN 1.0 ELSE 0 END)/NULLIF(COUNT(a.Id),0)*100,1) as pct
            FROM tblstudents s
            LEFT JOIN tblattendance a ON a.admissionNo=s.admissionNumber
            WHERE s.classId=? AND s.classArmId=?
            GROUP BY s.admissionNumber ORDER BY pct ASC
        """,(cid,aid)).fetchall()
        low_students=[r for r in att_summary if r['pct'] is not None and r['pct']<75]
    db.close()
    return render_template('teacher/dashboard.html',class_info=class_info,
        total=total,present_today=present_today,today=today,
        att_summary=att_summary,low_students=low_students)

# ── TEACHER STUDENTS ─────────────────────────────────────────
@app.route('/teacher/students')
@teacher_required
def teacher_students():
    db=get_db()
    students=db.execute("""SELECT s.*,c.className,ca.classArmName,
        COUNT(a.Id) as total_days,
        SUM(CASE WHEN a.status=1 THEN 1 ELSE 0 END) as present_days,
        ROUND(SUM(CASE WHEN a.status=1 THEN 1.0 ELSE 0 END)/NULLIF(COUNT(a.Id),0)*100,1) as pct
        FROM tblstudents s
        JOIN tblclass c ON c.Id=s.classId JOIN tblclassarms ca ON ca.Id=s.classArmId
        LEFT JOIN tblattendance a ON a.admissionNo=s.admissionNumber
        WHERE s.classId=? AND s.classArmId=?
        GROUP BY s.admissionNumber ORDER BY s.firstName""",(session['classId'],session['classArmId'])).fetchall()
    db.close()
    return render_template('teacher/students.html',students=students)

# ── TEACHER ATTENDANCE ───────────────────────────────────────
@app.route('/teacher/attendance',methods=['GET','POST'])
@teacher_required
def teacher_attendance():
    cid=session.get('classId'); aid=session.get('classArmId')
    if not cid or not aid:
        flash('You have not been assigned a class. Please contact Admin.','warning')
        return redirect(url_for('teacher_dashboard'))
    db=get_db(); today=date.today().isoformat()
    active=db.execute("SELECT * FROM tblsessionterm WHERE isActive=1").fetchone()
    if not active:
        flash('No active session. Please ask Admin to activate a session.','danger')
        db.close(); return redirect(url_for('teacher_dashboard'))
    already_taken=db.execute("SELECT COUNT(*) FROM tblattendance WHERE classId=? AND classArmId=? AND dateTimeTaken=? AND sessionTermId=? AND status=1",(cid,aid,today,active['Id'])).fetchone()[0]>0
    if request.method=='POST':
        if already_taken:
            flash('Attendance for today has already been recorded!','danger')
        else:
            students=db.execute("SELECT admissionNumber FROM tblstudents WHERE classId=? AND classArmId=?",(cid,aid)).fetchall()
            checked=request.form.getlist('present')
            db.execute("DELETE FROM tblattendance WHERE classId=? AND classArmId=? AND dateTimeTaken=? AND sessionTermId=?",(cid,aid,today,active['Id']))
            for s in students:
                db.execute("INSERT INTO tblattendance(admissionNo,classId,classArmId,sessionTermId,status,dateTimeTaken) VALUES(?,?,?,?,?,?)",
                    (s['admissionNumber'],cid,aid,active['Id'],1 if s['admissionNumber'] in checked else 0,today))
            db.commit(); flash('Attendance saved successfully!','success'); already_taken=True
        db.close(); return redirect(url_for('teacher_attendance'))
    students=db.execute("""SELECT s.firstName,s.lastName,s.admissionNumber,
        COALESCE(a.status,-1) AS att_status
        FROM tblstudents s LEFT JOIN tblattendance a
        ON a.admissionNo=s.admissionNumber AND a.dateTimeTaken=? AND a.sessionTermId=?
        WHERE s.classId=? AND s.classArmId=? ORDER BY s.firstName""",(today,active['Id'],cid,aid)).fetchall()
    db.close()
    return render_template('teacher/attendance.html',students=students,today=today,already_taken=already_taken,active=active)

# ── VIEW ATTENDANCE ──────────────────────────────────────────
@app.route('/teacher/view-attendance')
@teacher_required
def teacher_view_attendance():
    db=get_db(); cid=session['classId']; aid=session['classArmId']
    fd=request.args.get('date',''); ff=request.args.get('from_date','')
    ft=request.args.get('to_date',''); fa=request.args.get('adm','')
    q="SELECT a.*,s.firstName,s.lastName,s.admissionNumber,c.className,ca.classArmName,st.sessionName,tt.termName FROM tblattendance a JOIN tblstudents s ON s.admissionNumber=a.admissionNo JOIN tblclass c ON c.Id=a.classId JOIN tblclassarms ca ON ca.Id=a.classArmId JOIN tblsessionterm st ON st.Id=a.sessionTermId JOIN tblterm tt ON tt.Id=st.termId WHERE a.classId=? AND a.classArmId=?"
    p=[cid,aid]
    if fd: q+=" AND a.dateTimeTaken=?"; p.append(fd)
    if ff: q+=" AND a.dateTimeTaken>=?"; p.append(ff)
    if ft: q+=" AND a.dateTimeTaken<=?"; p.append(ft)
    if fa: q+=" AND a.admissionNo=?"; p.append(fa)
    q+=" ORDER BY a.dateTimeTaken DESC,s.firstName"
    records=db.execute(q,p).fetchall()
    students=db.execute("SELECT admissionNumber,firstName,lastName FROM tblstudents WHERE classId=? AND classArmId=? ORDER BY firstName",(cid,aid)).fetchall()
    db.close()
    return render_template('teacher/view_attendance.html',records=records,students=students,
        filter_date=fd,filter_from=ff,filter_to=ft,filter_adm=fa)

# ── STUDENT ATTENDANCE ───────────────────────────────────────
@app.route('/teacher/student-attendance')
@teacher_required
def teacher_student_attendance():
    db=get_db(); cid=session['classId']; aid=session['classArmId']
    fa=request.args.get('adm',''); ft=request.args.get('type','all')
    fd=request.args.get('date',''); ff=request.args.get('from_date',''); fto=request.args.get('to_date','')
    records=[]; student_info=None; pct=None
    if fa:
        student_info=db.execute("SELECT * FROM tblstudents WHERE admissionNumber=?",(fa,)).fetchone()
        q="SELECT a.*,st.sessionName,tt.termName FROM tblattendance a JOIN tblsessionterm st ON st.Id=a.sessionTermId JOIN tblterm tt ON tt.Id=st.termId WHERE a.admissionNo=?"
        p=[fa]
        if ft=='date' and fd: q+=" AND a.dateTimeTaken=?"; p.append(fd)
        elif ft=='range' and ff and fto: q+=" AND a.dateTimeTaken BETWEEN ? AND ?"; p+=[ff,fto]
        q+=" ORDER BY a.dateTimeTaken DESC"
        records=db.execute(q,p).fetchall()
        total=len(records); present=sum(1 for r in records if r['status']==1)
        pct=round(present/total*100,1) if total>0 else None
    students=db.execute("SELECT admissionNumber,firstName,lastName FROM tblstudents WHERE classId=? AND classArmId=? ORDER BY firstName",(cid,aid)).fetchall()
    db.close()
    return render_template('teacher/student_attendance.html',students=students,records=records,
        student_info=student_info,filter_adm=fa,filter_type=ft,filter_date=fd,
        filter_from=ff,filter_to=fto,pct=pct)

# ── DOWNLOAD CSV ─────────────────────────────────────────────
@app.route('/teacher/download-student/<adm_no>')
@teacher_required
def teacher_download_student(adm_no):
    db = get_db()
    records = db.execute("""
        SELECT s.firstName, s.lastName, s.admissionNumber,
               c.className, ca.classArmName,
               st.sessionName, tt.termName,
               a.status, a.dateTimeTaken
        FROM tblattendance a
        JOIN tblstudents s     ON s.admissionNumber=a.admissionNo
        JOIN tblclass c        ON c.Id=a.classId
        JOIN tblclassarms ca   ON ca.Id=a.classArmId
        JOIN tblsessionterm st ON st.Id=a.sessionTermId
        JOIN tblterm tt        ON tt.Id=st.termId
        WHERE a.admissionNo=? AND a.classId=? AND a.classArmId=?
        ORDER BY a.dateTimeTaken DESC
    """, (adm_no, session['classId'], session['classArmId'])).fetchall()
    db.close()

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['#','First Name','Last Name','Admission No',
                'Class','Division','Session','Term','Status','Date'])
    for i, r in enumerate(records, 1):
        w.writerow([i, r['firstName'], r['lastName'], r['admissionNumber'],
                    r['className'], r['classArmName'],
                    r['sessionName'], r['termName'],
                    'Present' if r['status']==1 else 'Absent',
                    r['dateTimeTaken']])

    resp = make_response(out.getvalue())
    resp.headers['Content-Disposition'] = f'attachment; filename=attendance_{adm_no}.csv'
    resp.headers['Content-Type'] = 'text/csv'
    return resp

if __name__=='__main__':
    os.makedirs('instance',exist_ok=True)
    init_db()
    print("\n"+"="*50+"\n  ✅  Attendify v2.0 is running!\n  🌐  Open: http://127.0.0.1:5000\n"+"="*50+"\n")
    app.run(host='0.0.0.0', port=5000, debug=False)

