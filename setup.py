from setuptools import setup, find_packages

# Get all packages and prefix them with parent package name
packages = ['qedc_appbms']
for pkg in find_packages():
    packages.append(f'qedc_appbms.{pkg}')

setup(
    name="qedc-appbms",
    description="QED-C Application Oriented Benchmarks package.",
    version="0.1.0",
    packages=packages,
    package_dir={'qedc_appbms': '.'},
)