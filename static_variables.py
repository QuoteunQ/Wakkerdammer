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

topics = {
'kidnapper':
    "- You are the kidnapper! During nights type $kidnap <player name> to kidnap someone, and vote for someone during days using $lynch <player name>. "
    "For questions please @ the gamemaster. Type $help to see other commands",
'cupid':
    "",
'protector':
    "",
'seer':
    "",
'witch':
    "",
'hunter':
    "", 
'elder':
    "",
'fool':
    "",
'civilian':
    "",
'werewolf':
    "",
'picky_werewolf':
    "- You are the picky werewolf! The other werewolves are {} (if there is an incorrect number in here contact the gamemaster). "
    "You are able to pick {} other werewolf(s). Pick someone by typing $pick <player name>. "
    "You vote to kill/mutilate in the werewolves groupchat. For questions please @ the gamemaster. Type $help to see other commands.",
'werewolves':
    "- Welcome to the werewolves groupchat! This groupchat will be used for discussing the game amongst yourselves.",
'lovers':
    "- Welcome! You've been made lovers by our dear cupid. Feel free to get acquainted in this channel."
}