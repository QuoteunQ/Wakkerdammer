import discord
import random
from static_variables import client, min_players, possible_roles, settings, gskey
from Topics import topics


class ww_game():
    def __init__(self, guild: discord.Guild, gm: discord.Member):
        """A game is initialised using the guild object where the game was started and the member object of whoever started the game, who becomes the gamemaster."""
        self.guild = guild                                                                              # guild (server) object this game is running in
        self.gm = gm                                                                                    # gamemaster member object
        self.gamestate = 0
        self.night_count = 0
        self.lobby = []                                                                                 # players that have typed $join
        self.roles = []                                                                                 # roles (str) included in this game (can have duplicates)
        self.player_names_objs: 'dict[str, player]' = {}                                                # dict with < player display_name : player object >
        self.player_roles_objs: 'dict[str, player]' = {}                                                # dict with < role (string) : [player objects] >
        self.ids: 'dict[str, int]' = {}                                                                 # dict with < player display_name : playerid >
        self.alive = set()                                                                              # set of display_names of alive players
        self.dead = set()                                                                               # set of display_names of dead players
        self.dead_this_night = set()                                                                    # set of display_names of players who are set to die at the end of this night
        self.mute_this_night = set()                                                                    # set of display_names of players who are set to be muted at the end of this night
        self.wolves = set()                                                                             # set of ALIVE player names in the wolf team
        self.town_square: discord.TextChannel = discord.utils.get(guild.channels, name='town_square')
        self.wolf_channel: discord.TextChannel = None
        self.lovers_channel: discord.TextChannel = None
        self.gm_channel: discord.TextChannel = None                                                     # text channel for gm for info about what's happening in the game


    # ---------------------------- Gamestate-specific functions --------------------------------------------------

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
                print(f"{name} has joined the game, playercount now at {len(self.lobby)}")
                await self.town_square.send(f"{name} has joined the game, playercount now at {len(self.lobby)}")

    
    async def leave(self, msg: discord.Message):
        """Called when a player types $leave, takes the command message as input. Lets the player leave the lobby for the game if it is in setup phase."""
        if self.gamestate != 0:
            await msg.channel.send("Please wait for someone to begin a game setup")
        else:
            name = msg.author.display_name
            if name in self.lobby:
                self.lobby.remove(name)
                del self.ids[name]
                print(f"{name} has left the game, playercount now at {len(self.lobby)}")
                await self.town_square.send(f"{name} has left the game, playercount now at {len(self.lobby)}")
            else:
                await msg.channel.send("No need, you weren't even in the game yet!")


    async def start(self, msg: discord.Message):
        """Starts the game with the roles included in the $gamestart command message. This changes the gamestate from setup (0) to end of day (1), ready to begin the first night."""
        if self.gamestate != 0:
            await msg.channel.send("No game setup taking place")
        else:
            if len(self.lobby) < min_players:
                await msg.channel.send("Insufficient players")
            else:
                roles = msg.content.split(' ')[1:]
                for role in roles:
                    if role not in possible_roles:
                        await msg.channel.send(f"Invalid role: '{role}', please try again")
                        return				# end function
                if len(roles) != len(self.lobby):
                    await msg.channel.send(f"Mismatch between amounts of roles ({len(roles)}) & players ({self.lobby})")
                else:
                    print("Starting game...\n"
                        f"Included roles are: {roles}\n"
                        f"Players playing: {self.lobby}, totalling {len(self.lobby)}")
                    self.roles = roles
                    await self.distribute_roles()
                    await self.gm_channel.send(
                        f"Game started! Players playing: {self.lobby}, totalling {len(self.lobby)}.\n"
                        f"The wolves are {self.wolves}.\n"
                        "Ready for $beginnight !")
                    await self.town_square.send(
                        "Game started! Please check if you have been added to a text channel, and that you are clear on your role and how to play it.\n"
                        "The gamemaster can start the night using $beginnight")
                    self.gamestate += 1


    async def begin_night(self):
        """Sets the gamestate to night: pre-wolves (2) if the gamestate is day end (1) and sends the appropriate messages to town_square
        and the channels of the roles which act in the night before the wolves."""
        if self.gamestate != 1:
            await self.gm_channel.send("The game is not ready to begin the night yet.")
        else:
            self.gamestate += 1
            self.night_count += 1
            await self.town_square.send(
                f"Beginning night {self.night_count}...\n"
                f"The gamestate is now {gskey[self.gamestate]}\n"
                "Please carry out your roles by interacting in your private channel(s) and good luck! :^)")
            await self.gm_channel.send(
                "Please check if all roles which should act before the wolves have performed their respective actions.\n"
                f"To move the game to night: wolves, use $startwolfvoting")

            for role in {'kidnapper', 'cupid', 'protector', 'seer'}:
                for player in self.player_roles_objs[role]:
                    await player.role_channel.send("It's now your turn to perform your action!")


    async def end_wolf_vote(self):
        """Called when all wolves have voted or the gamemaster ends the night early. Calculates who the wolf target is and attempts to kill them.
        Assumes valid_target has already been called for each individual wolf's vote. Also advances the gamestate to night: witch (4)."""
        if self.gamestate != 3:
            self.gm_channel.send(f"The game is unable to calculate the wolf kill during this state of the game ({gskey[self.gamestate]}).")
        else:
            wolf_votes = {name : 0 for name in self.alive}
            for wolf_name in self.wolves:
                wolf = self.player_names_objs[wolf_name]
                if wolf.kill_vote != '':                # if they have actually voted
                    wolf_votes[wolf.kill_vote] += 1
                    wolf.kill_vote = ''

            # stalemate:
            if list(wolf_votes.values()).count(max(wolf_votes.values())) > 1:
                await self.gm_channel.send("*** Wolves: Stalemate in lunch voting, no wolf target")
                await self.wolf_channel.send("Stalemate in voting, no lunch tonight rippp")
            
            else:
                target = self.player_names_objs[max(wolf_votes, key=wolf_votes.get)]
                await self.gm_channel.send(f"*** Wolves: {target.name} is the lunch target")
                await self.wolf_channel.send(f"{target.name} is the lunch target")

                if target.house_prot:
                    await self.gm_channel.send(f"*** Wolves: {target.name}'s house is protected")
                else:
                    for name in target.at_home:
                        player = self.player_names_objs[name]
                        if player.role == 'elder' and player.elder_prot:
                            player.elder_prot = False
                            await self.gm_channel.send(f"*** Wolves: {player.name} survived the attack because they are the elder")
                        else:
                            self.dead_this_night.add(player.name)
                            await self.gm_channel.send(f"*** Wolves: {player.name} was killed by the wolves")

            # move to witch if there is one
            self.gamestate += 1
            if 'witch' in self.roles:
                await self.town_square.send("The witch now has the oppurtunity to use her brews...")
                await self.gm_channel.send("When you feel the witch has had enough time to use their potions, use $endnight to advance the game.")
                for witch in self.player_roles_objs['witch']:
                    await witch.role_channel.send("You can now use your potions!\n"
                        f"{self.dead_this_night} have died, {self.mute_this_night} have been mutilated.\n"
                        f"You still have the following potions: {witch.potions}. Would you like to use any?")
            else:
                await self.gm_channel.send("Since there is no witch this game, the game will automatically move to the day. You don't need to use $endnight.")
                await self.handle_end_night()


    async def handle_end_night(self):
        """Handles all the actions that need to occur at the end of the night:
           - Killing whoever is in dead_this_night
           - Mutilating whoever is in mute_this_night
           - Sending night results to town_square channel
           - Resetting game- and player-level temporary night variables
           - Incrementing gamestate; by 1 if the hunter was killed tonight, otherwise by 2"""
        if self.gamestate != 4:
            await self.gm_channel.send("The game is not ready to end the night yet")
        else:
            await self.town_square.send("Dawn is on the horizon...")
            hunter_hour = False
            if len(self.dead_this_night) > 0 or len(self.mute_this_night) > 0:
                result_str = "Come morning, you find that, last night:\n"
                for name in self.mute_this_night:
                    player = self.player_names_objs[name]
                    await player.mutilate()
                    result_str += f"{name} was mutilated.\n"
                for name in self.dead_this_night:
                    player = self.player_names_objs[name]
                    # if player.role == 'hunter' , set them to active and hunter_hour = True
                    await player.die()  # maybe wait with properly killing them till after the hunter can do his thing - also make hunter_hour class variable?
                    if player.role not in {'werewolf, picky werewolf'} and player.wolf == True:
                        result_str += f"{name} died, they were the {player.role}, and they were the picked werewolf.\n"
                    else:
                        result_str += f"{name} died, they were the {player.role}.\n"
            else:
                result_str = "Everyone wakes up to a calm morning."
            await self.town_square.send(result_str)

            for name in self.alive:
                player = self.player_names_objs[name]
                player.reset_night_statuses()
            
            self.gamestate += 1
            self.dead_this_night = set()
            self.mute_this_night = set()

            if hunter_hour:
                await self.town_square.send("Since the hunter died tonight, they now get the chance to take someone with them to the grave.")
                await self.gm_channel.send("When the hunter has selected their target, or if you want to force the game to advance, use $startvoting")
            else:
                await self.gm_channel.send("You can now use $startvoting to start the day vote.")


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
            await self.gm_channel.send(f"{participant} is the {role}")

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
            if name in self.player_names_objs.keys():
                player = self.player_names_objs[name]
                await player.role_channel.delete()
        if self.wolf_channel:
            await self.wolf_channel.delete()
        if self.lovers_channel:
            await self.lovers_channel.delete()
        if self.gm_channel:
            await self.gm_channel.delete()
        print("All channels deleted")


    async def valid_target(self, msg: discord.Message, req_role: str, req_gs: int, req_target_count: int =1) -> bool:
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
                await msg.channel.send(f"The following target was not valid: {target}. Please try again.")
                return False

        if len(targets) != req_target_count:
            await msg.channel.send(f"This action requires {req_target_count} target(s), but you provided {len(targets)} target(s). Please try again.")
            return False
        
        if len(targets) != len(set(targets)):   # the same name occurs more than once
            await msg.channel.send("You provided the same name twice.")
            return False

        else: return True


# ----------------- Role classes -------------------------------
class player():
    def __init__(self, game: ww_game, name: str):
        self.game = game                                 # reference to the game object, to access game info from player
        self.name = name
        self.lover_names = []                            # names of players this player is a lover with
        self.is_alive = True
        self.role = 'civilian'
        self.role_channel: discord.TextChannel = None    # the player's ROLE-SPECIFIC text channel
        self.wolf = False
        self.mutilated = False
        self.lynch_vote = ''

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
            await self.game.town_square.send(f"{lover.name} tragically chooses to end their life after they find out that {self.name} has died")
        
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
                await self.role_channel.send(f"You have set the kidnap target to be {name}")
                if kidnappee.name in kidnappee.at_home:
                    self.at_home.append(kidnappee.name)
                    kidnappee.at_home.remove(kidnappee.name)
                    await self.game.gm_channel.send(f"*** Kidnapper: {self.name} has succesfully kidnapped {name}.")
                else:
                    await self.game.gm_channel.send(f"*** Kidnapper: {self.name} failed to kidnap {name} because they were not at home.")


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
                await self.role_channel.send(f"You have set your host target to be {name}")
                if self.name in self.at_home:               # if cupid was not kidnapped before trying to sleep somewhere
                    self.at_home.remove(self.name)
                    host.at_home.append(self.name)
                    await self.game.gm_channel.send(f"*** Cupid: {self.name} is sleeping at {name}'s.")
                else:
                    await self.game.gm_channel.send(f"*** Cupid: {self.name} failed to sleep at {name} because cupid was not at home.")
    
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
                await self.game.gm_channel.send(f"*** Cupid: {self.name} has chosen {name1} and {name1} to be the lovers")
            else:
                await self.role_channel.send("You've already chosen all the lovers")
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

    async def vote_lunch(self, msg: discord.Message):
        if self.kill_vote != '':
            await self.game.wolf_channel.send("You've already voted to kill someone tonight!")
        else:
            target = msg.content.split(' ')[1]
            self.kill_vote = target
            vote_count = len([wolf.kill_vote for wolf in self.game.wolves if wolf.kill_vote != ''])
            wolves_vote_msg = f"*** Wolves: {self.name} has voted to lunch {target}. {vote_count}/{len(self.game.wolves)} wolves have voted."
            await self.game.wolf_channel.send(wolves_vote_msg)
            await self.game.gm_channel.send(wolves_vote_msg)
        
        if vote_count == len(self.game.wolves):
            await self.game.wolf_channel.send("All wolves have voted, calculating target now...")
            await self.game.end_wolf_vote()



class picky_werewolf(werewolf):
    def __init__(self, game: ww_game, name: str):
        super().__init__(game, name)
        self.role = 'picky werewolf'
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
            await self.game.wolf_channel.send(f"{name} has been picked and added to the groupchat")
            self.charges -= 1
            await self.game.gm_channel.send(f"*** Picky werewolf: {self.name} has picked {name} and they have been added to the wolves channel.")
        else:
            self.role_channel.send("You've already picked enough wolves")


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
                await self.role_channel.send(f"You have protected {name}'s house.")
                await self.game.gm_channel.send(f"*** Protector: {self.name} has protected {name}'s house.")


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
    'picky werewolf':   lambda game, name: picky_werewolf(game, name),
    'protector':        lambda game, name: protector(game, name),
    'witch':            lambda game, name: witch(game, name),
    'elder':            lambda game, name: elder(game, name),
    'fool':             lambda game, name: fool(game, name)
}