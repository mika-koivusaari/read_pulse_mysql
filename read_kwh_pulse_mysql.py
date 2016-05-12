#!/usr/bin/python
import logging
import time
import serial
import MySQLdb
import re
from ConfigParser import SafeConfigParser
from ConfigParser import NoSectionError


class App:

    config = None
    db = None
    ser = None

    def readConfig():
        config = SafeConfigParser()
        config.read('read_kwh_pulse_mysql.ini')
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
            print 'Error in read_kwh_pulse_mysql.ini'
            exit()
        return confData

    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/null'
        self.stderr_path = '/dev/null'
        self.pidfile_path = '/var/run/readkwhpulse/readkwhpulse.pid'
        self.pidfile_timeout = 5

        self.config = readConfig()

        # connect
        mysqlConf = config['mysql']
        self.db = MySQLdb.connect(host=mysqlConf['host'], user=mysqlConf['user'], passwd=mysqlConf['passwd'],
                             db=mysqlConf['database'])
        logger.info("Connected to MySql")
        # create a cursor
        cursor = self.db.cursor()

        # configure the serial connections (the parameters differs on the device you are connecting to)
        serialConfig = config['serial']
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
        while ser.inWaiting() > 0:
            out += ser.read(1)
        logger.info('Serial is open.')

    def run(self):
        # pulse counter
        counter1 = 0
        counter2 = 0

        # sensorid of kWh counter
        sensorId1 = 116  # MLP
        sensorId2 = 115  # total

        # input from arduino "Counters: n,n"
        inputPattern = re.compile('Counters: (\\d*),(\\d*)')
        while True:
            time.sleep(59)

            #request counter values
            ser.write('GET\n')
            out = ''
            # let's wait one second before reading output (let's give device time to answer)
            time.sleep(1)
            while ser.inWaiting() > 0:
                out += ser.read(1)
            if out != '':
                m = inputPattern.match(out)
                if m:
                    counter1 = int(m.group(1))
                    counter2 = int(m.group(2))
                else:
                    logger.warn("No count")

            logger.debug(time.strftime('%H:%M') + ' ' + str(counter1) + ' ' + str(sensorId1) + ' ' + str(counter2) + ' ' + str(sensorId2))

            cursor.execute(
                'INSERT INTO data (sensorid,time,value) VALUES (%s,str_to_date(date_format(now(),"%%d.%%m.%%Y %%H:%%i"),"%%d.%%m.%%Y %%H:%%i"), %s)',
                (sensorId1, counter1))
            cursor.execute(
                'INSERT INTO data (sensorid,time,value) VALUES (%s,str_to_date(date_format(now(),"%%d.%%m.%%Y %%H:%%i"),"%%d.%%m.%%Y %%H:%%i"), %s)',
                (sensorId2, counter2))
            cursor.execute('COMMIT')
            counter1 = 0
            counter2 = 0
            #Main code goes here ...
            #Note that logger level needs to be set to logging.DEBUG before this shows up in the logs
#            logger.debug("Debug message")
#            logger.info("Info message")
#            logger.warn("Warning message")
#            logger.error("Error message")
#            time.sleep(10)



app = App()
logger = logging.getLogger("PulseReader")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.FileHandler("/var/log/testdaemon/pulsereader.log")
handler.setFormatter(formatter)
logger.addHandler(handler)

daemon_runner = runner.DaemonRunner(app)
#This ensures that the logger file handle does not get closed during daemonization
daemon_runner.daemon_context.files_preserve=[handler.stream]
daemon_runner.do_action()



except KeyboardInterrupt:
    #  GPIO.cleanup()       # clean up GPIO on CTRL+C exit
    if log is not None:
        log.close()
# GPIO.cleanup()           # clean up GPIO on normal exit
if log is not None:
    log.close()
cursor.close()
db.close()
