from setuptools import setup
import os
from datetime import date

app_name = 'Samba Domain Controller Controller'

APP = ['samba_gui.py']
DATA_FILES = []
OPTIONS = {'packages': 'wx',
           'excludes': ['pandas', 'scipy', 'numpy'],
           'iconfile': 'design/SDCC.icns',
           'plist': {
                'CFBundleDisplayName': app_name,
                'CFBundleName': app_name,
                'CFBundleShortVersionString': '1.0.0',
                'NSHumanReadableCopyright': 'Open source',
                'NSRequiresAquaSystemAppearance': False,
               }
           }

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

app_path = f"./dist/{app_name}.app"
dest_path = f'./releases/{date.today().strftime("%Y-%b-%d")}'

os.makedirs(dest_path, exist_ok=True)
os.rename(app_path, os.path.join(dest_path, f"{app_name}.app"))