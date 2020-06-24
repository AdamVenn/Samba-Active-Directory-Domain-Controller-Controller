"""
A ssh-based Samba Active Directory Domain Controller manager.
Basically calls the samba-tool commands on a remote server.
As we know, there is no GUI for Samba Domain Controllers, so this is the model to make one.

Abilities so far:
    Users:
        - list (users and details)
        - add
        - remove
    Groups:
        - list (groups and members)
        - add
        - remove
        - add members
        - remove members
    Organizational Units
        - list
        - add
    Computers:
        - list
"""

# TO DO:
#   - Add sub-group to group
#   - samba-tool user edit
#   - Find out restrictions on usernames, passwords, etc. and put in proper validation
#   - Implement samba-tool user show to bring up detailed user info
#   - OU management, including samba-tool user move

import paramiko
import re
from enum import Enum
from getpass import getpass
import platform
import subprocess

# Notes from the Samba help
"""Samba-tool commands:
  computer    - Computer management.
  dbcheck     - Check local AD database for errors.
  delegation  - Delegation management.
  dns         - Domain Name Service (DNS) management.
  domain      - Domain management.
  drs         - Directory Replication Services (DRS) management.
  dsacl       - DS ACLs manipulation.
  forest      - Forest management.
  fsmo        - Flexible Single Master Operations (FSMO) roles management.
  gpo         - Group Policy Object (GPO) management.
  group       - Group management.
  ldapcmp     - Compare two ldap databases.
  ntacl       - NT ACLs manipulation.
  ou          - Organizational Units (OU) management
  processes   - List processes (to aid debugging on systems without setproctitle).
  rodc        - Read-Only Domain Controller (RODC) management.
  schema      - Schema querying and management.
  sites       - Sites management.
  spn         - Service Principal Name (SPN) management.
  testparm    - Syntax check the configuration file.
  time        - Retrieve the time on a server.
  user        - User management.
  visualize   - Produces graphical representations of Samba network state
"""

"""
  add            - Create a new user.
  create         - Create a new user.
  delete         - Delete a user.
  disable        - Disable a user.
  edit           - Modify User AD object.
  enable         - Enable a user.
  getpassword    - Get the password fields of a user/computer account.
  list           - List all users.
  move           - Move a user to an organizational unit/container.
  password       - Change password for a user account (the one provided in authentication).
  setexpiry      - Set the expiration of a user account.
  setpassword    - Set or reset the password of a user account.
  show           - Display a user AD object.
  syncpasswords  - Sync the password of user accounts.
"""

"""
  add            - Creates a new AD group.
  addmembers     - Add members to an AD group.
  delete         - Deletes an AD group.
  list           - List all groups.
  listmembers    - List all members of an AD group.
  move           - Move a group to an organizational unit/container.
  removemembers  - Remove members from an AD group.
  show           - Display a group AD object.
"""

"""
  create       - Create an organizational unit.
  delete       - Delete an organizational unit.
  list         - List all organizational units.
  listobjects  - List all objects in an organizational unit.
  move         - Move an organizational unit.
  rename       - Rename an organizational unit.
"""

"""
  backup            - Create or restore a backup of the domain.
  classicupgrade    - Upgrade from Samba classic (NT4-like) database to Samba AD DC database.
  dcpromo           - Promote an existing domain member or NT4 PDC to an AD DC.
  demote            - Demote ourselves from the role of Domain Controller.
  exportkeytab      - Dump Kerberos keys of the domain into a keytab.
  functionalprep    - Domain functional level preparation
  info              - Print basic info about a domain and the DC passed as parameter.
  join              - Join domain as either member or backup domain controller.
  level             - Raise domain and forest function levels.
  passwordsettings  - Manage password policy settings.
  provision         - Provision a domain.
  schemaupgrade     - Domain schema upgrading
  tombstones        - Domain tombstone and recycled object management.
  trust             - Domain and forest trust management.
"""

"""
  --complexity=COMPLEXITY
                        The password complexity (on | off | default). Default
                        is 'on'
  --store-plaintext=STORE_PLAINTEXT
                        Store plaintext passwords where account have 'store
                        passwords with reversible encryption' set (on | off |
                        default). Default is 'off'
  --history-length=HISTORY_LENGTH
                        The password history length (<integer> | default).
                        Default is 24.
  --min-pwd-length=MIN_PWD_LENGTH
                        The minimum password length (<integer> | default).
                        Default is 7.
  --min-pwd-age=MIN_PWD_AGE
                        The minimum password age (<integer in days> |
                        default).  Default is 1.
  --max-pwd-age=MAX_PWD_AGE
                        The maximum password age (<integer in days> |
                        default).  Default is 43.
  --account-lockout-duration=ACCOUNT_LOCKOUT_DURATION
                        The the length of time an account is locked out after
                        exeeding the limit on bad password attempts (<integer
                        in mins> | default).  Default is 30 mins.
  --account-lockout-threshold=ACCOUNT_LOCKOUT_THRESHOLD
                        The number of bad password attempts allowed before
                        locking out the account (<integer> | default).
                        Default is 0 (never lock out).
  --reset-account-lockout-after=RESET_ACCOUNT_LOCKOUT_AFTER
                        After this time is elapsed, the recorded number of
                        attempts restarts from zero (<integer> | default).
                        Default is 30.
"""


def flatten(l, ltypes=(list, tuple)):
    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i + 1] = l[i]
        i += 1
    return ltype(l)


def all_legal_chars(s):
    if not all(32 <= ord(c) <= 122 for c in s):
        return False

    if re.search(r'[`~!@#$%,^&*()}{\[\]\'|\\:;"<>?/]', s):
        return False

    return True


def validate_ip(ip):
    return [0<=int(x)<256 for x in re.split('\.',re.match(r'^\d+\.\d+\.\d+\.\d+$',ip).group(0))].count(True)==4


def validate_list_of_strings(*user_input) -> (list, list):
    """
    Validates user input which should have been a list of strings.
    It's one of my typical validation functions that really tries to accept what the user gives it.
    Will accept:
        - variable arg length
        - strings, lists and tuples of high numbers of dimensions
    :param user_input: the thing the untrustworthy user gave you
    :return: a list of strings and a list of stringified exceptions we got when trying to make strings
    """
    validated = []
    errors = []
    if isinstance(user_input, str):
        validated.append(user_input)
        return validated

    user_input = list(flatten(user_input))

    if isinstance(user_input, list):
        for i in user_input:
            try:
                validated.append(str(i))
            except Exception as e:
                errors.append(repr(e))

    return validated, errors


class User:
    """Represents an Active Directory user.
    Can populate the class from the dict and just grab the info you want.
    More of a read-only class... Users should be managed through samba-tool.
    """
    def __init__(self, dic_user={}):
        # Basic properties used if we want to make a new user
        self.username = ''
        self.password = ''
        self.given_name = ''
        self.surname = ''
        self.flags = []
        # TO DO: Some checking to handle whether OU has 'OU=' at the beginning, or if it is in a sub ou
        self.ou = ''

        self.dic_full_info = dic_user
        if self.dic_full_info != {}:
            self.populate_from_dict()

    def populate_from_dict(self):
        """
        Get a dictionary from Samba-tool and pass in here to create the User class
        :param dicUser:
        :return:
        """
        # What the hell... Can someone tell me why I have to try four different keys for username?
        try:
            self.set_username(self.dic_full_info['sAMAccountName'])
        except KeyError:
            try:
                self.set_username(self.dic_full_info['sAMAccountName:'])
            except KeyError:
                try:
                    self.set_username(self.dic_full_info['userPrincipalName:'])
                except KeyError:
                    try:
                        self.set_username(self.dic_full_info['userPrincipalName'])
                    except KeyError as e:
                        self.set_username("USERNAME UNAVAILABLE")

        self.password = ''

        # Okay something went wrong when they were designing the naming system
        try:
            self.set_given_name(self.dic_full_info['givenName'])
        except KeyError:
            try:
                self.set_given_name(self.dic_full_info['givenName:'])
            except KeyError:
                try:
                    self.set_given_name(self.dic_full_info['cn'])
                except KeyError:
                    self.set_given_name('GIVEN NAME UNAVAILABLE')

        # Not having a surname is acceptable, but if you ask me, it should still be in the dictionary as ''
        try:
            self.set_surname(self.dic_full_info['sn'])
        except KeyError:
            self.surname = ''

        try:
            self.flags = self.parse_user_flags(self.dic_full_info['userAccountControl'])
        except KeyError:
            self.flags = ['FLAGS UNAVAILABLE']

    def set_username(self, username: str):
        if not isinstance(username, str):
            raise TypeError("Username is not text!")
        if not all_legal_chars(username):
            raise ValueError(f"Illegal characters found in {username}")
        if len(username) < 1:
            raise ValueError(f"Please enter a username.")
        if username[0] == ' ':
            raise SambaException(f"I'm sorry, having a name with a space at the beginning makes things too hard.")
        # I will let Samba manage maximum lengths and stuff
        self.username = username

    def set_password(self, password: str):
        if not isinstance(password, str):
            raise TypeError("Password is not text!")
        if len(password) < 1:
            raise ValueError(f"Please enter a password.")
        # Is it okay to allow backslash in password field?
        self.password = password

    def set_given_name(self, given_name: str):
        if not isinstance(given_name, str):
            raise TypeError("Given name is not text!")
        if not all_legal_chars(given_name):
            raise ValueError(f"Illegal characters found in {given_name}")
        if len(given_name) < 1:
            raise ValueError(f"Please enter a given name.")
        if given_name[0] == ' ':
            raise SambaException(f"I'm sorry, having a name with a space at the beginning makes things too hard.")
        # I will let Samba manage maximum lengths and stuff
        self.given_name = given_name

    def set_surname(self, surname: str):
        if not isinstance(surname, str):
            raise TypeError("Surname is not text!")
        if not all_legal_chars(surname):
            raise ValueError(f"Illegal characters found in {surname}")
        if not surname == '':
            # Empty surname field allowed but the line below will call an IndexError if run on an empty string
            if surname[0] == ' ':
                raise SambaException(f"I'm sorry, having a name with a space at the beginning makes things too hard.")
        # I will let Samba manage maximum lengths and stuff
        self.surname = surname

    @staticmethod
    def parse_distinguishedName(dn: str) -> list:
        """
        Take the distinguishedName entry from the 'user show' and break it up into its parts
        :param dn: the distinguishedName entry, with or without the 'distinguishedName: ' prefix
        :return: a list of tuples, eg. [('CN', 'John'), ('CN', 'Smith'), ('DC', 'domain'), ('DC', 'net')]
        """
        if not isinstance(dn, str):
            raise SambaException("User's distinguished name is not text!")
        if dn[:18] == 'distinguishedName:':
             # Accept either value or full string
             dn = dn[18:]
        dn = dn.lstrip(' ')
        lst_dn = dn.split(',')
        lst_dn = [(x.partition('=')[0], x.partition('=')[2])  for x in lst_dn]
        return lst_dn

    @staticmethod
    def parse_user_flags(userAccountControl) -> list:
        """
        Take the userAccountControl item (flags) and make a list of the flags the user has
        :param user_flags: the userAccountControl item from the user info
        :return: list of user's flags
        """
        userAccountControl = int(userAccountControl)
        return [flag.name for flag in AccountFlags if userAccountControl & flag.value == flag.value]


class AccountFlags(Enum):
    SCRIPT = 0x0001
    ACCOUNTDISABLE = 0x0002
    HOMEDIR_REQUIRED = 0x0008
    LOCKOUT = 0x0010
    PASSWD_NOTREQD = 0x0020
    PASSWD_CANT_CHANGE = 0x0040
    ENCRYPTED_TEXT_PWD_ALLOWED = 0x0080
    TEMP_DUPLICATE_ACCOUNT = 0x0100
    NORMAL_ACCOUNT = 0x0200
    INTERDOMAIN_TRUST_ACCOUNT = 0x0800
    WORKSTATION_TRUST_ACCOUNT = 0x1000
    SERVER_TRUST_ACCOUNT = 0x2000
    DONT_EXPIRE_PASSWORD = 0x10000
    MNS_LOGON_ACCOUNT = 0x20000
    SMARTCARD_REQUIRED = 0x40000
    TRUSTED_FOR_DELEGATION = 0x80000
    NOT_DELEGATED = 0x100000
    USE_DES_KEY_ONLY = 0x200000
    DONT_REQ_PREAUTH = 0x400000
    PASSWORD_EXPIRED = 0x800000
    TRUSTED_TO_AUTH_FOR_DELEGATION = 0x1000000
    PARTIAL_SECRETS_ACCOUNT = 0x04000000


class SambaException(Exception):
    """Exception for errors returned via SSH and samba-tool"""
    pass


class AlliterationError(Exception):
    """Exception for poetic errors"""
    pass


class SshSamba:
    def __init__(self, ip_address='10.150.17.100'):
        # Variables to make the connection:
        self.remote_server_ip = ip_address
        self.user = 'root'
        self.password = ''

        self.built_in_groups = ('Administrators',
                                'Pre-Windows 2000 Compatible Access',
                                'Domain Admins',
                                'Event Log Readers',
                                'DnsAdmins',
                                'Cryptographic Operators',
                                'Domain Controllers',
                                'DnsUpdateProxy',
                                'IIS_IUSRS',
                                'Incoming Forest Trust Builders',
                                'Group Policy Creator Owners',
                                'Enterprise Admins',
                                'Network Configuration Operators',
                                'Schema Admins',
                                'Print Operators',
                                'Users',
                                'Server Operators',
                                'Backup Operators',
                                'Distributed COM Users',
                                'Enterprise Read-only Domain Controllers',
                                'Domain Guests',
                                'RAS and IAS Servers',
                                'Guests',
                                'Replicator',
                                'Certificate Service DCOM Access',
                                'Windows Authorization Access Group',
                                'Remote Desktop Users',
                                'Read-only Domain Controllers',
                                'Performance Monitor Users',
                                'Performance Log Users',
                                'Denied RODC Password Replication Group',
                                'Domain Users',
                                'Cert Publishers',
                                'Domain Computers',
                                'Allowed RODC Password Replication Group',
                                'Terminal Server License Servers',
                                'Account Operators')
        self.built_in_users = ('krbtgt',)
        self.ssh = None  # Will be Paramiko SSH Client

    def set_ip(self, ip: str):
        """
        Setter for the IP address of the Domain Controller.
        :return: Silence = success
        """
        if not validate_ip(ip):
            raise ValueError("Invalid IP address. Please enter 4 sets of numbers separated by .")
        else:
            self.remote_server_ip = ip

    def set_user(self, user: str):
        """
        Setter for the administrating user.
        :return: Silence = success
        """
        # Can't think of any validation restrictions for username. Let me know if you have some!
        self.user = user

    def set_password(self, password: str):
        """
        Setter for the administrating user's password.
        :return: Silence = success
        """
        # Again, passwords should be anything the user wants, right? Let me know if otherwise.
        if not isinstance(password, str):
            raise ValueError("Passsword must be a string.")
        self.password = password

    def connect_to_server(self):
        """
        Initialise the connection to the server.
        """
        print("Connecting to server...")
        print("")
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.remote_server_ip, username=self.user, password=self.password)

        # OS should keep our memory safe from other processes, but I will overwrite and free the memory
        # now we are finished with the password.
        self.password = "sahjdio327nyc327qey273eyn921ye923e912eyn2yd283e7bh8237e2y38eb723ye8723ey738"
        del self.password

        print("Connected!")

    def get_domain(self) -> dict:
        """
        Get the domain info by asking the remote host
        :return: Dictionary containing the domain info from samba-tool
        """
        domain_info = self.samba_command(f'domain info {self.remote_server_ip}')
        dicDomain = {}

        # Assumes no one is using colons in their naming...
        domain_info = [line.split(':') for line in domain_info if line != '']
        for line in domain_info:
            dicDomain[line[0].rstrip(' ')] = line[1].lstrip(' ')

        return dicDomain

    def get_domain_long(self) -> str:
        """
        Parse the domain info dictionary to get a useable domain name string.
        :return: String of the domain name in the format 'DC=domain,DC=net'
        """
        return 'DC=' + ',DC='.join(self.get_domain()['Domain'].split('.'))

    def close(self):
        """
        Good practice to close the connection when you're done.
        """
        self.ssh.close()

    def _sh_command(self, cmd: str) -> dict:
        """
        Run a command and get the results back as a tuple of a list of strings.
        :param cmd: any command to execute on the remote host through Paramiko SSH Client
        :return: Dict of stdin, stdout, stderr as lists of strings (lines of text returned)
        """
        def process_stream(std: bytes):
            if std == b'':
                std = None
            if std:
                std = std.decode('utf-8')
                std = std.split('\n')
            return std

        if not self.ssh:
            raise ConnectionError("No SSH client active.")
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        try:
            stdin = stdin.read()
            stdin = process_stream(stdin)
        except IOError:
            stdin = None

        try:
            stdout = stdout.read()
            stdout = process_stream(stdout)
        except IOError:
            stdout = None

        try:
            stderr = stderr.read()
            stderr = process_stream(stderr)
        except IOError:
            stderr = None

        return {'stdin': stdin,
                'stdout': stdout,
                'stderr': stderr,
                }

    def samba_command(self, cmd: str) -> list:
        """
        Execute a samba-tool command.
        Raises an exception if the remote host returns an error in stderr or starts telling you how to use samba-tool.
        :param cmd: the stuff that comes after typing 'samba-tool'
        :return: a list of of strings (lines of text returned)
        """
        output = self._sh_command(f'samba-tool {cmd}')
        if output['stderr']:
            # Error returned by SSH
            raise SambaException(output['stderr'])
        if not output['stdout']:
            # No data in answer
            return []
        if '\n'.join(flatten(output['stdout']))[0:7] == 'Usage: ':
            # Incorrect Samba-tool command
            raise SambaException(f"Didn't understand command: {cmd}")

        return output['stdout']

    def get_users(self) -> list:
        """
        Get details of all users
        :return: list of user objects
        """
        lstUsers = self.samba_command('user list')
        lstUsers = [usr for usr in lstUsers if usr not in self.built_in_users and usr != '']
        lst_user_objects = []
        for usr in lstUsers:
            lstUsr = self.samba_command(f'user show \"{usr}\"')
            dicUsr = {}
            for info in lstUsr:
                if info != '':
                    key, value = info.split(': ')
                    dicUsr[key] = value
            lst_user_objects.append(User(dic_user=dicUsr))

        return lst_user_objects

    def _get_group_members(self, grp: str) -> list:
        """
        Get the members of group. To be called by 'get groups'. I made it private but I guess you can use it if you like.
        :return: list of username strings
        """
        lstUsers = self.samba_command(f'group listmembers \"{grp}\"')
        lstUsers = [usr for usr in lstUsers if usr not in self.built_in_users and usr != '']
        return lstUsers

    def get_groups(self) -> dict:
        """
        Get all non-built-in groups and members
        :return: dictionary -  group name: [group member, group member]
        """
        lstGroups = self.samba_command('group list')
        lstGroups = [grp for grp in lstGroups if grp not in self.built_in_groups and grp != '']
        dicGroups = {group: self._get_group_members(group) for group in lstGroups}
        return dicGroups

    def get_organizational_units(self) -> list:
        """
        Get a list of the OUs in the domain
        :return: list of strings
        """
        # TO DO: Parse 'OU=' stuff to build tree of OUs
        return self.samba_command('ou list')

    def get_computers(self) -> list:
        """
        Get a list of the computer in the domain
        :return: list of computer names
        """
        return self.samba_command('computer list')

    def _add_user(self, username, pw, given_name='', surname='', organizational_unit=None):
        """
        Mimic the command:
        user create User1 passw0rd --given-name=John --surname=Smith --must-change-at-next-login --userou='OU=OrgUnit'
        Internal use only - please make a user object and use self.add_users instead.
        Silence = success. Exception will be raised if something went wrong
        """
        if not all_legal_chars(username):
            raise ValueError("Illegal characters found in username")
        if not all_legal_chars(given_name):
            raise ValueError("Illegal characters found in given name")
        if not all_legal_chars(surname):
            raise ValueError("Illegal characters found in surname")
        if organizational_unit:
            if not all_legal_chars(organizational_unit):
                raise ValueError("Illegal characters found in organizational unit")

        if organizational_unit:
            self.samba_command(f"user create \"{username}\" \"{pw}\" --given-name=\"{given_name}\" --surname=\"{surname}\" --userou='OU=\"{organizational_unit}\"' --must-change-at-next-login")
        else:
            self.samba_command(f"user create \"{username}\" \"{pw}\" --given-name=\"{given_name}\" --surname=\"{surname}\" --must-change-at-next-login")

    def add_users(self, lstUsers):
        """
        Add a list of users to the domain. Users must be a user object please.
        :param lstUsers: List (or not) of user objects
        Silence = success. Exception will be raised if something went wrong
        """
        if not isinstance(lstUsers, list):
            lstUsers = [lstUsers]

        lstErrors = []

        for usr in lstUsers:
            if not isinstance(usr, User):
                lstErrors.append(f'{usr} is not a user object')
                continue
            try:
                self._add_user(usr.username,
                               usr.password,
                               given_name=usr.given_name,
                               surname=usr.surname,
                               organizational_unit=usr.ou)
            except Exception as e:
                lstErrors.append(repr(e))

        if len(lstErrors) > 0:
            errors = '\n'.join(lstErrors)
            raise SambaException(f"Errors when adding users: {errors}")

    def delete_users(self, lstUsers):
        """
        Delete users from the domain
        :param lstUsers: list of user names (strings) or user objects to delete
        Silence = success. Exception will be raised if something went wrong
        """
        if not isinstance(lstUsers, list):
            lstUsers = [lstUsers]

        lstErrors = []

        for usr in lstUsers:
            if isinstance(usr, User):
                usr = usr.username
            try:
                self.samba_command(f'user delete \"{usr}\"')
            except Exception as e:
                lstErrors.append(repr(e))

        if len(lstErrors) > 0:
            errors = '\n'.join(lstErrors)
            raise SambaException(f"Errors when deleting users: {errors}")

    def disable_users(self, lstUsers):
        """
        Disables user accounts
        :param lstUsers: list of user names (strings) or user objects to disable
        Silence = success. Exception will be raised if something went wrong
        """
        if not isinstance(lstUsers, list):
            lstUsers = [lstUsers]

        lstErrors = []

        for usr in lstUsers:
            if isinstance(usr, User):
                usr = usr.username
            try:
                self.samba_command(f'user disable \"{usr}\"')
            except Exception as e:
                lstErrors.append(repr(e))

        if len(lstErrors) > 0:
            errors = '\n'.join(lstErrors)
            raise SambaException(f"Errors when disabling users: {errors}")

    def enable_users(self, lstUsers):
        """
        Enables user accounts
        :param lstUsers: list of user names (strings) or user objects to enable
        Silence = success. Exception will be raised if something went wrong
        """
        if not isinstance(lstUsers, list):
            lstUsers = [lstUsers]

        lstErrors = []

        for usr in lstUsers:
            if isinstance(usr, User):
                usr = usr.username
            try:
                self.samba_command(f'user enable \"{usr}\"')
            except Exception as e:
                lstErrors.append(repr(e))

        if len(lstErrors) > 0:
            errors = '\n'.join(lstErrors)
            raise SambaException(f"Errors when enabling users: {errors}")

    def password_user(self, user, password, must_change_at_next_login=False):
        if must_change_at_next_login:
            self.samba_command(f'user setpassword \"{user}\" --newpassword=\"{password}\" --must-change-at-next-login')
        else:
            self.samba_command(f'user setpassword \"{user}\" --newpassword=\"{password}\"')

    def edit_user(self, user, params):
        # TO DO: this
        # edit
        raise NotImplementedError("I'll do it soon, I swears!")

    def add_group(self, group: str):
        """
        Add a new group to the domain
        :param group: name of new group
        Silence = success. Exception will be raised if something went wrong
        """
        # TO DO: Add sub-group to group

        if not all_legal_chars(group):
            raise ValueError("Illegal characters found in group name")
        self.samba_command(f'group add \"{group}\"')

    def delete_group(self, group: str):
        """
        Removes a group from the domain
        :param group: name of group
        Silence = success. Exception will be raised if something went wrong
        """
        if not all_legal_chars(group):
            raise ValueError("Illegal characters found in group name")
        self.samba_command(f'group delete \"{group}\"')

    def add_members_to_group(self, group: str, members: list):
        """
        Add users to a group.
        :param group: The group to be modified
        :param members: A list of user names or user objects to be added to the group
        Silence = success. Exception will be raised if something went wrong
        """
        if not all_legal_chars(group):
            raise ValueError("Illegal characters found in group name")

        if not isinstance(members, list):
            members = [members]

        # Allow both usernames and user objects as input
        members = [mem.username if isinstance(mem, User) else mem for mem in members]

        members, errors = validate_list_of_strings(members)
        if errors:
            raise ValueError(f"Got the following errors from the list of members: {errors}")

        if not members:
            raise ValueError("No valid usernames found.")

        return self.samba_command(f'group addmembers \"{group}\" "{", ".join(members)}"')

    def delete_members_from_group(self, group: str, members: list):
        """
        Remove users from a group.
        :param group: The group to be modified
        :param members: A list of user names or user objects to be removed from the group
        Silence = success. Exception will be raised if something went wrong
        """
        if not all_legal_chars(group):
            raise ValueError("Illegal characters found in group name")

        if not isinstance(members, list):
            members = [members]

        # Allow both usernames and user objects as input
        members = [mem.username if isinstance(mem, User) else mem for mem in members]

        members, errors = validate_list_of_strings(members)
        if errors:
            raise ValueError(f"Got the following errors from the list of members: {errors}")

        self.samba_command(f'group removemembers \"{group}\" "{", ".join(members)}"')

    def add_organizational_unit(self, organizational_unit: str, parent_organizational_unit: str = None):
        """
        Add an organizational unit to the domain.
        :param organizational_unit:         The new OU to be added
        :param parent_organizational_unit:  If the OU is to be a child of another OU, specify it here.
                                            If the parent has parents itself, it will look like this:
                                            'parent,OU=grandparent'
        Silence = success. Exception will be raised if something went wrong
        """
        if not all_legal_chars(organizational_unit):
            raise ValueError("Illegal characters found in organizational unit")
        if parent_organizational_unit:
            if not all_legal_chars(parent_organizational_unit):
                raise ValueError("Illegal characters found in parent organizational unit")
            self.samba_command(f"ou create 'OU=\"{organizational_unit}\",OU=\"{parent_organizational_unit}\",{self.domain_long}'")
        else:
            self.samba_command(f"ou create 'OU=\"{organizational_unit}\"'")

    def get_password_policy(self) -> dict:
        """
        Get password policy for the domain
        :return: dictionary of password policy
        """
        dicPolicy = {}
        lstPolicy = self.samba_command('domain passwordsettings show')

        # Assumes no unexpected colons...
        policy_info = [line.split(':') for line in lstPolicy if line != '' and 'Password informations for domain' not in line]
        for line in policy_info:
            dicPolicy[line[0].rstrip(' ')] = line[1].lstrip(' ')

        return dicPolicy

    def set_password_policy(self, dicPolicy):
        """
        Call domain passwordsettings set to set the password policy for the domain.
        :param dicPolicy:   Pass in a dictionary containing the policy items.
                            The keys of the dictionary should be the same human-readable text returned by
                            get_password_policy (domain passwordsettings show).
                            The dictionary does not need to contain the entire policy,
                            but there must not be any extraneous keys.
        :return: Silence = success. Exception will be raised if something went wrong
        """
        dicSyntax = {
            'Password complexity': 'complexity',
            'Store plaintext passwords': 'store-plaintext',
            'Password history length': 'history-length',
            'Minimum password length': 'min-pwd-length',
            'Minimum password age (days)': 'min-pwd-age',
            'Maximum password age (days)': 'max-pwd-age',
            'Account lockout duration (mins)': 'account-lockout-duration',
            'Account lockout threshold (attempts)': 'account-lockout-threshold',
            'Reset account lockout after (mins)': 'reset-account-lockout',
        }
        policy_params = ''
        for key, value in dicPolicy.items():
            try:
                policy_params += f"--{dicSyntax[key]}={value} "
            except KeyError:
                raise AlliterationError(f"Please provide proper password policy parameters!\nInvalid parameter: {key}")

        self.samba_command(f'domain passwordsettings set {policy_params}')


def testing():
    tester = SshSamba()

    tester.connect_to_server()
    a = tester.get_users()
    for usr in a:
        print(usr.username)
    tester.close()


if __name__ == '__main__':
    testing()
    print('\n\ndone!')

