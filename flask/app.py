from matcha import app, socket, db

if __name__ == '__main__':
    socket.run(app,debug=True,host="0.0.0.0")