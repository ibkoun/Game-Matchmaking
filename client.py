import socket
import time
import random
import string
import json
import getpass
from enum import Enum
from player import Info
from threading import Thread


class Commands(Enum):
    HELP = "HELP"
    SIGN_UP = "SIGN UP"
    SIGN_IN = "SIGN IN"
    SIGN_OUT = "SIGN OUT"
    CASUAL = "CASUAL"
    COMPETITIVE = "COMPETITIVE"
    PROFILE = "PROFILE"


class AutomatedClient(Thread):
    def __init__(self, client_id, host="127.0.0.1", port=1233):
        Thread.__init__(self)
        self.client_id = client_id
        self.pre_credentials_commands = [Commands.SIGN_UP.value, Commands.SIGN_IN.value]
        self.post_credentials_commands = [Commands.COMPETITIVE.value]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.accounts = {}

    def run(self):
        while True:
            try:
                self.socket.connect((self.host, self.port))

                # Before signing up/signing in.
                while True:
                    time.sleep(random.randint(0, 5))
                    command = Commands.SIGN_UP.value if len(self.accounts) == 0\
                        else random.choice(self.pre_credentials_commands)
                    if command == Commands.SIGN_UP.value:
                        self.socket.send(str.encode(command))
                        credentials = self.socket.recv(2048)
                        account = json.loads(credentials.decode("utf-8"))
                        username = "Player-{}".format(self.client_id)
                        password = "".join(
                            [random.SystemRandom().choice(string.ascii_letters + string.digits + string.punctuation) for
                             i in range(10)])
                        account[Info.USERNAME.value] = username
                        account[Info.PASSWORD.value] = password
                        credentials = json.dumps(account)
                        self.socket.send(str.encode(credentials))
                        confirmation = self.socket.recv(2048)
                        if confirmation:
                            self.accounts[username] = account
                            break
                    elif command == Commands.SIGN_IN.value:
                        self.socket.send(str.encode(command))
                        credentials = self.socket.recv(2048)
                        account = json.loads(credentials.decode("utf-8"))
                        username = random.choice(self.accounts)
                        account[Info.USERNAME.value] = username
                        account[Info.PASSWORD.value] = self.accounts[username][Info.PASSWORD.value]
                        credentials = json.dumps(account)
                        self.socket.send(str.encode(credentials))
                        confirmation = self.socket.recv(2048)
                        if confirmation:
                            break

                # After signing up/signing in.
                while True:
                    time.sleep(random.randint(2, 5))
                    command = random.choice(self.post_credentials_commands)
                    self.socket.send(str.encode(command))
                    result = self.socket.recv(2048)
            except socket.error as e:
                print(e)
                self.socket.close()
                return


class ManualClient:
    def __init__(self, host="127.0.0.1", port=1233):
        self.pre_credentials_commands = [Commands.SIGN_UP.value, Commands.SIGN_IN.value]
        self.post_credentials_commands = [Commands.COMPETITIVE.value, Commands.PROFILE.value]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.host = host
        self.port = port

    def execute(self):
        while True:
            try:
                self.socket.connect((self.host, self.port))

                # Before signing up/signing in.
                while True:
                    command = input("\nEnter your commands (type 'help' for a list of commands): ").upper()
                    if command == Commands.HELP.value:
                        print("\nAvailable commands:")
                        for i in range(len(self.pre_credentials_commands)):
                            print("-{}".format(self.pre_credentials_commands[i]).lower())
                    elif command == Commands.SIGN_UP.value:
                        self.socket.send(str.encode(command))
                        credentials = self.socket.recv(2048)
                        account = json.loads(credentials.decode("utf-8"))
                        username = input("Enter your username: ")
                        password = getpass.getpass(prompt="Enter your password: ")
                        account[Info.USERNAME.value] = username
                        account[Info.PASSWORD.value] = password
                        credentials = json.dumps(account)
                        self.socket.send(str.encode(credentials))
                        data = self.socket.recv(2048)
                        confirmation = json.loads(data.decode("utf-8"))
                        if confirmation:
                            print("\nWelcome, {}!".format(username))
                            break
                        else:
                            print("\nUsername already exists.\n")
                    elif command == Commands.SIGN_IN.value:
                        self.socket.send(str.encode(command))
                        credentials = self.socket.recv(2048)
                        account = json.loads(credentials.decode("utf-8"))
                        username = input("Enter your username: ")
                        password = getpass.getpass(prompt="Enter your password: ")
                        account[Info.USERNAME.value] = username
                        account[Info.PASSWORD.value] = password
                        credentials = json.dumps(account)
                        self.socket.send(str.encode(credentials))
                        data = self.socket.recv(2048)
                        confirmation = json.loads(data.decode("utf-8"))
                        if confirmation:
                            print("\nWelcome, {}!".format(username))
                            break
                        else:
                            print("\nInvalid credentials.")
                    else:
                        print("\nInvalid command.")

                # After signing up/signing in.
                while True:
                    command = input("\nEnter your command (type 'help' for a list of commands): ").upper()
                    if command == Commands.HELP.value:
                        print("\nAvailable commands:")
                        for i in range(len(self.pre_credentials_commands)):
                            print("-{}".format(self.post_credentials_commands[i]).lower())
                    elif command == Commands.COMPETITIVE.value:
                        self.socket.send(str.encode(command))
                        print("\nSearching for a game...")
                        result = self.socket.recv(2048)
                        print(result.decode("utf-8"))
                    elif command == Commands.PROFILE.value:
                        self.socket.send(str.encode(command))
                        data = self.socket.recv(2048)
                        profile = json.loads(data.decode("utf-8"))
                        print("\nPROFILE")
                        for info in profile:
                            print("{}: {}".format(info, profile[info]))
                    elif command == Commands.SIGN_OUT.value:
                        pass
                    else:
                        print("\nInvalid command.")
            except socket.error as e:
                print(e)
                self.socket.close()
                return


if __name__ == "__main__":
    client = ManualClient()
    client.execute()
