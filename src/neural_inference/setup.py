from setuptools import setup

package_name = "neural_inference"

setup(
  name=package_name,
  version="0.1.0",
  packages=[
    "neural_manager",
    "neural_manager.neural_inference",
    "neural_manager.neural_inference.control",
    "neural_manager.neural_inference.features",
    "neural_manager.neural_inference.inference",
    "neural_manager.neural_inference.inference.tensorrt_utils",
    "neural_manager.neural_inference.logging",
  ],
  data_files=[
    ("share/" + package_name, ["package.xml"]),
    ("share/" + package_name + "/launch", ["launch/neural_gate.launch.py"]),
    ("share/" + package_name + "/config", ["config/neural_infer_params.yaml"]),
  ],
  install_requires=["setuptools"],
  zip_safe=True,
  maintainer="Hanamy",
  maintainer_email="rongerch@outlook.com",
  description="Neural network inference node for PX4 control",
  license="BSD-3-Clause",
  entry_points={
    "console_scripts": [
      "neural_infer_node = neural_manager.neural_inference.neural_infer:main",
      "neural_activation_watcher = neural_manager.neural_inference.activation_watcher:main",
    ],
  },
)
