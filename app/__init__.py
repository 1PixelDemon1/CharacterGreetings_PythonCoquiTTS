from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key-here'

    from app.views.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app