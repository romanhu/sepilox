#!/usr/bin/python3
# encoding=utf-8


import time
import configparser
import urllib.parse
import requests
import json
import sys
import socket
import time
import datetime
import logging

URL_LOGIN = "https://mein-senec.de/auth/login"
URL_LOGOUT = "https://mein-senec.de/endkunde/logout"
URL_STATUS = "https://mein-senec.de/endkunde/api/status/getstatusoverview.php?anlageNummer=0"
STATUSDATA_KEYS = ("powergenerated", "consumption", "gridexport", "gridimport", 
"accuexport", "accuimport", "acculevel")

file_handler = logging.FileHandler(filename='/tmp/sepilox.log')
file_handler.setLevel(logging.INFO)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
handlers = [file_handler, stdout_handler]


logging.basicConfig(
    level = logging.DEBUG,
    format = '[%(asctime)s] %(levelname)s: %(message)s',
    handlers = handlers
)

logger = logging.getLogger()

def main():
    logger.debug('Started SENEC plugin')
    pluginconfig = configparser.ConfigParser()
    pluginconfig.read("REPLACEBYBASEFOLDER/config/plugins/REPLACEBYSUBFOLDER/sepilox.cfg")

    try:
        username = pluginconfig.get('SENEC', 'USERNAME')
        password = pluginconfig.get('SENEC', 'PASSWORD')
        enabled = pluginconfig.get('SENEC', 'ENABLED')
        miniservername = pluginconfig.get('SENEC', 'MINISERVER')
        virtualUDPPort = int(pluginconfig.get('SENEC', 'UDPPORT'))
    except Exception:
        logger.exception("Failed to read config")  

    loxberryconfig = configparser.ConfigParser()
    loxberryconfig.read("REPLACEBYBASEFOLDER/config/system/general.cfg")
    miniserverIP = loxberryconfig.get(miniservername, 'IPADDRESS')
	
    if enabled != "1":
        print('Plugin has been disabled')
        sys.exit(-1)

    session = requests.Session()
    session.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko'}


    req = session.post(URL_LOGIN, data = {"username": username, "password": password})
    if req.status_code != 200 or req.url != "https://mein-senec.de/endkunde/":
        logger.error("Login failed")
        sys.exit(-1)


    req = session.get(URL_STATUS)
    if req.status_code != 200:
        logger.error("Failed to get SENEC status")
        sys.exit(-1)

    senec_status = req.json()
    logger.debug(f"Got SENEC status: {senec_status}")
    lastupdated = datetime.datetime.utcfromtimestamp(senec_status["lastupdated"])
    if datetime.datetime.utcnow() - lastupdated > datetime.timedelta(seconds = 600):
        logger.error(f"SENEC status data too old ({lastupdated} UTC)")
        sys.exit(-1)
        
    
    sendudp(f"wartungNotwendig={senec_status['wartungNotwendig']}", miniserverIP, virtualUDPPort)
    sendudp(f"steuereinheitState={senec_status['steuereinheitState']}", miniserverIP, virtualUDPPort)
    for key in STATUSDATA_KEYS:
        for timecat in ("today", "now"):
            tosend = f"{key}.{timecat}={senec_status[key][timecat]}"

            sendudp(tosend, miniserverIP, virtualUDPPort)
        
    session.get(URL_LOGOUT)


def sendudp(data, destip, destport):
    logger.debug(f"Sending '{data}' to {destip}:{destport} (UDP)")
    connection = socket.socket(socket.AF_INET,     
                               socket.SOCK_DGRAM) 

    res = connection.sendto(data.encode(), (destip, destport))

    connection.close()

    # check if all bytes in resultstr were sent
    if res != len(data.encode()):
        logger(f"Sent bytes do not match - expected {len(data)} : got {res}")
        logger(f"Packet-Payload {data}")
        sys.exit(-1)




if __name__ == '__main__':
    main()
