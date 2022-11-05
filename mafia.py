"""Contains abstracted game logic"""
from enum import Enum
import re

Abstain = object()


class Alarm(Exception):
    """Raised when a timer runs out"""


class Game:
    """Represents a game state"""

    def __init__(self, name, host):
        self.active = False
        self.name = name
        self.host = host
        self.players = []
        self.dead = []
        self.votes = {}
        self.phase = None
        self.day = 0
        self.timer = 0
        self.stop_timer = False

    class Phase(Enum):
        """Represents the current phase of the day"""

        DAY = "Day"
        VOTE = "Voting phase"
        TWILIGHT = "Twilight phase"
        NIGHT = "Night"

    def find_user(self, string):
        """Tries to find the user with a given name"""
        string = string.strip()
        # First try for an exact match
        if m := re.match(r"^\<\@(\d+)\>$", string):
            uid = int(m.group(1))
            matching_players = [p for p in self.players if p.id == uid]
            if len(matching_players) == 0:
                raise ValueError("That person isn't playing the game right now! Please don't ping them :(")
            if len(matching_players) > 1:
                raise ValueError("I'm sorry, but Discord appears to be possessed by a ghost.")
            return matching_players[0]
        # Best-effort fuzzy match
        users_starting_with_name = [
            p
            for p in self.players
            if (f"{p.name.lower()}#{p.discriminator}").find(string.lower()) > -1
            or p.display_name.lower().find(string.lower()) > -1
        ]
        if len(users_starting_with_name) == 0:
            raise ValueError(f"Can't find user whose name contains '{string}'")
        if len(users_starting_with_name) > 1:
            guesses = [f"{p.name}#{p.discriminator}" for p in users_starting_with_name]
            raise ValueError(f"I don't know who you mean by '{string}' (could be {', '.join(guesses)})")
        return users_starting_with_name[0]

    def votes_for(self, user):
        """The number of tallied votes for a given user"""
        return len([v for v in self.votes.values() if v == user])

    def total_votes(self):
        """The number of tallied votes"""
        return len(self.votes)
