"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup

APP = ['samba_gui.py']
DATA_FILES = []
OPTIONS = {'packages': 'wx',
           'excludes': ['pandas', 'scipy', 'numpy'],
           'plist': {
                'CFBundleDisplayName': 'Samba Domain Controller Controller',
                'CFBundleName': 'Samba Domain Controller Controller',
                'CFBundleShortVersionString': '1.0.0',
                'NSHumanReadableCopyright': 'June 2020 - Code on Github soon!'
               }
           }

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
