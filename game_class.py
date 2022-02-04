import discord
import random
from main import client
from Topics import topics
from role_classes import role_switch_dict


class ww_game():
    def __init__(self, guild: discord.Guild, gm: discord.Member):
        """A game is initialised using the guild object where the game was started and the member object of whoever started the game, who becomes the gamemaster."""
        self.guild = guild                                                          # guild (server) object this game is running in
        self.gm = gm                                                                # gamemaster member object
        self.gamestate = 0
        self.night_count = 0
        self.lobby = []                                                             # players that have typed $join
        self.roles = []                                                             # roles included in this game (can have duplicates)
        self.player_names_objs = {}                                                 # dict with < player display_name : player object >
        self.player_roles_objs = {}                                                 # dict with < role (string) : [player objects] >
        self.ids = {}                                                               # dict with < player display_name : playerid >
        self.alive = set()                                                          # set of display_names of alive players
        self.dead = set()                                                           # set of display_names of dead players
        self.dead_this_night = set()                                                # set of display_names of players who are set to die at the end of this night
        self.mute_this_night = set()                                                # set of display_names of players who are set to be muted at the end of this night
        self.wolves = set()                                                         # set of ALIVE player names in the wolf team
        self.town_square = discord.utils.get(guild.channels, name='town_square')    # the town_square text channel
        self.wolf_channel = None                                                    # the wolf text channel
        self.lovers_channel = None                                                  # the lovers text channel
        self.gm_channel = None                                                      # text channel for gm for info about what's happening in the game


    async def join(self, msg: discord.Message):
        """Called when a player types $join, takes the command message as input.
           Lets the player join the lobby for the game if it is in setup phase, and their display_name doesn't contain any spaces."""
        if self.gamestate != 0:
            await msg.channel.send("No game setup taking place")
        else:
            name = msg.author.display_name
            if ' ' in name:
                await msg.channel.send("Please make sure there are no spaces in your nickname")
            else:
                self.lobby.append(name)
                self.ids[name] = msg.author.id
                print("{} has joined the game, playercount now at {}".format(name, len(self.lobby)))
                await self.town_square.send("{} has joined the game, playercount now at {}".format(name, len(self.lobby)))

    
    async def leave(self, msg: discord.Message):
        """Called when a player types $leave, takes the command message as input. Lets the player leave the lobby for the game if it is in setup phase."""
        if self.gamestate != 0:
            await msg.channel.send("Please wait for someone to begin a game setup")
        else:
            name = msg.author.display_name
            if name in self.lobby:
                self.lobby.remove(name)
                del self.ids[name]
                print("{} has left the game, playercount now at {}".format(name, len(self.lobby)))
                await self.town_square.send("{} has left the game, playercount now at {}".format(name, len(self.lobby)))
            else:
                await msg.channel.send("No need, you weren't even in the game yet!")


    async def distribute_roles(self):
        """Distributes the roles randomly among the players in the game, and creates the appropriate secret channel for each role, as well as the channel for the werewolves."""
        lobby_copy = self.lobby.copy()
        roles_copy = self.roles.copy()
        random.shuffle(lobby_copy)
        random.shuffle(roles_copy)

        while len(lobby_copy) > 0:
            participant = lobby_copy.pop()
            role = roles_copy.pop()
            new_player = role_switch_dict[role](self, participant)
            self.alive.add(participant)
            self.player_names_objs[participant] = new_player
            if role in self.player_roles_objs.keys():
                self.player_roles_objs[role].append(new_player)
            else:
                self.player_roles_objs[role] = [new_player]
            await self.gm_channel.send("{} is the {}".format(participant, role))

            # role-specific channels
            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                self.guild.get_member(self.ids[participant]): discord.PermissionOverwrite(read_messages=True),
                self.gm: discord.PermissionOverwrite(read_messages=True),
                client.user: discord.PermissionOverwrite(read_messages=True)
            }
            new_player.role_channel = await self.guild.create_text_channel(name=role, overwrites=overwrites, topic=topics[role])

        # werewolves channel
        overwritesww = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.gm: discord.PermissionOverwrite(read_messages=True),
            client.user: discord.PermissionOverwrite(read_messages=True)
        }
        for wolf in self.wolves:
            overwritesww[self.guild.get_member(self.ids[wolf])] = discord.PermissionOverwrite(read_messages=True)

        self.wolf_channel = await self.guild.create_text_channel(name='werewolves', overwrites=overwritesww, topic=topics['werewolves'])
        print("All channels besides lovers channel created")


    async def delete_channels(self):
        """Deletes all channels used by the game except for the town_square. Called on $gamereset."""
        print("Removing channels...")
        for name in self.lobby:
            player = self.player_names_objs[name]
            await player.role_channel.delete()
        await self.wolf_channel.delete()
        await self.lovers_channel.delete()
        await self.gm_channel.delete()
        print("All channels deleted")


    async def valid_target(self, msg: discord.Message, req_role: str, req_gs: int, req_target_count: int =1):
        """Performs all checks to make sure a command message containing a (player) target is valid. This includes:
           - Is the message author alive
           - Was the right channel used for the command and does the author have the required role for the command. The <req_role> input is a role string which determines this.
             'wolf' and 'civilian' are used to denote messages that should originate from the wolf channel and town_square, respectively.
           - Was the message sent during the right gamestate (given by req_gs)
           - Are the targets alive players
           - Was the right amount of targets provided
           If not, the appropriate message is sent to the channel the message originated from.
           Message should take the form of '$command target1 target2 ...'
           Returns boolean."""
        if msg.author.display_name not in self.alive:
            await msg.channel.send("You're not even in the game and alive bruh")
            return False
    
        if req_role == 'wolf':
            if msg.channel.id != self.wolf_channel.id:
                await msg.channel.send("Yeah that's not the right channel for this mate")
                return False

        elif req_role == 'civilian':
            if msg.channel.id != self.town_square.id:
                await msg.channel.send("Yeah that's not the right channel for this mate")
                return False

        else:
            player = self.player_names_objs[msg.author.display_name]
            if player.role != req_role:
                # Still send the 'wrong channel' msg to avoid giving away info to other players. The msg will have come from a wrong channel anyhow
                await msg.channel.send("Yeah that's not the right channel for this mate")
                return False
            else:
                if msg.channel.id != player.role_channel.id:
                    await msg.channel.send("Yeah that's not the right channel for this mate")
                    return False

        if self.gamestate != req_gs:
            await msg.channel.send("We're not currently in the right phase of the game for you to do that.")
            return False

        # if none of the checks above returned False, we're good to go
        targets = msg.content.split(' ')[1:]
        for target in targets:
            if target not in self.alive:
                await msg.channel.send('The following target was not valid: {}. Please try again.'.format(target))
                return False

        if len(targets) != req_target_count:
            await msg.channel.send('This action requires {} target(s), but you provided {} target(s). Please try again.'.format(req_target_count, len(targets)))
            return False
        else: return True


    async def wolf_kill(self):
        """Called when all wolves have voted or the gamemaster ends the night early. Calculates who the wolf target is and attempts to kill them.
           Assumes valid_target has already been called for each individual wolf's vote."""
        wolf_votes = {name : 0 for name in self.alive}
        for wolf_name in self.wolves:
            wolf = self.player_names_objs[wolf_name]
            if wolf.kill_vote != '':
                wolf_votes[wolf.kill_vote] += 1

        # stalemate:
        if list(wolf_votes.values()).count(max(wolf_votes.values())) > 1:
            await self.gm_channel.send("*** Wolves: Stalemate in lunch voting, no wolf target")
            await self.wolf_channel.send("Stalemate in voting, no lunch tonight rippp")
        
        else:
            target = self.player_names_objs[max(wolf_votes, key=wolf_votes.get)]
            await self.gm_channel.send("*** Wolves: {} is the lunch target".format(target.name))
            await self.wolf_channel.send("{} is the lunch target".format(target.name))

            if target.house_prot:
                await self.gm_channel.send("*** Wolves: the target's house is protected".format(target.name))
            else:
                for name in target.at_home:
                    player = self.player_names_objs[name]
                    if player.role == 'elder' and player.elder_prot:
                        player.elder_prot = False
                        await self.gm_channel.send("*** Wolves: {} survived the attack because they are the elder".format(player.name))
                    else:
                        self.dead_this_night.add(player.name)
                        await self.gm_channel.send("*** Wolves: {} was killed by the wolves".format(player.name))


    async def handle_end_night(self):
        """Handles all the actions that need to occur at the end of the night:
           - Killing whoever is in dead_this_night
           - Mutilating whoever is in mute_this_night
           - Sending night results to town_square channel
           - Resetting game- and player-level temporary night variables
           - Incrementing gamestate"""
        await self.town_square.send("Dawn is on the horizon...")

        if len(self.dead_this_night) > 0 or len(self.mute_this_night) > 0:
            result_str = 'Come morning, you find that:\n'
            for name in self.dead_this_night:
                player = self.player_names_objs[name]
                if player.role not in {'werewolf, picky_werewolf'} and player.wolf == True:
                    result_str += "Last night {} died, they were the {}, and they were the picked werewolf.\n".format(name, player.role)
                else:
                    result_str += "Last night {} died, they were the {}.\n".format(name, player.role)
            for name in self.mute_this_night:
                result_str += "Last night {} was mutilated.\n".format(name)
        else:
            result_str = "Everyone wakes up to a calm morning."
        await self.town_square.send(result_str)
        
        for name in self.dead_this_night:
            player = self.player_names_objs[name]
            await player.die()
        
        for name in self.mute_this_night:
            player = self.player_names_objs[name]
            await player.mutilate()

        for name in self.alive:
            player = self.player_names_objs[name]
            player.reset_night_statuses()

        self.gamestate += 1
        self.dead_this_night = set()
        self.mute_this_night = set()


# ------------ Testing ------------
game1 = ww_game(0, 'me')
game1.lobby = ['Bram', 'Jasper']
game1.roles = ['werewolf', 'werewolf']
game1.distribute_roles()
playerB = game1.player_names_objs['Bram']
playerJ = game1.player_names_objs['Jasper']
print(game1.player_roles_objs)