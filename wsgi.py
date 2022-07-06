from main import app, db


if __name__ == '__main__':
    db.run()
    app.run()