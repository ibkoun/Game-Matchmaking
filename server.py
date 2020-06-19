import socket
import time
import random
import json
import concurrent.futures
from client import Commands, AutomatedClient
from threading import Thread, Condition, Event, Lock
from player import Player, Status, Info
from lobby import SoloLobby


class ClientThread(Thread):
    def __init__(self, server, connection, host, port):
        Thread.__init__(self)
        self.server = server
        self.connection = connection
        self.host = host
        self.port = port
        self.player_condition = Condition()
        self.player = None
        self.match = None

    def player_in_game(self):
        return self.player.info[Info.STATUS.value] == Status.IN_GAME.value

    def run(self):
        while True:
            try:
                data = self.connection.recv(2048)
                if not data:
                    break
                command = data.decode("utf-8")
                if command == Commands.SIGN_UP.value:
                    account = {Info.USERNAME.value: None, Info.PASSWORD.value: None}
                    credentials = json.dumps(account)
                    self.connection.send(str.encode(credentials))
                    data = self.connection.recv(2048)
                    credentials = data.decode("utf-8")
                    account = json.loads(credentials)
                    username = account[Info.USERNAME.value]
                    if self.server.players.get(username):
                        confirmation = json.dumps(False)
                        self.connection.send(str.encode(confirmation))
                    else:
                        confirmation = json.dumps(True)
                        player = Player(len(self.server.players), username)
                        self.server.players[username] = player
                        self.server.accounts[username] = account
                        self.connection.send(str.encode(confirmation))
                        self.player = player
                        self.player.online()
                        print("{} has connected.".format(username))
                elif command == Commands.SIGN_IN.value:
                    account = {Info.USERNAME.value: None, Info.PASSWORD.value: None}
                    credentials = json.dumps(account)
                    self.connection.send(str.encode(credentials))
                    data = self.connection.recv(2048)
                    credentials = data.decode("utf-8")
                    account = json.loads(credentials)
                    username = account[Info.USERNAME.value]
                    password = account[Info.PASSWORD.value]
                    if self.server.players.get(username):
                        if password == self.server.accounts[username][Info.PASSWORD.value]:
                            confirmation = json.dumps(True)
                            self.connection.send(str.encode(confirmation))
                            self.player = self.server.players[username]
                            self.player.info[Info.STATUS.value] = Status.ONLINE.value
                            self.player.online()
                            print("{} has connected.".format(username))
                        else:
                            confirmation = json.dumps(False)
                            self.connection.send(str.encode(confirmation))
                    else:
                        confirmation = json.dumps(False)
                        self.connection.send(str.encode(confirmation))
                elif command == Commands.PROFILE.value:
                    profile = json.dumps(self.player.info)
                    self.connection.send(str.encode(profile))
                elif command == Commands.LEADERBOARD.value:
                    leaderboard = sorted(self.server.competitive_matchmaking.leaderboard,
                                         key=lambda x: x.info[Info.RATING.value], reverse=True)
                    count = len(leaderboard)
                    data = json.dumps(count)
                    self.connection.send(str.encode(data))  # Send the total number of players to display.
                    players = []
                    for player in leaderboard:
                        count -= 1
                        rank = player.info[Info.RANK.value]
                        username = player.info[Info.USERNAME.value]
                        rating = player.info[Info.RATING.value]
                        rating_class = player.info[Info.CLASS.value]
                        players.append({Info.RANK.value: rank, Info.USERNAME.value: username,
                                        Info.RATING.value: rating, Info.CLASS.value: rating_class})
                        if len(players) % 50 == 0 or count == 0:  # Display 50 players (or less) at a time.
                            data = json.dumps(players)
                            self.connection.send(str.encode(data))
                            players.clear()
                            data = self.connection.recv(1024)
                            count = json.loads(data.decode("utf-8"))  # Wait for response before continuing.
                elif command == Commands.CASUAL.value:
                    pass
                elif command == Commands.COMPETITIVE.value:
                    # Notify the server that the queue isn't empty.
                    with self.server.competitive_matchmaking.queue_condition:
                        self.server.competitive_matchmaking.queue.append(self)
                        self.server.competitive_matchmaking.queue_condition.notify()

                    # Wait until the end of the match.
                    with self.player_condition:
                        self.player_condition.wait_for(self.player_in_game)
                        self.match.wait()
            except json.JSONDecodeError as e:
                print(e)
            except socket.error as e:
                print(e)
                if self.player:
                    self.player.offline()
                    print("{} has disconnected.".format(self.player.info[Info.USERNAME.value]))
                self.connection.close()
                del self
                return


class SoloLobbyThread(Thread):
    def __init__(self, matchmaking_system, capacity):
        Thread.__init__(self)
        self.matchmaking_system = matchmaking_system
        self.lobby = SoloLobby(capacity)
        self.players_threads = []
        self.lobby_condition = Condition()
        self.match = Event()

    def fill(self, entry):
        with self.lobby_condition:
            found_lobby = self.lobby.fill(entry.player)
            if found_lobby:
                entry.match = self.match
                self.players_threads.append(entry)
                if self.ready():
                    self.lobby_condition.notify()
            return found_lobby

    def ready(self):
        return self.lobby.ready()

    def run(self):
        with self.lobby_condition:
            self.lobby_condition.wait_for(self.ready)
            self.lobby.predict_outcome()
            before = self.lobby.display_players()
            predictions = self.lobby.display_predictions()
            for player_thread in self.players_threads:
                with player_thread.player_condition:
                    player_thread.player.in_game()
                    player_thread.player_condition.notify()
            self.lobby.simulate_match(self.matchmaking_system.rated)
            time.sleep(random.randint(2, 5))
            after = self.lobby.display_players()
            result = {"BEFORE": before, "PREDICTIONS": predictions, "AFTER": after}
            for player_thread in self.players_threads:
                data = json.dumps(result)
                player_thread.connection.send(str.encode(data))
                player_thread.player.online()
            self.matchmaking_system.update_leaderboard(self.lobby.players)
            self.matchmaking_system.lobbies.remove(self)
            self.match.set()
            del self


class MatchmakingSystem(Thread):
    def __init__(self, server, capacity, rated):
        Thread.__init__(self)
        self.server = server
        self.channels_count = 5
        self.capacity = capacity
        self.rated = rated
        self.leaderboard = []
        self.refresh_lock = Lock()
        self.queue = []
        self.lobbies = []
        self.queue_condition = Condition()

    def players_in_queue(self):
        return len(self.queue) > 0

    def update_leaderboard(self, players):
        self.refresh_lock.acquire()
        for player in players:
            if not player.info[Info.RANK.value]:
                self.leaderboard.append(player)
        self.leaderboard.sort(key=lambda x: x.info[Info.RATING.value], reverse=True)
        for i in range(len(self.leaderboard)):
            self.leaderboard[i].info[Info.RANK.value] = i + 1
        self.refresh_lock.release()

    def matchmaking(self):
        while True:
            # Wait for at least one player to queue up for a game.
            with self.queue_condition:
                self.queue_condition.wait_for(self.players_in_queue)
                if len(self.lobbies) == 0:
                    # Create a new lobby if there is none.
                    lobby = SoloLobbyThread(self, self.capacity)
                    lobby.daemon = True
                    lobby.start()
                    lobby.fill(self.queue.pop(0))
                    self.lobbies.append(lobby)
                else:
                    # Search for an available lobby.
                    found_lobby = False
                    player = self.queue.pop(0)
                    for lobby in self.lobbies:
                        if not lobby.ready():
                            found_lobby = lobby.fill(player)
                        if found_lobby:
                            break

                    # Create a new lobby if all the existing lobbies are full.
                    if not found_lobby:
                        lobby = SoloLobbyThread(self, self.capacity)
                        lobby.daemon = True
                        lobby.start()
                        lobby.fill(player)
                        self.lobbies.append(lobby)

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.channels_count) as executor:
            for i in range(self.channels_count):
                executor.submit(self.matchmaking)


class Server:
    def __init__(self, host="127.0.0.1", port=1233):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.host = host
        self.port = port
        self.accounts = {}
        self.players = {}
        self.threads = []
        # self.casual_matchmaking = MatchmakingSystem(self, 2, False)
        # self.casual_matchmaking.daemon = True
        self.competitive_matchmaking = MatchmakingSystem(self, 2, True)
        self.competitive_matchmaking.daemon = True

    def populate(self, m):
        for x in range(m):
            automated_client = AutomatedClient(x)
            automated_client.daemon = True
            automated_client.start()
            self.threads.append(automated_client)

    def execute(self):
        try:
            self.socket.bind((self.host, self.port))
            print("\nWaiting for a connection...")
            self.competitive_matchmaking.start()
            populate_thread = Thread(target=self.populate, args=(200,))
            populate_thread.daemon = True
            populate_thread.start()
            while True:
                self.socket.listen(5)
                (connection, (address, port)) = self.socket.accept()
                client_thread = ClientThread(self, connection, address, port)
                client_thread.start()
        except socket.error as e:
            print(e)
        self.socket.close()


if __name__ == "__main__":
    game_server = Server()
    game_server.execute()
