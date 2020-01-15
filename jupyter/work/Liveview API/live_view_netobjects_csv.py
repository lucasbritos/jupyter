#!/usr/bin/env python

"""
Script to get Services statistics per NetObject from LiveView Realtime
"""

#######################################################################
#  live_view_netobjects_csv.py
#
#  This is a private program for INTERNAL USE ONLY and CANNOT be COPIED
#  or DISTRIBUTED.
#
# Included Multithread
# Added header to csv file
# Get NetObjects dynamically
# Added config file
# Included logging to file
# Included log flag at collection start and collection end
# Bug fix - csv header
# Bug fix - included thread per netobjects to get data for all netobjetcs 
# Reconnection on servers and upadate netobjects list in each iteration
# Bug fix - cleaning the list of servers in each iteration
# Bug fix - included queue to avoid concurrency while writing csv
#
#########################################################################

# Import PacketLogic DB API
import packetlogic2

# Standard Imports
import sys
import time
import datetime
import logging
import logging.handlers
from logging.handlers import TimedRotatingFileHandler
import multiprocessing
import ConfigParser
import os.path

#Define CSV File Name
#filecsv = '/home/procera/scripts/rtm/live_view_netobjects.csv'
filecsv = '/tmp/live_view_netobjects.csv'

#Define Log File
#logfile='/home/procera/scripts/log/live_view_netobjects.log'
logfile='/tmp/live_view_netobjects.log'

#Define log level
log_level = 'INFO'

#Define Loop Periodicy in minutes
periodicy = 5

#Set up logging to log file
logHandler_log = logging.FileHandler(logfile)
logFormatter_log = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
logHandler_log.setFormatter( logFormatter_log )
logger_log = logging.getLogger( 'LoggerLog' )
logger_log.addHandler( logHandler_log )
level = logging.getLevelName(log_level)
logger_log.setLevel( level )

#Check arguments
if len(sys.argv) < 3 or (len(sys.argv) > 2 and sys.argv[1] != "realtime"):
        print ("usage: %s realtime <configfile>" % sys.argv[0])
        logger_log.error("usage: %s realtime <configfile>" % sys.argv[0])
        sys.exit(1)

#Confige Log Handler to write csv
try:
        logHandler_csv = TimedRotatingFileHandler( filecsv , when='midnight')
except:
        t, v, tb = sys.exc_info()
        logger_log.error("%s" % v, exc_info=True)
        sys.exit(1)
logFormatter_csv = logging.Formatter('%(message)s')
logHandler_csv.setFormatter( logFormatter_csv )
logger_csv = logging.getLogger( 'LoggerCsv' )
logger_csv.addHandler( logHandler_csv )
logger_csv.setLevel( logging.INFO )

#Dump queue into csv file
def listener_process(queue):
        while True:
                try:
                        record = queue.get()
                        if record is None: # We send this as a sentinel to tell the listener to quit.
                                break
                        logger_csv.info(record)
                except Exception:
                        t, v, tb = sys.exc_info()
                        logger_log.error("%s" % v, exc_info=True)
                        break

#Function to read config file
def ConfigSectionMap(section):
        dict1 = {}
        try:
                options = config.options(section)
        except:
                t, v, tb = sys.exc_info()
                logger_log.error("%s" % v, exc_info=True)
                sys.exit(1)

        for option in options:
                try:
                        dict1[option] = config.get(section, option)
                        if dict1[option] == -1:
                                DebugPrint("skip: %s" % option)
                except:
                        logger_log.error("exception on %s!" % option)
                        dict1[option] = None
        return dict1

if sys.argv[2].lower():
        configfile = sys.argv[2].lower()
        config = ConfigParser.ConfigParser()
        config.read(configfile)
else:
        print ("usage: %s <configfile> statistic" % sys.argv[0])
        logger_log.error("usage: %s <configfile> statistic" % sys.argv[0])
        sys.exit(1)


#Function to connect to stats machine
def server_connect():
	global servers
	servers = []	

	hosts = ConfigSectionMap("Servers")

	for k in hosts.keys():
        	try:
                	p = packetlogic2.connect(hosts[k], login, pwd)
       	 	except:
                	t, v, tb = sys.exc_info()
                	logger_log.error("Couldn't connect to %s: %s" % (k, v), exc_info=True)
                	continue

        	servers.append([p,k])

#Function to get NetObjects
global netobjects_list
def get_netobjects():
	netobjects_list = []
	for s in servers:
		try:
			rt = s[0].Realtime()
			no = rt.get_netobj_data()
			for m in no.list('/NetObjects/'):
				if m.name not in netobjects_list:
					netobjects_list.append(m.name)
		except:
                	t, v, tb = sys.exc_info()
                	logger_log.error("Couldn't get netobjects list from %s: %s" % (s[1], v), exc_info=True)
                	continue
	netobjects_list.append('PSM/Mobile')
	netobjects_list.append('PSM/Live_UBB')
	netobjects_list.append('PSM/Live_EMP') 

#Function to hold run on exact time
def hold(t):
        d = datetime.datetime.now()
        hold_m = ((t - 1 ) - (d.minute % t)) * 60
        hold_s = 60 - d.second
        hold_t = hold_m + hold_s
        time.sleep (hold_t)


#Function to open multiprocess in parallel
def multiproc(queue):
        jobs = []
        for s in servers:
                for n in netobjects_list:
                        try:
                                p = multiprocessing.Process(target=RealtimeView, args=(s[0],n,queue,))
                                p.start()
                                jobs.append(p)

                        except:
                                t, v, tb = sys.exc_info()
                                logger_log.error("%s" % v, exc_info=True)
                                continue

        for pw in jobs:
                pw.join()

        #Send sentinel to finish dumper
        queue.put_nowait(None)


#Class to get realtime data per thread
class RealtimeView(object):
	def __init__(self,server,netobject,queue):
		try:	
			self.server_id = server.host
			self.network = netobject		
			logger_log.info("Starting collecting data from %s for %s" % (self.server_id, self.network))
			self.rt = server.Realtime()
			self.access()
		except:
                	t, v, tb = sys.exc_info()
                	logger_log.error("Couldn't get data from %s: %s" % (self.server_id, v), exc_info=True)
                	return

	def access(self):
		self.count = 0 	
		try:	
			vb = self.rt.get_view_builder()
	       		vb.filter('Visible NetObject',self.network)
	       		vb.distribution('Service')
	       		self.rt.add_aggr_view_callback(vb, self.get_aggr_view)
			self.rt.update_forever(120.0)
        	except:
                	t, v, tb = sys.exc_info()
                	logger_log.error("Couldn't get data from %s for %s: %s" % (self.server_id, self.network, v), exc_info=True)
                	return


	def get_aggr_view(self,data):
		if data.children:
			try:
				for k in data.children:
                        		queue.put_nowait(",".join([str(j) for j in ["%s" % time.ctime(),self.server_id, self.network, k.name, k.speed[0], k.speed[1], k.connections]])+'\r')
			except:
                		t, v, tb = sys.exc_info()
                		logger_log.error("Couldn't write data from %s for %s to CSV file: %s" % (self.server_id, self.network, v), exc_info=True)
				self.rt.stop_updating()
                		return

			self.rt.stop_updating()
			logger_log.info("The data from %s for %s was written to the CSV file %s" % (self.server_id, self.network, filecsv))
		if self.count > 1:
			self.rt.stop_updating()
		self.count = self.count + 1

#Get Credentials
login = ConfigSectionMap("Credentials")['login']
pwd = ConfigSectionMap("Credentials")['pwd']

#First server connection
server_connect()
get_netobjects()
hold(periodicy)

#Create queue
queue = multiprocessing.Queue(-1)

#Run in loop
loop = True
while loop:
	#Insert header to csv file
        d = datetime.datetime.now()
	try:
		if (d.hour == 0 and d.minute >= 0 and d.minute < periodicy) or (os.path.getsize(filecsv) == 0):
			queue.put_nowait("TIME,HOST,NETOBJECT,SERVICE,IN,OUT,CONNECTIONS\r")
	except:
               	t, v, tb = sys.exc_info()
                logger_log.error("Couldn't write to CSV file: %s" % v, exc_info=True)
                pass

	#Run multiproc in a separate process
        procs = multiprocessing.Process(target=multiproc,args=(queue,))
        procs.start()	
	
	#Run dumper until the sentinel arrives 
	listener_process(queue)

	#Avoid defunct
        procs.join()

	#Reconection on servers
	time.sleep(periodicy*0.6*60)
	server_connect()
	get_netobjects()
	
	#Hold to run on periodicy
	hold(periodicy)
