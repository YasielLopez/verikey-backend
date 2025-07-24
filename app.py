from verikey import create_app
import logging

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    print("✅ Starting Verikey API...")
    print("📁 Using organized file structure")
    print("🔧 Enhanced error handling enabled")
    print("📊 Logging enabled")
    
    # Configure logging for development
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app.run(debug=True, host='0.0.0.0', port=5000)