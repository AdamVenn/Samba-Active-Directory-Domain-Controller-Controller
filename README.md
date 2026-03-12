# Samba-Active-Directory-Domain-Controller-Controller
A simple graphical interface for using samba-tool to manage your Samba Active Directory domain controller on a remote server over SSH

### What does it do?
 - View/edit domain password policy
 - View non built-in users
 - View non-built-in groups
 - Add/remove users
 - Add/remove groups
 - Add/remove users to/from non-built-in groups
 - Reset user passwords
 - Enable/disable users

### Why would you use this?
You made a Linux-based Active Directory domain controller using Samba 4, and need a simple GUI to manage users, groups and the password policy. If you followed the tutorial [here](https://wiki.samba.org/index.php/Setting_up_Samba_as_an_Active_Directory_Domain_Controller), you may well want this program!

### How is this different from the other options?
It:
 - is dead simple
 - requires no extra set up or install on the server side
 - is aimed specifically at Samba 4 Active Directory domain controllers
 - is a cross-platform desktop application
 - works with SSH
 - uses the official [samba-tool](https://wiki.samba.org/index.php/User_and_Group_management)
 - doesn't require updating
 - relies on SSH for security

### What do I need to build/run it?
 - Python
 - wxPython for the GUI
 - Paramiko for the SSH
 - PyYAML for the preferences file

### How can I use it?

 - download/clone the repo:
    - `git clone "https://github.com/AdamVenn/Samba-Active-Directory-Domain-Controller-Controller.git"`
 - set up your virtual environment:
    - `python -m venv venv`
    - `source venv/bin/activate` (macOS/Linux) or `.\venv\Scripts\activate` (Windows)
 - install the dependencies:
    - `pip install -r requirements.txt`
 - run it:
    - `python samba_gui.py`
 - enter the DC IP address, username and password to connect
 - optionally, build it on Mac:
    - `pip install py2app`
    - `python setup.py`

### Contributing

Contributions/advice/bug reports welcome!
