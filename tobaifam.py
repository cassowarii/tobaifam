"""Host of everyone's favorite murder simulator"""
# pylint:disable=missing-function-docstring
import asyncio
import functools
import os
import random
import re

import discord
from discord.ext import commands

import mafia
import messages
from mafia import Abstain, Alarm
from messages import system_message, yell_at_user

CMD_PREFIX = "="

DISCORD_API_TOKEN_VAR = "ACCESS_TOKEN"

# Declare our bot and API intents
# TODO: drive TWILIGHT vote via menu/reactions to avoid needing message_content
di = discord.Intents.default()
di.message_content = True
bot = commands.Bot(command_prefix=CMD_PREFIX, intents=di)

#
# Global state - TODO: move into an object when we make this reentrant
#
game = None
game_active = False
hosts = []
players = {}


#
# Assertion helpers
# TODO: relocate to game abstraction
#
def is_host(user):
    return game and game.active and game.host == user


def is_player(user):
    return game and game.active and user in game.players


def is_signup_host(user):
    return game and not game.active and game.host == user


def is_signup_player(user):
    return game and not game.active and user in game.players


#
# Decorator-style command assertions - must be placed AFTER the @bot.command decorator
# All of these assume the first arg to the command is the ctx.
#
# More general assertions should sit higher on the list than more specific assertions.
#
# TODO: possibly relocate to game abstraction? or own file
#
# Example:
# >>> @bot.command(brief="Example command")
# >>> @require_game_active()
# >>> @require_host()
# >>> def example(ctx):
# ...     pass
#
def require_host(yell_msg="You must be host to use this command."):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if not is_host(ctx.author):
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def require_signup_host(yell_msg="You must be the host of the current signing-up game to use this command."):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if not is_signup_host(ctx.author):
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def require_player(yell_msg="You must be a player to use this command."):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if not is_player(ctx.author):
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def require_signup_player(yell_msg="You must be signed up for a game to use this command."):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if not is_signup_player(ctx.author):
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def require_not_in_game(yell_msg="You're already part of the game!"):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if any(
                [is_host(ctx.author), is_player(ctx.author), is_signup_host(ctx.author), is_signup_player(ctx.author)]
            ):
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def require_game_not_active(yell_msg="There's already a game in progress!"):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if game is not None and game.active:
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def require_game_active(yell_msg="There's no game in progress!"):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if game is None or not game.active:
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def require_game_phase(phase, yell_msg="Now's not the time to do that!"):
    def _decorator(func):
        @functools.wraps(func)
        async def _wrapper(*args, **kwargs):
            ctx = args[0]
            if game is None or game.phase != phase:
                await yell_at_user(ctx, yell_msg)
            else:
                return await func(*args, **kwargs)

        return _wrapper

    return _decorator


#
# Commands
#


@bot.event
async def on_ready():
    print(f"--- {bot.user.name} has connected ---")


@bot.event
async def on_message(msg):
    # During voting phase, delete any messages that don't start with =vote
    if game and game.phase == game.Phase.VOTE:
        if msg.author not in (game.host, bot.user):
            if not msg.content.startswith(f"{CMD_PREFIX}vote") and not msg.content.startswith(f"{CMD_PREFIX}abstain"):
                await msg.delete()
                await msg.channel.send(
                    msg.author.mention
                    + f"You may only type `{CMD_PREFIX}vote [someone]` or `{CMD_PREFIX}abstain` at this time."
                )
                return
    await bot.process_commands(msg)


@bot.command(brief="Create a game as the manual host")
@require_game_not_active()
@require_not_in_game()
async def host(ctx, *, game_name=None):
    global game
    if game is None:
        default_name = False
        if game_name is None:
            default_name = True
            game_name = ctx.author.display_name + "'s game"

        # name, host, players, votes
        game = mafia.Game(game_name, ctx.author)

        if default_name:
            await ctx.send("Game created!!!! :slight_smile:")
        else:
            await ctx.send(f"Created {game.name}!!!! :slight_smile:")
        await ctx.send(
            f"Players, type `{CMD_PREFIX}join` to sign up for this game.\n"
            + f"(:information_source: **{game.host.display_name}** as the host, type `{CMD_PREFIX}cancel`"
            + "to cancel the signups.)"
        )
    else:
        await yell_at_user(ctx, f"{game.host.display_name} is already recruiting players for a game.")


@bot.command(brief="Sign up for a game")
@require_game_not_active()
async def join(ctx):
    if game is None:
        await yell_at_user(ctx, "No one is seeking players for a game right now :-(")
        await ctx.send(f"(If you want to start a new game as the host, type `{CMD_PREFIX}host` to create a new game.)")
    elif not game.active:
        game.players.append(ctx.author)
        await ctx.send(
            f"{ctx.author.mention} joined {game.name}.\n **Now playing ({len(game.players)}):** "
            + ", ".join([p.name for p in game.players])
        )
        if len(game.players) >= 3:
            await ctx.send(f"({game.host.mention}, as the host, you can start the game by typing `{CMD_PREFIX}start`.)")


@bot.command(brief="Un-sign-up for a game")
@require_game_not_active()
@require_signup_player()
async def unjoin(ctx):
    if game is None:
        await yell_at_user(ctx, "There's no game to leave right now!")
    else:
        game.players = [p for p in game.players if p != ctx.author]
        await ctx.send(
            f"{ctx.author.mention} left the game.\n **Now playing ({len(game.players)}):**"
            + ", ".join([p.name for p in game.players])
        )


@bot.command(brief="Cancel game during signups")
@require_game_not_active()
@require_signup_host()  # TODO: allow anyone (not just host) to cancel a game after like some amount of time idk
async def cancel(ctx):
    global game
    game = None
    await ctx.send("Game cancelled. :crying_cat_face:")


@bot.command(brief="Start game when you are the host")
@require_game_not_active()
@require_signup_host()
async def start(ctx):
    if len(game.players) < 3:
        await yell_at_user(ctx, "You need at least three players for a Mafia game!")
        return
    game.active = True
    game.day = 0
    game.phase = game.Phase.TWILIGHT
    await ctx.send(" ".join(p.mention for p in game.players) + " : The game is starting!\n")

    # Count down
    for i in range(3, 0, -1):
        await asyncio.sleep(0.5)
        await ctx.send(f"{i}...")

    # Print game-starting stuff
    await asyncio.sleep(0.5)
    await system_message(ctx, game.name)
    await asyncio.sleep(0.2)
    await ctx.send(random.choice(messages.START_MSGS))
    await enter_night_phase(ctx)


@bot.command(brief="Set a timer to end a particular phase")
@require_game_active()
@require_host()
async def timer(ctx, arg):
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
                time_phrase += f"{mins} minutes"

        if mins != 0 and secs != 0:
            time_phrase += " and "

        if secs != 0:
            if secs == 1:
                time_phrase += "1 second"
            else:
                time_phrase += f"{secs} seconds"

        if mins == 0 and secs == 0:
            time_phrase = "NOW"

        await system_message(ctx, f"{game.phase.value} will end {time_phrase}.", "hourglass")

        try:
            await timer_routine(ctx, time_amt)
        except Alarm as a:
            # Timer got cancelled early -- so abort!
            await ctx.send(a.args[0])
            return

        # Once timer finishes, move to the next phase of gameplay
        if game.phase == game.Phase.DAY:
            await enter_voting_phase(ctx)
        elif game.phase == game.Phase.VOTE:
            await enter_twilight_phase(ctx)
        elif game.phase == game.Phase.TWILIGHT:
            await enter_night_phase(ctx)
        elif game.phase == game.Phase.NIGHT:
            await enter_day_phase(ctx, None)
    else:
        await yell_at_user(
            ctx,
            "Unknown time format. :( Please specify something like '5m' or '30s'.",
        )


async def cast_vote(ctx, voted_user):
    game.votes[ctx.author] = voted_user

    if voted_user is Abstain:
        name = "Abstain"
        mention = "Abstain"
    else:
        name = voted_user.display_name
        mention = voted_user.mention

    majority_count = len(game.players) // 2 + 1
    await ctx.send(
        f"{ctx.author.mention} votes for {mention}! "
        + f"({game.votes_for(voted_user)} votes for {name}, {majority_count} needed for majority)"
    )

    if game.votes_for(voted_user) >= majority_count:
        if voted_user is Abstain:
            await system_message(
                ctx,
                "The town votes to abstain!",
                "neutral_face",
                messages.VOTE_ABSTAIN_RESPONSES,
            )
        else:
            await system_message(
                ctx,
                "Majority reached!",
                "open_mouth",
                messages.VOTE_MAJORITY_RESPONSES,
            )
        await enter_twilight_phase(ctx)

    elif game.total_votes() == len(game.players):
        await system_message(
            ctx,
            "Everyone voted, but no majority was reached!",
            "slight_frown",
            messages.VOTE_NO_DECISION_RESPONSES,
        )
        await enter_twilight_phase(ctx)


@bot.command(brief="Cast a vote during a game's voting phase")
@require_game_active()
@require_player()
@require_game_phase(mafia.Game.Phase.VOTE, yell_msg="Please wait until the end of the day to cast your vote!")
async def vote(ctx, *, arg=None):
    if arg is None:
        await yell_at_user(ctx, "Who are you voting for???")
    else:
        try:
            voted_user = game.find_user(arg)
            await cast_vote(ctx, voted_user)
        except ValueError as e:
            await yell_at_user(ctx, e.args[0])


@bot.command(brief="Abstain during a game's voting phase")
@require_game_active()
@require_player()
@require_game_phase(mafia.Game.Phase.VOTE, yell_msg="Please wait until the end of the day to cast your vote!")
async def abstain(ctx):
    await cast_vote(ctx, Abstain)


@bot.command(brief="Eliminate a player manually as the host")
@require_game_active()
@require_host()
async def kill(ctx, *, arg=None):
    if arg is None:
        await yell_at_user(ctx, "Who do you want to eliminate?")
    else:
        try:
            eliminated_user = game.find_user(arg)
            await eliminate_player(ctx, eliminated_user)
        except ValueError as e:
            await yell_at_user(ctx, e.args[0])


@bot.command(brief="Test functionality")
async def ping(ctx):
    await ctx.send(ctx.author.mention + " pong")


async def timer_routine(ctx, length):
    game.timer = length
    while game.timer > 0:
        await asyncio.sleep(1)
        if game.stop_timer:
            game.stop_timer = False
            raise Alarm("*(stopped previous timer)*")
        game.timer -= 1
        if game.timer == 0:
            # await system_message(ctx, NORMAL_ALARM_TEXT, 'bell', ALARM_TONES)
            pass
        elif game.timer % 120 == 0:
            await system_message(ctx, f"{timer // 60} minutes left")
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
        game.timer = 0
        game.stop_timer = True


async def enter_voting_phase(ctx, say_nothing=False):
    cancel_timer()
    game.phase = game.Phase.VOTE
    if not say_nothing:
        game.votes = {}
        await system_message(ctx, messages.NORMAL_VOTING_TEXT, "pencil2", messages.VOTING_TONES)
        await ctx.send(
            f"Type something like `{CMD_PREFIX}vote {game.host.display_name}`to vote for another user. "
            + f"(You can also ping whoever you're voting for after the `{CMD_PREFIX}vote` command.)\n"
            + f"You can also type `{CMD_PREFIX}abstain` to cast a vote for no one.\n"
            + "Voting phase ends when everyone has cast a vote, or when a majority is reached.\n"
            + f"(:information_source: **{game.host.display_name}**, you can type `{CMD_PREFIX}timer [time limit]` "
            + f"to place a time limit on voting, or `{CMD_PREFIX}day` to extend the day phase more.)"
        )


async def enter_day_phase(ctx, arg):
    if game.phase == game.Phase.NIGHT:
        cancel_timer()
        game.day += 1
        game.phase = game.Phase.DAY
        cancel_timer()
        await system_message(ctx, f"DAY {game.day} BEGINS", "sunny")
        await ctx.send(f"**Alive ({len(game.players)}):** {', '.join([p.mention for p in game.players])}")
    elif game.phase == game.Phase.TWILIGHT:
        await yell_at_user(ctx, "Please wait for the night to start before trying to end the night")
        return
    else:
        # can use this to extend day after calling an =vote
        cancel_timer()
        game.phase = game.Phase.DAY
        await system_message(ctx, f"DAY {game.day}***, um, ***CONTINUES", "sunny")

    if arg is None:
        await ctx.send(
            f"(:information_source: **{game.host.display_name}**, you can type:\n"
            + f"- `{CMD_PREFIX}timer X` to move to voting phase in X amount of time (X could be `5m`, `30s`, etc)\n"
            + f"- `{CMD_PREFIX}votingphase` to immediately end the day and move to voting phase.)\n"
        )
    else:
        await timer(ctx, arg)


async def enter_twilight_phase(ctx):
    if game.phase == game.Phase.VOTE:
        cancel_timer()
        game.phase = game.Phase.TWILIGHT
        # RESOLVE VOTES
        # Calculate who got eliminated

        majority_count = len(game.players) // 2 + 1
        eliminated = None

        voting_results_msg = (
            f"With **{len(game.players)}** players alive, a majority decision requires **{majority_count}** votes.\n"
        )
        for u in game.players:
            vote_count = game.votes_for(u)
            if vote_count > 0:
                voters = [p.display_name for p, v in game.votes.items() if v == u]
                voting_results_msg += f"**{u.display_name} ({vote_count})**: {', '.join(voters)}\n"
            if vote_count >= majority_count:
                eliminated = u

        if game.votes_for(Abstain) > 0:
            voters = [p.display_name for p, v in game.votes.items() if v == Abstain]
            voting_results_msg += f"**Abstain ({game.votes_for(Abstain)})**: {', '.join(voters)}\n"

        await system_message(ctx, "RESULTS", "ballot_box", messages.VOTING_END_TONES)
        await ctx.send(voting_results_msg)

        if eliminated is not None:
            await eliminate_player(ctx, eliminated)
        else:
            await ctx.send("No one is eliminated.")

        await ctx.send(
            f"(:information_source: **{game.host.display_name}**, say your piece, then type `{CMD_PREFIX}night`"
            + "to move to night phase.)"
        )


async def enter_night_phase(ctx):
    if game.phase == game.Phase.DAY:
        cancel_timer()
        # undo starting the day
        game.day -= 1
        game.phase = game.Phase.NIGHT
        await system_message(ctx, f"...***uh, ***GOING BACK TO NIGHT {game.day}", "first_quarter_moon_with_face")
    elif game.phase == game.Phase.VOTE:
        await yell_at_user(
            ctx,
            f"Voting is not over yet! Type '{CMD_PREFIX}timer 0` to end voting and resolve the elimination first.",
        )
    elif game.phase == game.Phase.TWILIGHT:
        cancel_timer()
        game.phase = game.Phase.NIGHT
        await system_message(ctx, f"NIGHT {game.day} BEGINS", "first_quarter_moon_with_face")

        if game.day == 0:
            await ctx.send(
                f"(:information_source: **{game.host.display_name}**, do whatever you need to, then type "
                + f"`{CMD_PREFIX}day` to start the first day. You can also specify a time limit, like "
                + f"`{CMD_PREFIX}day 5min`.)\n"
            )
        else:
            await ctx.send(
                f"(:information_source: **{game.host.display_name}**, you can type:\n"
                + f"- `{CMD_PREFIX}timer X` to end the night in a certain amount of time\n"
                + f"- `{CMD_PREFIX}day` to immediately end the night and move to the next day phase.)\n"
            )
    elif game.phase == game.Phase.NIGHT:
        await yell_at_user(ctx, "Hey! It's already nighttime, you weirdo!")


async def eliminate_player(ctx, eliminated):
    game.players = [p for p in game.players if p != eliminated]
    game.dead.append(eliminated)
    death_emoji = random.choice(messages.DEATH_EMOJIS)
    await ctx.send(f":{death_emoji}: {eliminated.mention} has been eliminated. :{death_emoji}:")


@bot.command(brief="Move to day phase in game")
@require_game_active()
@require_host()
async def day(ctx, *, arg=None):
    await enter_day_phase(ctx, arg)


@bot.command(brief="Move to night phase in game")
@require_game_active()
@require_host()
async def night(ctx):
    await enter_night_phase(ctx)


@bot.command(brief="Move to voting phase in game")
@require_game_active()
@require_host()
async def votingphase(ctx):
    if game.phase == game.Phase.DAY:
        await enter_voting_phase(ctx)
    elif game.phase == game.Phase.VOTE:
        yell_at_user(ctx, "It's already the voting phase, what are you doing?")
    elif game.phase == game.Phase.TWILIGHT:
        system_message(ctx, "NEVER MIND, CONTINUE VOTING")
        await enter_voting_phase(ctx, say_nothing=True)
    elif game.phase == game.Phase.NIGHT:
        await yell_at_user(ctx, "Voting already ended for the day!")


#
# startup routine
#

if __name__ == "__main__":

    access_token = os.environ.get(DISCORD_API_TOKEN_VAR, None)
    if access_token is None:
        raise EnvironmentError(
            f"{DISCORD_API_TOKEN_VAR} environment variable not set! Ensure you have a valid Discord API bot token!"
        )
    bot.run(access_token)
