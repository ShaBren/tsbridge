import socket, threading, time, traceback

from queue import Queue

class IRCConnection:
	_send_queue = Queue()
	_recv_queue = Queue()
	_connected = False
	_running = False
	
	def __init__( self, server, port, nick, channel ):
		self._server = server
		self._port = port
		self._nick = nick
		self._channel = channel
		self._socket = socket.socket()

	def run( self ):
		self._running = True
		
		self.connect()

		self._recv_thread = threading.Thread( target=self.listen )
		self._recv_thread.start()

		self._send_thread = threading.Thread( target=self.process_send_queue )
		self._send_thread.start()

	def connect( self ):
		print( "[IRC] Connecting..." )
		self._connected = False

		try:
			self._socket.connect( ( self._server, self._port ) )
		
			self._socket.send( bytes( "NICK %s\r\n" % ( self._nick, ), 'UTF-8' ) )
			self._socket.send( bytes( "USER %s %s PB :%s\r\n" % ( self._nick, self._nick, self._nick ), 'UTF-8' ) )
			self._socket.send( bytes( "JOIN %s\r\n" % ( self._channel, ), 'UTF-8' ) )

			self._connected = True
		except:
			self._connected = False
			print( "connect to %s on port %s failed.\n" % ( self._server, self._port ) )
			print( traceback.format_exc() )
			return
			
	def listen( self ):
		while self._running:
			while not self._connected:
				self.connect()
				time.sleep( 5 )

			data = self._socket.recv( 4096 )
			
			if len( data ) == 0:
				print( "connection to %s lost. Attempting to reconnect...\n" % ( self._server, ) )
				self._connected = False
				continue

			data = data.decode( "UTF-8" )
			data = data.rstrip()
			line = data.split()

			if len( line ) < 1:
				continue
	
			if line[0] == "PING":
				self.send_raw( "PONG " + line[1] )
			elif len( line ) > 2:
				if line[1] == 'PRIVMSG':
					msg_from = line[0].split('!')[0].lstrip(':')
					msg_to = line[2]
					msg = " ".join(line[3:])[1:]
					
					if msg_to == self._nick:
						channel = msg_from
					else:
						channel = msg_to

					if msg == self._nick + ": ping":
						self.send_text( "pong" )

					if msg.startswith( "\x01" ):
						msg = msg[8:-1]
						self._recv_queue.put( ( "ACTION", msg_from, channel, msg ) )
					else:
						self._recv_queue.put( ( "MSG", msg_from, channel, msg ) )

				elif line[1] == 'JOIN':
					msg_from = line[0].split('!')[0].lstrip(':')
					channel = line[2]

					self._recv_queue.put( ( "ENTER", msg_from, channel ) )

				elif line[1] == 'PART':
					msg_from = line[0].split('!')[0].lstrip(':')
					channel = line[2]

					self._recv_queue.put( ( "LEAVE", msg_from, channel ) )

				elif line[1] == 'QUIT':
					msg_from = line[0].split('!')[0].lstrip(':')

					self._recv_queue.put( ( "QUIT", msg_from ) )

				elif line[1] == 'NICK':
					old_nick = line[0].split('!')[0].lstrip(':')
					new_nick = line[2].lstrip(':')

					self._recv_queue.put( ( "NICK", old_nick, new_nick ) )


	def relay_message( self, user, msg ):
		self.send_text( "[%s] %s" + ( user, msg ) )

	def send_text( self, text ):
		if not text:
			return

		msg = "PRIVMSG %s :%s\r\n" % ( self._channel, text )
		self._send_queue.put( msg )
	
	def send_raw( self, text ):
		msg = "%s\r\n" % ( text, )
		self._send_queue.put( msg )
		
	def poll( self ):
		if self._recv_queue.empty():
			return None

		return self._recv_queue.get()

	def process_send_queue( self ):
		while self._running:
			if self._connected and not self._send_queue.empty():
				self._socket.send( bytes( self._send_queue.get(), 'UTF-8' ) )
				self._send_queue.task_done()
			
			time.sleep( 0.5 ) 
			
	def disconnect( self ):
		self._running = False
		self._connected = False
		self._socket.close()
		self._send_thread.join()
		self._recv_thread.join()
	
	def running( self ):
		return self._running
