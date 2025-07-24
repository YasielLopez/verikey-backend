from flask import Flask
from flask_cors import CORS
from verikey import init_app

app = init_app()

if __name__ == '__main__':
    print("✅ Starting Verikey API...")
    app.run(debug=True, host='0.0.0.0', port=5000)
