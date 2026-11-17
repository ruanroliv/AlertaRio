/* AlertaRio — Arduino Uno / Tinkercad.
   HC-SR04: VCC=5V, GND=GND, TRIG=D9, ECHO=D10.
   Potenciometro 10k: extremos 5V/GND, cursor=A0 (simula umidade).
   LED vermelho D6 e verde D5, cada um com resistor 220 ohms em serie.
   HC-SR04 mede distancia ate a superficie; nivel=altura_do_canal-distancia.
   Nunca use este circuito academico como instrumento de emergencia. */
// Tinkercad frequentemente oferece sensor de 3 pinos (SIG em D9).
// Use 0 para HC-SR04 de 4 pinos (TRIG D9 / ECHO D10).
#define THREE_PIN_SENSOR 0
const byte TRIG = 9, ECHO = THREE_PIN_SENSOR ? 9 : 10, SOIL = A0, RED = 6, GREEN = 5;
const float CHANNEL_HEIGHT_CM = 200.0;

void setup() {
  Serial.begin(9600);
  pinMode(TRIG, OUTPUT);
  if (!THREE_PIN_SENSOR) pinMode(ECHO, INPUT);
  pinMode(RED, OUTPUT); pinMode(GREEN, OUTPUT);
}
void loop() {
  pinMode(TRIG, OUTPUT);
  digitalWrite(TRIG, LOW); delayMicroseconds(2);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  if (THREE_PIN_SENSOR) pinMode(ECHO, INPUT);
  unsigned long duration = pulseIn(ECHO, HIGH, 30000UL);
  if (duration == 0) {
    Serial.println("{\"error\":\"ultrasonic_timeout\"}");
    digitalWrite(RED, LOW); digitalWrite(GREEN, LOW);
    delay(2000); return; // Falha NAO vira leitura de nivel zero.
  }
  float distance = duration * 0.0343 / 2.0;
  float water = constrain(CHANNEL_HEIGHT_CM - distance, 0.0, CHANNEL_HEIGHT_CM);
  float soil = analogRead(SOIL) * 100.0 / 1023.0;
  bool attention = water >= 100 || soil >= 65;
  digitalWrite(RED, attention ? HIGH : LOW);
  digitalWrite(GREEN, attention ? LOW : HIGH);
  Serial.print("{\"sensor_id\":\"AR-001\",\"water_level_cm\":");
  Serial.print(water, 1);
  Serial.print(",\"soil_moisture_pct\":"); Serial.print(soil, 1);
  // Chuva e campo de entrada do backend; o circuito NAO possui pluviometro.
  Serial.print(",\"uptime_ms\":"); Serial.print(millis());
  Serial.println("}");
  delay(2000);
}
