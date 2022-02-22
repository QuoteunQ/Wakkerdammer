import discord

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

min_players = 1
possible_roles = {'werewolf', 'picky werewolf', 'cupid', 'kidnapper', 'protector', 'seer', 'witch', 'hunter', 'elder', 'fool', 'civilian'}
gskey =  {0:'setup', 1: 'end of day', 2:'night: pre-wolves', 3:'night: wolves', 4:'night: witch', 5:'day: hunter', 6:'day: discussion', 7:'day: voting'}
known_commands = {'$hello', '$inspire', '$help', '$allroles', '$gamesetup', '$join', '$leave', '$kidnap', '$protect', '$hunt', '$lovers', '$sleepat', '$pick', '$lunch',
                '$playerlist', '$poopbreak', '$roles', '$gamestate', '$gm', '$alive', '$clearplayerlist', '$gamestart', '$gamereset', '$beginnight',
                '$startwolfvoting', '$endwolfvoting', '$endnight', '$endhunter'}

# Set specific settings for the games:
# - If kill_first is False, wolves mutilate on night 1
# - If lovers_on_night_1 is True, the lovers can only be made on night 1
settings = {'kill_first': False, 'lovers_on_night_1': True}
