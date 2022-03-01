import discord
import random
from static_variables import client, min_players, possible_roles, settings, gskey, topics


class WwGame():
    def __init__(self, guild: discord.Guild, gm: discord.Member):
        """A game is initialised using the guild object where the game was started and the member object of whoever started the game, who becomes the gamemaster."""
        self.guild = guild                                                                              # guild (server) object this game is running in
        self.gm = gm                                                                                    # gamemaster member object
        self.gamestate = 0
        self.night_count = 0
        self.lobby = []                                                                                 # players that have typed $join
        self.roles = []                                                                                 # roles (str) included in this game (can have duplicates)
        self.player_names_objs: 'dict[str, Player]' = {}                                                # dict with < player display_name : player object >
        self.player_roles_objs: 'dict[str, list(Player)]' = {}                                          # dict with < role (string) : [player objects] >
        self.ids: 'dict[str, int]' = {}                                                                 # dict with < player display_name : playerid >
        self.alive = set()                                                                              # set of display_names of alive players
        self.dead = set()                                                                               # set of display_names of dead players
        self.dead_this_night = set()                                                                    # set of display_names of players who are set to die at the end of this night
        self.mute_this_night = set()                                                                    # set of display_names of players who are set to be muted at the end of this night
        self.wolves = set()                                                                             # set of ALIVE player names in the wolf team
        self.hunter_source_gs = 0                                                                       # the gamestate the hunter(s) died in, which determines which gs to continue to once the hunters are done
        self.town_square: discord.TextChannel = discord.utils.get(guild.channels, name='town_square')
        self.wolf_channel: discord.TextChannel = None
        self.lovers_channel: discord.TextChannel = None
        self.gm_channel: discord.TextChannel = None                                                     # text channel for gm for info about what's happening in the game


    # ---------------------------- Gamestate-specific functions --------------------------------------------------

    async def join(self, msg: discord.Message):
        """Called when a player types $join, takes the command message as input. Lets the player join the lobby for the game if:
        - the game is in setup phase
        - their display_name doesn't contain any spaces
        - their name isn't in the lobby yet"""
        if self.gamestate != 0:
            await msg.channel.send("No game setup taking place")
        else:
            name = msg.author.display_name
            if ' ' in name:
                await msg.channel.send("Please make sure there are no spaces in your nickname")
            else:
                if name in self.lobby:
                    await msg.channel.send("You're already in the lobby bruh")
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


        # -------------------------------- Gamestate flow control functions ---------------------------------------------------

    async def start(self, msg: discord.Message):
        """Starts the game with the roles included in the $gamestart command message. This changes the gamestate from setup (0) to end of day (1),
        ready to begin the first night."""
        if self.gamestate != 0:
            await msg.channel.send("The game is unable to start outside of the setup phase.")
        else:
            if len(self.lobby) < min_players:
                await msg.channel.send(f"The minimum player count is {min_players}, but the lobby is currently only at {len(self.lobby)} players.")
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
                        "Game started! Please check if you have been added to a personal text channel, which will tell you your role. "
                        "You'll find instructions on how to play your role in the topic description of the channel.\n"
                        "The gamemaster can start the night using $beginnight")
                    self.gamestate += 1


    async def begin_night(self):
        """Sets the gamestate to night: pre-wolves (2) if the gamestate is day end (1) and sends the appropriate messages to town_square
        and the channels of the roles which act in the night before the wolves."""
        if self.gamestate != 1:
            await self.gm_channel.send(f"The game is not ready to begin the night during this state of the game ({gskey[self.gamestate]}).")
        else:
            self.gamestate += 1
            self.night_count += 1
            await self.town_square.send(
                f"Beginning night {self.night_count}...\n"
                f"The gamestate is now {gskey[self.gamestate]}\n"
                "Please carry out your roles by interacting in your private channel(s) and good luck! :^)")
            await self.gm_channel.send(
                "Please check if all roles which should act before the wolves have performed their respective actions.\n"
                f"To move the game to night: wolves, use $startwolves")

            for role in {'kidnapper', 'cupid', 'protector', 'seer', 'picky werewolf'}:
                if role in self.roles:
                    for player in self.player_roles_objs[role]:
                        await player.role_channel.send("It's now your turn to perform your personal role-specific action(s)!")


    async def start_wolf_vote(self):
        """Advances the game to the night: wolves gamestate (3). Called when the gamemaster uses $startwolves."""
        if self.gamestate != 2:
            await self.gm_channel.send(f"The game isn't ready to start the wolf voting during this state of the game ({gskey[self.gamestate]}).")
        else:
            self.gamestate += 1
            await self.gm_channel.send("Moving on to the wolves..."
                "(If you feel they are taking too much time voting you can use $endwolves to force the game to advance)")
            await self.wolf_channel.send("It's your turn to vote for tonight's kill now!")
            await self.town_square.send("It's now the wolves' turn to select a target...")


    async def end_wolf_vote(self):
        """Called when all wolves have voted or the gamemaster uses $endwolves. Calculates who the wolf target is and attempts to kill them.
        If wolf_mute_night_1 is set to False and it's the first night, sets the target to be mutilated instead of killed.
        Assumes valid_target has already been called for each individual wolf's vote. Also advances the gamestate to night: witch (4) if there is a witch in the game,
        otherwise ends the night by calling handle_end_night() automatically."""
        if self.gamestate != 3:
            self.gm_channel.send(f"The game is unable to calculate the wolf kill during this state of the game ({gskey[self.gamestate]}).")
        else:
            wolf_votes = {name : 0 for name in self.alive}
            for wolf_name in self.wolves:
                wolf = self.player_names_objs[wolf_name]
                if wolf.kill_vote != '':                # if they have actually voted
                    wolf_votes[wolf.kill_vote] += 1
                    wolf.kill_vote = ''

            if max(wolf_votes.values()) == 0:
                await self.gm_channel.send("*** Wolves: no votes were cast, no wolf target")
                await self.wolf_channel.send("No votes were cast, which means your fangs remain bloodless tonight.")
            else:
                # stalemate:
                if list(wolf_votes.values()).count(max(wolf_votes.values())) > 1:
                    await self.gm_channel.send("*** Wolves: Stalemate in lunch voting, no wolf target")
                    await self.wolf_channel.send("Stalemate in voting, which means your fangs remain bloodless tonight.")
                
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
                                if settings['wolf_mute_night_1'] and self.night_count == 1:
                                    self.mute_this_night.add(player.name)
                                    await self.gm_channel.send(f"*** Wolves: {player.name} was mutilated by the wolves")
                                else:
                                    self.dead_this_night.add(player.name)
                                    await self.gm_channel.send(f"*** Wolves: {player.name} was killed by the wolves")

            # move to witch if there is one
            self.gamestate += 1
            if 'witch' in self.roles:
                await self.town_square.send("The witch now has the oppurtunity to use her brews...")
                await self.gm_channel.send("Moving on to the witch...\n"
                    "When you feel the witch has had enough time to use their potions, use $endnight to advance the game.")
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
           - Changing gamestate to day: discussion (6) if no hunter died"""
        if self.gamestate != 4:
            await self.gm_channel.send(f"The game is not ready to end the night during this state of the game ({gskey[self.gamestate]})")
        else:
            await self.town_square.send("Dawn is on the horizon...")
            if len(self.dead_this_night) > 0 or len(self.mute_this_night) > 0:
                await self.town_square.send("Come morning, you find that, last night:")
                for name in self.mute_this_night:
                    player = self.player_names_objs[name]
                    await player.mutilate()
                for name in self.dead_this_night:
                    player = self.player_names_objs[name]
                    await player.die()
            else:
                await self.town_square.send("Everyone wakes up to a calm morning.")

            if self.gamestate != 5:     # if no hunter died
                await self.start_day_discussion()

            for name in self.alive:
                player = self.player_names_objs[name]
                player.reset_night_statuses()

            self.dead_this_night = set()
            self.mute_this_night = set()


    async def end_hunter_hour(self):
        """Called when all active hunters have shot someone, or when the gamemaster uses $endhunter.
        Moves the game on from day: hunter (5) to the next appropriate gamestate, depending on what gamestate the hunter(s) became active in.
        Cuts off any hunters which haven't selected their target."""
        if self.gamestate != 5:
            await self.gm_channel.send("You can only do that when there is an active hunter.")
        else:
            for hunter in self.player_roles_objs['hunter']:
                if hunter.loaded:
                    hunter.loaded = False
                    await hunter.role_channel.send("The gamemaster has decided to cut off your target selection, your gun will remain unused.")

            if self.hunter_source_gs == 4:          # from end of night, go to day: discussion
                self.hunter_source_gs = 0
                await self.start_day_discussion()
            elif self.hunter_source_gs == 7:        # from day voting, go to end of day
                self.hunter_source_gs = 0
                await self.end_day()


    async def start_day_discussion(self):
        if self.gamestate != 4 or self.gamestate != 5:
            await self.gm_channel.send(f"The game is unable to move to day: discussion during this state of the game ({gskey[self.gamestate]}).")
        else:
            self.gamestate = 6
            await self.town_square.send("Time to discuss who you want to lynch tonight!")
            await self.gm_channel.send("When you feel the day discussion has lasted long enough, you can use $startvoting to start the day vote.")


    async def end_day(self):
        if self.gamestate != 5 or self.gamestate != 7:
            await self.gm_channel.send(f"The game is unable to move to day: discussion during this state of the game ({gskey[self.gamestate]}).")
        else:
            self.gamestate = 1
            await self.gm_channel.send("Ready for $beginnight !")
            await self.town_square.send("The gamemaster can now begin the night.")


    async def distribute_roles(self):
        """Distributes the roles randomly among the players in the game, and creates the appropriate secret channel for each role, as well as the channel for the werewolves."""
        lobby_copy = self.lobby.copy()
        roles_copy = self.roles.copy()
        random.shuffle(lobby_copy)
        random.shuffle(roles_copy)

        overwrites_ww = {       # overwrites for the werewolves channel   
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.gm: discord.PermissionOverwrite(read_messages=True),
            client.user: discord.PermissionOverwrite(read_messages=True)
        }

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

            # Create role-specific channels here instead of on player creation because __init__ cannot be async
            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                self.guild.get_member(self.ids[participant]): discord.PermissionOverwrite(read_messages=True),
                self.gm: discord.PermissionOverwrite(read_messages=True),
                client.user: discord.PermissionOverwrite(read_messages=True)
            }
            new_player.role_channel = await self.guild.create_text_channel(name=role, overwrites=overwrites, topic=topics[role])

            if role in {'werewolf', 'picky_werewolf'}:
                overwrites_ww[self.guild.get_member(self.ids[participant])] = discord.PermissionOverwrite(read_messages=True)

        self.wolf_channel = await self.guild.create_text_channel(name='werewolves', overwrites=overwrites_ww, topic=topics['werewolves'])
        print("All channels besides lovers channel created")


    async def delete_channels(self):
        """Deletes all channels used by the game except for the town_square. Called on $gamereset."""
        print("Removing channels...")
        for player in self.player_names_objs.values():
            await player.role_channel.delete()
        if self.wolf_channel:
            await self.wolf_channel.delete()
        if self.lovers_channel:
            await self.lovers_channel.delete()
        if self.gm_channel:
            await self.gm_channel.delete()
        print("All channels deleted")


    async def valid_target(self, msg: discord.Message, req_role: str, req_gs: int, req_target_count: int =1) -> bool:
        """Performs all general checks to make sure a command message containing a (player) target is valid. This includes:
           - Is the message author alive (not applicable if hunter)
           - Was the right channel used for the command and does the author have the required role for the command. The <req_role> input is a role string which determines this.
             'wolf' and 'civilian' are used to denote messages that should originate from the wolf channel and town_square, respectively.
           - Was the message sent during the right gamestate (given by req_gs)
           - Are the targets alive players
           - Was the right amount of targets provided
           If not, the appropriate message is sent to the channel the message originated from.
           Message should take the form of '$command target1 target2 ...'
           Returns boolean."""
        if req_role != 'hunter':
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
                # Still send the 'wrong channel' msg to avoid giving away role info to other players. The msg will have come from a wrong channel anyhow
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
class Player():
    def __init__(self, game: WwGame, name: str):
        self.game = game                                    # reference to the game object, to access game info from player
        self.name = name
        self.lover_names = []                               # names of players this player is a lover with
        self.is_alive = True
        self.role = 'civilian'
        self.role_channel: discord.TextChannel = None       # the player's ROLE-SPECIFIC text channel
        self.wolf = False
        self.mutilated = False
        self.lynch_vote = ''

        # statuses which reset every night
        self.house_prot = False
        self.at_home = [name]                               # list of players who are at this player's house
        self.role_performed = False


    def reset_night_statuses(self):
        self.house_prot = False
        self.at_home = [self.name]
        self.role_performed = False

    async def become_wolf(self):
        self.wolf = True
        self.game.wolves.add(self.name)
        self.kill_vote = ''                                 # name of player for whom this wolf voted in the night
        await self.game.wolf_channel.set_permissions(self.game.guild.get_member(self.game.ids[self.name]), read_messages=True)

    # Define wolf-specific methods in Player to allow a picked person to retain their original role's functionality as well as act as a wolf.
    async def vote_lunch(self, msg: discord.Message):
        """Given a $lunch command message, sets this wolf's vote for the night kill to the name in the message. If all wolves have voted,
        automatically calls game.end_wolf_vote() to calculate the final target for the wolves."""
        if self.kill_vote != '':
            await self.game.wolf_channel.send("You've already voted to kill someone tonight!")
        else:
            target = msg.content.split(' ')[1]
            self.kill_vote = target
            vote_count = len([self.game.player_names_objs[wolf].kill_vote for wolf in self.game.wolves if self.game.player_names_objs[wolf].kill_vote != ''])
            wolves_vote_msg = f"*** Wolves: {self.name} has voted to lunch {target}. {vote_count}/{len(self.game.wolves)} wolves have voted."
            await self.game.wolf_channel.send(wolves_vote_msg)
            await self.game.gm_channel.send(wolves_vote_msg)
            if vote_count == len(self.game.wolves):
                await self.game.wolf_channel.send("All wolves have voted, calculating target now...")
                await self.game.end_wolf_vote()

    async def die(self):
        self.is_alive = False
        self.game.dead.add(self.name)
        self.game.alive.remove(self.name)

        if self.wolf:
            self.game.wolves.remove(self.name)

        if self.role not in {'werewolf', 'picky_werewolf'} and self.wolf:
            await self.game.town_square.send(f"{self.name} died, they were the {self.role}, and they were the picked werewolf.")
        else:
            await self.game.town_square.send(f"{self.name} died, they were the {self.role}.")
            
        # if there are any lovers, kill them too
        for name in self.lover_names.copy():
            lover = self.game.player_names_objs[name]
            if lover.is_alive:
                await lover.die()
                await self.game.town_square.send(f"{lover.name} tragically chooses to end their life after they find out that {self.name} has died.")
        
    async def mutilate(self):
        self.mutilated = True
        await self.role_channel.send("You have been mutilated! Please refrain from speaking in voice, as well as conveying words through text channels.")
        await self.game.town_square.send(f"{self.name} was mutilated.")


class Hunter(Player):
    def __init__(self, game: WwGame, name: str):
        super().__init__(game, name)
        self.role = 'hunter'
        self.loaded = False                             # whether the hunter is currently capable of firing

    async def die(self):
        self.is_alive = False
        self.game.dead.add(self.name)
        self.game.alive.remove(self.name)

        if self.wolf:
            self.game.wolves.remove(self.name)
            await self.game.town_square.send(f"{self.name} died, they were the {self.role}, and they were the picked werewolf.")
        else:
            await self.game.town_square.send(f"{self.name} died, they were the {self.role}.")
        await self.game.town_square.send(f"{self.name} will now get to decide who they take with them to the grave.")
            
        # if there are any lovers, kill them too
        for name in self.lover_names:
            lover = self.game.player_names_objs[name]
            if lover.is_alive:
                await lover.die()
                await self.game.town_square.send(f"{lover.name} tragically chooses to end their life after they find out that {self.name} has died.")

        if self.game.gamestate != 5:
            self.game.hunter_source_gs = self.game.gamestate
            self.game.gamestate = 5
            await self.game.gm_channel.send("Please wait for the hunter(s) to select their target. If you want to force the game to advance, use $endhunter")
        self.loaded = True

    async def hunt(self, msg: discord.Message):
        """Given a $shoot command message, kill the player given by the name in the message."""
        if not self.is_alive:
            if self.loaded:
                name = msg.content.split(' ')[1]
                target = self.game.player_names_objs[name]
                await self.game.town_square.send(f"{self.name} has decided to shoot {name}")
                await target.die()
                self.loaded = False
                if len([1 for hunter in self.game.player_roles_objs['hunter'] if hunter.loaded]) == 0:
                    await self.game.end_hunter_hour()
            else:
                await self.role_channel.send("You've already fired your gun, quit trying to shoot everyone!")
        else:
            await self.role_channel.send("You'll first need to die before you can use your gun.")


class Kidnapper(Player):
    def __init__(self, game: WwGame, name: str):
        super().__init__(game, name)
        self.role = 'kidnapper'
        self.prev_target = ''

    async def kidnap(self, msg: discord.Message):
        """Given a $kidnap command message, kidnap the player given by the name in the message by changing the at_home fields of both kidnapper and kidnappee."""
        if self.role_performed:
            await self.role_channel.send("You've already kidnapped someone tonight.")
        else:
            name = msg.content.split(' ')[1]
            if name == self.name:
                await self.role_channel.send("You can't choose yourself!")
            elif name == self.prev_target:
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


class Cupid(Player):
    def __init__(self, game: WwGame, name: str):
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
            if name == self.name:
                await self.role_channel.send("You can't choose yourself!")
            elif name == self.prev_target:
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
        if settings['lovers_on_night_1'] and self.game.night_count != 1:
            await self.role_channel.send("You can only choose lovers on the first night")
        else:
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



class Elder(Player):
    def __init__(self, game: WwGame, name: str):
        super().__init__(game, name)
        self.role = 'elder'
        self.elder_prot = True


class Fool(Player):
    def __init__(self, game: WwGame, name: str):
        super().__init__(game, name)
        self.role = 'fool'
        self.fool_prot = True
  

class Werewolf(Player):
    def __init__(self, game: WwGame, name: str):
        super().__init__(game, name)
        self.role = 'werewolf'
        self.wolf = True
        game.wolves.add(name)
        self.kill_vote = ''             # name of player for whom this wolf voted in the night


class PickyWerewolf(Werewolf):
    def __init__(self, game: WwGame, name: str):
        super().__init__(game, name)
        self.role = 'picky_werewolf'
        self.charges = 1

    async def pick_wolf(self, msg: discord.Message):
        """Given a $pick command message, make the player given by the name in the message a picked werewolf."""
        name = msg.content.split(' ')[1]
        if self.charges:
            target = self.game.player_names_objs[name]
            if not target.wolf:
                target.become_wolf()
                await self.game.wolf_channel.send(f"{name} has been picked and added to the groupchat")
                self.charges -= 1
                await self.game.gm_channel.send(f"*** Picky werewolf: {self.name} has picked {name} and they have been added to the wolves channel.")
            else:
                await self.role_channel.send("That player is already a wolf, please choose someone else.")
        else:
            await self.role_channel.send("You've already picked enough wolves")


class Protector(Player):
    def __init__(self, game: WwGame, name: str):
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


class Witch(Player):
    def __init__(self, game: WwGame, name: str):
        super().__init__(game, name)
        self.role = 'witch'
        self.potions = {'kill': 1, 'heal': 1, 'mute': 1}

    async def use_potion(self, msg: discord.Message):
        """Given a message containing 'potion_name target_name', uses the potion on the target."""
        potion, name = msg.content.split(' ')

        if potion == 'heal':
            if self.potions['heal']:
                if name in self.game.dead_this_night:
                    self.game.dead_this_night.remove(name)
                    self.potions['heal'] -= 1
                    await self.role_channel.send(f"You have healed {name} of their wounds so they may live.")
                    await self.game.gm_channel.send(f"*** Witch: {self.name} has saved {name} from death.")
                elif name in self.game.mute_this_night:
                    self.game.mute_this_night.remove(name)
                    self.potions['heal'] -= 1
                    await self.role_channel.send(f"You have saved {name}'s tongue.")
                    await self.game.gm_channel.send(f"*** Witch: {self.name} has prevented {name}'s mutilation.")
                else:
                    await self.role_channel.send("That person doesn't need any healing tonight (anymore). You can try again if you wish.")
            else:
                await self.role_channel.send("You don't have any healing potions left!")

        elif potion == 'kill':
            if self.potions['kill']:
                if name not in self.game.dead_this_night:
                    self.game.dead_this_night.add(name)
                    self.potions['kill'] -= 1
                    await self.role_channel.send(f"You have poisoned {name}, they won't wake up in the morning.")
                    await self.game.gm_channel.send(f"*** Witch: {self.name} has killed {name}.")
                else:
                    await self.role_channel.send("That person has already died tonight, so no use poisoning them too! You can try to use your killing potion again if you wish.")
            else:
                await self.role_channel.send("You don't have any killing potions left!")

        elif potion == 'mute':
            if self.potions['mute']:
                if self.game.player_names_objs[name].mutilated:
                    await self.role_channel.send("That person has already been mutilated, so no use doing it twice! Please pick someone else.")
                elif name in self.game.mute_this_night:
                    await self.role_channel.send("That person has already been mutilated tonight, so no use doing it twice! You can try to use your mutilating potion again if you wish.")
                else:
                    self.game.mute_this_night.add(name)
                    self.potions['mute'] -= 1
                    await self.role_channel.send(f"The acidic brew eats away {name}'s tongue, they will never speak again.")
                    await self.game.gm_channel.send(f"*** Witch: {self.name} has mutilated {name}.")
            else:
                await self.role_channel.send("You don't have any mutilating potions left!")

        else:
            await self.role_channel.send(f"Did not recognise the following potion: {potion}")


role_switch_dict = {    # works like a factory for making the player objects in WwGame.distribute_roles()
    'civilian':         lambda game, name: Player(game, name),
    'hunter':           lambda game, name: Hunter(game, name),
    'kidnapper':        lambda game, name: Kidnapper(game, name),
    'cupid':            lambda game, name: Cupid(game, name),
    'werewolf':         lambda game, name: Werewolf(game, name),
    'picky_werewolf':   lambda game, name: PickyWerewolf(game, name),
    'protector':        lambda game, name: Protector(game, name),
    'witch':            lambda game, name: Witch(game, name),
    'elder':            lambda game, name: Elder(game, name),
    'fool':             lambda game, name: Fool(game, name)
}