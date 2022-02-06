import os
import discord
import requests
import json
from classes import ww_game
from static_variables import client, min_players, possible_roles, gskey


games = {}                  # dict with < guild_id : game object >



def get_quote():
    """ Fetches inspiring quote from zenquotes.io """
    response = requests.get("https://zenquotes.io/api/random")
    json_data = json.loads(response.text)
    quote = json_data[0]['q'] + " -" + json_data[0]['a']
    return quote


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return 

# ----------------------- Commands which don't require a game taking place in the guild --------------------------

    if message.content.startswith('$hello'):
        await message.channel.send('Hello')

    elif message.content.startswith('$inspire'):
        quote = get_quote()
        await message.channel.send(quote)

    elif message.content.startswith('$help'):
        await message.channel.send("Commands: $inspire $gamesetup $join $leave $gamestart $playerlist $clearplayerlist $allroles $roles $setup? $gm $beginnight $action $endnight $beginvoting")
    
    elif message.content.startswith('$allroles'):
        await message.channel.send("Current roles in the game include: {}".format(possible_roles))

    elif message.content.startswith('$gamesetup'):
        if message.guild.id in games.keys():
            await message.channel.send("Failed to start game setup: there's still a game running in this server!")
        else:
            print("Starting game setup...")
            town_square_channel = discord.utils.get(message.guild.channels, name='town_square')
            if not town_square_channel:
                town_square_channel = await message.guild.create_text_channel(name='town_square')
                await town_square_channel.send("I've created this channel for all non-secret communication about the game.")
            new_game = ww_game(message.guild, message.author)
            overwritesgm = {
                message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                message.author: discord.PermissionOverwrite(read_messages=True),
                client.user: discord.PermissionOverwrite(read_messages=True)
            }
            new_game.gm_channel = await message.guild.create_text_channel(name='gamemaster', overwrites=overwritesgm)
            await new_game.gm_channel.send("""In this channel you as gamemaster will see updates about what's happening in the game.\n
                                            You can also use it to start the game without revealing the roles in the game to the players.""")
            print("The gamemaster is {}".format(new_game.gm.display_name))
            await town_square_channel.send("""Starting game setup... \n
                                            The gamemaster is {}.\n
                                            To join the game, please type '$join' \n
                                            Minimum {} players required to start the game \n
                                            To start the game, the GM can type '$gamestart <role> <role>' etc...\n
                                            Current roles in the game include: {}""".format(message.author.display_name, min_players, possible_roles))
            games[message.guild.id] = new_game


# --------------------------- Commands which do require a game taking place in the guild ---------------------------------------

    if message.guild.id not in games.keys():
        await message.channel.send("There's no game running in this server yet!")
        return

    game = games[message.guild.id]


# ------------------------------------ Game join & leave ------------------------------------------

    if message.content.startswith('$join'):
        await game.join(message)

    elif message.content.startswith('$leave'):
        await game.leave(message)


# ---------------------------- Night Commands Players -----------------------------------

    elif message.content.startswith('$kidnap'):
        if await game.valid_target(message, req_role='kidnapper', req_gs=1):
            await game.player_names_objs[message.author.display_name].kidnap(message)
    
    elif message.content.startswith('$protect'):
        if await game.valid_target(message, req_role='protector', req_gs=1):
            await game.player_names_objs[message.author.display_name].protect(message)

    elif message.content.startswith('$lovers'):
        if await game.valid_target(message, req_role='cupid', req_gs=1, req_target_count=2):
            await game.player_names_objs[message.author.display_name].make_lovers(message)

    elif message.content.startswith('$sleepat'):
        if await game.valid_target(message, req_role='cupid', req_gs=1):
            await game.player_names_objs[message.author.display_name].sleep_at(message)

    elif message.content.startswith('$lunch'):
        if await game.valid_target(message, req_role='wolf', req_gs=2):
            wolf_author = game.players_names_objs[message.author.display_name]
            if wolf_author.kill_vote != '':      # if they've already voted
                await message.channel.send("You've already voted to kill someone tonight!")
            else:
                target = message.content.split(' ')[1]
                wolf_author.kill_vote = target
                vote_count = len([wolf.kill_vote for wolf in game.wolves if wolf.kill_vote != ''])
                wolves_vote_msg = "*** Wolves: {} has voted to lunch {}. {}/{} wolves have voted".format(message.author.display_name, target, vote_count, len(game.wolves))
                await message.channel.send(wolves_vote_msg)
                await game.gm_channel.send(wolves_vote_msg)

    elif message.content.startswith('$pick'):
        if await game.valid_target(message, req_role='picky_werewolf', req_gs=1):
            await game.player_names_objs[message.author.display_name].pick_wolf(message)


# ------------------------------ Utility commands -------------------------------------

    elif message.content.startswith('$playerlist'):
        await message.channel.send("Players: {}".format(game.lobby))

    elif message.content.startswith('$poopbreak'):
        await message.channel.send("Aren't you a funnyman https://www.youtube.com/watch?v=DN0gAQQ7FAQ")
  
    elif message.content.startswith('$roles'):
        await message.channel.send('Roles included in this game are: {}'.format(game.roles))

    elif message.content.startswith('$gamestate'):
        await message.channel.send("State of Game: {}".format(gskey[game.gamestate]))

    elif message.content.startswith('$gm'):
        await message.channel.send("Current GM is: {}".format(game.gm.display_name))

    elif message.content.startswith('$alive'):
        await message.channel.send('Alive players are: {}'.format(game.alive))


# ----------------------- Commands which can only be used by the gamemaster ------------------------------------

    if message.author != game.gm:
        await message.channel.send("Relax bro you're not the GM")
        return

    if message.content.startswith('$clearplayerlist'):
        if game.gamestate == 0:
            game.lobby = []
            game.ids = {}
            await message.channel.send("Player list is now empty")
        else:
            await message.channel.send("You can't do that outside of game setup")

    elif message.content.startswith('$gamestart'):
        if game.gamestate != 0:
            await message.channel.send("No game setup taking place")
        else:
            if len(game.lobby) < min_players:
                await message.channel.send("Insufficient players")
            else:
                roles = message.content.split(' ')[1:]
                for role in roles:
                    if role not in possible_roles:
                        await message.channel.send("Invalid role {}, please try again".format(role))
                        return				# end function
                if len(roles) != len(game.lobby):
                    await message.channel.send("Mismatch between amounts of roles ({}) & players ({})".format(len(roles), len(game.lobby)))
                else:
                    print("Starting game...")
                    print("Included roles are: {}".format(roles))
                    print("Players playing: {}, totalling {}".format(game.lobby, len(game.lobby)))
                    game.roles = roles
                    await game.distribute_roles()
                    await game.gm_channel.send("""Game started! Players playing: {}, totalling {}.\n
                                                The wolves are {}.\n
                                                Ready for $beginnight !""".format(game.lobby, len(game.lobby), game.wolves))
                    await game.town_square.send("Game started! Please check if you have been added to a text channel, and that you are clear on your role and how to play it")

    elif message.content.startswith('$gamereset'):
        await game.delete_channels()
        print("Guild {} is resetting their game.".format(message.guild.name))
        town_square_channel = game.town_square
        del games[message.guild.id]
        await town_square_channel.send("Game reset!")



client.run(os.environ['id'])