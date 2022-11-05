import random
import re
import asyncio
import os

import discord
from discord.ext import commands

access_token = os.environ["ACCESS_TOKEN"]

di = discord.Intents.default()
di.message_content = True

cmd_prefix = '='

bot = commands.Bot(command_prefix=cmd_prefix, intents=di)

hosts = []
players = {}

Abstain = object()

class Alarm(Exception):
    pass

class Game:
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

    def find_user(self, string):
        string = string.strip()
        if m := re.match("^\<\@(\d+)\>$", string):
            uid = int(m.group(1))
            matching_players = [ p for p in self.players if p.id == uid ]
            if len(matching_players) == 0:
                raise ValueError("That person isn't playing the game right now! Please don't ping them :(")
            elif len(matching_players) == 1:
                return matching_players[0]
            else:
                raise ValueError("I'm sorry, but Discord appears to be possessed by a ghost.")
        else:
            users_starting_with_name = [ p for p in self.players
                    if ("%s#%s" % (p.name.lower(), p.discriminator)).find(string.lower()) > -1
                                        or p.display_name.lower().find(string.lower()) > -1 ]
            if len(users_starting_with_name) == 0:
                raise ValueError("Can't find user whose name contains '%s'" % string)
            elif len(users_starting_with_name) == 1:
                return users_starting_with_name[0]
            else:
                raise ValueError("I don't know who you mean by '%s' (could be %s)"
                                 % (string, ", ".join([ "%s#%s" % (p.name, p.discriminator) for p in users_starting_with_name ])))

    def votes_for(self, user):
        return len([ v for v in self.votes.values() if v == user ])

    def total_votes(self):
        return len(self.votes)

NORMAL_ALARM_TEXT = "DING DING DING"
NORMAL_VOTING_TEXT = "Time to vote!"

START_MSGS = [ 'START!', 'スタート！', '*commencer !*', '`COMIENZA EL JUEGO`', '开始。︀', '*~begin~*', '**COMMENCE**', "***So... it begins.***", "*And away we go.*", "Here it comes...!", "IT BEGINS", "Let the games.......... *begin!*" ]
ALARM_TONES = [ "BEEP BEEP!", "That's all, folks", "The end!!!", "Whoa nelly!", "It's over...", "...That's it. I'm callin' it...", "It's the end of an era!", "Ding dong! `Oh, someone's at the door...`", "womp womp", "DING DING D- oh sorry, is that annoying?", "BEEP BOOP END OF LINE", "The End~!", "It's all over for you, buddy...", "BEEP BEEP", "DING DONG", "Dingadang dong dang doo", "That's enough now!", "Dang dang... Sorry, I'm still new at this." ]
VOTING_TONES = [ "Count those votes!", "Aw yeah, it's votin' time!", "Let's Voting Today!", "Everybody Votes Channel!", "Cast those votes, buckaroo!", "Let's all vote for who we want to get rid of!", "Don't forget to vote for who you don't like!", "Let's do a vote!", "It's time for everyone to vote...", "Voting time is boating time!", "Let's all vote together!", "Cast those ballots!", "I liked when he said \"it's voting time\" and then he voted all over the place", "Vote 'em up, cowboy" ]
VOTING_END_TONES = [ "The votes are in!!!", "it's over!!!!!!", "Thank you for participating in our democracy!", "I do believe this represents the sum total of votes that shall be counted in this elimination election. Indubitably.", "Thanks for voting!", "STOP VOTING", "the end (of voting)", "OK we're good now you can stop casting votes", "guys that's enough votes", "Let's see what the ~~cat~~ vote dragged in", "Shall we see what the results were?", "Who's being voted off the island?" ]

# Global state, to be moved into an object when we make this reentrant
game = None

game_active = False

@bot.event
async def on_ready():
    print(f"--- {bot.user.name} has connected ---")

@bot.event
async def on_message(msg):
    # During voting phase, delete any messages that don't start with =vote
    if game and game.phase == 'VOTE':
        if msg.author != game.host and msg.author != bot.user:
            if not msg.content.startswith(cmd_prefix + 'vote') and not msg.content.startswith(cmd_prefix + 'abstain'):
                await msg.delete()
                await msg.channel.send(msg.author.mention + " You may only type `" + cmd_prefix + "vote [someone]` or `" + cmd_prefix + "abstain` at this time.")
                return

    await bot.process_commands(msg)

@bot.command(brief='Create a game as the manual host')
async def host(ctx, *, game_name=None):
    global game

    if await require_game_not_active(ctx) and await require_not_in_game(ctx):
        if game is None:
            default_name = False
            if game_name is None:
                default_name = True
                game_name = ctx.author.display_name + "'s game"

            # name, host, players, votes
            game = Game(game_name, ctx.author)

            if default_name:
                await ctx.send("Game created!!!! :slight_smile:")
            else:
                await ctx.send("Created %s!!!! :slight_smile:" % game.name)
            await ctx.send("Players, type `" + cmd_prefix + "join` to sign up for this game.\n"
                               + "(:information_source: **" + game.host.display_name + "**, as the host, type `"
                               + cmd_prefix + "cancel` to cancel the signups.)")
        else:
            await yell_at_user(ctx, game.host.mention + " is already recruiting players for a game.`")

@bot.command(brief='Sign up for a game')
async def join(ctx):
    if await require_game_not_active(ctx):
        if game is None:
            await yell_at_user(ctx, "No one is seeking players for a game right now :-(")
            await ctx.send("(If you want to start a new game where you're the host, type `" + cmd_prefix + "host` to create a new game.)")
        elif not game.active:
            game.players.append(ctx.author)
            await ctx.send(ctx.author.mention + " joined " + game.name + ".\n"
                                + "**Now in the game (" + str(len(game.players)) + ")**: "
                                   + ", ".join([str(p) for p in game.players]))
            if len(game.players) >= 3:
                await ctx.send("(" + game.host.mention + ", as the host, you can start the game by typing `" + cmd_prefix + "start`.)")

@bot.command(brief='Un-sign-up for a game')
async def unjoin(ctx):
    if await require_game_not_active(ctx) and await require_signup_player(ctx):
        if game is None:
            await yell_at_user(ctx, "There's no game to leave right now!")
        else:
            game.players = [ p for p in game.players if p != ctx.author ]
            await ctx.send(ctx.author.mention + " left the game.\n"
                               + "**Now in the game (" + str(len(game.players)) + ")**: "
                                   + ", ".join(game.players))

@bot.command(brief='Cancel game during signups')
async def cancel(ctx):
    # TODO ::: allow anyone (not just host) to cancel a game after like some amount of time idk
    global game
    if await require_game_not_active(ctx) and await require_signup_host(ctx):
        game = None
        await ctx.send("Game cancelled. :crying_cat_face:")

@bot.command(brief='Start game when you are the host')
async def start(ctx):
    if await require_game_not_active(ctx) and await require_signup_host(ctx):
        if len(game.players) < 3:
            await yell_at_user(ctx, "You need at least three players for a Mafia game!")
            return
        game.active = True
        game.day = 0
        game.phase = 'TWILIGHT'
        await ctx.send(" ".join(p.mention for p in game.players)+ " : The game is starting!\n")

        # Count down
        for i in range(3, 0, -1):
            await asyncio.sleep(0.5)
            await ctx.send("%d..." % i)

        # Print game-starting stuff
        await asyncio.sleep(0.5)
        await system_message(ctx, game.name)
        await asyncio.sleep(0.2)
        await ctx.send(START_MSGS[random.randint(0, len(START_MSGS) - 1)])
        await enter_night_phase(ctx)

@bot.command(brief='Set a timer to end a particular phase')
async def timer(ctx, arg):
    if await require_game_active(ctx) and await require_host(ctx):
        # Cancel any existing timer
        cancel_timer()

        # Parse time expression (if no units supplied, we assume minutes)
        time_amt = None
        if m := re.match(r"^([\d\.]+) *mi?n?u?t?e?s?$", arg):
            time_amt = float(m.group(1)) * 60
        elif m := re.match(r"^([\d]+) *s?e?c?o?n?d?s?$", arg):
            time_amt = float(m.group(1))
        elif m := re.match(r"^([\d]+)$", arg):
            time_amt = float(m.group(1)) * 60

        if time_amt is not None:
            mins = time_amt // 60
            secs = int(time_amt) % 60

            # phrase time stuff
            # e.g. "Day is ending in 5 minutes and 48 seconds"
            time_phrase = "in "

            if mins != 0:
                if mins == 1:
                    time_phrase += "1 minute"
                else:
                    time_phrase += "%d minutes" % mins

            if mins != 0 and secs != 0:
                time_phrase += " and "

            if secs != 0:
                if secs == 1:
                    time_phrase += "1 second"
                else:
                    time_phrase += "%d seconds" % secs

            if mins == 0 and secs == 0:
                time_phrase = "NOW"

            phase_text = {
                'DAY': "Day",
                'VOTE': "Voting phase",
                'TWILIGHT': "Twilight phase",
                'NIGHT': "Night",
            }
            await system_message(ctx, ":hourglass: %s will end %s." % (phase_text[game.phase], time_phrase))
            try:
                await timer_routine(ctx, time_amt)
            except Alarm as a:
                # Timer got cancelled early -- so abort!
                await ctx.send(a.args[0])
                return

            # Once timer finishes, move to the next phase of gameplay
            if game.phase == 'DAY':
                await enter_voting_phase(ctx)
            elif game.phase == 'VOTE':
                await enter_twilight_phase(ctx)
            elif game.phase == 'TWILIGHT':
                await enter_night_phase(ctx)
            elif game.phase == 'NIGHT':
                await enter_day_phase(ctx, None)
        else:
            await yell_at_user(ctx, "Unknown time format. :( Please specify something like '5m' or '30s'.")

async def cast_vote(ctx, voted_user):
    game.votes[ctx.author] = voted_user

    if voted_user is Abstain:
        name = 'Abstain'
        ping = 'Abstain'
    else:
        name = voted_user.display_name
        ping = voted_user.mention

    majority_count = len(game.players) // 2 + 1
    vote_status = "(%d votes for %s, %d needed for majority)" % (game.votes_for(voted_user), name, majority_count)
    await ctx.send("%s votes for %s... %s" % (ctx.author.mention, ping, vote_status))

    if game.votes_for(voted_user) >= majority_count:
        if voted_user is Abstain:
            await system_message(ctx, "The town votes to abstain!", 'neutral_face', [
                "How could you do this to poor Abstain?!", "Abstain will be eliminated", "Abstain carries the day...",
                "The Abstains have it!", "The town chickens out!", "And they all lived happily ever after"
            ])
        else:
            await system_message(ctx, "Majority reached!", 'open_mouth', [
                "%s is condemned..." % voted_user.display_name, "A TRIBUTE HAS BEEN CHOSEN", "A decision has been reached...",
                "It's all over for %s..." % voted_user.display_name, "NO MORE VOTES NECESSARY", "MAJORITY!!"
            ])
        await enter_twilight_phase(ctx)

    elif game.total_votes() == len(game.players):
        await system_message(ctx, "Everyone voted, but no majority was reached!", 'slight_frown', [
            "It's a hung jury!", "~Split Decision~", "Couldn't choose just one, huh?", "The town votes for... no one.",
            "Everybody lives, Rose!", "The town failed to reach a decision.", "Whoops, you didn't pick anyone!"
        ])
        await enter_twilight_phase(ctx)

@bot.command(brief="Cast a vote during a game's voting phase")
async def vote(ctx, *, arg=None):
    if await require_game_active(ctx) and await require_player(ctx):
        if game.phase == 'VOTE':
            if arg is None:
                await yell_at_user(ctx, "Who are you voting for???")
            else:
                try:
                    voted_user = game.find_user(arg)
                    await cast_vote(ctx, voted_user)
                except ValueError as e:
                    await yell_at_user(ctx, e.args[0])
        elif game.phase == 'DAY':
            await yell_at_user(ctx, "Please wait until the end of the day to cast your vote!")
        else:
            await yell_at_user(ctx, "It's not time to vote right now!")

@bot.command(brief="Cast a vote during a game's voting phase")
async def kill(ctx, *, arg=None):
    if await require_game_active(ctx) and await require_host(ctx):
        if arg is None:
            await yell_at_user(ctx, "Who do you want to eliminate?")
        else:
            try:
                eliminated_user = game.find_user(arg)
                await eliminate_player(ctx, eliminated_user)
            except ValueError as e:
                await yell_at_user(ctx, e.args[0])

@bot.command(brief="Abstain during a game's voting phase")
async def abstain(ctx):
    if await require_game_active(ctx) and await require_player(ctx):
        if game.phase == 'VOTE':
            await cast_vote(ctx, Abstain)
        elif game.phase == 'DAY':
            await yell_at_user(ctx, "Please wait until the end of the day to cast your vote!")
        else:
            await yell_at_user(ctx, "It's not time to vote right now!")

@bot.command(brief='Test functionality')
async def ping(ctx):
    await ctx.send(ctx.author.mention + ' pong')

async def system_message(ctx, msg, emoji=None, altmsgs=None):
    if emoji is None:
        emoji = ''
    else:
        emoji = ':%s: ' % emoji

    if altmsgs is None or random.randint(0, 2):
        await ctx.send("***-- %s%s --***" % (emoji, msg))
    else:
        await ctx.send("***-- %s%s --***" % (emoji, altmsgs[random.randint(0, len(altmsgs) - 1)]))

async def timer_routine(ctx, length):
    game.timer = length
    while game.timer > 0:
        await asyncio.sleep(1)
        if game.stop_timer:
            game.stop_timer = False
            raise Alarm("*(stopped previous timer)*")
            return
        game.timer -= 1
        if game.timer == 0:
            #await system_message(ctx, NORMAL_ALARM_TEXT, 'bell', ALARM_TONES)
            pass
        elif game.timer % 120 == 0:
            await system_message(ctx, "%d minutes left" % (timer // 60))
        elif game.timer == 60:
            await system_message(ctx, "One minute left")
        elif game.timer == 30:
            await system_message(ctx, "30 seconds left")
        elif game.timer == 15:
            await system_message(ctx, "15 seconds left!")
        elif game.timer == 10:
            await system_message(ctx, "10 seconds left!!")
        elif game.timer <= 5:
            await system_message(ctx, str(int(game.timer)))

def cancel_timer():
    if game.timer > 0:
        game.stop_timer = True

async def enter_voting_phase(ctx, say_nothing=False):
    cancel_timer()
    game.phase = 'VOTE'
    if not say_nothing:
        game.votes = {}
        await system_message(ctx, NORMAL_VOTING_TEXT, 'pencil2', VOTING_TONES)
        await ctx.send("Type something like `" + cmd_prefix + "vote " + game.host.display_name + "` to vote for another user. "
                       + "(You can also ping whoever you're voting for after the `" + cmd_prefix + "vote` command.)\n"
                     + "You can also type `" + cmd_prefix + "abstain` to cast a vote for no one.\n"
                     + "Voting phase ends when everyone has cast a vote, or when a majority is reached.\n"
                       + "(:information_source: **" + game.host.display_name + "**, you can type `" + cmd_prefix
                       + "timer [time limit]` to place a time limit on voting, or `"
                       + cmd_prefix + "day` to extend the day phase more.)")

async def enter_day_phase(ctx, arg):
    if game.phase == 'NIGHT':
        cancel_timer()
        game.day += 1
        game.phase = 'DAY'
        cancel_timer()
        await system_message(ctx, ":sunny: DAY %d BEGINS" % game.day)
        await ctx.send("**Alive (%d):** %s" % (len(game.players), ", ".join([ p.mention for p in game.players ])))
    elif game.phase == 'TWILIGHT':
        await yell_at_user(ctx, "Please wait for the night to start before trying to end the night")
        return
    else:
        # can use this to extend day after calling an =vote
        cancel_timer()
        game.phase = 'DAY'
        await system_message(ctx, ':sunny: DAY %d***, um, ***CONTINUES' % game.day)

    if arg is None:
        await ctx.send("(:information_source: **" + game.host.display_name + "**, you can type:\n"
                + "- `" + cmd_prefix + "timer X` to move to voting phase in X amount of time (X could be `5m`, `30s`, etc)\n"
                + "- `" + cmd_prefix + "votingphase` to immediately end the day and move to voting phase.)\n")
    else:
        await timer(ctx, arg)

async def enter_twilight_phase(ctx):
    if game.phase == 'VOTE':
        cancel_timer()
        game.phase = 'TWILIGHT'
        # RESOLVE VOTES
        # Calculate who got eliminated

        majority_count = len(game.players) // 2 + 1
        eliminated = None

        voting_results_msg = "With **%d** players alive, a majority decision required **%d** votes.\n" % (len(game.players), majority_count)
        for u in game.players:
            vote_count = game.votes_for(u)
            if vote_count > 0:
                voting_results_msg += ("**%s (%d)**: %s\n"
                   % (u.display_name, vote_count, ", ".join([ p.display_name for p in game.votes.keys() if game.votes[p] == u ])))
            if vote_count >= majority_count:
                eliminated = u

        if game.votes_for(Abstain) > 0:
            voting_results_msg += ("**Abstain (%d)**: %s\n"
                % (game.votes_for(Abstain), ", ".join([ p.display_name for p in game.votes.keys() if game.votes[p] == Abstain ])))

        await system_message(ctx, "RESULTS", 'ballot_box', VOTING_END_TONES)
        await ctx.send(voting_results_msg)

        if eliminated is not None:
            await eliminate_player(ctx, eliminated)
        else:
            await ctx.send("No one is eliminated.")

        await ctx.send("(:information_source: **" + game.host.display_name + "**, say your piece, then type `" + cmd_prefix + "night` to move to night phase.)")

async def enter_night_phase(ctx):
    if game.phase == 'DAY':
        cancel_timer()
        # undo starting the day
        game.day -= 1
        game.phase = 'NIGHT'
        #cancel_timer() TODO implement 'cancel timer' on phase change
        await system_message(ctx, "...***uh, ***GOING BACK TO NIGHT %d" % game.day, 'first_quarter_moon_with_face')
    elif game.phase == 'VOTE':
        await yell_at_user(ctx, "Voting is not complete yet! Type '" + cmd_prefix + "timer 0' to end voting phase and resolve the elimination first.")
    elif game.phase == 'TWILIGHT':
        cancel_timer()
        game.phase = 'NIGHT'
        #cancel_timer()
        await system_message(ctx, 'NIGHT %d BEGINS' % game.day, 'first_quarter_moon_with_face')

        if game.day == 0:
            await ctx.send("(:information_source: **" + game.host.display_name + "**, do whatever you need to, then type `"
                   + cmd_prefix + "day` when you're ready to start the first day. "
                   + "You can also specify a time limit like `" + cmd_prefix + "day 5min`.)\n")
        else:
            await ctx.send("(:information_source: **" + game.host.display_name + "**, you can type:\n"
                    + "- `" + cmd_prefix + "timer X` to end the night in a certain amount of time\n"
                    + "- `" + cmd_prefix + "day` to immediately end the night and move to the next day phase.)\n")
    elif game.phase == 'NIGHT':
        await yell_at_user(ctx, "Hey! It's already nighttime, you weirdo!")

DEATH_EMOJIS = [ 'skull_crossbones', 'skull', 'bone', 'dizzy_face', 'ghost', 'zombie', 'vampire', 'coffin', 'headstone', 'dagger', 'bomb', 'knife', 'hole' ]
async def eliminate_player(ctx, eliminated):
    game.players = [ p for p in game.players if p != eliminated ]
    game.dead.append(eliminated)
    death_emoji = DEATH_EMOJIS[random.randint(0, len(DEATH_EMOJIS)-1)]
    await ctx.send(":%s: %s has been eliminated. :%s:" % (death_emoji, eliminated.mention, death_emoji))

@bot.command(brief='Move to day phase in game')
async def day(ctx, *, arg=None):
    if await require_game_active(ctx) and await require_host(ctx):
        await enter_day_phase(ctx, arg)

@bot.command(brief='Move to night phase in game')
async def night(ctx):
    if await require_game_active(ctx) and await require_host(ctx):
        await enter_night_phase(ctx)

@bot.command(brief='Move to voting phase in game')
async def votingphase(ctx):
    if await require_game_active(ctx) and await require_host(ctx):
        if game.phase == 'DAY':
            await enter_voting_phase(ctx)
        elif game.phase == 'VOTE':
            yell_at_user(ctx, "It's already the voting phase, what are you doing?")
        elif game.phase == 'TWILIGHT':
            system_message(ctx, "NEVER MIND, CONTINUE VOTING")
            await enter_voting_phase(ctx, say_nothing=True)
        elif game.phase == 'NIGHT':
            await yell_at_user(ctx, "Voting already ended for the day!")

def is_host(user):
    return game and game.active and game.host == user

def is_player(user):
    return game and game.active and user in game.players

def is_signup_host(user):
    return game and not game.active and game.host == user

def is_signup_player(user):
    return game and not game.active and user in game.players

async def require_host(ctx):
    if is_host(ctx.author):
        return True
    else:
        await yell_at_user(ctx, "You must be host to use this command.")
        return False

async def require_signup_host(ctx):
    if is_signup_host(ctx.author):
        return True
    else:
        await yell_at_user(ctx, "You must be the host of the current signing-up game to use this command.")
        return False

async def require_player(ctx):
    if is_player(ctx.author):
        return True
    else:
        await yell_at_user(ctx, "You must be a player to use this command.")
        return False

async def require_signup_player(ctx):
    if is_signup_player(ctx.author):
        return True
    else:
        await yell_at_user(ctx, "You must be signed up for a game to use this command.")
        return False

async def require_not_in_game(ctx):
    if (not is_host(ctx.author) and not is_player(ctx.author)
            and not is_signup_host(ctx.author) and not is_signup_player(ctx.author)):
        return True
    else:
        await yell_at_user(ctx, "You're already part of the game!")
        return False

async def require_game_not_active(ctx):
    if not game or not game.active:
        return True
    else:
        await yell_at_user(ctx, "There's already a game in progress!")
        return False

async def require_game_active(ctx):
    if game and game.active:
        return True
    else:
        await yell_at_user(ctx, "There's no game in progress!")
        return False

async def yell_at_user(ctx, msg):
    await ctx.send(ctx.author.mention + ' :warning: `%s`' % msg)

bot.run(access_token)
