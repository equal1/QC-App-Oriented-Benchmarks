from setuptools import setup, find_packages

setup(
    name="qedc-appbms",
    description="QED-C Application Oriented Benchmarks package.",
    version="0.1.0",
    package_dir={'qedc_appbms': '.'},
    packages=['qedc_appbms'] + ['qedc_appbms.' + pkg for pkg in find_packages(where='.')],
)