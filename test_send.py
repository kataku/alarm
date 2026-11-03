import platform
import subprocess
from subprocess import check_output
import json
import datetime
import smtplib
import time
from presence import check_presence
import sms
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

with open('config.json') as json_data:
    c = json.load(json_data)
    json_data.close()

def are_we_home():
    home, not_home, details = check_presence(c)
    return home, not_home

def set_to_str(a):
    a = str(a)
    a = a.replace("{","")
    a = a.replace("}","")
    a = a.replace("'","")
    return a

def log_and_print(message):
    print(message)
    #mqttc.publish("alarm/log",str(message))
    if ("log" in c):
        log_file = open(c['log']+f"{datetime.datetime.now():%Y-%m-%d}"+".log","a")
        log_file.write(f"{datetime.datetime.now():%Y-%m-%d}" + " | " + str(datetime.datetime.now().time()) + ": " + message+"\r\n")
        log_file.close()

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
    sms.send_text(phone_number, message, log=log_and_print)

home,not_home = are_we_home()

message = "Source: " + "test_send.py"
message += "\r\nSensor: "+ " Test Message"
message += "\r\nhome: "+set_to_str(home)
message += "\r\nnot_home: "+set_to_str(not_home)
message += "\r\ndate: "+f"{datetime.datetime.now():%Y-%m-%d}"
message += "\r\ntime: "+str(datetime.datetime.now().time())

person = c["people"][0]

if (person["send_email"]):
    log_and_print("sending email to "+person["name"] + " at " + person["email"])
    send_email(person["email"],'Home Alarm System - Sensor Triggered',message)

if (person["send_text"]):
    log_and_print("sending text to "+ person["name"] + " at " + person["phone"])
    send_text(person["phone"],message.replace("\r\n"," | "))
