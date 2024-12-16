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
notified_last = 0.0

def log_and_print(message):
    print(message)
    if ("log" in c):
        log_file = open(c['log']+f"{datetime.datetime.now():%Y-%m-%d}"+".log","a")
        log_file.write(f"{datetime.datetime.now():%Y-%m-%d}" + " | " + str(datetime.datetime.now().time()) + ": " + message+"\r\n")
        log_file.close()

def get_friendly_sensor_name(id):
    for sensor in c["Sensors"]:
        if (sensor['id']==id):
            return sensor['name']
    return id.replace("b'","").replace("'","")

def are_we_home():

    home = set()
    not_home = set()

    for person in c["people"]:
        name = person["name"]
        ip = person["ip"]

        log_and_print("Looking for "+name)
        if ("Linux" in str(platform.system())):
            response =  str(subprocess.Popen(['ping', '-c 2', ip], stdout=subprocess.PIPE).communicate()[0])
        else:
            response = str(check_output(f"ping -n 2 {ip}"))

        if "Destination host unreachable" in response or "0 received" in response or 'Request timed out.' in response:
            #log_and_print(f"DOWN {ip} Ping Unsuccessful, Host is DOWN.")
            not_home.add(name)
        else:
            #log_and_print(f"UP {ip} Ping Successful, Host is UP!")
            home.add(name)

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
        server = smtplib.SMTP(smtp_server, smtp_port)
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
    sender_email = email_address
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
            
    call = 'adb shell service call isms 7 i32 1 s16 "com.android.mms" s16 "'+phone_number+'" s16 "null" s16 \''+message+'\' s16 "null" s16 "null"'
    print(call)
    #subprocess.call(call,shell=True)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    log_and_print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    for topic in c["topics"]:
        client.subscribe(topic)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    
    global notified_last

    sensor_id = str(msg.payload).replace("b'","").replace("'","")
    sensor_name = get_friendly_sensor_name(sensor_id)

    if (sensor_id==sensor_name):
        log_and_print(sensor_id + " is not a registered sensor")
        return
    
    log_and_print(msg.topic+" detected "+ sensor_name)
    home,not_home = are_we_home()

    message = "Source: " + msg.topic
    message += "\r\nSensor: "+ sensor_name
    message += "\r\nhome: "+str(home)
    message += "\r\nnot_home: "+str(not_home)
    message += "\r\ndate: "+f"{datetime.datetime.now():%Y-%m-%d}"
    message += "\r\ntime: "+str(datetime.datetime.now().time())

    log_and_print("Message:\r\n" + message)
    
    #for person in c["people"]:
    #    if (person["send_email"]):
    #        log_and_print("sending email to "+person["email"])
    #        send_email(person["email"],'Home Alarm System - Sensor Triggered',message)
    
    since = int(time.time()-notified_last)

    if (since > c['seconds_before_rearm'] ):
        print("fake notification")
        notified_last = time.time()
    else:
        log_and_print("we notified "+str(since)+" seconds ago, we rearm in "+str(c['seconds_before_rearm']-since)+" seconds")

    if (len(home)==0 and 1==0):
        since = int(time.time()-notified_last)
        if (since > c['seconds_before_rearm'] ):
            notified_last = time.time()
            log_and_print("notified_last = " + str(notified_last))
            for person in c["people"]:

                if (person["send_email"]):
                    log_and_print("sending email to "+person["email"])
                    send_email(person["email"],'Home Alarm System - Sensor Triggered',message)

                if (person["send_text"]):
                    log_and_print("sending text to: "+person["phone"])
                    send_text(person["phone"],message.replace("\r\n"," | "))
        else:
            log_and_print("we notified "+str(since)+" seconds ago, we rearm in "+str(c['seconds_before_rearm']-since)+" seconds")
   
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

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
mqttc.loop_forever()