import socket, threading, time, traceback

from queue import Queue

class TSConnection:
	_send_queue = Queue()
	_recv_queue = Queue()
	_connected = False
	_running = False
	_client_map = {}
	_log = None
	
	def __init__( self, server, port, nick, username, password ):
		self._server = server
		self._port = port
		self._nick = nick
		self._username = username
		self._password = password
		self._socket = socket.socket()

	def run( self ):
		self._log = open( "ts.log", 'a', 1 )

		self._running = True
		
		self.connect()

		self._recv_thread = threading.Thread( target=self.listen )
		self._recv_thread.start()

		self._send_thread = threading.Thread( target=self.process_send_queue )
		self._send_thread.start()

		self._keep_alive_thread = threading.Thread( target=self.keepalive )
		self._keep_alive_thread.start()

	def keepalive( self ):
		while self._running:
			if self._connected:
				self._socket.send( bytes( "clientlist\n", 'UTF-8' ) )
				self._socket.send( bytes( "servernotifyregister event=channel id=1\n", 'UTF-8' ) )

			time.sleep( 30 ) 

	def connect( self ):
		print( "[TS] Connecting..." )
		self._connected = False

		try:
			self._socket = socket.socket()
			self._socket.connect( ( self._server, self._port ) )
		
			self._socket.send( bytes( "login %s %s\n" % ( self._username, self._password ), 'UTF-8' ) )
			self._socket.send( bytes( "use 1\n", 'UTF-8' ) )
			self._socket.send( bytes( "servernotifyregister event=textchannel id=1\n", 'UTF-8' ) )
			self._socket.send( bytes( "servernotifyregister event=textserver id=1\n", 'UTF-8' ) )
			self._socket.send( bytes( "servernotifyregister event=channel id=1\n", 'UTF-8' ) )
			self._socket.send( bytes( "clientupdate client_nickname=[IRC]\n", 'UTF-8' ) )

			self._connected = True
		except:
			self._connected = False
			print( "connect to %s on port %s failed.\n" % ( self._server, self._port ) )
			print( traceback.format_exc() )
			return
			
	def listen( self ):
		while self._running:
			try:
				while not self._connected:
					self.connect()

				data = self._socket.recv( 4096 )
				
				if len( data ) == 0:
					print( "connection to %s lost. Attempting to reconnect...\n" % ( self._server, ) )
					self._connected = False
					continue

				data = data.decode( "UTF-8" )

				data.strip()

				#self._log.write( data + "\n" )

				parts = data.split()

				command = parts[0]

				args = {}

				for pair in parts[1:]:
					bits = pair.partition( "=" )
					args[ bits[0] ] = bits[2]

				if command == "notifytextmessage":
					msg = self.decode( args["msg"] )
					msg_from = self.decode( args["invokername"] )

					if msg_from.startswith( "[IRC]" ):
						continue

					self._recv_queue.put( ( "MSG", msg_from, "", msg ) )
				elif command == "notifycliententerview":
					msg_from = self.decode( args["client_nickname"] )
					self._client_map[ args["clid"] ] = msg_from
					self._recv_queue.put( ( "ENTER", msg_from, "" ) )
				elif command == "notifyclientleftview":
					msg_from = self._client_map[args["clid"]]
					del self._client_map[args["clid"]]
					self._recv_queue.put( ( "QUIT", msg_from, "" ) )
				elif command == "notifyclientmoved":
					msg_from = self._client_map[args["clid"]]
					if args["ctid"] == "1":
						self._recv_queue.put( ( "ENTER", msg_from, "" ) )
					else:
						self._recv_queue.put( ( "LEAVE", msg_from, "" ) )
				elif command.startswith( "clid" ):
					for client in data.split( "|" ):
						args = {}
						for pair in client.split():
							bits = pair.partition( "=" )
							args[ bits[0] ] = bits[2]
						if "clid" in args and "client_nickname" in args:
							self._client_map[ args["clid"] ] = args[ "client_nickname" ]
			
	
			except:
				print( traceback.format_exc() )

	def encode( self, data ):
		data = data.replace('\\', '\\\\')
		data = data.replace('/', '\\/')
		data = data.replace(' ', '\\s')
		data = data.replace('|', '\\p')
		data = data.replace('\n', '\\n')
		data = data.replace('\r', '\\r')
		data = data.replace('\t', '\\t')
		return data

	def decode( self, data ):
		data = data.replace('\\\\', '\\')
		data = data.replace('\\/', '/')
		data = data.replace('\\s', ' ')
		data = data.replace('\\p', '|')
		data = data.replace('\\a', '')
		data = data.replace('\\b', '')
		data = data.replace('\\f', '')
		data = data.replace('\\n', '\n')
		data = data.replace('\\r', '\r')
		data = data.replace('\\t', '    ')
		data = data.replace('\\v', '\n')
		data = data.replace('[URL]', '')
		data = data.replace('[/URL]', '')
		return data

	def relay_message( self, user, msg ):
		msg = self.encode( msg )
		user = self.encode( user )

		self.send_raw( "clientupdate client_nickname=[IRC]" + user )
		self.send_raw( "sendtextmessage targetmode=2 target=1 msg=" + msg )
		self.send_raw( "clientupdate client_nickname=" + self._nick )

	def send_text( self, text ):
		if not text:
			return

		text = self.encode( text )
		self.send_raw( "sendtextmessage targetmode=2 target=1 msg=" + text )
	
	def send_raw( self, text ):
		msg = "%s\n" % ( text, )
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
			
			time.sleep( 0.01 ) 
			
	def disconnect( self ):
		print( "[TS] Disconnecting" )
		self._running = False
		self._connected = False
		self._socket.close()
		self._send_thread.join()
		self._recv_thread.join()
	
	def running( self ):
		return self._running
