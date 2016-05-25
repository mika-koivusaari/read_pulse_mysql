#!/usr/bin/python
import logging
import time
import MySQLdb
import re
import argparse
import sys
import os
import signal
#configparser was renamed in python 3
if(sys.version_info[0] == 2):
    from ConfigParser import SafeConfigParser
    from ConfigParser import NoSectionError
else:
    from configparser import SafeConfigParser
    from configparser import NoSectionError

import serial
from pep3143daemon import DaemonContext, PidFile

def main():
    print (sys.argv[1:])
    parser = argparse.ArgumentParser(description="Pulse reader")

    parser.add_argument('method', choices=['start', 'stop', 'reload'])

    parser.add_argument("--cfg", dest="cfg", action="store",
                        default="/etc/pulsereader/pulsereader.ini",
                        help="Full path to configuration")


    parser.add_argument("--pid", dest="pid", action="store",
                        default="/var/run/pulsereader/pulsereader.pid",
                        help="Full path to PID file")

    parser.add_argument("--nodaemon", dest="nodaemon", action="store_true",
                        help="Do not daemonize, run in foreground")

    parsed_args = parser.parse_args()

    if parsed_args.method == 'stop':
        app = App(
            cfg=parsed_args.cfg,
            pid=parsed_args.pid,
            nodaemon=parsed_args.nodaemon
        )
        app.stop()

    elif parsed_args.method == 'start':
        app = App(
            cfg=parsed_args.cfg,
            pid=parsed_args.pid,
            nodaemon=parsed_args.nodaemon
        )
        app.start()

    elif parsed_args.method == 'reload':
        app = App(
                cfg=parsed_args.cfg,
                pid=parsed_args.pid,
                nodaemon=parsed_args.nodaemon
        )
        app.reload()

class App:

    config = None
    db = None
    ser = None
    logger=None
    config=None
    cursor=None
    daemon=None

    def reload_program_config(self,signum, frame):
        conf=self.readConfig(self._config_file)
        if conf!=None:
            self.config=conf
            self.close_resources()
            self.openConnections()

    def terminate(self,signum, frame):
        self.logger.info("terminate")

    def readConfig(self,conf_file=None):
        config = SafeConfigParser()
        if (conf_file == None):
            conf_file = 'read_kwh_pulse_mysql.ini'
        config.read(conf_file)
        confData = {}
        try:
            mysqlData = {}
            mysqlData['host'] = config.get('mysql', 'host')
            mysqlData['user'] = config.get('mysql', 'user')
            mysqlData['passwd'] = config.get('mysql', 'passwd')
            mysqlData['database'] = config.get('mysql', 'database')

            serialData = {}
            serialData['device'] = config.get('serial', 'device')

        except NoSectionError:
            if self.daemon!=None and self.daemon.is_open:
                self.logger.error("Error in "+str(conf_file))
                return None
            else:
                print ('Error in '+conf_file)
                exit()

        confData['mysql'] = mysqlData
        confData['serial'] = serialData
        if self.daemon!=None and self.daemon.is_open:
            self.logger.info("Config loaded from " + str(conf_file))
        else:
            print("Config loaded from " + str(conf_file))
        return confData

    def __init__(self, cfg, pid, nodaemon):
        self._config_file = cfg
        self._pid = pid
        self._nodaemon = nodaemon

    def program_cleanup(self,signum, frame):
        self.logger.info('Program cleanup')
        self.close_resources()
        raise SystemExit('Terminating on signal {0}'.format(signum))

    def close_resources(self):
        if self.db is not None:
            self.cursor.close(

            )
            self.db.close()
        if self.ser is not None:
            self.ser.close()

    def createLogger(self):
        self.logger = logging.getLogger('PulseReader')
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler = logging.FileHandler("/var/log/pulsereader/pulsereader.log")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        #TODO move to config
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug('Logger created.')

    def openConnections(self):
        self.logger.debug("openConnections "+str(self.config))
        # connect
        mysqlConf = self.config['mysql']
        if mysqlConf['host'] != 'None':
            self.db = MySQLdb.connect(host=mysqlConf['host'], user=mysqlConf['user'], passwd=mysqlConf['passwd'],
                                      db=mysqlConf['database'])
            self.logger.info("Connected to MySql")
            # create a cursor
            self.cursor = self.db.cursor()
        else:
            self.db = None
            self.logger.info('MySql host None, not connected.')

        try:
            serialConfig = self.config['serial']
            self.logger.debug("Open serial "+serialConfig['device'])
            # configure the serial connections (the parameters differs on the device you are connecting to)
            self.ser = serial.Serial(
                port=serialConfig['device']
#                ,
#                baudrate=9600,
#                parity=serial.PARITY_NONE,
#                stopbits=serial.STOPBITS_ONE,
#                bytesize=serial.EIGHTBITS
            )
            self.ser.isOpen()
            # Wait for a second if device sends some boot message, and then empty buffer
            time.sleep(1)
            while self.ser.inWaiting() > 0:
                out += self.ser.read(1)
            self.logger.info('Serial is open. ' + serialConfig['device'])
        except:
            self.logger.error(sys.exc_info()[0])
            self.logger.error(sys.exc_info()[1])
            self.logger.error(sys.exc_info()[2])
            raise

    def run(self):
        self.openConnections()
        self.logger.debug("Run")
        # pulse counter
        counter1 = 0
        counter2 = 0

        # sensorid of kWh counter
        sensorId1 = 116  # MLP
        sensorId2 = 115  # total

        # input from arduino "Counters: n,n"
        inputPattern = re.compile('Counters: (\\d*),(\\d*)')
        self.logger.debug(self.ser.isOpen())

        self.logger.debug("Start")
        while True:
            time.sleep(59)

            self.logger.debug("Request counter values")
            #request counter values
            self.ser.write('GET\n')
            out = ''
            # let's wait one second before reading output (let's give device time to answer)
            time.sleep(1)
            while self.ser.inWaiting() > 0:
                out += self.ser.read(1)
            if out != '':
                m = inputPattern.match(out)
                if m:
                    counter1 = int(m.group(1))
                    counter2 = int(m.group(2))
                else:
                    logger.warn("No count")

            self.logger.debug(time.strftime('%H:%M') + ' ' + str(counter1) + ' ' + str(sensorId1) + ' ' + str(counter2) + ' ' + str(sensorId2))

            if self.db is not None:
                self.logger.debug("Insert values")
                self.cursor.execute(
                    'INSERT INTO data (sensorid,time,value) VALUES (%s,str_to_date(date_format(now(),"%%d.%%m.%%Y %%H:%%i"),"%%d.%%m.%%Y %%H:%%i"), %s)',
                    (sensorId1, counter1))
                self.cursor.execute(
                    'INSERT INTO data (sensorid,time,value) VALUES (%s,str_to_date(date_format(now(),"%%d.%%m.%%Y %%H:%%i"),"%%d.%%m.%%Y %%H:%%i"), %s)',
                    (sensorId2, counter2))
                self.cursor.execute('COMMIT')
            else:
                self.logger.debug("No database, not inserted.")
            counter1 = 0
            counter2 = 0
            #Main code goes here ...
            #Note that logger level needs to be set to logging.DEBUG before this shows up in the logs
#            logger.debug("Debug message")
#            logger.info("Info message")
#            logger.warn("Warning message")
#            logger.error("Error message")
#            time.sleep(10)

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        'setting'
        self._config = value

    @property
    def pid(self):
        return self._pid


    @property
    def nodaemon(self):
        return self._nodaemon


    def stop(self):
        try:
            pid = open(self.pid).readline()
        except IOError:
            print("Daemon already gone, or pidfile was deleted manually")
            sys.exit(1)
        print("terminating Daemon with Pid: {0}".format(pid))
        os.kill(int(pid), signal.SIGTERM)
        sys.stdout.write("Waiting...")
        while os.path.isfile(self.pid):
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(0.5)
        print("Gone")

    def reload(self):
        try:
            pid = open(self.pid).readline()
        except IOError:
            print("Daemon not running, or pidfile was deleted manually")
            sys.exit(1)
        print("Sending SIGUSR1 to Daemon with Pid: {0}".format(pid))
        os.kill(int(pid), signal.SIGUSR1)
        sys.stdout.write("Ok")

    def start(self):
        print ("start")
        self.config=self.readConfig(self._config_file)
        print ("config read")
        self.daemon = DaemonContext(pidfile=PidFile(self.pid)
                               ,signal_map={
            signal.SIGTERM: self.program_cleanup,
            signal.SIGHUP: self.terminate,
            signal.SIGUSR1: self.reload_program_config
        })
#        daemon.signal_map={
#            signal.SIGTERM: self.program_cleanup,
#            signal.SIGHUP: self.terminate,
#            signal.SIGUSR1: self.reload_program_config
#        }
        print ("daemon context")
        if self.nodaemon:
            self.daemon.detach_process = False
#            daemon.stderr = "/tmp/pulse_err.out"
#            daemon.stdout = "/tmp/pulset.out"
        try:
            self.daemon.open()
            self.createLogger()
            self.logger.debug('After open')
            self.run()
        except:
            print ("Unexpected error:", sys.exc_info()[0])
            raise

#conf_file = None
#print sys.argv[1:]
#opts, args = getopt.getopt(sys.argv[2:], "hf:")
#print opts
#print args
#for opt, arg in opts:
#    print opt,arg
#    if opt == '-h':
#        print 'read_kwh_pulse.py -f <configfile>'
#        sys.exit()
#    elif opt in ("-f"):
#        conf_file = arg

#logger = logging.getLogger("PulseReader")
#logger.setLevel(logging.DEBUG)
#formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
#handler = logging.FileHandler("/var/log/pulsereader/pulsereader.log")
#handler.setFormatter(formatter)
#logger.addHandler(handler)

#app = App(conf_file,logger)

#app.run()

#daemon_runner = runner.DaemonRunner(app)
#context = daemon.DaemonContext(
#    working_directory='/tmp',
#    umask=0o002,
#    pidfile=lockfile.FileLock('/var/run/readkwhpulse/readkwhpulse.pid'),
#    )

#context.signal_map = {
#daemon_runner.daemon_context.signal_map={
#    signal.SIGTERM: app.program_cleanup,
#    signal.SIGHUP: 'terminate',
#    signal.SIGUSR1: app.reloadConfig,
#    }

#context.files_preserve = [handler.stream]

#with context:
#    app.run()

#This ensures that the logger file handle does not get closed during daemonization
#daemon_runner.daemon_context.files_preserve=[handler.stream]
#daemon_runner.daemon_context.signal_map
#daemon_runner.do_action()


if __name__ == "__main__":
  main()
