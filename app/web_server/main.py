# web_server/main.py

from server import create_app


def main():
    print("============================")
    print("      Starting server       ")
    print("============================")
    create_app(run_server=True)


if __name__ == "__main__":
    main()
