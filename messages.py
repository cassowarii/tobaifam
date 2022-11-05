"""Canned messages for host flavor"""
# pylint:disable=line-too-long
import random

NORMAL_ALARM_TEXT = "DING DING DING"
NORMAL_VOTING_TEXT = "Time to vote!"

START_MSGS = [
    "START!",
    "スタート！",
    "*commencer !*",
    "`COMIENZA EL JUEGO`",
    "开始。︀",
    "*~begin~*",
    "**COMMENCE**",
    "***So... it begins.***",
    "*And away we go.*",
    "Here it comes...!",
    "IT BEGINS",
    "Let the games.......... *begin!*",
]

ALARM_TONES = [
    "BEEP BEEP!",
    "That's all, folks",
    "The end!!!",
    "Whoa nelly!",
    "It's over...",
    "...That's it. I'm callin' it...",
    "It's the end of an era!",
    "Ding dong! `Oh, someone's at the door...`",
    "womp womp",
    "DING DING D- oh sorry, is that annoying?",
    "BEEP BOOP END OF LINE",
    "The End~!",
    "It's all over for you, buddy...",
    "BEEP BEEP",
    "DING DONG",
    "Dingadang dong dang doo",
    "That's enough now!",
    "Dang dang... Sorry, I'm still new at this.",
]

VOTING_TONES = [
    "Count those votes!",
    "Aw yeah, it's votin' time!",
    "Let's Voting Today!",
    "Everybody Votes Channel!",
    "Cast those votes, buckaroo!",
    "Let's all vote for who we want to get rid of!",
    "Don't forget to vote for who you don't like!",
    "Let's do a vote!",
    "It's time for everyone to vote...",
    "Voting time is boating time!",
    "Let's all vote together!",
    "Cast those ballots!",
    'I liked when he said "it\'s voting time" and then he voted all over the place',
    "Vote 'em up, cowboy",
]

VOTING_END_TONES = [
    "The votes are in!!!",
    "it's over!!!!!!",
    "Thank you for participating in our democracy!",
    "I do believe this represents the sum total of votes that shall be counted in this elimination election. Indubitably.",
    "Thanks for voting!",
    "STOP VOTING",
    "the end (of voting)",
    "OK we're good now you can stop casting votes",
    "guys that's enough votes",
    "Let's see what the ~~cat~~ vote dragged in",
    "Shall we see what the results were?",
    "Who's being voted off the island?",
]

VOTE_ABSTAIN_RESPONSES = [
    "How could you do this to poor Abstain?!",
    "Abstain will be eliminated",
    "Abstain carries the day...",
    "The Abstains have it!",
    "The town chickens out!",
    "And they all lived happily ever after",
]

VOTE_MAJORITY_RESPONSES = [
    "The bell tolls...",
    "A TRIBUTE HAS BEEN CHOSEN",
    "A decision has been reached...",
    "It's all over for you...",
    "NO MORE VOTES NECESSARY",
    "MAJORITY!!",
]

VOTE_NO_DECISION_RESPONSES = [
    "It's a hung jury!",
    "~Split Decision~",
    "Couldn't choose just one, huh?",
    "The town votes for... no one.",
    "Everybody lives, Rose!",
    "The town failed to reach a decision.",
    "Whoops, you didn't pick anyone!",
]

DEATH_EMOJIS = [
    "skull_crossbones",
    "skull",
    "bone",
    "dizzy_face",
    "ghost",
    "zombie",
    "vampire",
    "coffin",
    "headstone",
    "dagger",
    "bomb",
    "knife",
    "hole",
]


async def system_message(ctx, msg, emoji="", altmsgs=None):
    """Normal system message"""
    if emoji:
        emoji = f":{emoji}: "
    if altmsgs is None or random.randint(0, 2):
        await ctx.send(f"***-- {emoji}{msg} --***")
    else:
        await ctx.send(f"***-- {emoji}{random.choice(altmsgs)} --***")


async def yell_at_user(ctx, msg):
    """Error message"""
    await ctx.send(f"{ctx.author.mention} :warning: `{msg}`")
