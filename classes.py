import discord
import random
from static_variables import client, settings
from Topics import topics


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


# ----------------- Role classes -------------------------------
class player():
    def __init__(self, game: ww_game, name: str):
        self.game = game            # reference to the game object, to access game info from player
        self.name = name
        self.lover_names = []       # names of players this player is a lover with
        self.is_alive = True
        self.role = 'civilian'
        self.role_channel = None    # the player's ROLE-SPECIFIC text channel
        self.wolf = False
        self.mutilated = False

        # statuses which reset every night
        self.house_prot = False
        self.at_home = [name]        # list of players who are at this player's house
        self.role_performed = False


    def reset_night_statuses(self):
        self.house_prot = False
        self.at_home = [self.name]
        self.role_performed = False

    async def die(self):
        self.is_alive = False
        self.game.dead.add(self.name)
        self.game.alive.remove(self.name)

        if self.wolf:
            self.game.wolves.remove(self.name)
            
        # if there are any lovers, kill them too
        for name in self.lover_names:
            lover = self.game.player_names_objs[name]
            lover.is_alive = False
            self.game.dead.add(lover.name)
            self.game.alive.remove(lover.name)
            await self.game.town_square.send("{} tragically chooses to end their life after they find out that {} has died".format(lover.name, self.name))
        
    async def mutilate(self):
        # maybe have it mute the player in the voice (and text?) channel(s)?
        self.mutilated = True


class kidnapper(player):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'kidnapper'
        self.prev_target = ''

    async def kidnap(self, msg: discord.Message):
        """Given a $kidnap command message, kidnap the player given by the name in the message by changing the at_home fields of both kidnapper and kidnappee."""
        if self.role_performed:
            await self.role_channel.send("You've already kidnapped someone tonight.")
        else:
            name = msg.content.split(' ')[1]
            if name == self.prev_target:
                await self.role_channel.send("You can't choose the same target twice in a row. Please choose someone else.")
            else:
                kidnappee = self.game.player_names_objs[name]
                self.prev_target = name
                await self.role_channel.send("You have set the kidnap target to be {}".format(name))
                if kidnappee.name in kidnappee.at_home:
                    self.at_home.append(kidnappee.name)
                    kidnappee.at_home.remove(kidnappee.name)
                    await self.game.gm_channel.send("*** Kidnapper: {} has succesfully kidnapped {}.".format(self.name, name))
                else:
                    await self.game.gm_channel.send("*** Kidnapper: {} failed to kidnap {} because they were not at home.".format(self.name, name))


class cupid(player):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'cupid'
        self.prev_target = ''
        self.charges = 1

    async def sleep_at(self, msg: discord.Message):
        """Given a $sleepat command message, sleep at the house of the player given by the name in the message by changing the at_home fields of both cupid and the host."""
        if self.role_performed:
            await self.role_channel.send("You've already found a place to sleep tonight.")
        else:
            name = msg.content.split(' ')[1]
            if name == self.prev_target:
                await self.role_channel.send("You can't choose the same target twice in a row. Please choose someone else.")
            else:
                host = self.game.player_names_objs[name]
                self.prev_target = name
                await self.role_channel.send("You have set your host target to be {}".format(name))
                if self.name in self.at_home:               # if cupid was not kidnapped before trying to sleep somewhere
                    self.at_home.remove(self.name)
                    host.at_home.append(self.name)
                    await self.game.gm_channel.send("** Cupid: {} is sleeping at {}'s.".format(self.name, name))
                else:
                    await self.game.gm_channel.send("*** Cupid: {} failed to sleep at {} because cupid was not at home.".format(self.name, name))
    
    async def make_lovers(self, msg: discord.Message):
        """Given a $lovers command message, make the players given by the names in the message lovers and create a secret channel for them."""
        if settings['lovers_on_night_1'] and self.game.night_count == 1:
            if self.charges:
                name1, name2 = msg.content.split(' ')[1:]
                lover1 = self.game.player_names_objs[name1]
                lover2 = self.game.player_names_objs[name2]
                lover1.lover_names.append(name2)
                lover2.lover_names.append(name1)
                self.charges -= 1
                overwrites = {
                    self.game.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    self.game.gm: discord.PermissionOverwrite(read_messages=True),
                    client.user: discord.PermissionOverwrite(read_messages=True),
                    self.game.guild.get_member(self.game.ids[name1]): discord.PermissionOverwrite(read_messages=True),
                    self.game.guild.get_member(self.game.ids[name2]): discord.PermissionOverwrite(read_messages=True)
                }
                self.game.lovers_channel = await self.game.guild.create_text_channel(name='lovers', overwrites=overwrites, topic=topics['lovers'])
                await self.role_channel.send("Lovers have been assigned and added to a lover channel.")
                await self.game.lovers_channel.send("Welcome! You've been made lovers by our dear cupid. Feel free to get acquainted in this channel.")
                await self.game.gm_channel.send("*** Cupid: {} has chosen {} and {} to be the lovers".format(self.name, name1, name2))
            else:
                await self.role_channel.send("You've already chosen the lovers")
        else:
            await self.role_channel.send("You can only choose lovers on the first night")


class elder(player):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'elder'
        self.elder_prot = True


class fool(player):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'fool'
        self.fool_prot = True


class werewolf(player):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'werewolf'
        self.wolf = True
        game.wolves.add(name)
        self.kill_vote = ''             # name of player for whom this wolf voted in the night


class picky_werewolf(werewolf):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'picky_werewolf'
        self.charges = 1

    async def pick_wolf(self, msg: discord.Message):
        """Given a $pick command message, make the player given by the name in the message a picked werewolf."""
        name = msg.content.split(' ')[1]
        if self.charges:
            target = self.game.player_names_objs[name]
            target.wolf = True
            self.game.wolves.add(name)
            target.kill_vote = ''
            await self.game.wolf_channel.set_permissions(self.game.guild.get_member(self.game.ids[name]), read_messages=True)
            await self.game.wolf_channel.send("{} has been picked and added to the groupchat".format(name))
            self.charges -= 1
            await self.game.gm_channel.send("*** Picky werewolf: {} has picked {} and they have been added to the wolves channel.".format(self.name, name))
        else:
            self.role_channel.send("You've already picked a wolf")


class protector(player):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'protector'
        self.prev_target = ''

    async def protect(self, msg: discord.Message):
        """Given a $protect command message, protect the house of the player given by the name in the message by changing the house_prot field."""
        if self.role_performed:
            await self.role_channel.send("You've already protected someone tonight.")
        else:
            name = msg.content.split(' ')[1]
            if name == self.prev_target:
                await self.role_channel.send("You can't choose the same target twice in a row. Please choose someone else.")
            else:
                target = self.game.player_names_objs[name]
                self.prev_target = name
                target.house_prot = True
                await self.role_channel.send("You have protected {}'s house.".format(name))
                await self.game.gm_channel.send("*** Protector: {} has protected {}'s house.".format(self.name, name))


class witch(player):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'witch'
        self.potions = {'death': 1, 'life': 1, 'mute': 1}
    
    def witch_heal(self, recently_deceased, name):
        """Given a dead player's name, revive that player using a life potion if they are in the list of people who died this night."""
        if name in recently_deceased:
            if self.potions['life']:
                target = self.game.player_names_objs[name]
                target.is_alive = True
                self.potions['life'] -= 1
            else:
                # return message saying there's no more healing potions
                pass
        else:
            # return message saying name was invalid
            pass
    
    def witch_kill(self, name):
        """Given a player name, kill that player by using a death potion."""
        # function to check whether submitted name is valid, only then proceed
        if self.potions['death']:
            target = self.game.player_names_objs[name]
            target.is_alive = False
            self.potions['death'] -= 1
        else:
            # return message saying there's no more killing potions
            pass

    def witch_mutilate(self, name):
        """Given a player name, mutilate that player by using a mutilation potion."""
        # function to check whether submitted name is valid, only then proceed
        if self.potions['mute']:
            target = self.game.player_names_objs[name]
            #target.mutilate()
            self.potions['mute'] -= 1
        else:
            # return message saying there's no more mutilation potions
            pass


role_switch_dict = {    # works like a factory for making the player objects in ww_game.distribute_roles()
    'civilian':         lambda game, name: player(game, name),
    'kidnapper':        lambda game, name: kidnapper(game, name),
    'cupid':            lambda game, name: cupid(game, name),
    'werewolf':         lambda game, name: werewolf(game, name),
    'picky_werewolf':   lambda game, name: picky_werewolf(game, name),
    'protector':        lambda game, name: protector(game, name),
    'witch':            lambda game, name: witch(game, name),
    'elder':            lambda game, name: elder(game, name),
    'fool':             lambda game, name: fool(game, name)
}