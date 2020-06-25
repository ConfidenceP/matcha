from matcha import socket, logged_in_users, db
from flask import session, request
from flask_socketio import join_room, leave_room
import secrets
from bson.objectid import ObjectId


@socket.on("connect")
def connect():
    user_name = session.get("username")
    logged_in_users[user_name] = request.sid
    print(user_name, "connected: id -", logged_in_users[user_name])


@socket.on("disconnect")
def disconnect():
    logged_in_users[session.get("username")] = ""


@socket.on("flirt")
def like(data):
    liker = db.get_user(
        {"username": session.get("username")}, {"username": 1, "flirts": 1}
    )
    liked = db.get_user(
        {"username": data["to"]}, {"username": 1, "flirted": 1, "notifications": 1}
    )

    liker["flirts"].append(liked["username"])
    liked["flirted"].append(liker["username"])

    # print('liker:', liker['flirts'])
    # print('liked:', liked['flirted'])

    db.update_likes(liker["_id"], {"flirts": liker["flirts"]})
    db.update_likes(liked["_id"], {"flirted": liked["flirted"]})

    sid = logged_in_users.get(data["to"])
    if sid:
        socket.emit("flirt", {"from": session.get("username")}, room=sid)

    liked["notifications"].append(session.get("username") + " liked you")
    db.update_likes(liked["_id"], {"notifications": liked["notifications"]})


@socket.on("flirt-back")
def liked_back(data):
    like_back = db.get_user(
        {"username": session.get("username")},
        {"username": 1, "flirts": 1, "matched": 1, "rooms": 1},
    )
    liked = db.get_user(
        {"username": data["to"]},
        {"username": 1, "flirted": 1, "matched": 1, "rooms": 1, "notifications": 1},
    )
    room = secrets.token_hex(16)

    like_back["flirts"].append(liked["username"])
    liked["flirted"].append(like_back["username"])
    # add to the matched array.
    like_back["matched"].append(liked["username"])
    liked["matched"].append(like_back["username"])
    # add a unique room to this twos matched
    like_back["rooms"][liked["username"]] = room
    liked["rooms"][like_back["username"]] = room

    db.update_likes(
        like_back["_id"],
        {
            "flirts": like_back["flirts"],
            "matched": like_back["matched"],
            "rooms": like_back["rooms"],
        },
    )
    db.update_likes(
        liked["_id"],
        {
            "flirted": liked["flirted"],
            "matched": liked["matched"],
            "rooms": liked["rooms"],
        },
    )

    sid = logged_in_users.get(data["to"])
    if sid:
        socket.emit("matched", {"from": session.get("username")}, room=sid)
    liked["notifications"].append(
        session.get("username") + " has liked back. You can now chat"
    )
    db.update_likes(liked["_id"], {"notifications": liked["notifications"]})

    print(data)


@socket.on("Unlike")
def unlike(data):
    print(f"Unlike {data}")
    current_user = db.get_user(
        {"username": session.get("username")}, {"flirts": 1, "matched": 1}
    )
    unlikes = db.get_user(
        {"username": data["to"]}, {"flirted": 1, "matched": 1, "notifications": 1}
    )

    # print('unlikes ', unlikes)
    if data["to"] in current_user["flirts"]:
        current_user["flirts"].remove(data["to"])
        unlikes["flirted"].remove(session.get("username"))
    if current_user["matched"] and data["to"] in current_user["matched"]:
        current_user["matched"].remove(data["to"])
        unlikes["matched"].remove(session.get("username"))

    db.update_likes(
        current_user["_id"],
        {"flirts": current_user["flirts"], "matched": current_user["matched"]},
    )
    db.update_likes(
        unlikes["_id"], {"flirted": unlikes["flirted"], "matched": unlikes["matched"]}
    )

    # print(f" logged in users {logged_in_users[data['to']]}")
    sid = logged_in_users[data["to"]]
    if sid:
        socket.emit("Unlike", {"from": session.get("username")}, room=sid)

    unlikes["notifications"].append(session.get("username") + " has unliked you.")
    db.update_likes(unlikes["_id"], {"notifications": unlikes["notifications"]})


def join(data):
    join_room(data)


@socket.on("leave")
def leave(data):
    leave_room(data)


@socket.on("send")
def send(data):
    print(f"Sending message")
    users = db.users()
    current_user = db.get_user({"username": session.get("username")}, {"_id": 1})
    notification = None

    for user in users:
        if data["room"] in user["rooms"].values() and not user[
            "username"
        ] == session.get("username"):
            notification = user
            break

    if current_user["_id"] in user["blocked"]:
        return False

    db.insert_chat(data["from"], data["room"], data["message"])
    socket.emit(
        "recieve",
        {"from": data["from"], "message": data["message"]},
        include_self=False,
        room=data["room"],
    )
    if not notification["username"] in logged_in_users:
        # send email
        notification["notifications"].append(
            session.get("username") + " has sent you a message"
        )
        db.update_likes(
            notification["_id"], {"notifications": notification["notifications"]}
        )
    else:
        notification["notifications"].append(
            session.get("username") + " has sent you a message"
        )
        db.update_likes(
            notification["_id"], {"notifications": notification["notifications"]}
        )


@socket.on("view")
def view_user_profile(data):
    print("recieving the data")
    viewed_user = db.get_user({"_id": ObjectId(data["viewed"])})
    viewer = db.get_user({"_id": ObjectId(data["viewer"])}, {"username": 1})

    print(viewed_user["username"])
    if (
        data["viewer"] in viewed_user["views"]
        or viewer["_id"] in viewed_user["blocked"]
    ):
        return False

    if viewed_user["username"] in logged_in_users:
        print(data["viewed"], " is online")
        socket.emit(
            "notif_view",
            {"from": viewer["username"]},
            sid=logged_in_users[viewed_user["username"]],
        )

    viewed_user["notifications"].append(viewer["username"] + " has viewed you profile")

    viewed_user["views"].append(data["viewer"])
    db.update_likes(
        viewed_user["_id"],
        {"views": viewed_user["views"], "notifications": viewed_user["notifications"]},
    )

    print(data)


@socket.on("read")
def read(data):
    print("notifications read")
    user = db.get_user({"username": session.get("username")}, {"notifications": 1})
    user["notifications"] = []
    db.update_likes(user["_id"], {"notifications": user["notifications"]})