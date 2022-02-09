import os
import discord
import requests
import json
from textwrap import dedent
from classes import ww_game
from static_variables import client, min_players, possible_roles, gskey


games: 'dict[int, ww_game]' = {}                  # dict with < guild_id : game object >



def get_quote():
    """ Fetches inspiring quote from zenquotes.io """
    response = requests.get("https://zenquotes.io/api/random")
    json_data = json.loads(response.text)
    quote = json_data[0]['q'] + " -" + json_data[0]['a']
    return quote


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return 

# ----------------------- Commands which don't require a game taking place in the guild --------------------------

    if message.content.startswith('$hello'):
        await message.channel.send('Hello')
        return

    if message.content.startswith('$inspire'):
        quote = get_quote()
        await message.channel.send(quote)
        return

    if message.content.startswith('$help'):
        await message.channel.send("Commands: $inspire $gamesetup $join $leave $gamestart $playerlist $clearplayerlist $allroles $roles $setup? $gm $beginnight $action $endnight $beginvoting")
        return
    
    if message.content.startswith('$allroles'):
        await message.channel.send(f"Current roles in the game include: {possible_roles}")
        return

    if message.content.startswith('$gamesetup'):
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
            await new_game.gm_channel.send(
                "In this channel you as gamemaster will see updates about what's happening in the game.\n"
                "You can also use it to start the game without revealing the roles in the game to the players."
            )
            print(f"The gamemaster is {new_game.gm.display_name}")
            await town_square_channel.send(
                "Starting game setup...\n"
                f"The gamemaster is {new_game.gm.display_name}.\n"
                "To join the game, please type '$join'\n"
                f"Minimum {min_players} players required to start the game\n"
                "To start the game, the GM can type '$gamestart <role> <role>' etc...\n"
                f"Current roles in the game include: {possible_roles}"
            )
            games[message.guild.id] = new_game
        return


# --------------------------- Commands which do require a game taking place in the guild ---------------------------------------
    if message.guild.id not in games.keys():
        await message.channel.send("There's no game running in this server yet!")
        return

    game = games[message.guild.id]


# ------------------------------------ Game join & leave ------------------------------------------

    if message.content.startswith('$join'):
        await game.join(message)
        return

    if message.content.startswith('$leave'):
        await game.leave(message)
        return


# ---------------------------- Night Commands Players -----------------------------------

    if message.content.startswith('$kidnap'):
        if await game.valid_target(message, req_role='kidnapper', req_gs=1):
            await game.player_names_objs[message.author.display_name].kidnap(message)
        return
    
    if message.content.startswith('$protect'):
        if await game.valid_target(message, req_role='protector', req_gs=1):
            await game.player_names_objs[message.author.display_name].protect(message)
        return

    if message.content.startswith('$lovers'):
        if await game.valid_target(message, req_role='cupid', req_gs=1, req_target_count=2):
            await game.player_names_objs[message.author.display_name].make_lovers(message)
        return

    if message.content.startswith('$sleepat'):
        if await game.valid_target(message, req_role='cupid', req_gs=1):
            await game.player_names_objs[message.author.display_name].sleep_at(message)
        return

    if message.content.startswith('$lunch'):
        if await game.valid_target(message, req_role='wolf', req_gs=2):
            await game.player_names_objs[message.author.display_name].vote_lunch(message)
        return

    if message.content.startswith('$pick'):
        if await game.valid_target(message, req_role='picky werewolf', req_gs=1):
            await game.player_names_objs[message.author.display_name].pick_wolf(message)
        return


# ------------------------------ Utility commands -------------------------------------

    if message.content.startswith('$playerlist'):
        await message.channel.send(f"Players: {game.lobby}")
        return

    if message.content.startswith('$poopbreak'):
        await message.channel.send("Aren't you a funnyman https://www.youtube.com/watch?v=DN0gAQQ7FAQ")
        return

    if message.content.startswith('$roles'):
        await message.channel.send(f"Roles included in this game are: {game.roles}")
        return

    if message.content.startswith('$gamestate'):
        await message.channel.send(f"State of game: {gskey[game.gamestate]}")
        return

    if message.content.startswith('$gm'):
        await message.channel.send(f"Current GM is: {game.gm.display_name}")
        return

    if message.content.startswith('$alive'):
        await message.channel.send(f"Alive players are: {game.alive}")
        return


# ----------------------- Commands which can only be used by the gamemaster ------------------------------------

    if message.author != game.gm:
        await message.channel.send("Relax bro you're not the GM")
        return

    if message.content.startswith('$clearplayerlist'):
        if game.gamestate == 0 and not len(game.alive):
            game.lobby = []
            game.ids = {}
            await message.channel.send("Player list is now empty")
        else:
            await message.channel.send("You can't do that outside of game setup")
        return

    if message.content.startswith('$gamestart'):
        await game.start(message)
        return

    if message.content.startswith('$gamereset'):
        print(f"Guild {message.guild.id} is resetting their game.")
        await game.delete_channels()
        town_square_channel = game.town_square
        del games[message.guild.id]
        await town_square_channel.send("Game reset!")
        return

    if message.content.startswith('$endwolfvoting'):
        await game.wolf_kill()
        return



client.run(os.environ['id'])