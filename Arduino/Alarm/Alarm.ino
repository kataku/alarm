#include <ArduinoMqttClient.h>
#include <WiFi.h>
#include "arduino_secrets.h"
#include <RCSwitch.h>

///////please enter your sensitive data in the Secret tab/arduino_secrets.h
const char ssid[]     = WIFI_SSID;        // your network SSID
const char pass[]     = WIFI_PASS;    // your network password
const char host[]     = WIFI_HOST;
const char broker[]   = MQTT_ADDRESS;
int        port       = MQTT_PORT;
const char mq_user[]  = MQTT_USER;
const char mq_pass[]  = MQTT_PASS;
const char mq_topic[] = MQTT_TOPIC;
const int valuesKnowable = SENSOR_LIMIT;

int valuesKnown = 0;

unsigned long time_sent[valuesKnowable];
unsigned long value_sent[valuesKnowable];
unsigned long since_reconnect = 0;

RCSwitch mySwitch = RCSwitch();
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

void initWiFi() {
  
  WiFi.mode(WIFI_STA);
  WiFi.config(INADDR_NONE, INADDR_NONE, INADDR_NONE, INADDR_NONE);
  WiFi.setHostname(host); //define hostname
  //wifi_station_set_hostname( hostname.c_str() );
  WiFi.begin(ssid, pass);
  Serial.print("Connecting to WiFi ..");
  while (WiFi.status() != WL_CONNECTED) {
    // Wait for WIFI
  }
  Serial.println(WiFi.localIP());
  
}

void initMQTT(){
  Serial.print("Attempting to connect to the MQTT broker: ");
  Serial.println(broker);
  mqttClient.setUsernamePassword(mq_user, mq_pass);
  mqttClient.setId(mq_topic);
  
  mqttClient.connect(broker, port);
  Serial.print("Connecting to MQTT ..");
  while (!mqttClient.connected()) {
     // Wait for MQTT
  }
  Serial.println("Connected.");
}

void setup() {
  //Initialize serial and wait for port to open:
  Serial.begin(115200);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }  
  Serial.print("Serial Ready.");
  
  //setup pin for the 433 radio module
  pinMode(GPIO_NUM_27, INPUT);    
  mySwitch.enableReceive(GPIO_NUM_27);
  Serial.print("Pin Mode Set");  
  
  initWiFi();    
  initMQTT();
   
}

void check_services(){
  //recheck wifi
  if (WiFi.status() != WL_CONNECTED){
    Serial.println(WiFi.status());
    initWiFi();
  }
  //recheck MQTT - this sometimes says false when its true  
  if (mqttClient.connected()){
    since_reconnect = millis();    
  }
  if (millis() - since_reconnect > 60000){
    //try to reconnect to MQTT every 60 seconds if connected returns false
    initMQTT();
    since_reconnect = millis();
  }
}

void loop() {

  check_services();

  // call poll() regularly to allow the library to send MQTT keep alive which
  // avoids being disconnected by the broker
  mqttClient.poll();

  // call poll() regularly to allow the library to receive MQTT messages and
  // send MQTT keep alive which avoids being disconnected by the broker
  //mqttClient.poll();
  if (mySwitch.available()) {  
    Serial.print("Received ");
    Serial.print( mySwitch.getReceivedValue() );
    Serial.print(" / ");
    Serial.print( mySwitch.getReceivedBitlength() );
    Serial.print("bit ");
    Serial.print("Protocol: ");
    Serial.print( mySwitch.getReceivedProtocol() );
    Serial.print(" / ");
    Serial.println( mySwitch.getReceivedDelay() );

    unsigned long triggering_value = mySwitch.getReceivedValue();

    long since = millis() - valueLastSent(triggering_value);

    Serial.print("Millis since we sent this value: ");
    Serial.println(since);

    //the sensors send 10 repeats, we're gonna smooth that. 
    if (since > 3000){
      //trigger the send and catch failure
      if (!mqtt_send(triggering_value)){
        Serial.println("MQTT Send Failed");
        //recheck wifi and MQTT
        since_reconnect = 0;
        check_services();
        //try again but if this fails we give up
        mqtt_send(triggering_value);
      }      
    }
    mySwitch.resetAvailable();
  }
}

boolean mqtt_send(unsigned long message){
  if(mqttClient.beginMessage(mq_topic)){
    mqttClient.print(message);
    mqttClient.endMessage();
    Serial.println("message sent");    
    sentValue(message,millis());
    return true;
  }else{
    return false;
  }
}

void sentValue(long value,long time){
  //do we already have this value? Update the time.  
  for (int i = 0; i < valuesKnown; i++) {
    if (value_sent[i]==value){      
      time_sent[i]=time;
      return;
    }
  }
  //if we don't have it add it  
  time_sent[valuesKnown] = millis();
  value_sent[valuesKnown] = value;

  if (valuesKnown < valuesKnowable){
    valuesKnown++;
  }
}

unsigned long valueLastSent(long value){
  //loop till we find the value
  for (int i = 0; i < valuesKnown; i++) { 
    if (value_sent[i]==value){
      //return corrosponding time
      return time_sent[i];
    }
  }
  //didn't find it
  return 0;
}