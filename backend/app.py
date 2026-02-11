from flask import Flask
from flask_cors import CORS
from auth import auth_bp
from student_routes import student_bp
from mentor_routes import mentor_bp

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})

app.register_blueprint(auth_bp)
app.register_blueprint(student_bp)
app.register_blueprint(mentor_bp)

if __name__ == "__main__":
    app.run(debug=True)
