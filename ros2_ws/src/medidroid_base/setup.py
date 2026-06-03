import os
from glob import glob
from setuptools import setup

package_name = 'medidroid_base'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ubuntu',
    maintainer_email='user@todo.todo',
    description='ROS 2 package for the MediDroid base controller (ESP32 via Serial)',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'wasd_teleop = medidroid_base.wasd_teleop:main',
            'dummy_node = medidroid_base.dummy_node:main',
            'pi_motor_driver = medidroid_base.pi_motor_driver:main',
            'esp32_driver = medidroid_base.esp32_driver:main',
            'obstacle_detector = medidroid_base.obstacle_detector:main',
            'safety_gate = medidroid_base.safety_gate:main',
            'pose_manager = medidroid_base.pose_manager:main',
            'go_to = medidroid_base.go_to:main',
            'voice_command = medidroid_base.voice_command:main',
            'hardcoded_nav = medidroid_base.hardcoded_nav:main',
            'route_executor = medidroid_base.route_executor:main',
            'voice_listener = medidroid_base.voice_listener:main',
            'teach_route = medidroid_base.teach_route:main',
        ],
    },
)
