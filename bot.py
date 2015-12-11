import time

from IRCConnection import IRCConnection
from TSConnection import TSConnection

with open( 'querypass.txt' ) as passfile:
	querypass = passfile.read()

freenode = IRCConnection( "chat.freenode.net", 6667, "CLTSBridge", "#cubelime" )
freenode.run()

ts = TSConnection( "localhost", 10011, "CLTSBridge", "admin", querypass )
ts.run()

TYPE = 0
FROM = 1

def build_message( event ):
	print( event )

	if not event:
		return None

	if event[TYPE] == "MSG":
		return "<%s> %s" % ( event[1], event[3] )
	elif event[TYPE] == "ACTION":
		return "* %s %s" % ( event[1], event[3] )
	elif event[TYPE] == "ENTER":
		return "*** %s joined the channel ***" % ( event[1], )
	elif event[TYPE] == "CONNECT":
		return "*** %s connected ***" % ( event[1], )
	elif event[TYPE] == "LEAVE":
		return "*** %s left the channel ***" % ( event[1], )
	elif event[TYPE] == "QUIT":
		return "*** %s disconnected ***" % ( event[1], )
	elif event[TYPE] == "NICK":
		return "*** %s is now known as %s ***" % ( event[1], event[2] )
	else:
		return None

while freenode.running() and ts.running():
	try:
		im = freenode.poll()
		tm = ts.poll()

		if im:
			ts.send_text( build_message( im ) )
		if tm:
			freenode.send_text( build_message( tm ) )

		time.sleep( 0.5 )
	except KeyboardInterrupt:
		freenode.disconnect()
		ts.disconnect()
