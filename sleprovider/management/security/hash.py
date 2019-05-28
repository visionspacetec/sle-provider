from werkzeug.security import check_password_hash


def check_hashed_password(username, pass_plaintext, pass_hashed):
    if check_password_hash(pass_hashed.decode(), pass_plaintext.decode()):
        return pass_hashed
    else:
        return False
