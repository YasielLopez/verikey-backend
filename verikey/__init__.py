from flask import Flask
from flask_cors import CORS

def init_app():
    app = Flask(__name__)
    CORS(app)

    @app.route('/')
    def home():
        return {'message': 'Verikey API is running'}

    @app.route('/signup', methods=['POST'])
    def signup():
        return {'message': 'Signup successful'}, 200

    return app
