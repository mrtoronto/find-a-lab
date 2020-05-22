import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        "postgresql://postgres:qwertyboII626@localhost/flask_app"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['your-email@example.com']
    MAX_RESULTS = os.environ.get('MAX_RESULTS') or 15000 ### Max query results to prevent timeout
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT') 
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379' ### Redis URL
    RESULT_TTL = 5000 ### Seconds to save results on the page with the token
    ASYNC_FUNC = True