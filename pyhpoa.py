#HP OA Firmware Upgrader V0.1
#Thomas Attree
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import paramiko
import ConfigParser
import logging
import os
import sys
import time
import threading
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


def sshUpgrade(target,username,password,ip,firmFile):
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	
	try:
		ssh.connect(target,username=username,password=password)
	except:
		print ('[-] Could not connect to target' + target)
		print (sys.exc_info())
		exit(0)
		
	#Send update force command
	stdin, stdout, stderr = ssh.exec_command("update image force ftp://" + ip + ":2121/" + firmFile)

	#Accept warning although this shouldnt be needed when running in script mode
	#stdin.write("YES\n")
	stdin.flush()
	
	data = stdout.read().splitlines()
	for line in data:
		print (line)
	return

class FTPd(threading.Thread):

	handler = FTPHandler
	server_class = FTPServer

	def __init__(self, directory):
		threading.Thread.__init__(self)
		self.__serving = False
		self.__stopped = False
		self.__lock = threading.Lock()
		self.__flag = threading.Event()
		
		authorizer = DummyAuthorizer()
		authorizer.add_anonymous(directory)
		self.handler.authorizer = authorizer
		self.address = ('0.0.0.0', 2121)
		self.server = self.server_class(self.address, self.handler)
		self.host, self.port = self.server.socket.getsockname()[:2]
	
	def __repr__(self):
		status = [self.__class__.__module__ + "." + self.__class__.__name__]
		if self.__serving:
			status.append('active')
		else:
			status.append('inactive')
		status.append('%s:%s' % self.server.socket.getsockname()[:2])
		return '<%s at %#x>' % (' '.join(status), id(self))


	@property
	def running(self):
		return self.__serving

	def start(self, timeout=0.001):
		#Start serving until an explicit stop() request.
		#Polls for shutdown every 'timeout' seconds.
		
		if self.__serving:
			raise RuntimeError("Server already started")
		if self.__stopped:
			# ensure the server can be started again
			FTPd.__init__(self, self.server.socket.getsockname(), self.handler)
		self.__timeout = timeout
		threading.Thread.start(self)
		self.__flag.wait()
	
	def run(self):
		self.__serving = True
		self.__flag.set()
		while self.__serving:
			self.__lock.acquire()
			self.server.serve_forever(timeout=self.__timeout, blocking=False)
			self.__lock.release()
		self.server.close_all()

	def stop(self):
		"""Stop serving (also disconnecting all currently connected
		clients) by telling the serve_forever() loop to stop and
		waits until it does.
		"""
		if not self.__serving:
			raise RuntimeError("Server not started yet")
		self.__serving = False
		self.__stopped = True
		self.join()
		#sys.exit()
			

def main():
	config = ConfigParser.ConfigParser()
	config.read('oa.conf')

	try:
		try:
			targets = config.get('targets','oaip').split(',')
			for target in targets:
				print ('[+] ' + target)
		except:
			print ('[-] Unable to get target addresses')

		try:
			firmFile = config.get('firmware','file')
			print ('[+] Firmware file: ' + firmFile)
		except:
			print ('[-] Could not get FTP directory')
		try:
			ip = config.get('firmware','FTPServerIP')
			print ('[+] FTP Server IP: ' + ip)
		except:
			print ('[-] Could not get FTP Server IP')
		try:
			directory = config.get('firmware','directory')
			print ('[+] Firmware directory for FTP server: ' + directory)
		except:
			print ('[-] Could not get FTP directory')
		try:
			username = config.get('credentials','user')
			print ('[+] Username ' + username + ' will be used')
		except:
			print ('[-] Could not get username')

		try:
			password = config.get('credentials','password')
			print ('[+] Password ' + password + ' will be used')
		except:
			print ('[-] Could not get Password')

	except:
		print ('[-] Config errors. Please check the configuration and run script again')
		exit(0)

	#Start new thread FTP server
	ftpServer = FTPd(directory)
	ftpServer.start()
	
	for target in targets:
		print ('[+] Starting OA upgrade on ' + target)
		sshUpgrade(target,username,password,ip,firmFile)	
	ftpServer.stop()
	sys.exit()

if __name__ == '__main__':
	main()
