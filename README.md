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
If, like me, you made a Linux-based Active Directory domain controller using Samba 4, and need a simple GUI to manage users, groups and the password policy. If you followed the tutorial [here](https://wiki.samba.org/index.php/Setting_up_Samba_as_an_Active_Directory_Domain_Controller), you may well want this program!

### Didn't someone already make this?
There are [many options](https://www.samba.org/samba/GUI/), but nothing as simple and easy to set up as this, which is aimed at Samba 4 Active Directory domain controllers. I built this for an environment with Mac clients, and it has the advantage of not needing to install anything extra on the Domain Controller. Samba [says to use samba-tool](https://wiki.samba.org/index.php/User_and_Group_management), so I followed their advice.

### Shouldn't this be a web interface?
That would be great! There are a couple of Github projects doing this with modern web frameworks. Do try one of those out, but make sure you avoid PHP 5. I made this because I could not find one that worked for me and I have not yet learnt web interfaces.

### Shouldn't this be a Webmin module?
That would be great! Please make that. I made this because I have not yet learnt Perl or web interfaces.

### What is is made with?
 - Python 3.7/3.8
 - wxPython for the GUI
 - Paramiko for the SSH

### How can I use it?
Download the source and run it, or build it with Py2app on Mac using the included setup.py.

### Finally
This is still a work in progress, and contributions/advice/bug reports are welcome.
