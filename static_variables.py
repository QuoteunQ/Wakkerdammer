import discord

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

min_players = 1
possible_roles = {'werewolf', 'picky_werewolf', 'cupid', 'kidnapper', 'protector', 'seer', 'witch', 'hunter', 'elder', 'fool', 'civilian'}
gskey =  {0:'setup', 1: 'end of day', 2:'night: pre-wolves', 3:'night: wolves', 4:'night: witch', 5:'day: hunter', 6:'day: discussion', 7:'day: voting'}
known_commands = {
    '$hello', '$inspire', '$help', '$allroles',                                                     # commands not influencing a game
    '$gamesetup', '$join', '$leave',                                                                # game setup
    '$kidnap', '$protect', '$hunt', '$lovers', '$sleepat', '$pick', '$lunch', '$potion',            # night commands players
    '$playerlist', '$poopbreak', '$roles', '$gamestate', '$gm', '$alive',                           # utility commands
    '$clearplayerlist', '$gamestart', '$gamereset',                                                 # game control gamemaster
    '$beginnight', '$startwolves', '$endwolves', '$endnight', '$endhunter'                  # gamestate flow control gamemaster
}

# Set specific settings for the games:
# - If kill_first is False, wolves mutilate on night 1
# - If lovers_on_night_1 is True, the lovers can only be made on night 1
settings = {'kill_first': False, 'lovers_on_night_1': True}
