#ifndef DRIVE_MIXING_H
#define DRIVE_MIXING_H

enum MotorState {
  STOPPED,
  FORWARD,
  BACKWARD,
  TURN_LEFT,
  TURN_RIGHT,
  MANUAL_PWM
};

struct DriveMix {
  int leftPWM;
  int rightPWM;
};

inline DriveMix computeDriveMix(MotorState state, int speed) {
  speed = speed < 0 ? 0 : (speed > 255 ? 255 : speed);
  const int TURN_REVERSE_PERCENT = 25;
  const int turnReverse = (speed * TURN_REVERSE_PERCENT) / 100;

  switch (state) {
    case FORWARD:
      return {speed, speed};

    case BACKWARD:
      return {-speed, -speed};

    case TURN_LEFT:
      return {-turnReverse, speed};

    case TURN_RIGHT:
      return {speed, -turnReverse};

    case STOPPED:
    case MANUAL_PWM:
    default:
      return {0, 0};
  }
}

#endif
