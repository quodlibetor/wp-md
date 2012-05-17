from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup

import os
with open(os.path.join(os.path.dirname(__file__), "README.rst")) as fh:
    long_desc = fh.read()

setup(name="wp-md",
      version="0.1",
      py_modules=["wpmd", "distribute_setup"],
      description="Move WordPress pseudo-html into a couple markdown formats",
      long_description=long_desc,
      entry_points={
        'console_scripts': [
            'wp-md = wpmd:main',
            ]
        },
      author="Brandon W Maister",
      author_email="quodlibetor@gmail.com",
      url="https://github.com/quodlibetor/wp-md",
      classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Topic :: Text Processing",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Text Processing :: Markup :: XML"
        ]
)
