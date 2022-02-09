topics_temp = {
'kidnapper':
    "- You are the kidnapper! During nights type $kidnap <player name> to kidnap someone, and vote for someone during days using $lynch <player name>. "
    "For questions please @ the gamemaster. Type $help to see other commands",
'cupid':
    "",
'protector':
    "",
'seer':
    "",
'witch':
    "",
'hunter':
    "", 
'elder':
    "",
'fool':
    "",
'civilian':
    "",
'werewolf':
    "",
'picky werewolf':
    "- You are the picky werewolf! The other werewolves are {} (if there is an incorrect number in here contact the gamemaster). "
    "You are able to pick {} other werewolf(s). Pick someone by typing $pick <player name>. "
    "You vote to kill/mutilate in the werewolves groupchat. For questions please @ the gamemaster. Type $help to see other commands.",
'werewolves':
    "- Welcome to the werewolves groupchat! This groupchat will be used for discussing the game amongst yourselves.",
'lovers':
    "- Welcome! You've been made lovers by our dear cupid. Feel free to get acquainted in this channel."
}
print(topics_temp.items())
topics = {i:j for (i,j) in topics_temp.items()}