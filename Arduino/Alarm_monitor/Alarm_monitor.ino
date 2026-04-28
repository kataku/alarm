#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <PubSubClient.h>
#include <ESP8266WiFi.h>
#include <Preferences.h>
#include "arduino_secrets.h"

///////please enter your sensitive data in the Secret tab/arduino_secrets.h
const char ssid[]     = WIFI_SSID;        // your network SSID
const char pass[]     = WIFI_PASS;    // your network password
const char host[]     = WIFI_HOST;
const char broker[]   = MQTT_ADDRESS;
int        port       = MQTT_PORT;
const char mq_user[]  = MQTT_USER;
const char mq_pass[]  = MQTT_PASS;
const char mq_topics[] = MQTT_TOPICS;
const int valuesKnowable = SENSOR_LIMIT;

unsigned long since_reconnect = 0;
unsigned long reset_after = 86400000;//24hrs in millis
unsigned long message_shown_at = 0;

int sensorListSize = 28;
int ids[28];
String names[28];
bool armed;
bool triggered;

Preferences preferences;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels

// Declaration for SSD1306 display connected using I2C
#define OLED_RESET     -1 // Reset pin
#define SCREEN_ADDRESS 0x3C

//D5=GPIO12=SCL
//D6=GPIO14=SDA
#define I2C_SCL 12
#define I2C_SDA 14

#define D0 16
#define D1 5
#define D2 4
#define D3 0
#define D5 14
#define D6 12
#define D7 13
#define D8 15

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message recieved [");
  Serial.print(topic);
  Serial.print("] ");

  char buf[length + 1];
  memcpy(buf, payload, length);
  buf[length] = '\0';
  int x = atoi(buf);

  //int x = atoi ((const char*)payload);  
  Serial.print(x);

  Serial.print(" Length > ");

  Serial.println(length);
  
  //showMessage(String(x));

  Serial.print("Checking ID against list of size ");
  Serial.println(sensorListSize);
  for(int i=0;i<sensorListSize;i++){
    //Serial.print("Checking ID ");
    //Serial.print(i);
    //Serial.print(" > ");
    //Serial.print(ids[i]);
    //Serial.print(" == ");
    //Serial.println(x);
    if (ids[i]==x){
      Serial.println("sensor id in list");
      Serial.print("Armed = ");
      Serial.println(armed);
      if (armed){
        Serial.println(names[i]);
        digitalWrite(D8, HIGH);
        showMessage(names[i]);
        triggered = true;
      }
    }
  }
}

void dismissMessage(){
  display.clearDisplay();
  display.display();
}

void loop() {
  if (millis() > reset_after){ //default to once a day, found that sometimes they just get stuck and this is a naff but effective fix.
    Serial.println("resetting");
    ESP.restart();
  }

  if ( millis() - message_shown_at > 5000 && message_shown_at != 0){
    dismissMessage();
    message_shown_at = 0;
  }

  //arm or disarm
  if(digitalRead(D0) == HIGH){
    digitalWrite(D8, LOW);
    preferences.begin("alarm", false);
    if (armed){
      armed = false;
      preferences.putBool("armed", false);
      Serial.println("Disabled");
      showMessage("Disabled");
    }else{
      armed = true;
      preferences.putBool("armed", true);
      Serial.println("Enabled");
      showMessage("Enabled");
    }
    message_shown_at = millis();
    preferences.end();
    delay(1000); //debounce
  }
  //stop buzzer and dismiss
  if(digitalRead(D1) == HIGH){    
    triggered = false;
    digitalWrite(D8, LOW);
    dismissMessage();
  }  
  //stop buzzer but don't dismiss
  if(digitalRead(D2) == HIGH){        
    digitalWrite(D8, LOW);
  }

  check_services();

  //call poll() regularly to allow the library to send MQTT keep alives which
  // avoids being disconnected by the broker
  mqttClient.loop(); //call loop

}

void setup() {  

  //D3 D5 D6 are always high, these pins work with pull down
  pinMode(D0, INPUT);
  pinMode(D1, INPUT);
  pinMode(D2, INPUT);
  pinMode(D8, OUTPUT);
  digitalWrite(D8, LOW); 

  triggered = false;

  preferences.begin("alarm", true);
  armed = preferences.getBool("armed", false);  
  preferences.end();

  //Initialize serial and wait for port to open:
  Serial.begin(115200);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }
  Serial.println("Serial Ready.");
  
  initWiFi();
  initMQTT();
  
  Wire.begin(I2C_SDA, I2C_SCL);
  // initialize the OLED object
  if(!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;); // Don't proceed, loop forever
  }

  // Clear the buffer.
  display.clearDisplay();
  if (armed){
    showMessage("Enabled");
  }else{
    showMessage("Disabled");
  }

  message_shown_at = millis();

  ids[0]=2372542;
  ids[1]=12300311;
  ids[2]=6908350;
  ids[3]=6129598;
  ids[4]=6697406;
  ids[5]=6895294;
  ids[6]=14867079;
  ids[7]=6944190;
  ids[8]=15267975;
  ids[9]=15267971;
  ids[10]=2066839;
  ids[11]=2066835;
  ids[12]=2517919;
  ids[13]=2517911;
  ids[14]=2517907;
  ids[15]=7751870;
  ids[16]=735639;
  ids[17]=6479294;
  ids[18]=6253758;
  ids[19]=2070423;
  ids[20]=1742490;
  ids[21]=1742483;
  ids[22]=15478407;
  ids[23]=15478403;
  ids[24]=735635;
  ids[25]=2070419;
  ids[26]=2070419;
  ids[27]=14867075;
  //ids[28]=12015110;

  names[0]="Test Sensor";
  names[1]="Lab Bifolds";
  names[2]="Lab Window Top Left";
  names[3]="Lab Window Top Right";
  names[4]="Lab Window Bottom left";
  names[5]="Lab Window Bottom Right";        
  names[6]="Kitchen Window";
  names[7]="Conservatory Kitchen Door";
  names[8]="Conservatory Window left";        
  names[9]="Conservatory Window left Tamper";
  names[10]="Conservatory Window Right";
  names[11]="Conservatory Window Right Tamper";
  names[12]="Conservatory Door";        
  names[13]="Conservatory Door";
  names[14]="Conservatory Door Tamper";        
  names[15]="Lounge Bifolds";
  names[16]="Lounge Window 1";
  names[17]="Lounge Window 2";
  names[18]="Lounge Window 3";
  names[19]="Lounge Window 4";
  names[20]="Front Door";
  names[21]="Front Door Tamper";
  names[22]="Toilet Window";
  names[23]="Toilet Window Tamper";
  names[24]="Lounge Window 1 Tamper";        
  names[25]="Lounge Window 4 Tamper";
  names[26]="Lounge Window 4 Tamper";
  names[27]="kitchen Window tamper";
  //names[28]="IR Sensor";
}

void initWiFi() {
  
  Serial.println("WiFi Mode");
  WiFi.mode(WIFI_STA);
  WiFi.hostname("Alarm Reciever");
  WiFi.setPhyMode(WIFI_PHY_MODE_11G); //8266
  delay(1000);
  //wifi_station_set_hostname( hostname.c_str() );
  Serial.println("WiFi Begin");
  WiFi.begin(ssid, pass);
  Serial.print("Connecting to WiFi ...");
  
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(1000);
  }
  Serial.println(WiFi.localIP());  
}

void initMQTT(){
  Serial.print("Attempting to connect to the MQTT broker: ");
  Serial.println(broker);

  mqttClient.setServer(broker, port);
  mqttClient.setCallback(callback);

  while (mqttClient.connected()==false) {
      Serial.print("Attempting to connect to the MQTT broker: ");
      Serial.println(broker);
 
    //client id, user, pass, NULL,NULL,NULL,NULL,false
    if (!mqttClient.connect(mq_topics,mq_user,mq_pass,NULL,NULL,NULL,NULL,false)) {
      Serial.print("MQTT connection failed! Error code = ");
      Serial.println(mqttClient.state());
      Serial.print("failed, rc=");
      Serial.println(" try again in 5 seconds");
      delay(5000);
    } else {
      Serial.println("Connected to the MQTT broker!");            
    }    
    //subscribe TO TOPICS
    //http://www.steves-internet-guide.com/using-arduino-pubsub-mqtt-client/
    char topicsCopy[strlen(mq_topics) + 1];
    strcpy(topicsCopy, mq_topics);
    char *p = topicsCopy;
    char *str;
    while ((str = strtok_r(p, ";", &p)) != NULL){ // delimiter is the semicolon
      Serial.print(" Subscribed To: ");
      Serial.println(str);
      mqttClient.subscribe(str);
    }
  }//end while  

}

void check_services(){
  //recheck wifi
  if (WiFi.status() != WL_CONNECTED){
    Serial.print("WIFI NOT CONNECTED!: ");
    Serial.println(WiFi.status());
    initWiFi();
  }

  //recheck MQTT - this sometimes says false when its true (switched lib to avoid issue but keeping this logic as a failover) 
  if (mqttClient.connected()){
    since_reconnect = millis();
  }else{
    Serial.print("MQTT NOT CONNECTED!: ");
  }
  if (millis() - since_reconnect > 60000){
    //try to reconnect to MQTT every 60 seconds if connected returns false
    initMQTT();
    since_reconnect = millis();
  }
}

void showMessage(const String& message){
  display.clearDisplay();
  // Display Text
  display.setTextSize(2);
  display.setTextColor(WHITE);
  display.setCursor(0,0);  
  if (message.indexOf(' ')==-1){    
    display.println(message);
  }else{
    display.println(message.substring(0, message.indexOf(' ')));    
    display.println(message.substring(message.indexOf(' ') + 1));   
  }
  display.display(); 
}