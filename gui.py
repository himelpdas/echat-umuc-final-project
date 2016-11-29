#!/usr/bin/python
# -*- coding: utf-8 -*-

# for testing before client gui integration and other experimental features
# from dummy import *

# actual client gui integration begins
from client import main as client

from Tkinter import *
import tkMessageBox, tkSimpleDialog
from multiprocessing import Process, Queue
from Queue import Empty
import random
import datetime
import keyring
import json
import socket
import os
# import psutil

DEBUG = 0


class LoginDialog(tkSimpleDialog.Dialog):

    def __init__(self, parent, up_queue, down_queue):
        self.up_queue = up_queue
        self.down_queue = down_queue
        # entry 1, 2, checkbox, err label, user, pass
        self.e1 = self.e2 = self.e3 = self.e4 = self.cb = self.er = self.un = \
            self.pw = self.ip = self.pt = self.dm = None
        tkSimpleDialog.Dialog.__init__(self, parent, title="Login now...")

    def body(self, master):  # called by the init tkSimpleDialog.Dialog.__init__

        Label(master, text="Username:").grid(row=0)
        Label(master, text="Password:").grid(row=1)
        Label(master, text="IP/Domain:").grid(row=2)
        Label(master, text="Port #:").grid(row=3)

        self.e1 = StringVar()  # username
        self.e2 = StringVar()  # password
        self.e3 = StringVar()  # ip
        self.e4 = StringVar()  # port
        self.cb = IntVar()  # remember
        e1 = Entry(master, textvariable=self.e1)
        e2 = Entry(master, show="*", textvariable=self.e2)
        e3 = Entry(master, textvariable=self.e3)
        e4 = Entry(master, textvariable=self.e4)
        cb = Checkbutton(master, text="Remember me?", variable=self.cb)
        self.er = Label(master, fg="red")
        e1.grid(row=0, column=1)
        e2.grid(row=1, column=1)
        e3.grid(row=2, column=1)
        e4.grid(row=3, column=1)
        cb.grid(row=4, columnspan=2, sticky=W)

        login = LoginDialog.get_login()
        if LoginDialog.remember_me(login):
            self.e1.set(login["username"])
            self.e2.set(login["password"])
            self.e3.set(login["domain"])
            self.e4.set(login["port"])
            self.cb.set(login["remember"])

        return e1  # initial focus

    @staticmethod
    def remember_me(login):
        return all(map(lambda k: login.get(k), ["username", "password", "ip", "domain", "port", "remember"]))

    @staticmethod
    def get_login():
        try:
            login = json.loads(keyring.get_password("echatr", "login"))
        except (ValueError, TypeError):  # something went wrong
            login = {'remember': 0}
            keyring.set_password("echatr", "login", json.dumps(login))
        return login

    def validate(self):
        """validate the data

        This method is called automatically to validate the data before the
        dialog is destroyed. By default, it always validates OK.
        """
        self.un = self.e1.get()
        self.pw = self.e2.get()
        self.dm = self.e3.get()
        self.pt = self.e4.get()
        empty = None
        if not self.un:
            empty = "Username"
        elif not self.pw:
            empty = "Password"
        elif not self.dm:
            empty = "IP/Domain"
        elif not self.pt:
            empty = "Port #"

        error = None
        try:
            self.ip = socket.gethostbyname(self.dm)  # converts domain name and IP as well
            self.pt = int(self.pt)
            if not self.pt >= 0 and not self.pt <= 65535:
                raise TypeError
        except socket.gaierror:
            error = "Could not resolve address or IP"
        except ValueError:
            error = "Port # must be integer 0 to 65535"

        if empty or error:
            self.er.grid(row=5, column=1)
            if empty:
                self.er.config(text="%s is blank!" % empty)
            elif error:
                self.er.config(text="%s!" % error)
            return 0
        else:
            return 1  # override

    def apply(self):
        if not self.parent.client_process_is_quitting and self.parent.client_process_is_alive():
            self.parent.up_queue.put((None, "/quit"))

        self.parent.un = self.un
        self.parent.pw = self.pw
        self.parent.ip = self.ip
        self.parent.pt = self.pt
        remember = self.cb.get()

        if remember:
            keyring.set_password("echatr", "login",
                                 json.dumps({"username": self.un, "password": self.pw, "remember": 1, "ip": self.ip,
                                             "domain": self.dm, "port": self.pt}))
        else:
            keyring.set_password("echatr", "login", json.dumps({"remember": 0}))

        self.parent.re_login()


class GUI(Frame):

    colors = {'red', 'blue', 'green', 'orange', 'purple', 'yellow', 'teal', 'pink', 'grey'}

    def __init__(self, parent, title):
        Frame.__init__(self, parent)

        # init args
        self.parent = parent
        self.up_queue = Queue()  # GUI TO CLIENT COMMUNICATION
        self.down_queue = Queue()  # CLIENT TO GUI COMMUNICATION
        self.client_process = self.client_pid = self.client_process_is_quitting = None
        self.title = title

        # helper variables
        self._listbox_previous_select = None
        self._listbox_current_select = None
        self._default_user_colors = {'EChatr': {'fg': 'black', 'bg': 'white'}}
        self._color_generator = self.colorize_names()
        self._blink = False
        self._killing_process = False

        # declare widgets
        self.panel = None
        self.users = None
        self.messages = None
        self.message_entry = None
        self.message_label = None
        self.scrollbar = None

        # init widgets
        self.init_menu()
        self.init_ui()

        # set dimensions
        parent.update()  # force app width and height to update before mainloop  http://bit.ly/2eroHkk
        self.default_x = self.parent.winfo_width()
        self.default_y = self.parent.winfo_height()

        # task loop
        parent.protocol("WM_DELETE_WINDOW", self.on_close)  # http://bit.ly/2fPXjRS
        self.task_loop()

        # initial messages
        self.show_help_messages()

        # current user
        login = LoginDialog.get_login()
        self.un = login.get("username", None)
        self.pw = login.get("password", None)
        self.ip = login.get("ip", None)
        self.pt = login.get("port", None)

        if LoginDialog.remember_me(login):  # safer than self.login
            self.re_login()

    def client_process_is_alive(self):
        return getattr(self.client_process, 'is_alive', lambda: None)()

    def start_client_process(self):
        self.client_process = Process(target=client, args=(self.up_queue, self.down_queue))
        self.client_process.start()
        self.client_pid = self.client_process.pid
        self.client_process_is_quitting = False

    def on_close(self):
        self.up_queue.put((None, "/quit"))  # kill dummy server
        self.parent.destroy()

    def reset_styling(self):
        if self._listbox_current_select:
            self.messages.tag_config(self._listbox_current_select, underline=False)
        self._listbox_previous_select = None
        self._listbox_current_select = None
        self.users.delete(0, END)  # reset the list box
        self.message_label.config(text=" <guest> Login First! ",
                                  fg="black",
                                  bg="white")

    def re_login(self):  #
        if not self.client_process_is_alive():  # http://bit.ly/2fVCXDc
            self.reset_styling()
            self.start_client_process()
            self.up_queue.put((self.ip, self.pt))
            self.up_queue.put((self.un, self.pw))
        else:
            self.parent.after(100, self.re_login)

    def task_loop(self):

        if self._listbox_current_select:
            self._blink = not self._blink
            self.messages.tag_config(self._listbox_current_select, underline=self._blink)

        try:
            incoming = self.down_queue.get_nowait()
            incoming_type = incoming[0]

        except Empty:
            if DEBUG:
                print "[Debug] Down Queue Empty"
            pass

        else:
            if incoming_type == "message":
                self.add_message(*incoming[1:])

            elif incoming_type == "system":
                system_type = incoming[2]

                if system_type == "login_success":
                    if self.un == incoming[1]:  # redundant check
                        self.message_label.config(text=" <%s> Enter Message: " % self.un,
                                                  fg=self._default_user_colors[self.un]['fg'],
                                                  bg=self._default_user_colors[self.un]['bg'])

                if system_type == "app_shutdown":
                    self.parent.after(incoming[1], self.on_close)

                if system_type == "client_restart":
                    self.client_process_is_quitting = True
                    self.parent.after(incoming[1], self.re_login)

                if system_type == "disable_widget":
                    getattr(self, incoming[1]).config(state=DISABLED)

                if system_type == "enable_widget":
                    getattr(self, incoming[1]).config(state=NORMAL)

                if system_type == "run_method":
                    getattr(self, incoming[1])()

            elif incoming_type == "user":
                add = incoming[2]
                name = incoming[1]

                if add:
                    self.add_user(name)

                else:  # remove
                    # self.del_user(user)
                    pass

        finally:
            self.parent.after(200, self.task_loop)  # update gui event loop

    def set_centered_geometry(self):
        self.parent.minsize(self.default_x, self.default_y)  # set minsize so widgets wont hide  http://bit.ly/2ersPkb
        x_offset = (self.parent.winfo_screenwidth() - self.default_x) / 2
        y_offset = (self.parent.winfo_screenheight() - self.default_y) / 2
        self.parent.geometry("%sx%s+%s+%s" % (self.default_x, self.default_y, x_offset, y_offset))
        self.panel.sash_place(0, self.default_x / 4, 0)

    def show_help_messages(self):
        self.add_message("EChatr", "\n<----------------EChatr Help---------------->"
        "\n\nUsing EChatr is very simple. To start, go to file -> login -> enter the Server IP or domain name, "
        "the Server port number, the username and the password. If you would automatically like to "
        'connect with these credentials on program startup, simply select "remember me?" Your credentials are '
        "stored safely in the operating system's keyring system (i.e. OSX KeyChain). Note, you will not be able to "
        "send messages until you are logged in."
        "\n\n[--------Fast Commands--------]"
        "\n\nTo use fast commands you must be logged in. Simply enter these commands in the message box."
        "\n\n/help - (from menu: help -> guide) Show this menu."
        "\n\n/quit - Immediately quit server link and EChatr Client Process. Login again to "
        "restart the EChatr Client process and reconnect to the server. This is useful to pause chatting without "
        "closing the entire program."
        "\n\n/exit - (from menu: file -> exit) Exit the entire program. This will also quit "
        "the EChatr Client Process.")
        self.messages.see("1.0")  # scroll to top when entering a message

    def init_menu(self):
        menu_bar = Menu(self.parent)
        file_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Login", command=lambda: LoginDialog(self, self.up_queue, self.down_queue))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=lambda: self.on_close())
        help_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Guide", command=lambda: self.up_queue.put((None, "/help")))  # TODO
        help_menu.add_separator()
        help_menu.add_command(
            label="About",
            command=lambda: tkMessageBox.showinfo("About "+self.title,
                                                  message=self.title+"\n\n"
                                                                     "Backend: David Nadwodny\n"
                                                                     "Frontend: Himel Das\n"
                                                                     "Manager: Dachelle Robinson\n"
                                                                     "Professor: Nicholas Duchon\n"
                                                                     u"\n\u00a9 2016 UMUC CMSC 495 7980"
                                                  )
        )
        self.parent.config(menu=menu_bar)

    def colorize_names(self):
        # colorize default system Echatr log
        _fg = self._default_user_colors['EChatr']['fg']
        _bg = self._default_user_colors['EChatr']['bg']
        self.messages.tag_config('EChatr', background=_bg, foreground=_fg)  # color EChatr occurrences in the messages

        while True:
            name = yield
            self.users.insert(0, name)  # opposite of END
            while 1:
                _fg = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
                _bg = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
                if GUI.color_dist(_fg, _bg) > 0.456:
                    _fg = "#%02x%02x%02x" % _fg
                    _bg = "#%02x%02x%02x" % _bg
                    my_colors = {'fg': _fg, 'bg': _bg}
                    if my_colors not in self._default_user_colors.keys():  # make sure no dupes
                        break
            self.users.itemconfig(0, my_colors)  # color the name on the user list
            self._default_user_colors[name] = my_colors
            self.messages.tag_config(name, background=_bg, foreground=_fg)  # color name occurrences in the messages

    def init_ui(self):

        self.parent.title(self.title)

        frame = Frame(self)

        self.panel = PanedWindow(frame, orient=HORIZONTAL, relief=RAISED, borderwidth=1, showhandle=True)
        self.panel.pack(fill=BOTH, side=LEFT, expand=True)

        self.scrollbar = scrollbar = Scrollbar(frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        frame.pack(fill=BOTH, expand=True)

        self.messages = Text(self.panel, bg="gray12", fg="gray93", wrap=WORD,
                             yscrollcommand=scrollbar.set)  # when yview change, change position of scrollbar
        scrollbar.config(command=self.messages.yview)  # when scrollbar change, change yview of text widget
        self.messages.bind("<Key>", lambda e: "break")  # make readonly  http://bit.ly/2erqllU  http://bit.ly/2ersn5y

        self.users = Listbox(self.panel, bg="gray12", selectforeground="yellow",
                             exportselection=False,  # ensure selection even when clicking outside http://bit.ly/2fQb8Qq
                             selectbackground="turquoise")
        self.users.bind("<<ListboxSelect>>", self.listbox_select_callback)  # http://bit.ly/2erzieI
        self._color_generator.next()  # also .send(None) works

        self.panel.add(self.users)
        self.panel.add(self.messages)

        self.message_label = Label(self)
        self.message_entry = Entry(self, bg="gray99", state=DISABLED)
        self.message_label.pack(side=LEFT)
        self.message_entry.pack(side=RIGHT, fill=X, expand=True)  # expand entire x free space

        self.reset_styling()

        # bind widgets to callbacks
        self.message_entry.bind("<Return>", self.message_entry_callback)

        # show all
        self.pack(fill=BOTH, expand=True)

    def listbox_select_callback(self, evt):
        if self._listbox_previous_select:
            previous_colors = self._default_user_colors[self._listbox_previous_select]
            self.messages.tag_config(self._listbox_previous_select,
                                     underline=False,
                                     background=previous_colors["bg"], foreground=previous_colors["fg"])
        self._listbox_current_select = self.users.get(ANCHOR)  # ANCHOR not ACTIVE http://bit.ly/2fQerqY
        self.messages.tag_config(self._listbox_current_select, background="turquoise", foreground="yellow")
        self._listbox_previous_select = self._listbox_current_select

    def message_entry_callback(self, evt):  # event object http://bit.ly/2fUt88N
        new = self.message_entry.get()
        if new:
            self.send_message(self.un, new)
            self.message_entry.delete(0, END)
            self.messages.see("1.0")  # scroll to top when entering a message

    def send_message(self, name, message):
        send = (name, message)
        self.up_queue.put(send)

    def add_message(self, name, message):
        line = "<%s> %s %s\n\n" % (name, datetime.datetime.now().strftime("%I:%M:%S %p"), message)
        self.messages.insert("1.0", line)
        self.messages.tag_add(name, "1.0", "1.%s" % (len(name)+14))  # additional len for time and <>

    def add_user(self, name):
        if not name in self.users.get(0, END):  # this is not needed, but leave here in case
            self._color_generator.send(name)

    @staticmethod
    def rgb_to_ycc(r, g, b):  # http://bit.ly/1blFUsF
        y = .299*r + .587*g + .114*b
        cb = 128 - .168736*r - .331364*g + .5*b
        cr = 128 + .5*r - .418688*g - .081312*b
        return y, cb, cr

    @staticmethod
    def to_ycc(color):
        """ converts color tuples to floats and then to yuv """
        return GUI.rgb_to_ycc(*[x/255.0 for x in color])

    @staticmethod
    def color_dist(c1, c2):
        """ returns the squared euclidean distance between two color vectors in yuv space """
        return sum((a-b)**2 for a, b in zip(GUI.to_ycc(c1), GUI.to_ycc(c2)))

    def set_embedded_icon(self):  # http://bit.ly/2fYgMfK  # http://bit.ly/2fYlB8E
        icon = '''R0lGODdhFQAVAPMAAAQ2PESapISCBASCBMTCxPxmNCQiJJya/ISChGRmzPz+/PxmzDQyZDQyZDQy
        ZDQyZCwAAAAAFQAVAAAElJDISau9Vh2WMD0gqHHelJwnsXVloqDd2hrMm8pYYiSHYfMMRm53ULlQ
        HGFFx1MZCciUiVOsPmEkKNVp3UBhJ4Ohy1UxerSgJGZMMBbcBACQlVhRiHvaUsXHgywTdycLdxyB
        gm1vcTyIZW4MeU6NgQEBXEGRcQcIlwQIAwEHoioCAgWmCZ0Iq5+hA6wIpqislgGhthEAOw=='''
        img = PhotoImage(data=icon)
        self.parent.tk.call('wm', 'iconphoto', self.parent._w, img)

    def set_bitmap_icon(self):
        """Under Windows, the DEFAULT parameter can be used to set the icon for the widget and any descendants that
        don't have an icon set explicitly. DEFAULT can be the relative path to a .ico file
        (example: root.iconbitmap(default='myicon.ico') ). See Tk documentation for more information."""
        if os.name == "nt":
            self.parent.wm_iconbitmap(default="icon.ico")  # only works on windows :(  # fixed for all platforms
        else:
            self.parent.wm_iconbitmap("icon.ico")


def main():

    # # for experimenting only # #
    # queue = Queue()
    # kill_queue = Queue()
    # p = Process(target=dummy_server_process, args=(queue, down_queue, kill_queue))
    # p.start()
    # # # #

    root = Tk()
    app = GUI(root, "EChatr - Encrypted Chat System")
    app.set_centered_geometry()
    app.set_bitmap_icon()
    root.mainloop()


if __name__ == '__main__':
    main()
