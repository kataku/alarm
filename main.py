import paho.mqtt.client as mqtt
import platform
import subprocess
from subprocess import check_output
import json
import datetime
import smtplib
import time
import threading
from presence import check_presence
import os
from os.path import isfile, join
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#-------------------------------------------------------------------------------------
# INITIALISE SOME VARIABLES
#-------------------------------------------------------------------------------------
notified_last = 0
someone_is_home = False
someone_is_home_previous = False
home = set()
not_home = set()
last_exit = int(time.time()) #we're gonna startup listening for devices
last_sensor = int(time.time()) #we're gonna startup listening for devices
last_log_cleanup = None
last_homenow = time.time() #last time we heard from the homenow service (startup counts as a grace period)
homenow_silent = False
homenow_lock = threading.Lock()

#-------------------------------------------------------------------------------------
# FUNCTION DEFINITIONS
#-------------------------------------------------------------------------------------
def log_and_print(message):
    print(message)
    mqttc.publish("alarm/log",str(message))
    if ("log" in c):
        log_file = open(c['log']+f"{datetime.datetime.now():%Y-%m-%d}"+".log","a")
        log_file.write(f"{datetime.datetime.now():%Y-%m-%d}" + " | " + str(datetime.datetime.now().time()) + ": " + message+"\r\n")
        log_file.close()

    delete_old_logs()

def delete_old_logs():
    #once a day is plenty - this used to scan the whole folder on every log line
    global last_log_cleanup
    today = datetime.date.today()
    if (last_log_cleanup == today):
        return
    last_log_cleanup = today

    #hard coded for now
    path = 'logs'
    try:
        alarmlogs = [f for f in os.listdir(path) if isfile(join(path, f))]
    except OSError:
        return

    for file in alarmlogs:
        try:
            date_from_name = file.replace(".log","")[-10:]
            date = datetime.datetime.strptime(date_from_name,'%Y-%m-%d')
            if date < (datetime.datetime.now()-datetime.timedelta(365)): #keep logs for a year
                os.remove(path+"/"+file)
        except (ValueError, OSError):
            continue #not one of our logs, or already gone - never let housekeeping stop the alarm

def get_friendly_sensor_name(id):
    for sensor in c["Sensors"]:
        if (sensor['id']==id):
            return sensor['name']
    return id.replace("b'","").replace("'","")

def are_we_home():
    home, not_home, details = check_presence(c)
    mqttc.publish("alarm/homenowdebug",str(details))
    return home, not_home

def email_helper(sender_email, receiver_email, subject, message, smtp_server, smtp_port, smtp_username, smtp_password):
    # Create a multipart message
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject

    # Add body to the email
    msg.attach(MIMEText(message, "plain"))

    try:
        # Create a secure SSL/TLS connection to the SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30) #never hang the mqtt callback
        server.ehlo()
        server.starttls()
        server.ehlo()

        # Login to the SMTP server
        server.login(smtp_username, smtp_password)

        # Send the email
        server.sendmail(sender_email, receiver_email, msg.as_string())

        # Close the SMTP connection
        server.quit()

        log_and_print("Email sent successfully!")
    except Exception as e:
        log_and_print("Failed to send email. Error:" + str(e))

def send_email(email_address,subject,message):
    # Creating all the parameters
    sender_email = c['smtp_sender_email']
    receiver_email = email_address
    #we can setup a throw away gmail and set insecure apps ON for this
    smtp_server = c['smtp_server']
    smtp_port = c['smtp_port']
    smtp_username = c['smtp_username']
    smtp_password = c['smtp_password']

    # Call the function
    email_helper(sender_email, receiver_email, subject, message, smtp_server, smtp_port, smtp_username, smtp_password)

def send_text(phone_number,message):
    #( ) < > | ; & * \ ~ " '
    message=message.replace('\\','\\\\')
    message=message.replace(' ','\\ ')
    message=message.replace('(','\\(')
    message=message.replace(')','\\)')
    message=message.replace('<','\\<')
    message=message.replace('>','\\>')
    message=message.replace(';','\\;')
    message=message.replace('|','\\|')
    message=message.replace('&','\\&')
    message=message.replace('*','\\*')
    message=message.replace('~','\\~')
    message=message.replace('"','\\"')
    message=message.replace("'",'\\"')
    message=message.replace('`','\\`')
    message=message.replace('%','\\%')
    message=message.replace('¬','\\¬')

    try:
        call = 'adb shell service call isms 7 i32 1 s16 "com.android.mms" s16 "'+phone_number+'" s16 "null" s16 \''+message+'\' s16 "null" s16 "null"'
        #log_and_print(call)
        subprocess.call(call,shell=True,timeout=30) #never hang the mqtt callback
    except:
        log_and_print("text send to " +phone_number+ " failed")

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    log_and_print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    for topic in c["topics"]:
        client.subscribe(topic)

    client.subscribe("alarm/homenow")
    client.subscribe("alarm/force")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    
    #print(msg.topic)
    #print(msg.payload)

    if (str(msg.topic) == "alarm/homenow"):
        on_homenow(client, userdata, msg)
    elif(str(msg.topic) == "alarm/force"):
        on_force(client, userdata, msg)
    else:
        on_sensor(client, userdata, msg)

def on_force(client, userdata, msg):
    global notified_last
    global someone_is_home
    global someone_is_home_previous
    global last_exit
    global home
    global not_home
    global last_sensor

    message = str(msg.payload).replace("b'","").replace("b\"","").replace("'","").replace("\"","")
    
    print("message: " + message)

    if (message == "arm"):
        someone_is_home = False
        someone_is_home_previous = False
        last_exit = -c['seconds_to_check_is_home_after_exit']
        log_and_print("force armed")
    if (message == "disarm"):
        someone_is_home = True
        someone_is_home_previous = True
        last_exit = -c['seconds_to_check_is_home_after_exit']
        log_and_print("force disarmed")
    if (message == "state"):
        if (someone_is_home):
            log_and_print("state: disarmed")
        else:
            log_and_print("state: armed")
        
        log_and_print("seconds since last exit: "+str(int(time.time())-(last_exit)))
        log_and_print("seconds since last sensor: "+str(int(time.time())-(last_sensor)))

def notify_arrival(arrived, home, not_home):
    #tell whoever wants to know that these people are now home
    for person in c["people"]:
        if (person["name"] in arrived):

            message = person["name"] + ' is home'
            message += "\r\n" + "home: "+str(home)
            message += "\r\n" + "not_home: "+str(not_home)
            message += "\r\n" + "date: "+f"{datetime.datetime.now():%Y-%m-%d}"
            message += "\r\n" + "time: "+str(datetime.datetime.now().time())

            log_and_print("Message:\r\n" + message)

            for notify in c["people"]:
                if (person["name"] in notify["notify_if_home"]):

                    log_and_print("home = "+str(home))

                    if (notify["send_email"]):
                        log_and_print("sending email to " + notify["name"] + " at " + notify["email"])
                        send_email(notify["email"],'Home Alarm System - ' + person["name"] + ' is home',message)

                    if (notify["send_text"]):
                        log_and_print("sending text to " + notify["name"] + " at " + notify["phone"])
                        send_text(notify["phone"],message.replace("\r\n"," | "))

def notify_everyone(subject, message):
    #email/text everyone who gets sensor alerts
    for person in c["people"]:
        if (person["send_email"]):
            send_email(person["email"], subject, message)
        if (person["send_text"]):
            send_text(person["phone"], message.replace("\r\n"," | "))

def homenow_watchdog():
    #runs in its own thread: callbacks only fire when messages arrive, so silence needs a timer
    global homenow_silent
    limit = c.get("homenow_silent_seconds", 300)
    while True:
        time.sleep(30)
        try:
            silent_for = int(time.time() - last_homenow)
            with homenow_lock:
                alert = (silent_for > limit and not homenow_silent)
                if alert:
                    homenow_silent = True
            if alert:
                message = "No homenow update for " + str(silent_for//60) + " minutes. The alarm may not arm when you leave until the homenow service is back."
                log_and_print("WARNING: " + message)
                notify_everyone("Home Alarm System - homenow silent", message)
        except Exception as e:
            print("homenow watchdog error: " + repr(e))

def parse_homenow(payload):
    #homenow publishes a JSON list of names, e.g. ["Leon", "Chrissy"] ([] = no-one home)
    text = payload.decode("utf-8", errors="replace").strip()
    try:
        names = json.loads(text)
        if isinstance(names, list):
            return {str(n) for n in names}
    except ValueError:
        pass

    #older format: "set()" or "{'Leon', 'Chrissy'}" - keeps things working while the services restart
    if text in ("", "set()"):
        return set()
    return {n.strip().strip("'\"") for n in text.strip("{}").split(",") if n.strip()}

def on_homenow(client, userdata, msg):
    global last_exit
    global home
    global not_home
    global someone_is_home
    global someone_is_home_previous
    global last_homenow
    global homenow_silent
    since = int(time.time()-last_exit)

    last_homenow = time.time() #any message counts as a sign of life

    with homenow_lock:
        recovered = homenow_silent
        homenow_silent = False
    if (recovered):
        log_and_print("homenow is back")
        notify_everyone("Home Alarm System - homenow is back", "homenow updates have resumed.")

    names = parse_homenow(msg.payload)

    #update home and not home when homenow fires (whole-name match, not substring)
    home = set()
    not_home = set()

    for person in c['people']:
        if person["name"] in names:
            home.add(person["name"])
        else:
            not_home.add(person["name"])

    #has someoone used an exit recently enough?
    if (since < c['seconds_to_check_is_home_after_exit'] ):

        log_and_print("seconds since last exit: " + str(since) + " \r\nsomeone_is_home: " + str(someone_is_home) + "\r\nsomeone_is_home_previous: " + str(someone_is_home_previous))
        
        change = False
        latest_is_home = len(home) > 0

        if someone_is_home_previous == latest_is_home:
            if (someone_is_home != latest_is_home):
                
                was_home = someone_is_home
                someone_is_home = latest_is_home
                change = True

                #arrival missed by the ping at the door (phone not on wifi yet) - notify now
                if (someone_is_home and not was_home):
                    log_and_print("Late arrival detected via homenow")
                    notify_arrival(home, home, not_home)

                if (someone_is_home):
                    log_and_print("Someone was home 2 minutes in a row, disarming")
                else:
                    log_and_print("No-one was home 2 minutes in a row, arming")
        else:
            someone_is_home_previous = latest_is_home
            change = True
            
            if (someone_is_home_previous):
                log_and_print("someone was home for 1 minute")
            else:
                log_and_print("No-one was home for 1 minute")
                
        if (change):
            log_and_print("Updated:\r\nsomeone_is_home: " + str(someone_is_home) + "\r\nsomeone_is_home_previous: " + str(someone_is_home_previous))

def on_sensor(client, userdata, msg):

    global notified_last
    global someone_is_home
    global someone_is_home_previous
    global last_exit
    global home
    global not_home
    global last_sensor

    sensor_id = str(msg.payload).replace("b'","").replace("b\"","").replace("'","")
    sensor_name = get_friendly_sensor_name(sensor_id)

    if (sensor_id==sensor_name):
        log_and_print(sensor_id + " is not a registered sensor")
        return
    
    last_sensor = int(time.time())
    log_and_print(msg.topic+" detected "+ sensor_name)

    is_exit = False

    #is this an exit sensor
    for exit_sensor in c["exits"]:
        if (exit_sensor["id"]==sensor_id):
            log_and_print("Sensor is an Exit listening to homenow for "+str(c['seconds_to_check_is_home_after_exit'])+" seconds")
            is_exit = True
            break

    if (is_exit):
        last_exit = time.time() #record the last time an exit was triggered
        home,not_home = are_we_home() #do a fresh ping
        
    #no-one was home but now someone is - Notfy folks of their arrival home where relevant
    if (is_exit and someone_is_home is False and len(home)>0):
        log_and_print("Someone is now home!")
        # we're gonna disarm right away if phone found to prevent false alarms
        someone_is_home = True
        someone_is_home_previous = True

        notify_arrival(home, home, not_home)

    #make up and MQTT the message anyway
    message = "Source: " + msg.topic
    message += "\r\nSensor: "+ sensor_name
    message += "\r\nhome: "+set_to_str(home)
    message += "\r\nnot_home: "+set_to_str(not_home)
    message += "\r\ndate: "+f"{datetime.datetime.now():%Y-%m-%d}"
    message += "\r\ntime: "+str(datetime.datetime.now().time())

    log_and_print("Message:\r\n" + message)
    
    #someone_is_home to trying to avoid triggers when no-ones opened an exit
    if (someone_is_home is False):
        since = int(time.time()-notified_last)
        if (since > c['seconds_before_rearm'] ):

            log_and_print("No-ones home, notifying about sensor:")
            log_and_print("since last notification = " + str(since))
            notified_last = time.time()

            for person in c["people"]:

                if (person["send_email"]):
                    log_and_print("sending email to "+person["name"] + " at " + person["email"])
                    send_email(person["email"],'Home Alarm System - Sensor Triggered',message)

                if (person["send_text"]):
                    log_and_print("sending text to "+ person["name"] + " at " + person["phone"])
                    send_text(person["phone"],message.replace("\r\n"," | "))
        else:
            log_and_print("No-ones home but we notified "+str(since)+" seconds ago, we rearm in "+str(c['seconds_before_rearm']-since)+" seconds")

def set_to_str(a):
    a = str(a)
    a = a.replace("{","")
    a = a.replace("}","")
    a = a.replace("'","")
    return a

#-------------------------------------------------------------------------------------
# EXECUTION BEGINS HERE
#-------------------------------------------------------------------------------------

with open('config.json') as json_data:
    c = json.load(json_data)
    json_data.close()

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.username_pw_set(username=c["username"],password=c["password"])
log_and_print("Connecting...")
mqttc.connect(c["server"], 1883, 60)

notified_last = -c['seconds_before_rearm']

#decide if we should startup disarmed
home,not_home = are_we_home()
if (len(home) > 0):
    someone_is_home = True
    someone_is_home_previous = True

threading.Thread(target=homenow_watchdog, daemon=True).start()

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting. Kept on the main thread on purpose: if a callback raises,
# the process exits and systemd restarts it (loop_start() would silently lose the thread).
mqttc.loop_forever()