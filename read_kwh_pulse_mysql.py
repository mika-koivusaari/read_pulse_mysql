#!/usr/bin/python
import logging
import time
import serial
import MySQLdb
import re
import argparse
import sys
import signal
from ConfigParser import SafeConfigParser
from ConfigParser import NoSectionError

from pep3143daemon import DaemonContext, PidFile

def main():
    print sys.argv[1:]
    parser = argparse.ArgumentParser(description="Pulse reader")

    parser.add_argument('method', choices=['start', 'stop', 'reload'])

#    subparsers = parser.add_subparsers(help='commands', dest='method')
#    subparsers.required = True

#    stop_parser = subparsers.add_parser('stop', help='Stop PulseReader')
#    stop_parser.set_defaults(method='stop')

#    start_parser = subparsers.add_parser('start', help='Start PulseReader')
#    start_parser.set_defaults(method='start')

#    reload_parser = subparsers.add_parser('reload', help='Reload configuration')
#    reload_parser.set_defaults(method='reload_config')

    parser.add_argument("--cfg", dest="cfg", action="store",
                        default="/etc/pulsereader/pulsereader.ini",
                        help="Full path to configuration")


    parser.add_argument("--pid", dest="pid", action="store",
                        default="/var/run/pulsereader/el_aap.pid",
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

    def reloadConfig(self):
        logger.debug("reload")

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
            confData['mysql'] = mysqlData

            serialData = {}
            serialData['device'] = config.get('serial', 'device')
            confData['serial'] = serialData

        except NoSectionError:
            print 'Error in '+conf_file
            exit()
        return confData

    def __init__(self, cfg, pid, nodaemon):
        self._config_file = cfg
        self._pid = pid
        self._nodaemon = nodaemon
        self.logger = logging.getLogger('PulseReader')
        #TODO move to config
        self.logger.setLevel(logging.DEBUG)

    def program_cleanup(self):
        if self.db is not None:
            self.cursor.close(

            )
            self.db.close()
        if self.ser is not None:
            self.ser.close()

    def __del__(self):
        self.program_cleanup()

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
            self.logger.debug("Open serial")
            # configure the serial connections (the parameters differs on the device you are connecting to)
            serialConfig = self.config['serial']
            self.ser = serial.Serial(
                port=serialConfig['device'],
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
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
        self.logger.debug("Run")
        self.openConnections()
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


    @property
    def pid(self):
        return self._pid


    @property
    def nodaemon(self):
        return self._nodaemon


    def quit(self):
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


    def start(self):
        print "start"
        self.readConfig(self._config_file)
        print "config read"
        daemon = DaemonContext(pidfile=PidFile(self.pid))
        print "daemon context"
        if self.nodaemon:
            daemon.detach_process = False
#        dlog = open(self.config.get('main', 'dlog'), 'w')
#        daemon.stderr = dlog
#        daemon.stdout = dlog
        print "next open"
        daemon.open()
        print "after open"
        self.run()

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
