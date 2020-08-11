"""
Main entrance to the application
"""

# Local application imports
from app import create_app


application = create_app()

if __name__ == '__main__':
    application.run()
