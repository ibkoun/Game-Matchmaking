import math
import itertools
import numpy as np
from enum import Enum


class Info(Enum):
    USER_ID = "USER ID"
    USERNAME = "USERNAME"
    PASSWORD = "PASSWORD"
    RANK = "RANK"
    CLASS = "CLASS"
    RATING = "RATING"
    GAMES = "GAMES"
    WINS = "WINS"
    LOSSES = "LOSSES"
    WIN_RATIO = "WIN RATIO"
    STATUS = "STATUS"


class Status(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    IN_QUEUE = "IN QUEUE"
    IN_GAME = "IN GAME"


class Classes(Enum):
    SSS = "SSS"
    SS = "SS"
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"

    def rating_class(rating):
        if not rating:
            return None
        elif 0 <= rating < 1200:
            return Classes.E.value
        elif 1200 <= rating < 1400:
            return Classes.D.value
        elif 1400 <= rating < 1600:
            return Classes.C.value
        elif 1600 <= rating < 1800:
            return Classes.B.value
        elif 1800 <= rating < 2000:
            return Classes.A.value
        elif 2000 <= rating < 2200:
            return Classes.S.value
        elif 2200 <= rating < 2400:
            return Classes.SS.value
        elif rating >= 2400:
            return Classes.SSS.value


class Player:
    def __init__(self, user_id, username, rating=1200):
        self.info = {Info.USER_ID.value: user_id,
                     Info.RANK.value: None,
                     Info.USERNAME.value: username,
                     Info.CLASS.value: Classes.rating_class(rating),
                     Info.RATING.value: rating,
                     Info.GAMES.value: 0,
                     Info.WINS.value: 0,
                     Info.LOSSES.value: 0,
                     Info.WIN_RATIO.value: 0,
                     Info.STATUS.value: Status.ONLINE.value}

    # Predict the chance of a player of getting 1st, ..., nth place against other players.
    def predict_placements(self, odds):
        n = len(odds)
        predictions = [0] * n
        player_username = self.info[Info.USERNAME.value]
        for i in range(len(predictions)):
            wins = itertools.combinations(odds[player_username], n - 1 - i)
            for win_combination in wins:
                pi = np.prod([odds[player_username][opponent_username] for opponent_username in win_combination])
                loss_combination = set(odds[player_username]) - set(win_combination)
                pi *= np.prod([odds[opponent_username][player_username] for opponent_username in loss_combination])
                predictions[i] += pi
        p = sum(predictions)
        assert p == 1 or math.isclose(p, 1), str(p)
        return predictions

    # Predict the chance of a player of winning against an opponent using the elo rating formula.
    def predict_score(self, opponent):
        player_rating = math.pow(10, self.info[Info.RATING.value] / 400)
        opponent_rating = math.pow(10, opponent.info[Info.RATING.value] / 400)
        return player_rating / (player_rating + opponent_rating)

    # Update the elo rating of the player after a match.
    def update_rating(self, k, expected_score, final_score):
        rating = self.info[Info.RATING.value] + k * (expected_score - final_score)
        self.info[Info.RATING.value] = max(0, int(rating))
        self.info[Info.CLASS.value] = Classes.rating_class(self.info[Info.RATING.value])

    def win(self):
        self.info[Info.GAMES.value] += 1
        self.info[Info.WINS.value] += 1
        self.info[Info.WIN_RATIO.value] = self.info[Info.WINS.value] / self.info[Info.GAMES.value]

    def lose(self):
        self.info[Info.GAMES.value] += 1
        self.info[Info.LOSSES.value] += 1
        self.info[Info.WIN_RATIO.value] = self.info[Info.WINS.value] / self.info[Info.GAMES.value] * 100
