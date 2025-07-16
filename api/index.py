import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import app

# Vercel expects the app to be available as 'app'
if __name__ == "__main__":
    app.run()

