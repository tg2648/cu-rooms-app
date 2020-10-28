"""
Application configuration
"""

# Standard library imports
import os

# Third party imports
import boto3
from dotenv import load_dotenv
from itsdangerous.url_safe import URLSafeSerializer


basedir = os.path.abspath(os.path.dirname(__file__))  # This directory
load_dotenv(os.path.join(basedir, '.env'))  # Add .env to environment variables


class Config(object):
    """Base configuration"""

    SECRET_KEY = os.getenv('SECRET_KEY')
    SERIALIZER = URLSafeSerializer(SECRET_KEY)
    SESSION_COOKIE_SECURE = True

    # CAS
    CAS_LOGIN_ROUTE = os.getenv('CAS_LOGIN_ROUTE')
    CAS_LOGOUT_ROUTE = os.getenv('CAS_LOGOUT_ROUTE')
    CAS_VALIDATE_ROUTE = os.getenv('CAS_VALIDATE_ROUTE')
    CAS_AFTER_LOGIN = os.getenv('CAS_AFTER_LOGIN')

    # Dynamo [required by flask_dynamo]
    DYNAMO_SESSION = boto3.Session(
        region_name='us-east-2',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('AWS_SECRET')
    )


class ProdConfig(Config):
    """Production configuration"""

    ENV = 'prod'
    DEBUG = False

    CAS_SERVER = os.getenv('CAS_SERVER_PROD')
    CAS_AFTER_LOGOUT = os.getenv('CAS_AFTER_LOGOUT_PROD')
    DB_ACCESS_LOGS = os.getenv('DB_ACCESS_LOGS_PROD')
    DB_SCHEDULING = os.getenv('DB_SCHEDULING_PROD')


class DevConfig(Config):
    """Development configuration"""

    ENV = 'dev'
    DEBUG = True

    CAS_SERVER = os.getenv('CAS_SERVER_DEV')
    CAS_AFTER_LOGOUT = os.getenv('CAS_AFTER_LOGOUT_DEV')
    DB_ACCESS_LOGS = os.getenv('DB_ACCESS_LOGS_DEV')
    DB_SCHEDULING = os.getenv('DB_SCHEDULING_DEV')
