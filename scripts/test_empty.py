
from launch import LaunchContext
from launch_ros.utilities.evaluate_parameters import evaluate_parameter_dict
try:
    evaluate_parameter_dict(LaunchContext(), {'test': []})
    print("Empty list succeeded")
except Exception as e:
    import traceback
    traceback.print_exc()
