from sleprovider.management.security.authManager import AuthManager

user = ''  # Enter username here
password = ''  # Enter password here

AuthManager.create_user(user, password)

print("Current password db state:")
users = AuthManager.read_db()
for usr, hsh in users.items():
    print(usr, hsh)

# AuthManager.delete_user(user)
