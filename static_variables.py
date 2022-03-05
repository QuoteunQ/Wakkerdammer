import discord

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

min_players = 1
possible_roles = {'werewolf', 'picky_werewolf', 'cupid', 'kidnapper', 'protector', 'seer', 'witch', 'hunter', 'elder', 'fool', 'civilian'}

# gamestates: 'setup', 'end of day', 'night: pre-wolves', 'night: wolves', 'night: witch', 'day: hunter', 'day: discussion', 'day: voting', 'finished'

known_commands = {
    '$hello', '$inspire', '$help', '$allroles',                                                     # commands not influencing a game
    '$gamesetup', '$join', '$leave',                                                                # game setup
    '$kidnap', '$protect', '$shoot', '$lovers', '$sleepat', '$pick', '$lunch', '$potion',           # player commands
    '$lynch',
    '$playerlist', '$poopbreak', '$roles', '$gamestate', '$gm', '$alive', '$settings',              # utility commands
    '$clearplayerlist', '$changesetting', '$gamestart', '$gamereset',                               # game control gamemaster
    '$beginnight', '$startwolves', '$endwolves', '$endnight', '$endhunter',                         # gamestate flow control gamemaster
    '$startvoting', '$endvoting'
}

topics = {
    'kidnapper':
        "- You are the kidnapper! During nights type $kidnap <player name> to kidnap someone. "
        "You can't select the same target two nights in a row. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'cupid':
        "- You are cupid! During nights type $sleepat <player name> to stay over at someone's house. "
        "Make the lover couple using $lovers <player name 1> <player name 2>. The setting that you can only make lovers on night 1 is set to: {}. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'protector':
        "- You are the protector! During nights type $protect <player name> to protect someone's house (including your own). "
        "You can't select the same target two nights in a row. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'seer':
        "- You are the seer! During nights type $lookat <player name> to obtain that person's role. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'witch':
        "- You are the witch! You will be told at the end of each night who that night's victims are. "
        "You can then use your potions by typing $potion <kill/heal/mute> <player name> to use the specified potion on the specified player. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'hunter':
        "- You are the hunter! When you are killed, you can use $shoot <player name> to take someone with you to the grave. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.", 
    'elder':
        "- You are the elder! You will survive the wolves' first attack if they target you. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'fool':
        "- You are the fool! You will survive the first time the town attempst to lynch you by voting. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'civilian':
        "- You are a civilian! Sit tight during the night, but when day comes, "
        "you can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'werewolf':
        "- You are a werewolf! You have been added to another channel together with the other werewolves. "
        "During nights type $lunch <player name> in that channel to cast your vote for that player regarding that night's kill. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'picky_werewolf':
        "- You are the picky werewolf! You have been added to another channel together with the other werewolves. "
        "During nights type $lunch <player name> in that channel to cast your vote for that player regarding that night's kill. "
        "You can pick another wolf from among the remaining players to add to the pack by typing $pick <player name>. "
        "You can vote for someone during days using $lynch <player name>. "
        "For questions please @ the gamemaster. Type $help to see other commands.",
    'werewolves':
        "- Welcome to the werewolves groupchat! This channel will be used for discussing the game amongst yourselves, "
        "as well as casting your individual votes for each night's kill. For this game, "
        "the setting that you mutilate instead of kill your target during the first night is set to: {}",
    'lovers':
        "- Welcome! You've been made lovers by our dear cupid. Feel free to get acquainted in this channel.",
    'gamemaster':
        "- In this channel you as gamemaster will see updates about what's happening in the game. "
        "You can also use it to start the game without revealing the roles in the game to the players. "
        "Your commands to control the game include: '$gamestart', '$clearplayerlist', '$changesetting', '$beginnight', "
        "'$startwolves', '$endwolves', '$endnight', '$endhunter', '$startvoting', '$endvoting'."
}