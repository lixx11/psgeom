#coding: utf8

"""
Setup script for psgeom.
"""

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(name='psgeom',
      version='0.0.1',
      author="TJ Lane",
      author_email="tjlane@slac.stanford.edu",
      description='scattering experiment geometry',
      packages=["psgeom"],
      package_dir={"psgeom": "psgeom"})