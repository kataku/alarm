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

  while (!mqttClient.connected()) {
    if (!mqttClient.connect(broker, port)) {
      Serial.print("MQTT connection failed! Error code = ");
      Serial.println(mqttClient.connectError());          
      delay(1000);
    }else{
      Serial.println("You're connected to the MQTT broker!");
      Serial.println();
    }
    
  }

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

void loop() {
  
  //recheck wifi
  if (WiFi.status() != WL_CONNECTED){
    Serial.println(WiFi.status());
    initWiFi();
  }
  //recheck MQTT
  if (!mqttClient.connected()){
    initMQTT();
  }
  
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
      
      mqttClient.beginMessage(mq_topic);
      mqttClient.print(triggering_value);
      mqttClient.endMessage();

      sentValue(triggering_value,millis());
    }
    mySwitch.resetAvailable();
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