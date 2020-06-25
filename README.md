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

### How is this different from all the other options?
There are [many options](https://www.samba.org/samba/GUI/), but this:
 - is dead simple
 - requires no extra set up or install on the server side
 - is aimed specifically at Samba 4 Active Directory domain controllers
 - is made for Mac and Linux
 - works with SSH
 - uses samba-tool like [Samba tells us to](https://wiki.samba.org/index.php/User_and_Group_management)
 - will stay up to date with your SSH and Samba packages, and won't stop working when you upgrade PHP.

### Shouldn't this be a web interface?
There are a couple of nice looking Github projects doing this with modern web frameworks. Do try one of those out,  as long as you don't have to downgrade to PHP 5...

### Shouldn't this be a Webmin module?
That would be great! Please make that. I'm afraid I needed this to work quickly and didn't have time learn how to do that.

### Which packages do I need to build/run it?
 - Python 3.7/3.8
 - wxPython for the GUI
 - Paramiko for the SSH
 - PyYAML for the preferences file

### How can I use it?
Download the source and run it, or build it with Py2app on Mac using the included setup.py.

### Finally
This is still a work in progress, and contributions/advice/bug reports are welcome.
