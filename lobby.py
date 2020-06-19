import math
import random
from player import Info


class SoloLobby:
    def __init__(self, capacity):
        self.players = []
        self.capacity = capacity
        self.odds = {}
        self.predictions = {}

    def fill(self, entry):
        if len(self.players) == 0:
            username = entry.info[Info.USERNAME.value]
            self.odds[username] = {}
            self.players.append(entry)
            return True
        elif len(self.players) < self.capacity:
            username = entry.info[Info.USERNAME.value]
            player_rating = entry.info[Info.RATING.value]
            average_rating = (player_rating + sum([player.info[Info.RATING.value] for player in self.players])) /\
                             (len(self.players) + 1)
            rating_variance = (math.pow(player_rating - average_rating, 2) +
                               sum([math.pow(player.info[Info.RATING.value] - average_rating, 2)
                                    for player in self.players])) / len(self.players)
            if rating_variance <= math.pow(200, 2):
                self.odds[username] = {}
                self.players.append(entry)
                return True
        return False

    def ready(self):
        return len(self.players) == self.capacity

    def swap(self, i, j):
        player = self.players[j]
        self.players[j] = self.players[i]
        self.players[i] = player

    def display_players(self):
        players = []
        for i in range(len(self.players)):
            username = self.players[i].info[Info.USERNAME.value]
            rating = self.players[i].info[Info.RATING.value]
            rating_class = self.players[i].info[Info.CLASS.value]
            players.append({Info.RANK.value: i + 1, Info.USERNAME.value: username, Info.RATING.value: rating,
                            Info.CLASS.value: rating_class})
        return players

    def display_predictions(self):
        players = []
        for player in self.players:
            username = player.info[Info.USERNAME.value]
            rating = player.info[Info.RATING.value]
            rating_class = player.info[Info.CLASS.value]
            expected_score = sum((i + 1) * self.predictions[username][i] for i in range(len(self.predictions[username])))
            players.append({Info.RANK.value: round(expected_score, 2), Info.USERNAME.value: username, Info.RATING.value: rating,
                            Info.CLASS.value: rating_class})
        return players

    def predict_outcome(self):
        # Calculate the odds of winning for each player.
        for i in range(self.capacity):
            player_username = self.players[i].info[Info.USERNAME.value]
            for j in range(i + 1, self.capacity):
                opponent_username = self.players[j].info[Info.USERNAME.value]
                self.odds[player_username][opponent_username] = self.players[i].predict_score(self.players[j])
                self.odds[opponent_username][player_username] = self.players[j].predict_score(self.players[i])

        # Calculate the chance of getting 1st, ..., nth place for each player.
        for player in self.players:
            username = player.info[Info.USERNAME.value]
            self.predictions[username] = player.predict_placements(self.odds)

    def simulate_match(self, rated):
        # Rearrange the order of players in the lobby.
        for i in range(self.capacity):
            for j in range(i + 1, self.capacity):
                ei = self.players[i].predict_score(self.players[j])
                p = random.random()
                if p >= ei and j > i:
                    self.swap(i, j)

        # Update the rating and the record of each player.
        if rated:
            for i in range(self.capacity):
                username = self.players[i].info[Info.USERNAME.value]
                expected_score = sum((j + 1) * self.predictions[username][j] for j in range(len(self.predictions)))
                final_score = i + 1
                self.players[i].update_rating(32, expected_score, final_score)
                if final_score == 1:
                    self.players[i].win()
                else:
                    self.players[i].lose()
