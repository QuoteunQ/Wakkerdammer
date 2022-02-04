import discord
from game_class import ww_game
from main import client, lovers_on_night_1
from Topics import topics


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
        if lovers_on_night_1 and self.game.night_count == 1:
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