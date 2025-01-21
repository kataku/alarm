import paho.mqtt.client as mqtt
import platform
import subprocess
from subprocess import check_output
import json
import datetime
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#-------------------------------------------------------------------------------------
# FUNCTION DEFINITIONS
#-------------------------------------------------------------------------------------
def log_and_print(message):
    print(message)
    if ("homelog" in c):
        log_file = open(c['homelog']+f"{datetime.datetime.now():%Y-%m-%d}"+".log","a")
        log_file.write(f"{datetime.datetime.now():%Y-%m-%d}" + " | " + str(datetime.datetime.now().time()) + ": " + message+"\r\n")
        log_file.close()

def are_we_home():

    home = set()
    not_home = set()
    retries = 4

    for person in c["people"]:
        name = person["name"]
        ip = person["ip"]
        try:
            print("Looking for "+name)
            if ("Linux" in str(platform.system())):
                response =  str(subprocess.Popen(['ping', '-c '+str(retries), ip], stdout=subprocess.PIPE).communicate()[0])
            else:
                response = str(check_output(f"ping -n {retries} {ip}"))

            mqttc.publish("alarm/homenowdebug",str(response))

            if response.count("Destination host unreachable")==retries or "0 received" in response or 'Request timed out.' in response:
                #log_and_print(f"DOWN {ip} Ping Unsuccessful, Host is DOWN.")
                not_home.add(name)
            else:
                #log_and_print(f"UP {ip} Ping Successful, Host is UP!")
                home.add(name)
        except:
            log_and_print("Ping for " + name + " failed, which we count as not on network")
            not_home.add(name)
        
    return home, not_home

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    log_and_print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.

def update_people():
    global noones_home
        
    if (len(home)==0):
        if (not noones_home):
            log_and_print("No-one is Home")            
        noones_home = True
    else:        
        noones_home = False

    for person in c["people"]:
        if (person["name"] in home):
            person["home"] = True
        else:
            person["home"] = False

#-------------------------------------------------------------------------------------
# EXECUTION BEGINS HERE
#-------------------------------------------------------------------------------------

with open('config.json') as json_data:
    c = json.load(json_data)
    json_data.close()

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.on_connect = on_connect

mqttc.username_pw_set(username=c["username"],password=c["password"])
log_and_print("Connecting...")
mqttc.connect(c["server"], 1883, 60)

#set initial state
home,not_home = are_we_home()
noones_home=False
update_people()

while(1):

    #check for phones by ip
    home,not_home = are_we_home()
    mqttc.publish("alarm/homenow",str(home))
    print("home = "+str(home))

    #update state variables
    update_people()
    time.sleep(60)