# web_server/main.py

from flask import Flask

from server import Server


def create_app(run_server=False):
    app = Flask(__name__, template_folder="../web_app", static_folder="../web_app/static")
    Server(app, run_server=run_server)
    return app


if __name__ == "__main__":
    print("============================")
    print("      Starting server       ")
    print("============================")
    create_app(run_server=True)
