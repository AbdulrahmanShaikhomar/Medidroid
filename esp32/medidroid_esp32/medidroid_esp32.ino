#include <WiFi.h>
#include <WebServer.h>
#include <esp_system.h>
#include "drive_mixing.h"

#define L_RPWM 25
#define L_LPWM 26
#define R_RPWM 27
#define R_LPWM 14

#define ENC_L_A 18
#define ENC_L_B 19
#define ENC_R_A 32
#define ENC_R_B 33

#define US_TRIG_PIN 21
#define US_ECHO_PIN 22
#define LED_OBS_SEEN_PIN 4
#define LED_OBS_WARN_PIN 5
#define LED_OBS_STOP_PIN 13

#define RESET_LED_PIN 2

const char* apSsid = "ESP32-Car";
const char* apPassword = "12345678";

WebServer server(80);

enum ObstacleState {
  OBSTACLE_CLEAR,
  OBSTACLE_SEEN,
  OBSTACLE_WARNING,
  OBSTACLE_STOP,
  OBSTACLE_SENSOR_ERROR
};

MotorState state = STOPPED;

int motorSpeed = 130;
int leftMotorTrimPercent = 115;
int rightMotorTrimPercent = 100;

volatile long leftTicks = 0;
volatile long rightTicks = 0;

unsigned long lastEncoderReport = 0;
unsigned long lastPiCommand = 0;
unsigned long lastUltrasonicReadMs = 0;

const bool PI_TIMEOUT_ENABLED = false;
const unsigned long PI_TIMEOUT_MS = 1000;
const unsigned long ULTRASONIC_INTERVAL_MS = 75;
const unsigned long ULTRASONIC_TIMEOUT_US = 30000;
const long OBSTACLE_SEEN_CM = 200;
const long OBSTACLE_WARNING_CM = 80;
const long OBSTACLE_STOP_CM = 35;

String serialBuffer = "";
int currentLeftPWM = 0;
int currentRightPWM = 0;
long lastDistanceCm = -1;
ObstacleState obstacleState = OBSTACLE_SENSOR_ERROR;

long sortAndPickMedian(long a, long b, long c) {
  if (a > b) {
    long t = a;
    a = b;
    b = t;
  }
  if (b > c) {
    long t = b;
    b = c;
    c = t;
  }
  if (a > b) {
    long t = a;
    a = b;
    b = t;
  }
  return b;
}

const char* obstacleStateLabel(ObstacleState s) {
  switch (s) {
    case OBSTACLE_CLEAR:
      return "Clear";
    case OBSTACLE_SEEN:
      return "Seen";
    case OBSTACLE_WARNING:
      return "Warning";
    case OBSTACLE_STOP:
      return "Stop";
    case OBSTACLE_SENSOR_ERROR:
    default:
      return "Sensor Error";
  }
}

void updateObstacleLeds() {
  digitalWrite(LED_OBS_SEEN_PIN, obstacleState == OBSTACLE_SEEN ? HIGH : LOW);
  digitalWrite(LED_OBS_WARN_PIN, obstacleState == OBSTACLE_WARNING ? HIGH : LOW);
  digitalWrite(LED_OBS_STOP_PIN, obstacleState == OBSTACLE_STOP ? HIGH : LOW);
}

long readUltrasonicOnceCm() {
  digitalWrite(US_TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(US_TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(US_TRIG_PIN, LOW);

  unsigned long durationUs = pulseIn(US_ECHO_PIN, HIGH, ULTRASONIC_TIMEOUT_US);
  if (durationUs == 0) {
    return -1;
  }

  long distanceCm = (long)(durationUs / 58UL);
  if (distanceCm < 2 || distanceCm > 400) {
    return -1;
  }

  return distanceCm;
}

long readUltrasonicMedianCm() {
  long s1 = readUltrasonicOnceCm();
  delay(5);
  long s2 = readUltrasonicOnceCm();
  delay(5);
  long s3 = readUltrasonicOnceCm();

  int validCount = 0;
  long values[3];
  if (s1 >= 0) values[validCount++] = s1;
  if (s2 >= 0) values[validCount++] = s2;
  if (s3 >= 0) values[validCount++] = s3;

  if (validCount == 0) {
    return -1;
  }
  if (validCount == 1) {
    return values[0];
  }
  if (validCount == 2) {
    return (values[0] + values[1]) / 2;
  }

  return sortAndPickMedian(values[0], values[1], values[2]);
}

void updateUltrasonic() {
  if (millis() - lastUltrasonicReadMs < ULTRASONIC_INTERVAL_MS) {
    return;
  }

  lastUltrasonicReadMs = millis();
  lastDistanceCm = readUltrasonicMedianCm();

  if (lastDistanceCm < 0) {
    obstacleState = OBSTACLE_SENSOR_ERROR;
  } else if (lastDistanceCm <= OBSTACLE_STOP_CM) {
    obstacleState = OBSTACLE_STOP;
  } else if (lastDistanceCm <= OBSTACLE_WARNING_CM) {
    obstacleState = OBSTACLE_WARNING;
  } else if (lastDistanceCm <= OBSTACLE_SEEN_CM) {
    obstacleState = OBSTACLE_SEEN;
  } else {
    obstacleState = OBSTACLE_CLEAR;
  }

  updateObstacleLeds();
}

void IRAM_ATTR leftEncoderISR() {
  if (digitalRead(ENC_L_A) == digitalRead(ENC_L_B)) {
    leftTicks++;
  } else {
    leftTicks--;
  }
}

void IRAM_ATTR rightEncoderISR() {
  if (digitalRead(ENC_R_A) == digitalRead(ENC_R_B)) {
    rightTicks++;
  } else {
    rightTicks--;
  }
}

void stopAll() {
  currentLeftPWM = 0;
  currentRightPWM = 0;
  ledcWrite(L_RPWM, 0);
  ledcWrite(L_LPWM, 0);
  ledcWrite(R_RPWM, 0);
  ledcWrite(R_LPWM, 0);
}

void applyRawPWM(int lPWM, int rPWM) {
  const bool RIGHT_MOTOR_INVERTED = true;

  lPWM = constrain(lPWM, -255, 255);
  rPWM = constrain(rPWM, -255, 255);

  lPWM = constrain((int)(((long)lPWM * leftMotorTrimPercent) / 100), -255, 255);
  rPWM = constrain((int)(((long)rPWM * rightMotorTrimPercent) / 100), -255, 255);

  if (RIGHT_MOTOR_INVERTED) {
    rPWM = -rPWM;
  }

  ledcWrite(L_RPWM, lPWM >= 0 ? 0 : -lPWM);
  ledcWrite(L_LPWM, lPWM >= 0 ? lPWM : 0);
  ledcWrite(R_RPWM, rPWM >= 0 ? 0 : -rPWM);
  ledcWrite(R_LPWM, rPWM >= 0 ? rPWM : 0);
}

void updateStateDrivenPWM() {
  DriveMix targetMix = computeDriveMix(state, motorSpeed);

  currentLeftPWM = targetMix.leftPWM;
  currentRightPWM = targetMix.rightPWM;

  applyRawPWM(currentLeftPWM, currentRightPWM);
}

void applyMotorState(int spd) {
  motorSpeed = constrain(spd, 0, 255);
  updateStateDrivenPWM();
}

void doStop() {
  state = STOPPED;
  stopAll();
}

void setSpeed(int spd) {
  motorSpeed = constrain(spd, 0, 255);
  Serial.print("Speed: ");
  Serial.println(motorSpeed);
}

void setLeftTrim(int trimPercent) {
  leftMotorTrimPercent = constrain(trimPercent, 50, 150);
  Serial.print("Left trim: ");
  Serial.println(leftMotorTrimPercent);
}

void setRightTrim(int trimPercent) {
  rightMotorTrimPercent = constrain(trimPercent, 50, 150);
  Serial.print("Right trim: ");
  Serial.println(rightMotorTrimPercent);
}

void executeCommand(char cmd) {
  switch (cmd) {
    case 'f':
      state = FORWARD;
      Serial.println("Forward");
      break;

    case 'b':
      state = BACKWARD;
      Serial.println("Backward");
      break;

    case 'a':
      state = TURN_LEFT;
      Serial.println("Left");
      break;

    case 'd':
      state = TURN_RIGHT;
      Serial.println("Right");
      break;

    case 's':
      doStop();
      Serial.println("Stop");
      break;

    case '+':
      setSpeed(motorSpeed + 10);
      break;

    case '-':
      setSpeed(motorSpeed - 10);
      break;
  }
}

void parseCommand(String cmd) {
  cmd.trim();

  if (cmd.startsWith("M,")) {
    int comma = cmd.indexOf(',', 2);
    if (comma == -1) {
      return;
    }

    int lPWM = constrain(cmd.substring(2, comma).toInt(), -255, 255);
    int rPWM = constrain(cmd.substring(comma + 1).toInt(), -255, 255);

    state = MANUAL_PWM;
    lastPiCommand = millis();
    currentLeftPWM = lPWM;
    currentRightPWM = rPWM;
    applyRawPWM(lPWM, rPWM);
  } else if (cmd.length() == 1) {
    executeCommand(cmd[0]);
  }
}

String pageHtml() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
  <title>MediDroid</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; background: #0d0d0d; color: #fff; touch-action: none; }
    .wrap { max-width: 420px; margin: 0 auto; padding: 20px; text-align: center; }
    h1 { font-size: 26px; margin-bottom: 4px; color: #4af; }
    .hint { color: #888; font-size: 13px; margin-bottom: 18px; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 16px 0; }
    button {
      border: none; border-radius: 12px; padding: 20px 8px;
      font-size: 16px; color: #fff; background: #1e6fe8;
      width: 100%; cursor: pointer; user-select: none; -webkit-user-select: none;
    }
    button.stop { background: #c0392b; }
    button.util { background: #333; font-size: 14px; padding: 12px 8px; }
    .row { display: flex; gap: 10px; margin-top: 10px; }
    .row button { flex: 1; }
    input[type=range] { width: 100%; margin: 10px 0 4px; accent-color: #1e6fe8; }
    .speedval { font-size: 16px; color: #aaa; margin-bottom: 6px; }
    .status { margin-top: 12px; font-size: 13px; color: #4c4; min-height: 18px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>MediDroid</h1>
    <p class="hint">Hold buttons or WASD keys. Release to stop.</p>

    <div class="grid">
      <div></div>
      <button id="btnF">Forward</button>
      <div></div>

      <button id="btnL">Left</button>
      <button id="btnS" class="stop">Stop</button>
      <button id="btnR">Right</button>

      <div></div>
      <button id="btnB">Backward</button>
      <div></div>
    </div>

    <p class="speedval">Speed: <span id="sv">)rawliteral";

  html += String(motorSpeed);

  html += R"rawliteral(</span></p>
    <input id="spd" type="range" min="0" max="255" value=")rawliteral";

  html += String(motorSpeed);

  html += R"rawliteral(">

    <p class="speedval">Left Trim: <span id="lv">)rawliteral";

  html += String(leftMotorTrimPercent);

  html += R"rawliteral(</span>%</p>
    <input id="ltrim" type="range" min="50" max="150" value=")rawliteral";

  html += String(leftMotorTrimPercent);

  html += R"rawliteral(">

    <p class="speedval">Right Trim: <span id="tv">)rawliteral";

  html += String(rightMotorTrimPercent);

  html += R"rawliteral(</span>%</p>
    <input id="trim" type="range" min="50" max="150" value=")rawliteral";

  html += String(rightMotorTrimPercent);

  html += R"rawliteral(">

    <div class="row">
      <button class="util" id="slow">- Slower</button>
      <button class="util" id="fast">+ Faster</button>
    </div>

    <p class="speedval">Distance: <span id="distVal">--</span> cm</p>
    <p class="speedval">Obstacle: <span id="obsVal">Sensor Error</span></p>

    <div class="status" id="st">Ready</div>
  </div>

  <script>
    function send(cmd) {
      fetch('/cmd?c=' + encodeURIComponent(cmd), { cache: 'no-store' }).catch(() => {});
    }

    function status(t) {
      document.getElementById('st').textContent = t;
    }

    function press(cmd, label) {
      send(cmd);
      status(label);
    }

    function release() {
      send('s');
      status('Stop');
    }

    function bind(id, cmd, label) {
      const el = document.getElementById(id);
      el.addEventListener('pointerdown', e => { e.preventDefault(); press(cmd, label); });
      el.addEventListener('pointerup', e => { e.preventDefault(); release(); });
      el.addEventListener('pointercancel', release);
      el.addEventListener('pointerleave', release);
    }

    bind('btnF', 'f', 'Forward');
    bind('btnB', 'b', 'Backward');
    bind('btnL', 'a', 'Left');
    bind('btnR', 'd', 'Right');
    bind('btnS', 's', 'Stop');

    document.getElementById('slow').addEventListener('click', () => { send('-'); status('Slower'); });
    document.getElementById('fast').addEventListener('click', () => { send('+'); status('Faster'); });

    document.getElementById('spd').addEventListener('input', e => {
      const v = e.target.value;
      document.getElementById('sv').textContent = v;
      fetch('/speed?v=' + v, { cache: 'no-store' }).catch(() => {});
      status('Speed ' + v);
    });

    document.getElementById('ltrim').addEventListener('input', e => {
      const v = e.target.value;
      document.getElementById('lv').textContent = v;
      fetch('/ltrim?v=' + v, { cache: 'no-store' }).catch(() => {});
      status('Left trim ' + v + '%');
    });

    document.getElementById('trim').addEventListener('input', e => {
      const v = e.target.value;
      document.getElementById('tv').textContent = v;
      fetch('/trim?v=' + v, { cache: 'no-store' }).catch(() => {});
      status('Right trim ' + v + '%');
    });

    function refreshObstacle() {
      fetch('/obstacle', { cache: 'no-store' })
        .then(r => r.json())
        .then(data => {
          document.getElementById('distVal').textContent = data.distance_cm >= 0 ? data.distance_cm : '--';
          document.getElementById('obsVal').textContent = data.state;
        })
        .catch(() => {});
    }

    const KEYS = { w:'f', s:'b', a:'a', d:'d', arrowup:'f', arrowdown:'b', arrowleft:'a', arrowright:'d' };
    let activeKey = null;

    document.addEventListener('keydown', e => {
      if (e.repeat) return;
      const k = e.key.toLowerCase();

      if (KEYS[k]) {
        e.preventDefault();
        activeKey = k;
        press(KEYS[k], k);
      } else if (k === '+') {
        send('+');
        status('Faster');
      } else if (k === '-') {
        send('-');
        status('Slower');
      }
    });

    document.addEventListener('keyup', e => {
      const k = e.key.toLowerCase();
      if (KEYS[k] && activeKey === k) {
        e.preventDefault();
        activeKey = null;
        release();
      }
    });

    window.addEventListener('blur', () => {
      send('s');
      status('Stop');
    });

    refreshObstacle();
    setInterval(refreshObstacle, 250);
  </script>
</body>
</html>
)rawliteral";

  return html;
}

void handleRoot() {
  server.send(200, "text/html", pageHtml());
}

void handleCmd() {
  if (server.hasArg("c") && server.arg("c").length() > 0) {
    executeCommand(server.arg("c")[0]);
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Bad request");
  }
}

void handleSpeed() {
  if (server.hasArg("v")) {
    setSpeed(server.arg("v").toInt());
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Bad request");
  }
}

void handleTrim() {
  if (server.hasArg("v")) {
    setRightTrim(server.arg("v").toInt());
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Bad request");
  }
}

void handleLeftTrim() {
  if (server.hasArg("v")) {
    setLeftTrim(server.arg("v").toInt());
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Bad request");
  }
}

void handleObstacle() {
  String body = "{\"distance_cm\":";
  body += String(lastDistanceCm);
  body += ",\"state\":\"";
  body += obstacleStateLabel(obstacleState);
  body += "\"}";
  server.send(200, "application/json", body);
}

void setup() {
  pinMode(RESET_LED_PIN, OUTPUT);
  digitalWrite(RESET_LED_PIN, LOW);

  esp_reset_reason_t reason = esp_reset_reason();
  if (reason != ESP_RST_POWERON) {
    digitalWrite(RESET_LED_PIN, HIGH);
  }

  pinMode(ENC_L_A, INPUT_PULLUP);
  pinMode(ENC_L_B, INPUT_PULLUP);
  pinMode(ENC_R_A, INPUT_PULLUP);
  pinMode(ENC_R_B, INPUT_PULLUP);
  pinMode(US_TRIG_PIN, OUTPUT);
  pinMode(US_ECHO_PIN, INPUT);
  pinMode(LED_OBS_SEEN_PIN, OUTPUT);
  pinMode(LED_OBS_WARN_PIN, OUTPUT);
  pinMode(LED_OBS_STOP_PIN, OUTPUT);
  digitalWrite(US_TRIG_PIN, LOW);
  digitalWrite(LED_OBS_SEEN_PIN, LOW);
  digitalWrite(LED_OBS_WARN_PIN, LOW);
  digitalWrite(LED_OBS_STOP_PIN, LOW);

  attachInterrupt(digitalPinToInterrupt(ENC_L_A), leftEncoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_L_B), leftEncoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_R_A), rightEncoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_R_B), rightEncoderISR, CHANGE);

  Serial.begin(115200);
  delay(50);
  Serial.println("MediDroid ESP32 booting...");
  Serial.print("Reset reason: ");
  Serial.println((int)reason);

  ledcAttach(L_RPWM, 1000, 8);
  ledcAttach(L_LPWM, 1000, 8);
  ledcAttach(R_RPWM, 1000, 8);
  ledcAttach(R_LPWM, 1000, 8);
  stopAll();

  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSsid, apPassword);
  Serial.print("WiFi AP: ");
  Serial.println(apSsid);
  Serial.print("IP: ");
  Serial.println(WiFi.softAPIP());

  server.on("/", handleRoot);
  server.on("/cmd", handleCmd);
  server.on("/speed", handleSpeed);
  server.on("/ltrim", handleLeftTrim);
  server.on("/trim", handleTrim);
  server.on("/obstacle", handleObstacle);
  server.begin();

  lastPiCommand = millis();
  Serial.println("Ready.");
}

void loop() {
  server.handleClient();
  updateUltrasonic();

  if (state != MANUAL_PWM) {
    updateStateDrivenPWM();
  }

  if (PI_TIMEOUT_ENABLED && state == MANUAL_PWM && (millis() - lastPiCommand > PI_TIMEOUT_MS)) {
    doStop();
    Serial.println("WATCHDOG: Pi timed out - motors stopped.");
  }

  if (millis() - lastEncoderReport >= 50) {
    lastEncoderReport = millis();
    Serial.print("E,");
    Serial.print(leftTicks);
    Serial.print(",");
    Serial.println(rightTicks);
  }

  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (serialBuffer.length() > 0) {
        parseCommand(serialBuffer);
        serialBuffer = "";
      }
    } else if (serialBuffer.length() < 64) {
      serialBuffer += c;
    }
  }
}
