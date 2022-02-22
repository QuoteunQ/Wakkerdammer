overwritesdead = {} # contains permissions for the death realm 
mutilated = [] # not in use??
lynchvotes = {} # votes for lynching

  

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



  if message.content.startswith('$lookat'):
    if message.channel.name == 'seer'and gamestate == 1and message.author.nick in alive:
      target = message.content.split(' ')[1]
      if target not in alive:
        await message.channel.send("The player you submitted is not in the game or is not alive")
        return
      lookat['target'] = target 
      await message.channel.send("You have chosen {} as your seer target".format(target))
      print("Seer: {} has chosen to look at {}'s role'".format(message.author.nick, target))    

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