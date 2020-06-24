import functools
import os
import yaml
from time import sleep
import multiprocessing
import threading

import wx
from wx.lib.newevent import NewEvent
import wx.adv

from ssh_samba import SshSamba
from ssh_samba import User


# =========================================================================
# =========================     Global Functions     ======================
# =========================================================================
def get_selected_rows(listCtrl: wx.ListCtrl) -> list:
    """    Gets the selected items for the list control.
    Selection is returned as a list of selected indices,
    low to high.
    """
    selection = []
    index = listCtrl.GetFirstSelected()
    while index >= 0:  # GetFirstSelected & GetNextSelected return -1 if there is nothing selected
        selection.append(index)
        index = listCtrl.GetNextSelected(index)

    return selection

background_return = None  # Return value for threads running in the background
# =========================================================================
# =========================     Custom events     =========================
# =========================================================================
# These events will be fired by child threads, to be picked up by the main application
EvtThread, EVT_THREAD = NewEvent()
EvtConnectionMade, EVT_CONNECTION_MADE = NewEvent()
EvtUsersChanged, EVT_USERS_CHANGED = NewEvent()

# ====================================================================================
# =========================     Decorators     =========================
# ====================================================================================
# Decorate any function with this in order to bring up an error window should it go wrong.
def error_window(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, *kwargs)
        except Exception as e:
            try:
                wx.MessageBox(f"An error occured:\n{e.args[0]}")
            except:
                wx.MessageBox(f"An error occured:\n{repr(e)}")
    return wrapped


def loading_window(function):
    """
    Puts the passed function in another thread and displays a loading window until it returns
    NB does not yet handle receiving arguments!
    """
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        thFunc = threading.Thread(target=function, args=args, kwargs=kwargs)
        thFunc.start()
        throbber = wx.ProgressDialog(title="Working",
                         message="Sending SSH commands...",
                         maximum=10,
                         parent=None,
                         style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
        throbber.Centre(wx.BOTH)
        while thFunc.is_alive():
            throbber.Pulse(newmsg="Sending SSH commands...")
            sleep(0.1)
        thFunc.join()
        global background_return
        function_result = background_return
        background_return = None
        throbber.Destroy()
        return function_result
    return wrapped

# ============================================================================
# ======================     Main Application Class     ======================
# ============================================================================
class AppMain(wx.App):
    def OnInit(self):
        self.SetAppName("ssh_samba")

        # Preferences file path
        self.fpPreferences = wx.StandardPaths.Get().GetUserLocalDataDir() + '/prefs.yaml'

        # Initialise model
        self.ad = SshSamba()  # This will be the ssh_samba model

        # Initialise preferences dictionary
        self.dicPrefs = {
            'IP Address': '',
            'Username': '',
            'Connect automatically': False,
        }
        self.read_preferences_file()

        # Connect automatically if stated in prefs
        if self.connect_automatically():
            self.show_main_window()
            return True

        # Show startup window if not
        self.frStartup = FrStartup(self)
        self.Bind(EVT_CONNECTION_MADE, self.show_main_window)
        self.frStartup.Show(True)
        return True

    def read_preferences_file(self):
        """
        Get the preferences from file into self.dicPrefs
        """
        if os.path.exists(self.fpPreferences):
            with open(self.fpPreferences, 'r') as file:
                self.dicPrefs = yaml.full_load(file)
        if not 'IP Address' in self.dicPrefs:
            self.dicPrefs['IP Address'] = ''
        if not 'Username' in self.dicPrefs:
            self.dicPrefs['Username'] = ''
        if not 'Connect automatically' in self.dicPrefs:
            self.dicPrefs['Connect automatically'] = False

    def write_preferences_file(self):
        """
        Write dicprefs to file to recall it later
        """
        folder = os.path.dirname(self.fpPreferences)
        if not os.path.exists(folder):
            os.mkdir(folder)
        if not os.access(folder, os.W_OK):
            raise PermissionError(f"Trying to save preferences but cannot write to folder {os.path.basename(folder)}")

        with open(self.fpPreferences, 'w') as file:
            yaml.dump(self.dicPrefs, file)

        print("Preferences saved")

    def connect_automatically(self):
        """
        Use the already parsed preferences file to connect to the server automatically.
        :return: True if connected, False is not
        """
        if not self.dicPrefs['Connect automatically']:
            return False
        try:
            self.ad.set_ip(self.dicPrefs['IP Address'])
            self.ad.set_user(self.dicPrefs['Username'])
            self.ad.set_password('')
            self.ad.connect_to_server()
            return True
        except:
            return False

    def show_main_window(self, event=None):
        self.frMain = FrMainwindow(self)
        self.frMain.Show(True)


# ==============================================================================
# ===============     Startup window to initiate the connection     ============
# ==============================================================================
class FrStartup(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent=None, title="Connect to Domain Controller")
        self.app = parent
        self.init_gui()
        self.populate()
        # The secrete recipe to fit window to content
        self.panStartup.SetAutoLayout(True)
        self.sizerGrid.Fit(self.panStartup)
        self.panStartup.Fit()
        self.Fit()
        self.CenterOnScreen()
        # self.SetInitialSize((600, 400))

    @error_window
    def init_gui(self):
        # =========================     Initialise the GUI     =========================
        # ==============================================================================
        self.panStartup = wx.Panel(self)
        self.sizerGrid = wx.GridBagSizer(vgap=1, hgap=1)
        self.panStartup.SetSizer(self.sizerGrid)

        self.txtIP = wx.StaticText(self.panStartup, label="IP address", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.txtIP, pos=(0, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.entIP = wx.TextCtrl(self.panStartup, value="")
        self.entIP.Bind(wx.EVT_CHAR, self.on_key_IP)
        self.sizerGrid.Add(self.entIP, pos=(1, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.txtUser = wx.StaticText(self.panStartup, label="User", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.txtUser, pos=(2, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.entUser = wx.TextCtrl(self.panStartup, value="root")
        self.sizerGrid.Add(self.entUser, pos=(3, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.txtPass = wx.StaticText(self.panStartup, label="Password\n(Leave blank if you have passwordless SSH)", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.txtPass, pos=(4, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.entPass = wx.TextCtrl(self.panStartup, value="", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.entPass, pos=(5, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.chkAuto = wx.CheckBox(self.panStartup, label="Connect automatically\n(if you have passwordless SSH)")
        # self.chkAuto.SetValue(True)
        self.sizerGrid.Add(self.chkAuto, pos=(6, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)

        self.butConnect = wx.Button(self.panStartup, label="Connect")
        self.butConnect.Bind(wx.EVT_BUTTON, self.on_but_connect)

        self.sizerGrid.Add(self.butConnect, pos=(7, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)

    def dummy_function(self):
        """
        Placeholder function so I can make the buttons before the things they do.
        """
        pass

    def on_key_IP(self, event):
        """
        Validate the IP entry box as we go to only allow numbers and .
        """
        keycode = event.GetKeyCode()
        tupAllowed_keycodes = (
            wx.WXK_CONTROL,  # command/control
            wx.WXK_RAW_CONTROL,  # command on Mac when remapped
            wx.WXK_CONTROL_C,
            wx.WXK_CONTROL_X,
            wx.WXK_CONTROL_V,
            wx.WXK_CONTROL_Z,
            wx.WXK_BACK,
            wx.WXK_TAB,
            wx.WXK_RETURN,
            wx.WXK_ESCAPE,
            wx.WXK_DELETE,
            wx.WXK_START,
            wx.WXK_LBUTTON,
            wx.WXK_RBUTTON,
            wx.WXK_CANCEL,
            wx.WXK_MBUTTON,
            wx.WXK_CLEAR,
            wx.WXK_SHIFT,
            wx.WXK_ALT,
            wx.WXK_END,
            wx.WXK_HOME,
            wx.WXK_LEFT,
            wx.WXK_UP,
            wx.WXK_RIGHT,
            wx.WXK_DOWN,
            wx.WXK_SELECT,
            wx.WXK_CONTROL_A,
            wx.WXK_SNAPSHOT,
            wx.WXK_INSERT,
            wx.WXK_NUMPAD0,
            wx.WXK_NUMPAD1,
            wx.WXK_NUMPAD2,
            wx.WXK_NUMPAD3,
            wx.WXK_NUMPAD4,
            wx.WXK_NUMPAD5,
            wx.WXK_NUMPAD6,
            wx.WXK_NUMPAD7,
            wx.WXK_NUMPAD8,
            wx.WXK_NUMPAD9,
            wx.WXK_DECIMAL,
            wx.WXK_NUMLOCK,
            wx.WXK_NUMPAD_TAB,
            wx.WXK_NUMPAD_ENTER,
            wx.WXK_NUMPAD_HOME,
            wx.WXK_NUMPAD_LEFT,
            wx.WXK_NUMPAD_UP,
            wx.WXK_NUMPAD_RIGHT,
            wx.WXK_NUMPAD_DOWN,
            wx.WXK_NUMPAD_END,
            wx.WXK_NUMPAD_BEGIN,
            wx.WXK_NUMPAD_INSERT,
            wx.WXK_NUMPAD_DELETE,
            wx.WXK_NUMPAD_DECIMAL,
            wx.WXK_COMMAND,
        )
        if chr(keycode).isnumeric() or chr(keycode) == '.':
            event.Skip()
            return
        if keycode in tupAllowed_keycodes:
            event.Skip()
            return

    @error_window
    def on_but_connect(self, event=None):
        """
        Call SshSamba's connect to server function with the input from the GUI
        """
        self.app.ad.set_ip(self.entIP.GetValue())
        self.app.dicPrefs['IP Address'] = app.ad.remote_server_ip
        self.app.ad.set_user(self.entUser.GetValue())
        self.app.dicPrefs['Username'] = app.ad.user
        self.app.ad.set_password(self.entPass.GetValue())
        self.app.dicPrefs['Connect automatically'] = self.chkAuto.GetValue()
        self.app.write_preferences_file()
        self.app.ad.connect_to_server()
        wx.PostEvent(self.app, EvtConnectionMade())
        self.Destroy()

    def populate(self):
        self.entIP.SetValue(self.app.dicPrefs['IP Address'])
        self.entUser.SetValue(self.app.dicPrefs['Username'])


# =======================================================================
# =========================     Main Window     =========================
# =======================================================================
class FrMainwindow(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent=None, title="Samba Domain Controller Controller")
        self.app = parent

        self.init_menu()
        self.init_gui()

        # Bind frame to events to have events change the GUI
        self.Bind(EVT_THREAD, self.template_on_thread)
        self.Bind(EVT_USERS_CHANGED, self.populate_users)

        # Initalise GUI content
        self.populate_gui()

        # The secrete recipe to fit window to content
        self.panMaster.SetAutoLayout(True)
        self.sizerGrid.Fit(self.panMaster)
        self.panMaster.Fit()
        self.Fit()

    def init_shortcuts(self):
        # ===================================================================================
        # =============     Bind global (to the window) keyboard shortcuts     ==============
        # ===================================================================================
        self.Bind()

    @error_window
    def init_menu(self):
        # ===================================================================================
        # =========================     Initialise the Menu Bar     =========================
        # ===================================================================================
        menuBar = wx.MenuBar()
        self.menuApplication = wx.Menu()

        menuItemQuit = self.menuApplication.Append(
            wx.ID_ANY,
            "Quit",
            "Quit the application."
        )

        self.menuItemAutoConnect = self.menuApplication.Append(
            wx.ID_ANY,
            "Don't connect Automatically",
            "Stop using system-installed ssh keys to connect automatically."
        )

        menuBar.Append(self.menuApplication, '&Application')

        # Bind menu functions
        self.Bind(
            event=wx.EVT_MENU,
            handler=self.on_menu_quit,
            source=menuItemQuit
        )
        self.Bind(
            event=wx.EVT_MENU,
            handler=self.on_menu_auto_connect,
            source=self.menuItemAutoConnect
        )
        self.SetMenuBar(menuBar)

    @error_window
    def init_gui(self):
        # ==============================================================================
        # =========================     Initialise the GUI     =========================
        # ==============================================================================
        # Make the master panel, and the sizer for the frame
        self.panMaster = wx.Panel(self)
        self.sizerFrame = wx.BoxSizer(wx.VERTICAL)
        self.sizerFrame.Add(self.panMaster, 1, wx.EXPAND)
        self.SetSizer(self.sizerFrame)

        # The GUI is organised in a 2D array of static box Sizers
        # You can access each cell by co-ordinate: self.lstBoxes[y][x]
        # You can also iterate through it.
        # Choose the number of rows and columns below.
        self.sizerGrid = wx.GridBagSizer(vgap=1, hgap=1)
        self.panMaster.SetSizer(self.sizerGrid)

        # This is our design:
        # ---------------------------------
        # |          |          |          |
        # |   0, 0   |   0, 1   |   0, 2   |
        # |          |          |          |
        # -----------           |          |
        # |          |          |          |
        # |   1, 0   |          |          |
        # |          |          |          |
        # ---------------------------------

        # ====================   Adding content to each FlexGridSizer   ====================
        #  -----------------------
        # | this  |       |       |
        # |  box  |       |       |
        # |       |       |       |
        #  -------        |       |
        # |       |       |       |
        # |       |       |       |
        # |       |       |       |
        #  -----------------------
        self.boxDomain = wx.StaticBox(self.panMaster, label="Your Domain")
        self.boxDomainSizer = wx.StaticBoxSizer(self.boxDomain, wx.VERTICAL)
        # This list of domain info to be replaced by the populate_gui function
        dic_domain_info = {
            'Domain info 1': 'info',
            'Domain info 2': 'info',
            'Domain info 3': 'info',
        }
        self.lst_txt_domain_info = [wx.StaticText(self.panMaster, label=x) for x in dic_domain_info.values()]
        for txt in self.lst_txt_domain_info:
            self.boxDomainSizer.Add(txt, 1, wx.ALL | wx.EXPAND, 1)

        self.sizerGrid.Add(self.boxDomainSizer, pos=(0, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)


        # ======================================================================================
        #  -----------------------
        # |       |       |       |
        # |       |       |       |
        # |       |       |       |
        #  -------        |       |
        # | this  |       |       |
        # |  box  |       |       |
        # |       |       |       |
        #  -----------------------

        self.boxPolicy = wx.StaticBox(self.panMaster, label="Password Policy")
        self.boxPolicySizer = wx.StaticBoxSizer(self.boxPolicy, wx.VERTICAL)

        # This list of password info to be replaced by the populate_gui function
        dic_password_policy = {
            'Policy 1': 'value',
            'Policy 2': 'value',
            'Policy 3': 'value',
        }
        self.lst_password_policy_boxes = [[wx.StaticText(self.panMaster, label=key), wx.TextCtrl(self.panMaster, value=value)] for key, value in dic_password_policy.items()]
        self.sizerPolicy = wx.FlexGridSizer(2, 1, 1)
        for policy_item in self.lst_password_policy_boxes:
            self.sizerPolicy.Add(policy_item[0], 0, wx.ALL, 1)
            self.sizerPolicy.Add(policy_item[1], 0, wx.ALL, 1)
        self.boxPolicySizer.Add(self.sizerPolicy, 0, wx.ALL, 5)

        self.but_policy_update = wx.Button(self.panMaster, label="Update password policy")
        self.but_policy_update.Bind(wx.EVT_BUTTON, self.on_but_policy_update)
        self.boxPolicySizer.Add(self.but_policy_update, 0, wx.EXPAND, 5)

        self.sizerGrid.Add(self.boxPolicySizer, pos=(1, 0), span=(1, 1), flag=wx.ALL, border=5)

        # ======================================================================================
        #  -----------------------
        # |       |       |       |
        # |       | this  |       |
        # |       |  box  |       |
        #  -------        |       |
        # |       |       |       |
        # |       |       |       |
        # |       |       |       |
        #  -----------------------

        self.boxUsers = wx.StaticBox(self.panMaster, label="Users")
        self.boxUsersSizer = wx.StaticBoxSizer(self.boxUsers, wx.VERTICAL)

        self.lstctrlUsers = wx.ListCtrl(self.panMaster, style=wx.LC_REPORT)
        self.lstctrlUsers.InsertColumn(0, 'Login name', width=100)
        self.lstctrlUsers.InsertColumn(1, 'Given name', width=100)
        self.lstctrlUsers.InsertColumn(2, 'Surname', width=100)
        self.lstctrlUsers.InsertColumn(3, 'Flags', width=200)

        self.sizer_buttons_users = wx.FlexGridSizer(cols=2, vgap=1, hgap=1)
        self.but_user_add = wx.Button(self.panMaster, label="Add users")
        self.but_user_add.Bind(wx.EVT_BUTTON, self.on_but_user_add)
        self.sizer_buttons_users.Add(self.but_user_add, 1, wx.ALL | wx.EXPAND, 2)
        self.but_user_enable = wx.Button(self.panMaster, label="Enable users")
        self.but_user_enable.Bind(wx.EVT_BUTTON, self.on_but_user_enable)
        self.sizer_buttons_users.Add(self.but_user_enable, 1, wx.ALL | wx.EXPAND, 2)
        self.but_user_delete = wx.Button(self.panMaster, label="Delete users")
        self.but_user_delete.Bind(wx.EVT_BUTTON, self.on_but_user_delete)
        self.sizer_buttons_users.Add(self.but_user_delete, 1, wx.ALL | wx.EXPAND, 2)
        self.but_user_disable = wx.Button(self.panMaster, label="Disable users")
        self.but_user_disable.Bind(wx.EVT_BUTTON, self.on_but_user_disable)
        self.sizer_buttons_users.Add(self.but_user_disable, 1, wx.ALL | wx.EXPAND, 2)
        self.but_user_change_pw = wx.Button(self.panMaster, label="Change password")
        self.but_user_change_pw.Bind(wx.EVT_BUTTON, self.on_but_user_password)
        self.sizer_buttons_users.Add(self.but_user_change_pw, 1, wx.ALL | wx.EXPAND, 2)
        self.sizer_buttons_users.AddGrowableCol(0)
        self.sizer_buttons_users.AddGrowableCol(1)

        self.boxUsersSizer.Add(self.lstctrlUsers, 1, wx.ALL | wx.EXPAND, 5)
        self.boxUsersSizer.Add(self.sizer_buttons_users, 1, wx.ALL | wx.EXPAND, 5)
        # self.boxUsersSizer.AddStretchSpacer()
        # self.boxUsersSizer.Fit(self.panMaster)

        self.sizerGrid.Add(self.boxUsersSizer, pos=(0, 1), span=(2, 1), flag=wx.ALL | wx.EXPAND, border=5)

        # ======================================================================================
        #  -----------------------
        # |       |       |       |
        # |       |       | this  |
        # |       |       |  box  |
        #  -------        |       |
        # |       |       |       |
        # |       |       |       |
        # |       |       |       |
        #  -----------------------
        # This panel uses a variable, latestRow, to allow adding in GrowableRows at the bottom, even if you swap stuff

        self.boxGroups = wx.StaticBox(self.panMaster, label="Groups")
        self.boxGroupsSizer = wx.StaticBoxSizer(self.boxGroups, wx.VERTICAL)

        self.treeGroups = wx.TreeCtrl(self.panMaster, style=wx.TR_MULTIPLE)

        self.sizer_buttons_groups = wx.FlexGridSizer(cols=2, vgap=1, hgap=1)
        self.but_group_add = wx.Button(self.panMaster, label="Add groups")
        self.but_group_add.Bind(wx.EVT_BUTTON, self.on_but_group_add)
        self.sizer_buttons_groups.Add(self.but_group_add, 1, wx.ALL | wx.EXPAND, 2)
        self.but_group_remove = wx.Button(self.panMaster, label="Remove groups")
        self.but_group_remove.Bind(wx.EVT_BUTTON, self.on_but_group_remove)
        self.sizer_buttons_groups.Add(self.but_group_remove, 1, wx.ALL | wx.EXPAND, 2)
        self.but_members_add = wx.Button(self.panMaster, label="Add selected users to group")
        self.but_members_add.Bind(wx.EVT_BUTTON, self.on_but_members_add)
        self.sizer_buttons_groups.Add(self.but_members_add, 1, wx.ALL | wx.EXPAND, 2)
        self.but_members_remove = wx.Button(self.panMaster, label="Remove selected users from group")
        self.but_members_remove.Bind(wx.EVT_BUTTON, self.on_but_members_remove)
        self.sizer_buttons_groups.Add(self.but_members_remove, 1, wx.ALL | wx.EXPAND, 2)
        self.sizer_buttons_groups.AddGrowableCol(0)
        self.sizer_buttons_groups.AddGrowableCol(1)

        self.boxGroupsSizer.Add(self.treeGroups, 1, wx.ALL | wx.EXPAND, 5)
        self.boxGroupsSizer.Add(self.sizer_buttons_groups, 1, wx.ALL | wx.EXPAND, 5)
        # self.boxGroupsSizer.AddStretchSpacer()
        # self.boxGroupsSizer.Fit(self.panMaster)

        self.sizerGrid.Add(self.boxGroupsSizer, pos=(0, 2), span=(2, 1), flag=wx.ALL | wx.EXPAND, border=5)

        # ==========    Now that the rows and columns have been populated, choose which ones stretch    ==============

        self.sizerGrid.AddGrowableCol(2, 1)
        self.sizerGrid.AddGrowableCol(1, 1)
        self.sizerGrid.AddGrowableRow(1, 1)


    # ===========================================================================================
    # =========================     Functions called by GUI Widgets     =========================
    # ===========================================================================================

    # I find it useful to have a dummy function to apply to widgets I want on the GUI
    # but have not written the function for yet.
    def dummy_function(self, *args):
        """
        A placeholder function to allow the making of widget on the GUI before writing its function.
        """
        pass

    # Functions to be called from widgets on the GUI
    # I like to prefix all functions called from widgets with 'on_'
    # Subcategories are:
    #   - on_menu:      called from clicking a menu item
    #   - on_key:       called from key press
    #   - on_but:       called from button click
    #   - on_chkBox:    called from check box click
    #   - on_but_ent:   called from pressing the button linked to an entry box
    #   - on_sel:       called from selecting something
    #   - on_thread:    called from a sub-thread firing an event
    def on_menu(self, event):
        pass

    def on_menu_quit(self, event):
        self.shut_down()

    @error_window
    def on_menu_auto_connect(self, event):
        app.dicPrefs['Connect automatically'] = False
        app.write_preferences_file()

    def on_key_quit(self, event):
        # TO DO:
        #   Have cmd q call the clean shutdown function and not just straight quit.
        pass

    def on_key(self, event):
        if event.GetKeyCode() == wx.WXK_NUMPAD_ENTER or event.GetKeyCode() == wx.WXK_RETURN:
            # Do positive action!
            self.dummy_function()
        elif event.GetKeyCode() == wx.WXK_DELETE or event.GetKeyCode() == wx.WXK_BACK:
            # Do negative action :(
            self.dummy_function()
        else:
            # They pressed an irrelevant button
            event.Skip()

    @error_window
    def on_but_policy_update(self, event=None):
        dicPolicy = {}
        for policy_item in self.lst_password_policy_boxes:
            dicPolicy[policy_item[0].GetLabel()] = policy_item[1].GetValue()
        self.bg_set_password_policy(dicPolicy)
        self.populate_password_policy()

    @error_window
    def on_but_user_add(self, event=None):
        self.frUserAdd = FrAddUsers(self.app)
        self.frUserAdd.Show(True)

    @error_window
    def on_but_user_delete(self, event=None):
        lstUsers = self.get_selected_usernames()
        if lstUsers:
            self.bg_delete_users(lstUsers)
            self.populate_users()
            self.populate_groups()

    @error_window
    def on_but_user_disable(self, event=None):
        lstUsers = self.get_selected_usernames()
        if lstUsers:
            self.bg_disable_users(lstUsers)
            self.populate_users()

    @error_window
    def on_but_user_enable(self, event=None):
        lstUsers = self.get_selected_usernames()
        if lstUsers:
            self.bg_enable_users(lstUsers)
            self.populate_users()

    @error_window
    def on_but_user_password(self, event=None):
        lstUsers = self.get_selected_usernames()
        if not lstUsers:
            return
        if len(lstUsers) != 1:
            wx.MessageBox("Please select only one user", "Change user password")
            return
        usr = lstUsers[0]
        dlg = wx.TextEntryDialog(self.app.frMain, 'Please enter the new password', 'Change user password')
        if dlg.ShowModal() == wx.ID_OK:
            new_password = dlg.GetValue()
            self.bg_password_user(usr, new_password)
            self.populate_users()

        dlg.Destroy()

    @error_window
    def on_but_group_add(self, event=None):
        # TO DO:
        #  - Add multiple groups
        #  - Add sub-group to group
        dlg = wx.TextEntryDialog(self.app.frMain, 'Please enter the name of the new group', 'Add group')
        if dlg.ShowModal() == wx.ID_OK:
            group_to_add = dlg.GetValue()
            self.bg_add_group(group_to_add)
            self.populate_groups()

        dlg.Destroy()

    @error_window
    def on_but_group_remove(self, event=None):
        sel = self.treeGroups.GetSelections()
        if len(sel) > 1:
            wx.MessageBox("Please select just one group for deletion.", "Remove group")
            return
        if len(sel) == 0:
            return
        grp = self.treeGroups.GetItemText(sel[0])
        if grp not in self.bg_get_groups().keys():
            wx.MessageBox(f"{grp} is not a group!", "Remove group")
            return
        self.bg_delete_group(grp)
        self.populate_groups()


    @error_window
    def on_but_members_add(self, event=None):
        lstUsers = self.get_selected_usernames()
        if len(lstUsers) == 0:
            wx.MessageBox("Please select users from the users panel.", "Remove group members")
            return
        lstSelection = self.treeGroups.GetSelections()
        if len(lstSelection) != 1:
            wx.MessageBox("Please select one group from the group panel.", "Remove group members")
            return
        grp = self.treeGroups.GetItemText(lstSelection[0])
        if grp not in self.bg_get_groups().keys():
            wx.MessageBox(f"{grp} is not a group!", "Add users to group.")
            return
        if lstUsers:
            self.bg_add_members_to_group(grp, lstUsers)
            self.populate_groups()

    @error_window
    def on_but_members_remove(self, event=None):
        """
        User has selected some group members in the group tree.
        Each of these members will be removed from parent on the tree.
        :param event: Just takes the button click event if there is one.
        """
        lstSelection = self.treeGroups.GetSelections()
        if len(lstSelection) == 0:
            return

        lstSelected_usernames = [self.treeGroups.GetItemText(x) for x in lstSelection]
        lstUsers = [usr.username for usr in self.bg_get_users()]
        lstRejects = []
        for i in lstSelected_usernames:
            if i not in lstUsers:
                lstRejects.append(i)

        if lstRejects:
            wx.MessageBox(f"Please select only users on the tree to remove from their parent group.")
            return

        lstGrps = self.bg_get_groups().keys()
        lstGroups_and_members_to_delete = [(self.treeGroups.GetItemText(self.treeGroups.GetItemParent(x)), self.treeGroups.GetItemText(x)) for x in lstSelection]
        for grp, usr in lstGroups_and_members_to_delete:
            assert grp in lstGrps
            assert usr in lstUsers
            self.bg_delete_members_from_group(grp, usr)

        self.populate_groups()


    # ==========================================================================
    # =========================     Main functions     =========================
    # ==========================================================================
    @error_window
    def populate_gui(self, event=None):
        """
        Clear and repopulate the data in the GUI.
        Used when the program is loaded, data is loaded from file or data is input by the user.
        """
        # You'll want some kind of check to see if the program is just opened, ie. no data model has been populated yet.
        # program_just_opened_and_there_is_no_data = True
        # if program_just_opened_and_there_is_no_data:
        #     [x.SetValue(False) for x in self.dicChkBoxes.values()]
        #     self.lstBoxUsers.Clear()
        #     return
        self.populate_users()
        self.populate_groups()
        self.populate_domain()
        self.populate_password_policy()
        self.FitInside()

    @error_window
    def populate_users(self, event=None):
        self.lstctrlUsers.DeleteAllItems()
        for usr in self.bg_get_users():
            # get_users returns list of user objects
            item = [usr.username, usr.given_name, usr.surname, str(usr.flags)]
            self.lstctrlUsers.Append(item)
        self.Layout()

    @error_window
    def populate_groups(self, event=None):
        self.treeGroups.DeleteAllItems()
        root = self.treeGroups.AddRoot(self.bg_get_domain_name())
        for grp, members in self.bg_get_groups().items():
            item_grp = self.treeGroups.AppendItem(root, grp)
            for mem in members:
                self.treeGroups.AppendItem(item_grp, mem)
        self.treeGroups.ExpandAll()
        self.Layout()

    @error_window
    def populate_domain(self, event=None):
        for txt in self.lst_txt_domain_info:
            txt.Destroy()
        self.lst_txt_domain_info = [wx.StaticText(self.panMaster, label=f"{x}: {y}") for x, y in self.bg_get_domain().items()]
        for txt in self.lst_txt_domain_info:
            self.boxDomainSizer.Add(txt, 0, wx.ALL | wx.EXPAND, 1)
        self.Layout()

    @error_window
    def populate_password_policy(self, event=None):
        for policy_item in self.lst_password_policy_boxes:
            policy_item[0].Destroy()
            policy_item[1].Destroy()
        self.lst_password_policy_boxes = [[wx.StaticText(self.panMaster, label=key), wx.TextCtrl(self.panMaster, value=value)] for key, value in self.bg_get_password_policy().items()]
        for policy_item in self.lst_password_policy_boxes:
            self.sizerPolicy.Add(policy_item[0], 0, wx.ALL, 1)
            self.sizerPolicy.Add(policy_item[1], 0, wx.ALL, 1)
        self.Layout()

    @loading_window
    @error_window
    def bg_get_users(self):
        """Gets the users in the domain. Run as background process using decorator, which returns background_return"""
        global background_return
        background_return = self.app.ad.get_users()

    @loading_window
    @error_window
    def bg_get_groups(self):
        """Gets the groups in the domain. Run as background process using decorator, which returns bakground_return"""
        global background_return
        background_return = self.app.ad.get_groups()

    @loading_window
    @error_window
    def bg_get_domain(self):
        """Gets the domain info. Run as background process using decorator, which returns bakground_return"""
        global background_return
        background_return = self.app.ad.get_domain()

    @loading_window
    @error_window
    def bg_get_domain_name(self):
        """Gets the domain name. Run as background process using decorator, which returns bakground_return"""
        global background_return
        background_return = self.app.ad.get_domain_long()

    @loading_window
    @error_window
    def bg_get_password_policy(self):
        """Gets the domain name. Run as background process using decorator, which returns bakground_return"""
        global background_return
        background_return = self.app.ad.get_password_policy()

    @loading_window
    @error_window
    def bg_add_users(self, lstUsers):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.add_users(lstUsers)

    @loading_window
    @error_window
    def bg_delete_users(self, lstUsers):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.delete_users(lstUsers)

    @loading_window
    @error_window
    def bg_disable_users(self, lstUsers):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.disable_users(lstUsers)

    @loading_window
    @error_window
    def bg_enable_users(self, lstUsers):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.enable_users(lstUsers)

    @loading_window
    @error_window
    def bg_password_user(self, user, password, must_change_at_next_login=False):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.password_user(user, password, must_change_at_next_login=must_change_at_next_login)

    @loading_window
    @error_window
    def bg_add_group(self, group):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.add_group(group)

    @loading_window
    @error_window
    def bg_delete_group(self, group):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.delete_group(group)

    @loading_window
    @error_window
    def bg_add_members_to_group(self, group, members):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.add_members_to_group(group, members)

    @loading_window
    @error_window
    def bg_delete_members_from_group(self, group, members):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.delete_members_from_group(group, members)

    @loading_window
    @error_window
    def bg_set_password_policy(self, dicPolicy):
        """
        Run as background process using decorator.
        No return value
        """
        self.app.ad.set_password_policy(dicPolicy)

    def get_selected_usernames(self):
        username_column = 0
        return [self.lstctrlUsers.GetItem(row, username_column).Text for row in get_selected_rows(self.lstctrlUsers)]

    def shut_down(self):
        """
        Shut down application cleanly.
        """
        # Do something with preferences maybe
        #self.lstPrefs
        #self.fpPreferences

        # Warn user/Terminate sub processes
        wx.Exit()

    @error_window
    def template_on_but_error(self, event=None):
        raise Exception("This is an error!")

    def template_on_chkbox(self, event):
        # Get the states of all the check boxes to process their info
        dicOptions = {label: box.GetValue() for label, box in self.dicChkBoxes.items()}
        self.dummy_function(dicOptions)

    def template_on_but_ent(self, event):
        # Get the value from the relevant entry box
        ent = self.entOne.GetValue()
        if ent:
            self.dummy_function(ent)
            self.entOne.Clear()

    def template_on_sel(self, event):
        important_information = self.lstCtlStuff.GetFirstSelected()
        self.dummy_function(important_information)

    def template_on_thread(self, event):
        feedback_from_thread = event.attr1
        self.dummy_function(feedback_from_thread)

    def template_make_new_thread(self):
        # Make a new thread using the threading module.
        # This allows you to run a background task
        self.thNew = threading.Thread(target=self.background_task)
        self.thNew.start()

    def template_background_task(self):
        # If the background task needs to communicate something back to main task,
        # for example, task progress, we need to do some multiprocessing.

        # First, make a variable that will be shared between processes.
        # This will be an array of C-Types. See the docs of the array module for more info.
        # Examples, 'l' = signed long, 'u' = unicode character, 'i' = signed int, etc.
        # Here, we will make an array of 5 zeroes, of type signed long
        no_of_progress_bars = 5
        progress = multiprocessing.Array('l', [0] * no_of_progress_bars)
        self.procExample = multiprocessing.Process(target=self.dummy_function, args=(progress,))
        self.procExample.start()

        # THIS is why we made that thread event at the top, and why we have our 'on_thread' function above
        # This sub thread will monitor the child process by continually posting an event containing the
        # shared variable we just made.
        # To summarise:
        #   - child process modifies variable
        #   - child thread reads variable and puts it in event
        #   - parent thread listens for event
        #   - parent thread runs on_thread function
        while self.procExample.is_alive():
            wx.PostEvent(frame, EvtThread(attr1=progress))
            sleep(1)

        # Now, the child process has finished. Let's fire the event for the final time and finish up.
        wx.PostEvent(frame, EvtThread(attr1=progress))
        dialog = "Background task finished!"
        wx.MessageBox(frame, dialog)

# =====================================================
# ===============     Add users window     ============
# =====================================================
class FrAddUsers(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent=None, title="Add users")
        self.app = parent
        self.init_gui()

        # This is the secret recipe for fitting the window to the content
        self.panUsers.SetAutoLayout(True)
        self.sizerGrid.Fit(self.panUsers)
        self.panUsers.Fit()
        self.Fit()

    def init_gui(self):
        # =========================     Initialise the GUI     =========================
        # ==============================================================================
        self.panUsers = wx.Panel(self)
        self.sizerGrid = wx.GridBagSizer(vgap=1, hgap=1)
        self.panUsers.SetSizer(self.sizerGrid)

        # Titles
        self.txtUsername = wx.StaticText(self.panUsers, label="Username", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.txtUsername, pos=(0, 0), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.txtGiven_name = wx.StaticText(self.panUsers, label="Given Name", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.txtGiven_name, pos=(0, 1), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.txtSurname = wx.StaticText(self.panUsers, label="Surname", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.txtSurname, pos=(0, 2), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        self.txtPassword = wx.StaticText(self.panUsers, label="Password", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.sizerGrid.Add(self.txtPassword, pos=(0, 3), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)

        #Entry boxes
        self.lstEnts = []
        no_of_rows = 10
        no_of_cols = 4
        for row in range(0, no_of_rows):
            self.lstEnts.append([wx.TextCtrl(self.panUsers) for x in range(no_of_cols)])
            for col, ent in enumerate(self.lstEnts[row]):
                self.sizerGrid.Add(ent, pos=(row + 1, col), span=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)

        # Buttons
        self.butAdd_users = wx.Button(self.panUsers, label="Add users")
        self.butAdd_users.Bind(wx.EVT_BUTTON, self.on_but_add)
        self.sizerGrid.Add(self.butAdd_users, pos=(row + 2, 0), span=(1, 2), flag=wx.ALL | wx.EXPAND, border=5)
        self.butCancel = wx.Button(self.panUsers, label="Cancel")
        self.butCancel.Bind(wx.EVT_BUTTON, self.on_but_cancel)
        self.sizerGrid.Add(self.butCancel, pos=(row + 2, 2), span=(1, 2), flag=wx.ALL | wx.EXPAND, border=5)
        self.butImport = wx.Button(self.panUsers, label="Import CSV")
        self.butImport.Bind(wx.EVT_BUTTON, self.on_but_import)
        self.sizerGrid.Add(self.butImport, pos=(row + 3, 0), span=(1, 4), flag=wx.ALL | wx.EXPAND, border=5)

    @error_window
    def on_but_add(self, event=None):
        """
        Call SshSamba's connect to server function with the input from the GUI
        """
        lstUsers_to_add = []

        for row, lst_of_boxes in enumerate(self.lstEnts):
            lstVals = [box.GetValue() for box in lst_of_boxes]
            if any([x == '' for x in lstVals]):
                continue
            lstUsers_to_add.append(User())
            lstUsers_to_add[row].set_username(lstVals[0])
            lstUsers_to_add[row].set_given_name(lstVals[1])
            lstUsers_to_add[row].set_surname(lstVals[2])
            lstUsers_to_add[row].set_password(lstVals[3])

        if not lstUsers_to_add:
            wx.MessageBox("No valid user details found.", "Add Users")
            return

        self.app.frMain.bg_add_users(lstUsers_to_add)
        wx.PostEvent(self.app.frMain, EvtUsersChanged())
        self.Destroy()

    @error_window
    def on_but_import(self, event=None):
        """
        Import a CSV of user details to add to the AD
        """
        # Write me please
        pass

    def on_but_cancel(self, event=None):
        self.Destroy()


class FrLoading(wx.Frame):
    def __init__(self):
        super().__init__(parent=None)
        self.dlg = wx.ProgressDialog(title="Working",
                         message="Sending SSH commands...",
                         maximum=10,
                         parent=self,
                         style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)


if __name__ == '__main__':
    app = AppMain()
    app.MainLoop()

