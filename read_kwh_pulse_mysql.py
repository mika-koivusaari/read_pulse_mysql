#!/usr/bin/python
import time
import serial
import MySQLdb
import re
from ConfigParser import SafeConfigParser
from ConfigParser import NoSectionError

def readConfig():
  config = SafeConfigParser()
  config.read('read_kwh_pulse_mysql.ini')
  confData={}
  try:
    mysqlData={}
    mysqlData['host'] = config.get('mysql','host')
    mysqlData['user'] = config.get('mysql','user')
    mysqlData['passwd'] = config.get('mysql','passwd')
    mysqlData['database'] = config.get('mysql','database')
    confData['mysql'] = mysqlData

    serialData={}
    serialData['device'] = config.get('serial','device')
    confData['serial'] = serialData

  except NoSectionError:
    print 'Error in read_kwh_pulse_mysql.ini'
    exit()
  return confData

#pulse counter
counter1=0
counter2=0
#logfile name
log=None
#current day, needed to close old log and open new on midnight
day=''
#sensorid of kWh counter
sensorId1=116 #MLP
sensorId2=115 #total

inputPattern=re.compile('Counters: (\\d*),(\\d*)')

config = readConfig()

# connect
mysqlConf=config['mysql']
db = MySQLdb.connect(host=mysqlConf['host'], user=mysqlConf['user'], passwd=mysqlConf['passwd'],db=mysqlConf['database'])
# create a cursor
cursor = db.cursor()
print 'Connected to MySql'

# configure the serial connections (the parameters differs on the device you are connecting to)
serialConfig=config['serial']
ser = serial.Serial(
	port=serialConfig['device'],
	baudrate=9600,
	parity=serial.PARITY_NONE,
	stopbits=serial.STOPBITS_ONE,
	bytesize=serial.EIGHTBITS
)

#ser.open()
ser.isOpen()
print 'Serial is open.'
#Wait for a second if device sends some boot message, and then empty buffer
time.sleep(1)
while ser.inWaiting() > 0:
  out += ser.read(1)

try:
  while True:
    time.sleep(59)

    ser.write('GET\n')
    out = ''
    # let's wait one second before reading output (let's give device time to answer)
    time.sleep(1)
    while ser.inWaiting() > 0:
        out += ser.read(1)
    if out != '':
#      print ">>" + out
      m=inputPattern.match(out)
      if m:
#        print 'count1 =',m.group(1),' count2=',m.group(2)
        counter1=int(m.group(1))
        counter2=int(m.group(2))
      else:
        print 'no count, error'

    print time.strftime('%H:%M')+' '+str(counter1)+' '+str(sensorId1)+' '+str(counter2)+' '+str(sensorId2)


#    if day!=time.strftime('%d'):
#      if log is not None:
#        log.close()
#      logname='mlp_energy_'+time.strftime('%Y%m%d')+'.log'
#      day=time.strftime('%d')
#      log=open(logname,'a')

#    log.write(time.strftime('%H:%M')+' '+str(counter)+'\n')

    cursor.execute('INSERT INTO data (sensorid,time,value) VALUES (%s,str_to_date(date_format(now(),"%%d.%%m.%%Y %%H:%%i"),"%%d.%%m.%%Y %%H:%%i"), %s)',(sensorId1,counter1))
    cursor.execute('INSERT INTO data (sensorid,time,value) VALUES (%s,str_to_date(date_format(now(),"%%d.%%m.%%Y %%H:%%i"),"%%d.%%m.%%Y %%H:%%i"), %s)',(sensorId2,counter2))
    cursor.execute('COMMIT')
    counter1=0
    counter2=0
#    log.flush()
#    os.fsync(log.fileno())
#    print time.strftime('%H:%M')+' '+str(counter1)+' '+str(sensorId1)+' '+str(counter2)+' '+str(sensorId2)

except KeyboardInterrupt:
#  GPIO.cleanup()       # clean up GPIO on CTRL+C exit
  if log is not None:
    log.close()
#GPIO.cleanup()           # clean up GPIO on normal exit
if log is not None:
  log.close()
cursor.close()
db.close()
