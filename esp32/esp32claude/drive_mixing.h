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
  const int INNER_WHEEL_PERCENT = 30;
  const int innerSpeed = (speed * INNER_WHEEL_PERCENT) / 100;

  switch (state) {
    case FORWARD:
      return {speed, speed};

    case BACKWARD:
      return {-speed, -speed};

    case TURN_LEFT:
      return {innerSpeed, speed};

    case TURN_RIGHT:
      return {speed, innerSpeed};

    case STOPPED:
    case MANUAL_PWM:
    default:
      return {0, 0};
  }
}

#endif
