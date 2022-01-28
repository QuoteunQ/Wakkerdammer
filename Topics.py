from replit import db 

db['topics'] = {'kidnapper': "You are the kidnapper! During nights type $kidnap <player nickname> to kidnap someone, and vote for someone during days using $lynch <player nickname>. For questions please @ the gamemaster. Type $help to see other commands",
'cupid': '',
'protector': '',
'seer': '',
'witch': '{}'.format(db['witchpots']),
'hunter': '', 
'elder': '',
'fool': '',
'civillian': '',
'werewolf': '',
'picky_werewolf': 'You are the picky werewolf! The other werewolves are {} (if there is an incorrect number in here contact the gamemaster). You are able to pick {} other werewolf(s). After you use all your picks the werewolf groupchat will be created, which should be in the first night otherwise you cant choose someone to mutilate. Pick someone by typing $pick <player nickname>. You vote to kill/mutilate in the werewolves groupchat. For questions please @ the gamemaster. Type $help to see other commands'.format(wolves, db['picks']),
'werewolves': 'Welcome to the werewolves groupchat! This groupchat will be used for discussing the game amongst yourselves',
'lovers': ''
}