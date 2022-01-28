#import kanye
import os
import discord
import requests
import json
import random 
from replit import db

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

min_players = 1
lobby = [] # players that are have typed $join
ids = {} # dict with < playernickname : playerid > 
possible_roles = ['werewolf', 'picky_werewolf', 'cupid', 'kidnapper', 'protector', 'seer', 'witch', 'hunter', 'elder', 'fool', 'civillian']
gamestate = 0 # <-- key for gamestate = 
gskey =  {0:'setup', 1:'night', 2:'witch + hunter', 3:'day', 4:'voting', 5: 'prenight'}
#setup = False
roles = [] # roles included in this game 
wolves = [] # list of player nicknames in the wolf team
witchpots = {'death': 1, 'life':1, 'mute':1} 
kill_first = False # If False, wolves mutilate on first night
wwpicks = 1 # Picky werewolf picks
alive = []  # list of player nicknames still alive (string)
players = [] # list of player classes that are in the game
#night = False # whether there is a night going on 
nightcount = 0
couple = [] # nicknames of the lovers
kidnap = {'target': None, 'prev': None, 'player': None} # Data for kidnapping decision
protect = {'target': None, 'prev': None, 'player': None} # protector
stayat = {'target': None, 'prev': None, 'player': None} # slut
lookat = {'target': None, 'player': None} # seer
hunt = {'target': None, 'player': None} # hunter
overwritesww = {} # contains permissions for werewolf chat 
overwritesdead = {} # contains permissions for the death realm 
lunchvotes = [] # votes for werewolf kill
wolftarget = None # who the werewolves target
mutilated = [] # not in use??
newdead = [] # newly killed    people this night
newmute = [] # newly mutilated people this night
# witchhour = False # if the witch can be active now
dead = [] # list of dead players
lynchvotes = {} # votes for lynching
guild = None
town_square_channel = None

class player():
    def __init__(self, name, role):
      self.name = name
      self.role = role
      self.lover = False
      self.alive = True

      #Role specific
      self.protected = False #  
      self.kidnapee = False  #
      self.wolftarget = False
      self.elderprot = False
      self.foolprot = False
      self.wolf = False
      self.hosting = False
      self.mutilated = False

      if role == 'werewolf' or role == 'picky_werewolf':
        self.wolf = True
        wolves.append(name)

      if role == 'kidnapper':
        kidnap['player'] = name
      if role == 'protector':
        protect['player'] = name
      if role == 'cupid':
        stayat['player'] = name
      if role == 'seer':
        lookat['player'] = name
      if role == 'hunter':
        hunt['player'] == name

      if role == 'elder':
        self.elderprot = True
      if role == 'fool':
        self.foolprot = True
    
    def mutilate(self):
      # maybe have it mute the player in the voice (and text?) channel(s)?
      pass

    def reset_mods(self):
      self.wolftarget = False

async def kill(nick, guild):
  """ Called when a player is killed, checks lovers and hunter """
  global hunt
  global couple
  global newdead
  global gamestate
  global roles
  channel = discord.utils.get(guild.channels, name='town_square')
  if channel:
    for i in players:
      if i.name == nick:
        i.alive = False
        alive.remove(i.name)
        if i.name in wolves and i.role != 'werewolf' and i.role != 'picky_werewolf':
          # Need to remove player from wolves list?
          print("{} dies, and was a picked wolf and the {}".format(i.name, i.role))
          if gamestate == 4:
            await channel.send("{} dies, and was a picked wolf and a {}".format(i.name, i.role))
        else:
          print("{} dies, they were the {}".format(i.name, i.role))
          if gamestate == 4:
            await channel.send("{} dies, they were the {}".format(i.name, i.role))
        if gamestate != 4: # if not in voting
          newdead.append(i.name)
        if 'hunter' in roles:
          if i.role == 'hunter':
            hunterkill(guild) 
        if 'cupid' in roles:
          if i.nick in couple and len(couple) > 1:
            remain = couple.remove(i.nick)[0]
            if remain not in alive:
              print("Error: Couple did not die the first time")
            print("{} was one of the lovers. Their lover, {}, dies as a consequence".format(i.nick, remain))
            if gamestate == 4:
              await channel.send("{} tragically chooses to end their life after they find out that {} has died".format(remain, i))
            kill(remain, guild)
            couple = []     

async def hunterkill(guild):
  """" Called when the hunter is killed, kills the hunter target """
  global hunt
  global newdead
  global gamestate
  if hunt['target']:
    channel = discord.utils.get(guild.channels, name='town_square')
    if channel:
      for i in players:
          if i.name == hunt['target'] and hunt['target'] in alive:
            kill(i.name, guild)
            if gamestate != 4: # if not in voting
              newdead.append(i.name)
            print("{} was the hunter, {} was their target".format(hunt['player'], hunt['target']))
            await channel.send("{} was the hunter, {} was their target".format(hunt['player'], hunt['target']))
    else:
      print("Hunterkill: NO TOWN_SQUARE CHANNEL")
  

async def lynchresult(guild):
  """ Calculates who the lynchtarget is based on the current votes in the lynchvotes dict when all players finish voting or the gamemaster uses $endvoting. This function handles all the changes to global varibales required, including alive players and ...., and performs checks for fool, hunter and lovers """
  # global lynchtarget 
  global lynchvotes
  global couple
  print("Calculating Lynch result...")
  channel = discord.utils.get(guild.channels, name='town_square')
  if channel:
    await channel.send("Calculating Lynch result...")
    if list(lynchvotes.values()).count(None) == len(lynchvotes):
      print("No votes have been cast, no player is lynched")
      await channel.send("No votes have been cast, no player is lynched")
      return
    votecount = {player:0 for player in alive}
    for i in lynchvotes.values():
      votecount[i] += 1
    print("Count of lynch votes: {}".format(votecount))
    await channel.send("Lynch votes: {}".format(votecount))
    if list(votecount.values()).count(max(votecount.values())) > 1: #if stalemate
      print("*** Voting: Stalemate in lynch voting, no player dies")
      await channel.send("Stalemate in voting, nobody is lynched")
      return
    lynchtarget = max(votecount, key=votecount.get)
    print("*** Voting: {} is the lynch target".format(lynchtarget))
    for player in players:
      if player.name == lynchtarget:
        if player.role == 'fool' and player.foolprot:
          print("*** The lynchtarget is the fool, nobody dies")
          await channel.send("Nobody is lynched today")
          player.foolprot = False
        else:
          player.alive = False
          alive.remove(player.name)
          if player.name in wolves and player.role != 'werewolf' and player.role != 'picky_werewolf':
            # Need to remove player from wolves list?
            print("{} dies, and was a picked wolf".format(lynchtarget))
            await channel.send("The result is damning, and even before the final ballot is cast, {} realises their mistake and begins to run. But they are caught and dragged to the hanging tree. They are strung up and with little ceremony is executed on suspicion of lycanthropy. In his death throes they begin to change.  His limbs lengthen, his fingers become wicked claws, and his eyes become starry, far seeing and endless. In an instant it is over, and all that hangs before you is a dead wolf. But it is clear to all that the {} is no more.. ".format(lynchtarget, player.role))
          else:
            print("{} is lynched, they were the {}".format(lynchtarget, player.role))
            await channel.send("{} is forcefully escorted to the gallows. The village watches silently as {} hangs. The items on their person reveal them to be the {}".format(lynchtarget, lynchtarget, player.role))
          hunter = None # nickname of hunter player
          if 'cupid' in roles:
            if lynchtarget in couple:
              suicid = couple - [lynchtarget]
              suicid = suicid[0]
              print("{} was a lover, the other lover {} dies".format(lynchtarget, suicid))
              await channel.send("{} was a lover, the other lover {} dies".format(lynchtarget, suicid)) 
          if 'hunter' in roles:
            hunterkill(guild)                         
  else:
    print("Lynchresult: NO TOWN_SQUARE CHANNEL FOUND")

async def lunchresult(guild, wwchannel):
  """ Calculates who the lunchtarget is, is called when wolves finish voting or gamemaster uses $endnight early"""
  global wolftarget
  global lunchvotes
  
  votecount = {player:0 for player in alive}
  for i in lunchvotes:
      votecount[i] += 1
  print("Count of lunch votes: {}".format(votecount))
  await wwchannel.send("Lunch votes: {}".format(votecount))
  #values = votecount.values
  if list(votecount.values()).count(max(votecount.values())) > 1: #if stalemate
    print("*** Wolves: Stalemate in lunch voting, no wolf target")
    await wwchannel.send("Stalemate in voting, no lunch tonight rippp")
    return
  wolftarget = max(votecount, key=votecount.get)
  print("*** Wolves: {} is the lunch target".format(wolftarget))
  await wwchannel.send("{} is the lunch target".format(wolftarget))
  for player in players:
    if player.name == wolftarget:
      player.wolftarget = True

async def distribute_roles(lobby, roles, guild):
  """ Returns a list of player classes with input names and input roles divided randomly amongst them. Also makes text channels for each role, lovers and WWs"""
  global players 
  global ids
  global GM
  global wolves
  global alive

  players = []
  lobb = lobby.copy()
  roless = roles.copy()
  random.shuffle(lobb)
  random.shuffle(roless)
  while lobb:
    participant = lobb.pop()
    role = roless.pop() # local roles, not global
    new = player(participant, role)
    players.append(new)
    print("{} is the {}".format(participant, role))
    # Make secret channels for each role
    overwrites = {
      guild.default_role: discord.PermissionOverwrite(read_messages=False),
      guild.get_member(ids[participant]): discord.PermissionOverwrite(read_messages=True),
      guild.get_member(ids[GM]): discord.PermissionOverwrite(read_messages=True),
      client.user: discord.PermissionOverwrite(read_messages=True)
      }
    await guild.create_text_channel(name='{}'.format(role), overwrites=overwrites, topic=db['topics'][role])

  # Make werewolves channel
  overwritesww = {
    guild.default_role: discord.PermissionOverwrite(read_messages=False),
    guild.get_member(ids[GM]): discord.PermissionOverwrite(read_messages=True),
    client.user: discord.PermissionOverwrite(read_messages=True)
  }
  for wolf in wolves:
    overwritesww[guild.get_member(ids[wolf])] = discord.PermissionOverwrite(read_messages=True)
  await guild.create_text_channel(name='werewolves', overwrites=overwritesww, topic=db['topics']['werewolves'])
  print("All channels besides lover channel created")
  #print("players", players)
  #("db", db['playerss'])

  alive = lobb
  return players

def anydead(playerlist):
  global alive
  global mutilated
  global kill_first
  global nightcount
  global newdead
  global newmute
  """Takes a list of players and finds out which are dead and which mutilated, removes them from the alive list and adds to mutilated list, and returns a list of dead players and a list of newly mutilated players"""
  dead = []
  mute = [] 
  for i in playerlist:
    if i.alive == False and i.name in alive:
      print("*** {} has died".format(i.name))
      dead.append(i.name)
    if i.wolftarget:
      if i.elderprot == True:
        print("*** {} was saved because they are the elder")
        i.elderprot = False
      else:
        if nightcount == 1 and not kill_first:
          i.mutilated = True
          mute.append(i.name)
          print("*** {} was mutilated by the wolves".format(i.name))
        else:
          i.alive = False
          print("*** {} was killed by the wolves".format(i.name))
          dead.append(i.name)
  for i in dead:
    if not i in newdead:
      newdead.append(i)
    if i in alive:
      alive.remove(i)
  for i in mute:
    if not i in newmute:
      newmute.append(i)
  return dead, mute

async def remove_channels(guild):
  global roles
  print("Removing Channels....")
  #roles.append('werewolves')
  for role in roles:
    if role == 'cupid':
      await discord.utils.get(guild.channels, name='lovers').delete()
      print('lover channel deleted')
    channel = discord.utils.get(guild.channels, name=role)
    await channel.delete() # delete channel for each role
    print("{} channel deleted".format(role))
  await discord.utils.get(guild.channels, name='werewolves').delete()
  print("werewolves channel deleted")
  if 'cupid' in roles:
    await discord.utils.get(guild.channels, name='lovers').delete()
    print("lovers channel deleted")


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
async def on_message(message):
  global players 
  #global setup
  global ids
  global lobby
  global roles
  global GM
  global wolves
  global nightcount
  global kidnap
  global prevprotect
  global stayat
  global lookat
  global hunt
  global wolftarget
  global mutilated
  global newmute
  global newdead
  global alive
  global couple
  #global witchhour
  global dead
  global lunchvotes
  global gamestate
  global guild
  global town_square_channel

  if message.author == client.user:
    return 

  if message.content.startswith('$hello'):
    await message.channel.send('Hello')

  if message.content.startswith('$test'):
    guild = message.guild
    print(guild.id)
    town_square_channel = discord.utils.get(guild.channels, name='town_square')
    print(town_square_channel.id)

  if message.content.startswith('$inspire'):
    quote = get_quote()
    await message.channel.send(quote)
    #author = message.author.id
    #await message.channel.send(author)

  if message.content.startswith('$help'):
    await message.channel.send("Commands: $inspire $gamesetup $join $leave $gamestart $playerlist $clearplayerlist $allroles $roles $setup? $gm $beginnight $action $endnight $beginvoting")

# ----------- Night Commands Players ---------------

  if message.content.startswith('$kidnap'):
    if message.channel.name == 'kidnapper'and gamestate == 1and message.author.nick in alive:
      target = message.content.split(' ')[1]
      if not target in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      if target == kidnap['prev']:
        await message.channel.send("You cannot kidnap the same person twice in a row")
        return
      kidnap['target'] = target
      print("Kidnapper: {} has kidnapped {}".format(message.author.nick, target))
      await message.channel.send("You have set the kidnap target to be {}".format(target))
      
  if message.content.startswith('$protect'):
    if message.channel.name == 'protector'and gamestate == 1and message.author.nick in alive:
      target = message.content.split(' ')[1]
      if not target in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      if target == protect['prev']:
        await message.channel.send("You cannot protect the same person twice in a row")
        return
      protect['target'] = target
      print("Protector: {} has protected {}".format(message.author.nick, target))
      await message.channel.send("You have set the protector target to be {}".format(target))

  if message.content.startswith('$lovers'):
    if message.channel.name == 'cupid'and gamestate == 1and message.author.nick in alive:
      if nightcount != 1: # A problem if using graverobber / roleswitch
        await message.channel.send("You can only choose lovers on the first night")
        return
      loves = message.content.split(' ')[1:]
      if len(loves) != 2:
        await message.channel.send("Unexpected number of lovers")
        return
      firstlove = loves[0]
      secndlove = loves[1]
      if not firstlove in alive :
        await message.channel.send("The first lover is not in the game")
        return
      if not secndlove in alive:
        await message.channel.send("The second lover is not in the game")
        return
      print("*** Cupid: {} has chosen {} and {} to be the lovers".format(message.author.nick, firstlove, secndlove))
      guild = message.guild
      overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.get_member(ids[GM]): discord.PermissionOverwrite(read_messages=False),
        client.user: discord.PermissionOverwrite(read_messages=True),
        guild.get_member(ids[firstlove]): discord.PermissionOverwrite(read_messages=True),
        guild.get_member(ids[secndlove]): discord.PermissionOverwrite(read_messages=True)
      }
      await guild.create_text_channel(name='lovers', overwrites=overwrites, topic=db['topics']['lovers'])
      await message.channel.send("Lovers have been assigned and added to a lover channel")
      print("Cupid: Lover channel created")
      
  if message.content.startswith('$sleepat'):
    if message.channel.name == 'cupid'and gamestate == 1and message.author.nick in alive:
      target = message.content.split(' ')[1]
      if not target in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      if target == stayat['prev']:
        await message.channel.send("You cannot sleep at the same person twice in a row")
        return
      stayat['target'] = target
      print("Cupid/Slut: {} is sleeping at {}'s'".format(message.author.nick, target))
      await message.channel.send("Your sleeping at target is {}".format(target))

  if message.content.startswith('$hunt'): #hunter need to be alive?
    if message.channel.name == 'hunter' and message.author.nick in alive: 
      target = message.content.split(' ')[1]
      if not target in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      hunt['target'] == target
      await message.channel.send("{} is now your hunter target".format(target))
      print("Hunter: {} has chosen {} as their hunter target".format(message.author.nick, target))

  if message.content.startswith('$lookat'):
    if message.channel.name == 'seer'and gamestate == 1and message.author.nick in alive:
      target = message.content.split(' ')[1]
      if target not in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      lookat['target'] = target 
      await message.channel.send("You have chosen {} as your seer target".format(target))
      print("Seer: {} has chosen to look at {}'s role'".format(message.author.nick, target))    

  if message.content.startswith('$pick'):
    if message.channel.name == 'picky_werewolf'and gamestate == 1and message.author.nick in alive:
      target = message.content.split(' ')[1]
      if target not in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      guild = message.guild
      for player in players:
        if player.name == target:
          player.wolf = True
          wolves.append(target)
          channel = discord.utils.get(guild.channels, name='werewolves')
          await channel.set_permissions(guild.get_member(ids[target]), read_messages=True)
          await message.channel.send("{} has been picked and added to the groupchat".format(target))
          print('*** Picky Werewolf: {} has picked {} and the werewolf groupchat has been updated'.format(message.author.nick, target))

  if message.content.startswith('$lunch'):
    #print("lunch command")
    if message.channel.name == 'werewolves'and gamestate == 1 and message.author.nick in alive:
      target = message.content.split(' ')[1]
      if target not in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      wwcount = len(wolves)
      lunchvotes.append(target)
      print("Wolves: {} has voted to lunch {}. {}/{} wolves have voted".format(message.author.nick, target, len(lunchvotes), wwcount))
      await message.channel.send("{} has voted to lunch {}. {}/{} wolves have voted".format(message.author.nick, target, len(lunchvotes), wwcount))

      if wwcount == len(lunchvotes): #if all wolves voted
        await lunchresult(message.guild, message.channel)

  if message.content.startswith('$potions?'):
    if message.channel.name == 'witch':
      await message.channel.send('The potions you have left are: {} killing potion, {} healing potion, and {} mutilation potion'.format(witchpots['death'], witchpots['life'], witchpots['mute']))

  if message.content.startswith('$potion'):
    if message.channel.name == 'witch' and message.author.nick in alive:
      if gamestate != 2:
        await message.channel.send("The game is not ready for your potions")
        return
      content = message.content.split(' ')
      use = content[1]
      target = content[2]
      if target not in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      if use == 'death':
        if witchpots['death'] == 0:
          await message.channel.send("No killing pots left unluck")
        else:
          witchpots['death'] -= 1
          for i in players:
            if i.name == target:
              if i.alive == False:
                await message.channel.send("That player is dead")
                return
              i.alive = False
              await message.channel.send("Aait, killing {}".format(i.name))
              print("*** The witch has chosen to kill {}".format(i.name))
              newdead.append(i.name)
              witchpots['death'] -= 1
      elif use == 'life':
        if witchpots['life'] == 0:
          await message.channel.send("No healing pots left rest in rip")
        else:
          for i in players:
            if i.name == target:
              if i.alive == True:
                await message.channel.send("What u worried about, they aint dead (and you can't heal mutilation)")
              elif i.name in dead:
                await message.channel.send("That person is dead but has not died this round, you can't save them")
              else:
                i.alive = True
                if i.name in newdead:
                  newdead.remove(i.name)
                i.mutilated = False
                if i.name in newmute:
                  newmute.remove(i.name)
                await message.channel.send("Oke, {} is getting saved".format(i.name))
                print("*** The witch has chosen to heal {}".format(i.name))
                witchpots['life'] -= 1
                # also remove the dead from nightresults?
      elif use == 'mute':
        if witchpots['mute'] == 0:
          await message.channel.send("No mutilating pots left")
        else:
          for i in players:
            if i.name == target:
              if i.mutilated == True:
                await message.channel.send("They allready mutilated bro")
              else:
                newmute.append(i.name)
                i.mutilated = True
                await message.channel.send("Coolio, mutilating {}".format(i.name))
                print("*** The witch has chosen to mutilate".format(i.name))
                witchpots['mute'] -= 1
      else:
        await message.channel.send("Did not recognize name of potion")

# ----------- Night Commands GM ---------------------

  if message.content.startswith('$beginnight'):
    if message.author.nick != GM:
      await message.channel.send("Relax bro you're not the GM")
      return
    if gamestate != 0 or gamestate != 4 or len(players) == 0: # if the game is not in setup or is not in voting mode
      await message.channel.send("The game is not ready to begin the night yet")
      return
    gamestate = 1 # set gamestate to night
    nightcount += 1
    for i in wolves:  # Remove dead wolves from wolf list
      if not i in alive:
        wolves.remove(i)
    await message.channel.send("Beginning night {}...\nPlease carry out your roles by interacting in your private channel(s) and good luck! :^)".format(nightcount))  
    print("Night started!! \n------ To end the night, you can type $endnight ------")   

  if message.content.startswith('$endnight'):
    if message.author.nick != GM:
      await message.channel.send("Relax bro you're not the GM")
      return
    if gamestate != 1:
      await message.channel.send("The game is not ready to end the night yet")
      return
    print("+++ Ending night, calculating kidnapper/cupid/protector spaghetti")
    await message.channel.send("The night is drawing to a close...\nMost night actions are now completed")
    if len(lunchvotes) < len(wolves): #cut off the wolf votes if they are not finished
      guild = message.guild
      channel = discord.utils.get(guild.channels, name='werewolves')
      await lunchresult(message.guild, channel) # find the lunch result if there is one
    gamestate += 1 # set gamestate to witching hour

    # Handle results by role, this is the spaghetti 
    if 'kidnapper' in roles:
      if wolftarget == kidnap['player']:
        for i in players:
          if i.name == kidnap['target']:
            i.wolftarget = True
            print("*** {} became a wolftarget because they were kidnapped by {}".format(i.name, kidnap['player']))

    if 'cupid' in roles:
      if stayat['target'] == kidnap['target']:
        stayat['target'] = kidnap['player']
        print("*** {} was staying at the kidnap target {} and so is at the kidnapper {} tonight".format(stayat['player'], kidnap['target'], kidnap['player']))
      if stayat['target'] == wolftarget:
        for i in players:
          if i.name == stayat['player']:
            i.wolftarget = True
            print('*** {} has become a wolftarget for staying at {}"s, who is a wolftarget'.format(stayat['player'], wolftarget))   

    if 'protector' in roles: # protector protects 
      for i in players:
        if i.wolftarget and protect['target'] == i.name:
          i.wolftarget = False
          print("*** {} was saved because they were protected".format(i.name))

    if 'seer' in roles:
      channel = discord.utils.get(message.guild.channels, name='seer')
      seerresult = 'fail to find player / player role'
      for i in players:
        if i.name == lookat['target']:
          seerresult = i.role
      await channel.send("Seer action results: {} is the {}".format(lookat['target'], seerresult))
      print('*** The seer has recieved the lookat results and now knows that {} is the {}'.format(lookat['target'], seerresult))

    dead, mute = anydead(players) # calculate results 
    for i in newmute:
      if i not in mutilated:
        mutilated.append(i)
    print("Dead: {}. Mutilated: {} Giving witch and hunter the info (if applicable)".format(newdead, newmute))

    if 'witch' in roles:
      channel = discord.utils.get(message.guild.channels, name='witch')
      await channel.send("{} has been killed tonight and {} has been mutilated. Please type which potions you would like to use tonight by typing $potion <type> <player nickname>. Potion types are 'death', 'life', and 'mute' You can type '$potions?' to see which potions you have left. If you decide to not use any potions, please let the gamemaster know".format(newdead, newmute))
 
    if 'hunter' in roles:
      channel = discord.utils.get(message.guild.channels, name='hunter')
      await channel.send("{} has been killed tonight and {} has been mutilated. Does this information change your hunt target? You can change your hunt target by typing $hunt <player nickname>".format(newdead, newmute))
    print("------ Night successfully ended: ready for $nightresults -------\nWitch/Hunter etc. may need some time")

  if message.content.startswith('$nightresults'):
    if message.author.nick != GM:
      await message.channel.send("Relax bro you're not the GM")
      return
    if gamestate == 1:
      await message.channel.send("The game is not ready for the night results yet")
      return
    dead, mute = anydead(players) # check if any died/mutilated from the witch, if so it so <-- this necessary???? handle every
    if 'hunter' in roles:
      if hunt['player'] in dead and hunt['target']:
        hunterkill(message.guild)
    nrdead = len(newdead)
    nrmute = len(newmute)
    lunchvotes = []
    if nrdead > 0 or nrmute > 0:
      await message.channel.send("Tonight's has {} victims: {} has died, and {} has been mutilated".format(nrdead + nrmute, newdead, newmute))
    else:
      await message.channel.send("Everyone wakes up to a calm morning")
    # handle lovers dying, does not work if multiple cupids: 
    if 'cupid' in roles and couple != []:
      for i in newdead:
        if i in couple and len(couple) > 1:
          remain = couple.remove(i)[0]
          if remain in newdead:
            print("*** Lovers have both died tonight")
          else:
            print("*** One lover is dead, the other dies as a consequence")
            await message.channel.send("{} tragically chooses to end their life after they find out that {} has died".format(remain, i))
            for j in players:
              if j.name == remain:
                j.alive = False
                alive.remove(j.name)
      couple = []


    kidnap['prev'] = kidnap['target']
    kidnap['target'] = None
    protect['prev'] = protect['target']
    protect['target'] = None
    stayat['prev'] = stayat['target']
    stayat['target'] = None
    lookat['target'] = None
    newmute = []
    newdead = []
    gamestate += 1 # set gamestate to DAY
    for i in players:
      i.reset_mods()
    print("------- Night results sent. To begin voting, type: $beginvoting -------")

# ------------- Voting Commands GM and Player -----------------

  if message.content.startswith('$beginvoting'):
    if message.author.nick != GM:
      await message.channel.send("Relax bro you're not the GM")
      return
    if gamestate != 3: # if the game has not just sent night results
      await message.channel.send("The game is not ready to begin voting yet")
      return
    gamestate = 1 # set gamestate to voting 
    lynchvotes = {pl:None for pl in alive}
    await message.channel.send('Get ready to vote!! You can vote by typing "$vote <player nickname>" in any channel, though you probably want to vote in your private channel. Voting will end when all alive players have voted, or the gamemaster ends voting early')
    print("+++ Beginning voting procedure... \n   +To end voting early, typing '$endvoting', or wait for all players to vote")

  if message.content.startswith('$vote '):
    if gamestate != 4: 
      await message.channel.send("Chill, not ready to vote")
      return
    if message.author.nick in alive:
      target = message.content.split(' ')[1]
      if target not in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      livecount = len(alive)
      lynchvotes[message.author.nick] = target
      print("Voting: {} has voted to lynch {}. {}/{} players have voted".format(message.author.nick, target, len(lynchvotes), livecount))
      await message.channel.send("{}'s vote to lynch {} has been recorded. {}/{} players have voted. You can change this vote until voting ends by voting again for someone else".format(message.author.nick, target, len(lynchvotes), livecount))
      if len(lynchvotes) == livecount:
        print("All players have voted")
        await lynchresult(message.guild, None)

    if message.content.startswith('$endvot'):
      if message.author.nick != GM:
        await message.channel.send("Relax bro you're not the GM")
        return
      if gamestate != 4: # if the game has not just sent night results
        await message.channel.send("The game is not ready to end voting yet")
        return
      lynchresult(message.guild)

# ----------- Game Setup & Start ------------------
  if message.content.startswith('$gamesetup'): 
    if gamestate == 0: # if setup == false
      gmnick = message.author.nick
      if gmnick:
        GM = gmnick
        ids[gmnick] = message.author.id
      else:
        await message.channel.send("Yo get a nickname man")
        return
      print("Starting game setup")
      await message.channel.send("Starting game setup... \nTo join the game, please type '$join' \nMinimum {} players required to start the game \nTo start the game, the GM can type '$gamestart <role> <role>'' etc..".format(min_players))
      await message.channel.send("Current roles in the game include: {}".format( possible_roles))
    else:
      await message.channel.send("Fail to start game setup: another game setup is taking place")

  if message.content.startswith('$join'):
    if gamestate != 0:
      await message.channel.send("No game setup taking place")
      return
    else:
      name = message.author.nick
      if name == None:
        await message.channel.send("Yo please get a nickname before joining")
        return
      if ' ' in name:
        await message.channel.send("Please make sure there are no spaces in your nickname")
        return
      participant = name
      lobby.append(participant)
      ids[name] = message.author.id
      print("{} has joined the game, playercount now at {}".format(participant, len(lobby)))
      #await message.channel.send("{} added to the game".format(participant))

  if message.content.startswith('$leave'):
    if gamestate != 0:
      await message.channel.send("Please wait for someone to begin a game setup")
      return
    participant = message.author.nick
    if participant in lobby:
      lobby.remove(participant)
      print("{} has left the game, playercount now at {}".format(participant, len(lobby)))
      await message.channel.send("{} removed from the game".format(participant))

  if message.content.startswith('$gamestart'):
    if gamestate != 0:
      await message.channel.send("Need to complete game setup")
      return
    if len(lobby) < min_players:
      await message.channel.send("Insufficient players")
      return
    roles = message.content.split(' ')[1:]
    for role in roles:
      if role not in possible_roles:
        await message.channel.send("Invalid role {}, please try again".format(role))
        return
    if len(roles) != len(lobby):
      await message.channel.send("Mismatch between amounts of roles & players")
      return
    print("Starting game...")
    print("Included roles are: {}".format(roles))
    print("Players playing: {}".format(lobby))
    print("{} players are playing".format(len(lobby)))
    players = await distribute_roles(lobby, roles, message.guild)
    alive = lobby
    print("The wolves are {}".format(wolves))
    print("------- Ready for $beginnight ---------")
    await message.channel.send("Game started! Please check if you have been added to a text channel, and that you are clear on your role and how to play it")

# -------------------------- Reset Game --------------------------------

  if message.content.startswith('$gamereset'):
    if message.author.nick != GM:
      await message.channel.send("You aren't the GM")
      return
    await message.channel.send('Resetting game...')
    await remove_channels(message.guild)
    lobby = []
    wolves = []
    players = []
    ids = {}
    nightcount = 0
    gamestate = 0
    await message.channel.send('Game reset!')
    roles = []
    print("Finished resetting game!")

# -------------------------- Utility commands ---------------------------------
  if message.content.startswith('$playerlist'):
    await message.channel.send("Players: {}".format(lobby))

  if message.content.startswith('$clearplayerlist'):
    lobby = []

  if message.content.startswith('$allroles'):
    await message.channel.send("Current roles in the game include: {}".format( possible_roles))

  if message.content.startswith('$poopbreak'):
    await message.channel.send("Aren't you a funnyman https://www.youtube.com/watch?v=DN0gAQQ7FAQ")
  
  if message.content.startswith('$roles'):
    await message.channel.send('Roles included in this game are: {}'.format(roles))

  if message.content.startswith('$gamestate'):
    await message.channel.send("State of Game: {}".format(gskey[gamestate]))
  
  if message.content.startswith('$gm'):
    await message.channel.send("Current GM is: {}".format(GM))

  if message.content.startswith('$alive'):
    await message.channel.send('Alive players are:'.format(alive))

client.run(os.environ['id'])