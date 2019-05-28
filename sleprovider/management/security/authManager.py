from twisted.cred.checkers import FilePasswordDB
from werkzeug.security import generate_password_hash
from .hash import check_hashed_password


class AuthManager(object):
    @staticmethod
    def create_user(user, password):
        user_already_exists = False
        try:
            with open("http.password", "r+") as f:
                d = f.readlines()
                f.seek(0)
                for i in d:
                    if i.split('=')[0] == user:
                        user_already_exists = True
                        break
        except FileNotFoundError:
            print("Creating new password db")
        if not user_already_exists:
            f = open('http.password', 'ab')
            try:
                f.write('='.join([user, generate_password_hash(password)]).encode())
                f.write('\n'.encode())
                print("Added new user: {}".format(user))
            except Exception as e:
                print(e)
            f.close()
        else:
            print("User: {} already exists!".format(user))

    @staticmethod
    def delete_user(user):
        with open("http.password", "r+") as f:
            d = f.readlines()
            f.seek(0)
            for i in d:
                if not (i.split('=')[0] == user):
                    f.write(i)
            f.truncate()
            print("Deleted user: {}".format(user))

    @staticmethod
    def read_user(user):
        checker = FilePasswordDB('http.password', delim=b'=', hash=check_hashed_password)
        return checker.getUser(user.encode())

    @staticmethod
    def read_db():
        checker = FilePasswordDB('http.password', delim=b'=', hash=check_hashed_password)
        credentials = {}
        for user, password in checker._loadCredentials():
            credentials.update({user.decode(): password.decode()})
        return credentials
