#include "Stepper.h"
#include "Wire.h"
#include "TFLI2C.h"

/*
SCL
SDA
AREF
GND --- BBS 8
13  DBM
12  DAM
11  PBM PAS 3
10  --- DAS 12
9   BAM BAS 9
8   BBM

7   --- DBS 13
6   --- PBS 11
5
4
3   PAM
2
1

niebieski z czerwonym
*/

const int stepsPerRevolution = 200;
// const int mainDirA = 10, mainDirB = 7;
// const int secondaryDirA = 13, secondaryDirB = 12;

const int mainDirA = 13, mainDirB = 12;
const int secondaryDirA = 10, secondaryDirB = 7;

Stepper mainStepper = Stepper(stepsPerRevolution, mainDirA, mainDirB);
Stepper secondaryStepper = Stepper(stepsPerRevolution, secondaryDirA, secondaryDirB);
TFLI2C sensor; // TF-Luna via I2C: https://www.makerguides.com/wp-content/uploads/2024/11/image-55-768x492.png
int16_t dist;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  // brakes: always LOW
  for(int i : (int[]){8, 9}) { pinMode(i, OUTPUT); digitalWrite(i, LOW); }
  // PWMs: always HIGH
  for(int i : (int[]){3, 6, 11}) { pinMode(i, OUTPUT); digitalWrite(i, HIGH); }
  mainStepper.setSpeed(1);
  secondaryStepper.setSpeed(2);
}

void measure(int x, int y) {
  if (sensor.getData(dist, 0x10)) { // result in cm (TODO: check it)
    Serial.print("\nR ");
    Serial.print(x);
    Serial.print(" ");
    Serial.print(y);
    Serial.print(" ");
    Serial.println(dist);
  } else {
    Serial.println("\nE");
  }
}

void sweep_handler(int a, int b, int c, int d, int e, int f) {
  Serial.println("xo");
  mainStepper.step(a);
  Serial.println("yo");
  secondaryStepper.step(d);

  int i = 0;
  int x = a, y = d;
  if(c>0 ? x>b : x<b) return;
  if(f>0 ? y>e : y<e) return;
  while(1) {
    if(i % 2 == 0) {
      while(1) {
        measure(x, y);
        y += f;
        if (y > e) {
          y -= f;
          break;
        }
        Serial.println("y+");
        secondaryStepper.step(f);
      }
    } else {
      while(1) {
        measure(x, y);
        y -= f;
        if (y < d) {
          y += f;
          break;
        }
        Serial.println("y-");
        secondaryStepper.step(-f);
      }
    }
    x += c;
    if(c>0 ? x>b : x<b) {
      x -= c;
      break;
    }
    Serial.println("x+");
    mainStepper.step(c);
    i += 1;
  }
  mainStepper.step(-x);
  secondaryStepper.step(-y);
}


void loop() {
  if(Serial.available()) {
    if(Serial.findUntil("SWEEP ", nullptr)) {
      Serial.println("\nL");
    } else {
      Serial.println("\n.");
      return;
    }
    int input_ints[6] = {};
    for(int i = 0; i < 6; ++i) input_ints[i] = Serial.parseInt();
    if(!Serial.available()) { // there needs to be some character after the command (like `\n`)
      Serial.println("\nI");
      return;
    }
    sweep_handler(input_ints[0],input_ints[1],input_ints[2],input_ints[3],input_ints[4],input_ints[5]);
  }
}

// inspired by https://www.makerguides.com/arduino-motor-shield-stepper-motor-tutorial/
