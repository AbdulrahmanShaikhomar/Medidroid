# MediDroid - Medical Robotic Assistant

## Project Overview
MediDroid is an autonomous mobile robot designed for medical assistance tasks, including medicine delivery, patient interaction, and telepresence. This project integrates ROS 2 (Humble/Foxy) for navigation, SLAM for mapping, and a voice pipeline for natural language interaction.

## Team Members
*   **M1**: Abdulrahman Zuhair Mohammed Shaikomar
*   **M2**: Abdulaziz Fawaz Mohammedali Sheikoon
*   **M3**: Abdullah Abubakr Ali Alaidarous

## System Architecture

### Hardware
*   **Platform**: TurtleBot / Custom Chassis
*   **Compute**: Jetson Nano / Raspberry Pi 4
*   **Sensors**: RPLIDAR, Microphone Array, Camera
*   **Actuation**: DC Motors with Encoders

### Software Stack
*   **OS**: Ubuntu 22.04 / 20.04
*   **Middleware**: ROS 2 Humble/Foxy
*   **Navigation**: Nav2 Stack
*   **SLAM**: Slam Toolbox / Gmapping
*   **Voice**: Python-based pipeline (STT/TTS + LLM Integration)
*   **Control**: Teleoperation & Web Dashboard

## Repository Structure
*   `/src`: ROS 2 source packages
*   `/docs`: Documentation and reports
*   `/scripts`: Utility scripts (setup, testing)
*   `/simulation`: Gazebo/Webots world files

---
*Locked in for EE499 Senior Project.*
