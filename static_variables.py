import discord

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

min_players = 1
possible_roles = {'werewolf', 'picky_werewolf', 'cupid', 'kidnapper', 'protector', 'seer', 'witch', 'hunter', 'elder', 'fool', 'civilian'}
gskey =  {0:'setup', 1:'night: pre-wolves', 2:'night: wolves', 3:'night: witch', 4:'day: hunter', 5:'day: discussion', 6:'day: voting'}

# Set specific settings for the games:
# - If kill_first is False, wolves mutilate on night 1
# - If lovers_on_night_1 is True, the lovers can only be made on night 1
settings = {'kill_first': False, 'lovers_on_night_1': True}
