from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import mysql.connector
import os
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime


# --- Configuration ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
database_name = 'pathshala'

# a = int(input("Enter 1 for production and 0 for local development: "))
# production_global = True if a == 1 else False
production_global = True 

app = Flask(__name__, static_folder=UPLOAD_FOLDER, static_url_path='/static')
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if production_global:
    app.config['SERVER_NAME'] = 'http://165.22.208.62:5003'
    app.config['PREFERRED_URL_SCHEME'] = 'http'

# --- Database Class ---
class Database:
    def __init__(self, host="localhost", user="root", password="", database=database_name, production=False):
        global production_global
        production = production_global
        if production:
            self.host = '127.0.0.1'
            self.user = 'root'
            self.password = 'Ssipmt@2025DODB'
            self.database = database_name
            print("[DB Config] Using PRODUCTION database settings.")
        else:
            self.host = 'localhost'
            self.user = 'root'
            self.password = ''
            self.database = database_name

        self.connection = None
        self.cursor = None
        self._connected = False
        self.connect()

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self.cursor = self.connection.cursor(dictionary=True)
            self._connected = True
        except mysql.connector.Error as err:
            self.connection = None
            self.cursor = None
            self._connected = False

    def is_connected(self):
        return self._connected and self.connection is not None and self.connection.is_connected()

    def execute(self, query, params=None):
        if not self.is_connected():
            return None
        try:
            if self.cursor.with_rows:
                self.cursor.fetchall()

            self.cursor.execute(query, params)

            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP')):
                self.connection.commit()

            return self.cursor
        except mysql.connector.Error as err:
            if self.connection and self.connection.is_connected():
                self.connection.rollback()
            return None
        except Exception as e:
            if self.connection and self.connection.is_connected():
                self.connection.rollback()
            return None

    def fetchall(self):
        if not self.is_connected() or not self.cursor:
            return []
        return self.cursor.fetchall()

    def fetchone(self):
        if not self.is_connected() or not self.cursor:
            return None
        return self.cursor.fetchone()

    def close(self):
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.connection:
            self.connection.close()
            self.connection = None
        self._connected = False

# --- Helper Functions ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- API Routes ---

@app.route('/')
def index():
    return '<html style="text-align: center; background-color: #000;"><h1 style="color:#fff;"> API is running </h1></html>'

@app.route('/fetch_school', methods=['GET'])
def fetch_school():
    db = Database()
    if not db.is_connected():
        return jsonify({
            "status": False,
            "message": "Server is unable to connect to the database. Please check server logs."
        }), 500

    query = 'SELECT * FROM school'
    cursor = db.execute(query)

    if cursor is None:
        return jsonify({
            "status": False,
            "message": "An error occurred while fetching school data."
        }), 500

    schools = cursor.fetchall()
    return jsonify({
        "status": True,
        "message": "School data fetched successfully.",
        "data": schools
    }), 200

@app.route('/data', methods=['GET'])
def show_all_students():
    db = Database()
    result = db.execute("SELECT * FROM student")
    students = result.fetchall()
    if students:
        table_headers = students[0].keys() if students else []

    result1 = db.execute("SELECT * FROM teacher")
    teacher = result1.fetchall()
    table_headers1 = teacher[0].keys() if teacher else []

    result1 = db.execute("SELECT * FROM school")
    schools = result1.fetchall()
    table_headers2 = schools[0].keys() if schools else []
    html = """
    <html>
    <head>
        <title>All Student Data Pathshala</title>
        <style>
            body { background-color: #121212; color: #fff; font-family: sans-serif; padding: 20px; }
            h1 { text-align: center; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #333; padding: 8px; text-align: left; }
            th { background-color: #1f1f1f; }
            tr:nth-child(even) { background-color: #2a2a2a; }
            tr:hover { background-color: #3a3a3a; }
        </style>
    </head>
    <body>
        <h1>All Registered Students of Pathshala</h1>
        <table>
            <tr>""" + "".join(f"<th>{col}</th>" for col in table_headers) + "</tr>"

    for row in students:
        html += "<tr>" + "".join(f"<td>{row[col]}</td>" for col in table_headers) + "</tr>"

    html += """
        </table>
        <h1>All Registered Teachers</h1>
        <table>
            <tr>""" + "".join(f"<th>{col}</th>" for col in table_headers1) + "</tr>"
    for row in teacher:
        html += "<tr>" + "".join(f"<td>{row[col]}</td>" for col in table_headers1) + "</tr>"

    html += """
        </table>
        <h1>All Registered Schools</h1>
        <table>~
            <tr>""" + "".join(f"<th>{col}</th>" for col in table_headers2) + "</tr>"
    for row in schools:
        html += "<tr>" + "".join(f"<td>{row[col]}</td>" for col in table_headers2) + "</tr>"

    html += """
        </table>
    </body>
    </html>
    """

    return Response(html, mimetype='text/html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    db = None
    try:
        udise_code = data.get('udise_code')
        password = data.get('password')
        if not udise_code or not password:
            return jsonify({
                "status": False,
                "message": "UDISE code and password required"
            }), 400

        db = Database()
        if not db.is_connected():
            return jsonify({
                "status": False,
                "message": "Server is unable to connect to the database. Please check server logs."
            }), 500

        cursor = db.execute("SELECT * FROM school WHERE udise_code = %s AND password = %s", (udise_code, password))

        if cursor is None:
            return jsonify({
                "status": False,
                "message": "An error occurred during query execution. Check server logs for details."
            }), 500

        result = cursor.fetchone()

        try:
            if cursor.with_rows:
                cursor.fetchall()
        except Exception as e:
            pass

        if result:
            return jsonify({
                "status": True,
                "message": "Login successful",
                "data": result
            }), 200
        else:
            return jsonify({
                "status": False,
                "message": "Invalid username or password"
            }), 401
    except mysql.connector.Error as err:
        print(f"[LOGIN ERROR] MySQL error: {err}")
        return jsonify({
            "status": False,
            "message": "Database error during login. Please check server logs."
        }), 500
    finally:
        if db:
            db.close()

@app.route('/register', methods=['POST'])
def register():
    db = None
    try:
        required_fields = ['name', 'school_name', 'class', 'mobile', 'name_of_tree', 'udise_code','employeeId']
        for field in required_fields:
            if field not in request.form:
                return jsonify({
                    "status": False,
                    "message": f"Missing required form field: {field}"
                }), 400

        name = request.form['name']
        school_name = request.form['school_name']
        student_class = request.form['class']
        mobile = request.form['mobile']
        name_of_tree = request.form['name_of_tree']
        udise_code = request.form['udise_code']
        employeeId = request.form['employeeId']

        plant_image_file = request.files.get('plant_image')
        certificate_file = request.files.get('certificate')

        plant_image_path = None
        if plant_image_file and allowed_file(plant_image_file.filename):
            original_extension = plant_image_file.filename.rsplit('.', 1)[1].lower()
            plant_image_string_part = "plantimage"
            filename_plant = f"{secure_filename(name)}_{secure_filename(mobile)}_{plant_image_string_part}.{original_extension}"
            plant_image_full_path = os.path.join(UPLOAD_FOLDER, filename_plant)
            plant_image_file.save(plant_image_full_path)
            plant_image_path = os.path.join("uploads", filename_plant)
        else:
            return jsonify({
                "status": False,
                "message": "Plant image file is missing or has an unsupported format (allowed: png, jpg, jpeg, gif)"
            }), 400

        certificate_path = None
        if certificate_file and allowed_file(certificate_file.filename):
            original_extension = certificate_file.filename.rsplit('.', 1)[1].lower()
            certificate_string_part = "certificateimage"
            filename_certificate = f"{secure_filename(name)}_{secure_filename(mobile)}_{certificate_string_part}.{original_extension}"
            certificate_full_path = os.path.join(UPLOAD_FOLDER, filename_certificate)
            certificate_file.save(certificate_full_path)
            certificate_path = os.path.join("uploads", filename_certificate)
        else:
            return jsonify({
                "status": False,
                "message": "Certificate file is missing or has an an unsupported format (allowed: png, jpg, jpeg, gif)"
            }), 400

        db = Database()
        if not db.is_connected():
            return jsonify({
                "status": False,
                "message": "Server is unable to connect to the database for registration."
            }), 500

        verified = 'false'
        query = """
        INSERT INTO student (name, school_name, class, mobile, name_of_tree, plant_image, certificate, udise_code, verified, employee_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            name,
            school_name,
            student_class,
            mobile,
            name_of_tree,
            plant_image_path,
            certificate_path,
            udise_code,
            verified,
            employeeId
        )

        cursor = db.execute(query, params)

        if cursor is None:
            return jsonify({
                "status": False,
                "message": "Failed to register student due to database error. Check server logs."
            }), 500

        if cursor.rowcount == 1:
            return jsonify({
                "status": True,
                "message": "Student registered successfully!",
                "data": {
                    "name": name,
                    "mobile": mobile,
                    "plant_image_url": plant_image_path,
                    "certificate_url": certificate_path
                }
            }), 201
        else:
            return jsonify({
                "status": False,
                "message": "Student registration failed for unknown reasons."
            }), 500

    except Exception as e:
        print(f"[REGISTER ERROR] Unhandled exception: {str(e)}")
        return jsonify({
            "status": False,
            "message": f"Server error during registration: {str(e)}"
        }), 500
    finally:
        if db:
            db.close()

@app.route('/teacher_dashboard', methods=['POST'])
def teacher_dashboard():
    data = request.get_json()
    udise_code = data.get('udise_code')

    if not udise_code:
        return jsonify({
            "status": False,
            "message": "UDISE code is required."
        }), 400

    db = Database()
    if not db.is_connected():
        return jsonify({
            "status": False,
            "message": "Server is unable to connect to the database. Please check server logs."
        }), 500

    query = "SELECT COUNT(*) FROM student WHERE udise_code = %s"
    params = (udise_code,)
    cursor = db.execute(query, params)

    if cursor is None:
        return jsonify({
            "status": False,
            "message": "An error occurred while fetching teacher data."
        }), 500
    result = cursor.fetchone()

    try:
        if cursor.with_rows:
            cursor.fetchall()
    except Exception as e:
        print(f"[WARNING] Error consuming remaining results: {e}")
    actual_count = result['COUNT(*)'] if result else -1

    teacher_query = "SELECT mobile FROM teacher WHERE udise_code = %s LIMIT 1"
    teacher_cursor = db.execute(teacher_query, (udise_code,))
    teacher_result = teacher_cursor.fetchone() if teacher_cursor else None
    teacher_mobile = teacher_result['mobile'] if teacher_result else None

    if result:
        return jsonify({
            "status": True,
            "message": "Total Count of Students of Udise Code {} fetched successfully".format(udise_code),
            "COUNT": actual_count,
            "teacher_mobile": teacher_mobile
        }), 200
    else:
        return jsonify({
            "status": False,
            "message": "Invalid UDISE code."
        }), 401

@app.route('/fetch_student', methods=['POST','GET'])
def fetch_student():
    if request.method == 'POST':
        data=request.get_json()
        udise_code = data.get('udise_code')
        db = Database()
        query = 'SELECT * FROM student WHERE udise_code = %s'
        params = (udise_code,)
        results = db.execute(query, params)
        if results is None:
            return jsonify({
                "status": False,
                "message": "An error occurred while fetching student data."
            }), 500
        students = results.fetchall()
        return jsonify({
            "status": True,
            "message": "Student data fetched successfully.",
            "data": students
        }), 200
    else:
        db = Database()
        query = 'SELECT * FROM student'
        cursor = db.execute(query)
        if cursor is None:
            return jsonify({
                "status": False,
                "message": "An error occurred while fetching student data."
            }), 500
        students = cursor.fetchall()
        return jsonify({
            "status": True,
            "message": "All student data fetched successfully.",
            "data": students
        }), 200

@app.route('/uploads/<filename>', methods=['GET','POST'])
def uploaded_file(filename):
    try:
        return send_from_directory(
            app.config['UPLOAD_FOLDER'],
            filename,
            as_attachment=True
        )
    except Exception as e:
        print(f"[UPLOAD ERROR] {str(e)}")
        return jsonify({
            "status": False,
            "message": f"Error retrieving file: {str(e)}"
        }), 500

@app.route('/get_photo', methods=['POST'])
def get_photo():
    data = request.get_json()
    file_name = data.get('file_name')
    if not file_name:
        return jsonify({
            "status": False,
            "message": "File name is required."
        }), 400

    try:
        return send_from_directory(
            directory=app.config['UPLOAD_FOLDER'],
            path=file_name,
            as_attachment=True
        )
    except Exception as e:
        print(f"[GET_PHOTO ERROR] {str(e)}")
        return jsonify({
            "status": False,
            "message": f"Error retrieving file: {str(e)}"
        }), 500

@app.route('/supervisor_dashboard', methods=['POST'])
def supervisor_dashboard():
    data = request.get_json()
    udise_code = data.get('udise_code')

    db = None
    try:
        if not udise_code:
            return jsonify({
                "status": False,
                "message": "UDISE code is required."
            }), 400

        db = Database()
        if not db.is_connected():
            return jsonify({
                "status": False,
                "message": "Server is unable to connect to the database. Please check server logs."
            }), 500

        query_students = "SELECT COUNT(*) AS total_students FROM student WHERE udise_code = %s"
        params_students = (udise_code,)
        cursor_students = db.execute(query_students, params_students)

        if cursor_students is None:
            return jsonify({
                "status": False,
                "message": "An error occurred while fetching student count."
            }), 500

        result_students = cursor_students.fetchone()
        try:
            if cursor_students.with_rows:
                cursor_students.fetchall()
        except Exception as e:
            print(f"[WARNING] Error consuming remaining results from students query: {e}")

        total_students = result_students['total_students'] if result_students else 0

        query_teachers = "SELECT COUNT(*) AS total_teachers FROM teacher"
        cursor_teachers = db.execute(query_teachers)

        if cursor_teachers is None:
            return jsonify({
                "status": False,
                "message": "An error occurred while fetching teacher count."
            }), 500

        result_teachers = cursor_teachers.fetchone()
        try:
            if cursor_teachers.with_rows:
                cursor_teachers.fetchall()
        except Exception as e:
            print(f"[WARNING] Error consuming remaining results from teachers query: {e}")

        total_teachers = result_teachers['total_teachers'] if result_teachers else 0

        query_schools = "SELECT COUNT(DISTINCT udise_code) AS total_schools FROM student"
        cursor_schools = db.execute(query_schools)

        if cursor_schools is None:
            return jsonify({
                "status": False,
                "message": "An error occurred while fetching total school count."
            }), 500

        result_schools = cursor_schools.fetchone()
        try:
            if cursor_schools.with_rows:
                cursor_schools.fetchall()
        except Exception as e:
            print(f"[WARNING] Error consuming remaining results from schools query: {e}")

        total_schools = result_schools['total_schools'] if result_schools else 0

        return jsonify({
            "status": True,
            "message": f"Dashboard data for UDISE Code {udise_code} fetched successfully.",
            "total_number_of_student": total_students,
            "total_number_of_teacher": total_teachers,
            "total_number_of_school": total_schools
        }), 200

    except Exception as e:
        print(f"[SERVER ERROR] Unhandled exception in supervisor_dashboard route: {str(e)}")
        return jsonify({
            "status": False,
            "message": f"Server error: {str(e)}"
        }), 500
    finally:
        if db:
            db.close()

@app.route('/check_verified_status', methods=['POST'])
def check_student():
    data=request.get_json()
    udise_code = data.get('udise_code')
    if not udise_code:
        return jsonify({
            "status": False,
            "message": "UDISE code is required."
        }), 400

    db = Database()
    if not db.is_connected():
        return jsonify({
            "status": False,
            "message": "Server is unable to connect to the database. Please check server logs."
        }), 500

    query = "SELECT * FROM student WHERE udise_code = %s AND verified = 'false'"
    params = (udise_code,)
    cursor = db.execute(query, params)

    if cursor is None:
        return jsonify({
            "status": False,
            "message": "An error occurred while verifying the student."
        }), 500
    students = cursor.fetchall()

    return jsonify({
        "status": True,
        "message": "Unverified students fetched successfully.",
        "data": students
    }), 200

@app.route('/verify_student', methods=['POST'])
def verify_student():
    data = request.get_json()
    name=data.get('name')
    mobile = data.get('mobile')

    if not name or not mobile:
        return jsonify({
            "status": False,
            "message": "Name and mobile number are required."
        }), 400

    db = Database()
    if not db.is_connected():
        return jsonify({
            "status": False,
            "message": "Server is unable to connect to the database. Please check server logs."
        }), 500

    query = "UPDATE student SET verified = 'true' WHERE name = %s AND mobile = %s"
    params = (name, mobile)
    cursor = db.execute(query, params)

    if cursor is None:
        return jsonify({
            "status": False,
            "message": "An error occurred while verifying the student."
        }), 500

    if cursor.rowcount == 1:
        return jsonify({
            "status": True,
            "message": "Student verified successfully."
        }), 200
    else:
        return jsonify({
            "status": False,
            "message": "No student found with the provided UDISE code or already verified."
        }), 404

@app.route('/fetch_teacher', methods=['POST', 'GET'])
def fetch_teacher():
    db = Database()

    if request.method == 'GET':
        query = 'SELECT * FROM teacher'
        cursor = db.execute(query)

        if cursor is None:
            return jsonify({
                "status": False,
                "message": "An error occurred while fetching teacher data."
            }), 500

        teachers = cursor.fetchall()

        enriched_teachers = []
        for teacher in teachers:
            emp_id = teacher.get("employee_id")

            count_query = "SELECT COUNT(*) AS student_count FROM student WHERE employee_id = %s"
            count_cursor = db.execute(count_query, (emp_id,))

            if count_cursor:
                count_row = count_cursor.fetchone()
                count = count_row.get('student_count', 0) if count_row else 0
            else:
                count = 0

            teacher["student_count"] = count
            enriched_teachers.append(teacher)

        return jsonify({
            "status": True,
            "message": "Teacher data fetched successfully.",
            "data": enriched_teachers
        }), 200
    else:
        data = request.get_json()
        udise_code = data.get('udise_code')

        if not udise_code:
            return jsonify({
                "status": False,
                "message": "UDISE code is required."
            }), 400

        db = Database()
        if not db.is_connected():
            return jsonify({
                "status": False,
                "message": "Server is unable to connect to the database. Please check server logs."
            }), 500

        query = 'SELECT * FROM teacher WHERE udise_code = %s'
        params = (udise_code,)
        results = db.execute(query, params)

        if results is None:
            return jsonify({
                "status": False,
                "message": "An error occurred while fetching teacher data."
            }), 500

        teachers = results.fetchall()
        return jsonify({
            "status": True,
            "message": "Teacher data fetched successfully.",
            "data": teachers
        }), 200

# ================================  WEB API  ===================================

@app.route('/web_dashboard', methods=['GET'])
def web_dashboard():
    db = Database()
    if not db.is_connected():
        return jsonify({
            "status": False,
            "message": "Server is unable to connect to the database. Please check server logs."
        }), 500

    query = "SELECT COUNT(*) AS total_students FROM student"
    cursor = db.execute(query)

    if cursor is None:
        return jsonify({
            "status": False,
            "message": "An error occurred while fetching student count."
        }), 500

    result = cursor.fetchone()
    try:
        if cursor.with_rows:
            cursor.fetchall()

    except Exception as e:
        print(f"[WARNING] Error consuming remaining results: {e}")

    total_students = result['total_students'] if result else 0

    query_teachers = "SELECT COUNT(*) AS total_teachers FROM teacher"
    cursor_teachers = db.execute(query_teachers)

    if cursor_teachers is None:
        return jsonify({
            "status": False,
            "message": "An error occurred while fetching teacher count."
        }), 500
    result_teachers = cursor_teachers.fetchall()

    query_schools = "SELECT COUNT(*) as total_schools FROM school"
    cursor_schools = db.execute(query_schools)
    result_schools = cursor_schools.fetchall()

    try:
        if cursor_teachers.with_rows:
            cursor_teachers.fetchall()
    except Exception as e:
        print(f"[WARNING] Error consuming remaining results: {e}")

    return jsonify({
        "status": True,
        "message": "Dashboard data fetched successfully.",
        "total_students": total_students,
        "total_teachers": result_teachers[0]['total_teachers'] if result_teachers else 0,
        "total_schools": result_schools[0]['total_schools'] if result_schools else 0
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)