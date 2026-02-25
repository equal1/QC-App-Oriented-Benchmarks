from setuptools import setup, find_packages

# Get all packages recursively and prefix them with parent package name
packages = ['qedc_appbms'] + [f'qedc_appbms.{pkg}' for pkg in find_packages()]

setup(
    name="qedc-appbms",
    description="QED-C Application Oriented Benchmarks package.",
    version="0.1.0",
    packages=packages,
    package_dir={'qedc_appbms': '.'},
)