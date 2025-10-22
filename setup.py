from setuptools import setup
import os

NAMESPACE = "qedc_appbms"   # import name (use underscores)

def iter_packages(base="."):
    for root, dirs, files in os.walk(base):
        if "__init__.py" in files:
            rel = os.path.relpath(root, base)
            if rel == ".":
                continue
            yield rel.replace(os.sep, "."), root

packages = []
package_dir = {}
for relname, path in iter_packages("."):
    pkgname = f"{NAMESPACE}.{relname}"   # e.g. qedc_appbms.module1.subpkg
    packages.append(pkgname)
    package_dir[pkgname] = path

setup(
    name="qedc-appbms",                   # distribution name (pip install this)
    version="0.1.0",
    description="QED-C Application Oriented Benchmarks package.",
    packages=packages,
    package_dir=package_dir,
    python_requires=">=3.8",              # for PEP 420 namespace packages
)
