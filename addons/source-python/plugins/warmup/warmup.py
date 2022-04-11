import core, memory, random
from events import Event
from engines.sound import Sound
from listeners.tick import Delay
from memory.hooks import PreHook
from players.entity import Player
from messages import TextMsg, SayText2
from filters.players import PlayerIter
from filters.entities import EntityIter
from memory import Convention, DataType
from commands.client import ClientCommand
from colors import GREEN, LIGHT_GREEN, RED
from filters.weapons import WeaponClassIter
from engines.server import queue_command_string
from listeners import OnLevelInit, OnLevelShutdown

warm_up = False

#=========================================
# Player class
#=========================================

class WarmupPlayer(Player):
	''' Extended player class '''
	global warm_up

	def __init__(self, index, caching=True):
		super().__init__(index)

	def respawn_user(self): 
		if warm_up: # Is currently warm up
			if self.dead and self.team in [2, 3]: # Player is dead and is in valid team to respawn
				self.delay(0, self.spawn, (True,)) # Respawn the player
	
	def give_grenade(self):
		if not self.dead: # The player is alive
			self.remove_user_weapons() # Remove all weapons
			self.restrict_weapons_name('hegrenade') # Restrict all weapons expect hegrenade
			if not self.get_property_int('localdata.m_iAmmo.011'): # The player doesn't have hegrenade
				self.give_named_item('weapon_hegrenade') # Give hegrenade

	def give_knife(self):
		if not self.dead: # The player is alive
			self.remove_user_weapons() # Remove all weapons
			weapons = [weapon.basename for weapon in WeaponClassIter(not_filters='knife')] # Weapons that will be restricted
			self.restrict_weapons(*weapons) # Restrict all weapons expect knife
			self.give_named_item('weapon_knife') # Give knife

	def remove_user_weapons(self):
		if not self.dead: # The player is alive
			for weapon in self.weapons(): # Loop all player weapons
				if weapon.classname.startswith('weapon_'): # Ensure the weapon is in weapons category
					weapon.remove() # Remove the weapon

	def restrict_weapons_name(self, name):
		weapons = [weapon.basename for weapon in WeaponClassIter(f'{name}')] # Weapons that will be restricted
		self.restrict_weapons(*weapons) # Restrict all weapons expect given weapon name

	def give_weapon(self, name):
		if not self.dead: # The player is alive
			self.remove_user_weapons() # Remove the player weapons
			self.restrict_weapons_name(f'{name}') # Restrict all weapons expect given one
			self.give_named_item(f'weapon_{name}') # Give player the weapon

	def restore(self):
		weapons = [weapon.basename for weapon in WeaponClassIter()] # Loop all weapons
		self.unrestrict_weapons(*weapons) # Unrestrict every weapon

	def tell_weapon(self, weapon):
		SayText2(f'{GREEN}[Warm Up]: {LIGHT_GREEN}-> You cannot {GREEN}buy {RED}{weapon} {LIGHT_GREEN}during {RED}warm up!').send(self.index) # Tell message can't purchase a weapon
		Sound('buttons/weapon_cant_buy.wav').play(self.index) # Play a sound

#=========================================
# Functions
#=========================================
def stop_warm_up():
	global warm_up
	warm_up = False # Set warm up is over
	for player in PlayerIter(): # Loop all weapons
		WarmupPlayer(player.index).restore() # Unrestrict all weapons
	queue_command_string('mp_restartgame 1') # Restart the server

def warming_up(duration, count):
	global my_delay
	TextMsg(f'Warm Up: {duration - count} seconds').send() # Send centertell message how much warm up is remaining
	count += 1 # One second have passed, increase the count
	if count == duration: # 45 seconds have passed
		stop_warm_up() # Stop the warm up
	else:
		my_delay = Delay(1, warming_up, (duration, count)) # Keep delaying until warm up is over

def remove_idle_weapons():
	for weapon in EntityIter(): # Loop all entitys 
		if weapon.classname.startswith('weapon_'): # The entity belongs to weapon
			if weapon.owner_handle in [-1, 0]: # The weapon is idle
				weapon.remove() # Remove the idle weapon

#=========================================
# Events & Listerners & ClientCommand
#=========================================
@ClientCommand('buy')
def buy_command(command, index):
	'''Called when a player buy weapon.'''
	weapon = command[1].lower() # Get the weapon name, player attemps to buy
	global warm_up
	if warm_up: # Is currently warm up
		WarmupPlayer(index).tell_weapon(weapon.title()) # Tell the message can't buy weapons
		return False # Block weapon purchase

@Event('player_spawn')
def player_spawn(args):
	'''Called when a player spawns.'''
	global warm_up
	if warm_up: # Is currently warm up
		remove_idle_weapons() # Remove all idle weapons
		player = WarmupPlayer.from_userid(args['userid']) # Create player class
		global effect # Check given effect at map start
		if effect == 1: # The effect is hegrenade
			player.give_grenade() # Give player hegrenade
		elif effect == 2: # The effect is deagle only
			player.give_weapon('deagle') # Give player deagle
		elif effect == 3: # The effect is knife only
			player.give_knife() # Give player knife

@Event('weapon_fire')
def weapon_fire(args):
	'''Called when a player fire weapon.'''
	global warm_up
	if warm_up: # Is currently warm up
		weapon = args.get_string('weapon') # Get the weapon that have fired
		player = Player.from_userid(args['userid']) # Create player class
		global effect
		if effect == 1: # The effect is hegrenades only
			if weapon == 'hegrenade': # The fired weapon was hegrenade
				player.delay(2, player.give_named_item, ('weapon_hegrenade',)) # Give new hegrenade in 2 seconds

@Event('player_death')
def player_death(args):
	'''Called when a player dies.'''
	WarmupPlayer.from_userid(args['userid']).respawn_user() # Respawn the player class

@Event('player_team')
def player_team(args):
	'''Called when a player switch team.'''
	if args.get_int('team') in [2, 3]: # Player joins to terrorist & counter-terrorist
		WarmupPlayer.from_userid(args['userid']).respawn_user() # Respawn the player

@OnLevelInit
def map_start(map_name):
	'''Called when a new map starts'''
	print(f'[Warmup]: {map_name}')
	global warm_up
	warm_up = True # Set warmup
	global effect
	effect = random.randint(1, 3) # Get the random values for effect
	Delay(1.0, warming_up, (45, 1)) # Activate warm up timer by one second delay

@OnLevelShutdown
def map_change():
	'''Called when a map changes'''
	for player in PlayerIter(): # Loop all players
		WarmupPlayer(player.index).restore() # Remove weapon restricts
	global my_delay # Global the delay name
	try:
		if not my_delay is None and my_delay.running: # Does the delay exists and is it running
			my_delay.cancel() # Cancel the delay
	except: # Delay wasn't define
		pass

#=========================================
# Terminate round hook
#=========================================
server = memory.find_binary('server', srv_check=False)

if core.PLATFORM == 'windows':
	identifier = b'\x55\x8B\xEC\x83\xEC\x2A\x8B\x45\x0C\x53\x56\x57\x33\xF6'
else:
	identifier = '_ZN12CCSGameRules14TerminateRoundEfi'

terminate_round = server[identifier].make_function(
	Convention.THISCALL,
	[DataType.POINTER, DataType.VOID, DataType.INT, DataType.INT],
	DataType.INT
)
    
@PreHook(terminate_round)
def pre_terminate_round(stack_data):
	global warm_up
	if warm_up: # Is warmup
		return 0 # Block round ending