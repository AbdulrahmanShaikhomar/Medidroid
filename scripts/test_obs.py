
from launch_ros.utilities.normalize_parameters import normalize_parameter_dict
d = {'observation_sources': 'scan'}
print(normalize_parameter_dict(d))
