/*
  FENG 497 - Yesil alan olay butonlari (ESP32)
  Her basista seri porta bir JSON satiri gonderir; Python paneli (Canli durum) okur.

  Buton      GPIO   Olay         Modeldeki karsiligi
  Yesil      13     arrival      gelis hizi (lambda)
  Mavi       12     start        bekleme suresi (Wq)
  Turuncu    14     end          muayene suresi (mu)
  Gri 1      27     doctor_on    aktif hekim (c)
  Gri 2      26     doctor_off   aktif hekim (c)

  Baglanti: butonun bir ucu GPIO'ya, diger ucu GND'ye (dahili pull-up kullanilir).
  Zaman damgasini Python yazar (ESP32'de saat yok).
*/

const char* DEVICE = "esp32-yesil-01";
const int PINS[] = {13, 12, 14, 27, 26};
const char* EVENTS[] = {"arrival", "start", "end", "doctor_on", "doctor_off"};
const int N = 5;
const unsigned long DEBOUNCE_MS = 40;

int lastState[N];
unsigned long lastChange[N];

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < N; i++) {
    pinMode(PINS[i], INPUT_PULLUP);
    lastState[i] = HIGH;
    lastChange[i] = 0;
  }
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  unsigned long now = millis();
  for (int i = 0; i < N; i++) {
    int s = digitalRead(PINS[i]);
    if (s != lastState[i] && now - lastChange[i] > DEBOUNCE_MS) {
      lastChange[i] = now;
      lastState[i] = s;
      if (s == LOW) {  // basildi
        Serial.print("{\"device\":\"");
        Serial.print(DEVICE);
        Serial.print("\",\"event\":\"");
        Serial.print(EVENTS[i]);
        Serial.print("\",\"ms\":");
        Serial.print(now);
        Serial.println("}");
        digitalWrite(LED_BUILTIN, HIGH);
        delay(30);
        digitalWrite(LED_BUILTIN, LOW);
      }
    }
  }
}
