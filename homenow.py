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

    for person in c["people"]:
        name = person["name"]
        ip = person["ip"]
        try:
            print("Looking for "+name)
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
        except:
            log_and_print("Ping for " + name + " failed, which we count as not on network")
            not_home.add(name)
        
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
        print(call)
        subprocess.call(call,shell=True)
    except:
        log_and_print("text send to " +phone_number+ " failed")

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
            mqttc.publish("alarm/homenow","No-one is Home")
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

    #react to any changes
    for person in c["people"]:
        if (person["name"] in home and noones_home):

            message = person["name"] + ' is home'
            message += "\r\nhome: "+str(home)
            message += "\r\nnot_home: "+str(not_home)
            message += "\r\ndate: "+f"{datetime.datetime.now():%Y-%m-%d}"
            message += "\r\ntime: "+str(datetime.datetime.now().time())

            log_and_print("Message:\r\n" + message)

            #noone was home now this person is! Do we need to tell anyone?
            for who_wants_to_know in c["people"]:
                if (person["name"] in who_wants_to_know["notify_if_home"]):
                    log_and_print("home = "+str(home))
                    log_and_print("sending email to " + person["name"] + " at " + person["email"])
                    send_email(person["email"],'Home Alarm System - ' + person["name"] + ' is home',message)
                    mqttc.publish("alarm/homenow","sending email to " + person["name"] + " at " + person["email"])
                    #send_text(person["phone"],message.replace("\r\n"," | "))

    #update state variables
    update_people()
    time.sleep(60)