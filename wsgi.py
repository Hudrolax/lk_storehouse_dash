from main import app, db

server = app.server

if __name__ == '__main__':
    db.run()
    server.run()