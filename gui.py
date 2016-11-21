#!/usr/bin/python
# -*- coding: utf-8 -*-

from Tkinter import *
import tkMessageBox, tkSimpleDialog
from multiprocessing import Process, Queue
from Queue import Empty
import random
import datetime
import time


dummy_names = ["Dachelle", "David", "Himel", "John", "Julia", "Robert", "Sally", "Trisha"]

lorem_ipsum = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et " \
              "dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip " \
              "ex ea commodo consequat duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore " \
              "eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident sunt in culpa qui officia " \
              "deserunt mollit anim id est laborum".split(" ")


def dummy_server_process(queue, kill):
    while 1:
        fragments = random.sample(lorem_ipsum, random.choice(range(1, 15)))
        fragments[0] = fragments[0].capitalize()
        message = " ".join(fragments)
        message += (random.choice(["!", "?", "."]))
        print "dummy server: %s" % message
        queue.put([random.choice(dummy_names[1:]), message])
        time.sleep(random.choice(range(1, 5)))

        try:
            if kill.get_nowait():
                print "dummy server killed!"
                break
        except Empty:
            pass


class LoginDialog(tkSimpleDialog.Dialog):

    def __init__(self, *args, **kwargs):
        self.e1 = self.e2 = self.cb = None
        tkSimpleDialog.Dialog.__init__(self, title="Login now...", *args, **kwargs)

    def body(self, master):

        Label(master, text="Username:").grid(row=0)
        Label(master, text="Password:").grid(row=1)

        self.e1 = Entry(master)
        self.e2 = Entry(master, show="*")

        self.e1.grid(row=0, column=1)
        self.e2.grid(row=1, column=1)

        self.cb = Checkbutton(master, text="Remember me?")
        self.cb.grid(row=2, columnspan=2, sticky=W)

        return self.e1  # initial focus

    def apply(self):
        first = int(self.e1.get())
        second = int(self.e2.get())
        print first, second  # TODO


class GUI(Frame):

    colors = {'red', 'blue', 'green', 'orange', 'purple', 'yellow', 'teal', 'pink', 'grey'}

    def __init__(self, parent, queue, kill, title):
        Frame.__init__(self, parent)

        # init args
        self.parent = parent
        self.queue = queue
        self.kill = kill  # temp
        self.title = title

        # helper variables
        self._listbox_previous_select = None
        self._listbox_current_select = None
        self._default_user_colors = {}
        self._blink = False

        # declare widgets
        self.panel = None
        self.users = None
        self.messages = None
        self.message_entry = None

        # user info
        self.this_user = dummy_names[0]

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

    def on_close(self):
        self.kill.put(True)  # kill dummy server
        self.parent.destroy()

    def task_loop(self):
        if self._listbox_current_select:
            self._blink = not self._blink
            self.messages.tag_config(self._listbox_current_select, underline=self._blink)

        try:
            incoming = self.queue.get_nowait()
            self.add_message(*incoming)
        except Empty:
            pass
        finally:
            self.parent.after(200, self.task_loop)  # update gui event loop

    def set_centered_geometry(self):
        self.parent.minsize(self.default_x, self.default_y)  # set minsize so widgets wont hide  http://bit.ly/2ersPkb
        x_offset = (self.parent.winfo_screenwidth() - self.default_x) / 2
        y_offset = (self.parent.winfo_screenheight() - self.default_y) / 2
        self.parent.geometry("%sx%s+%s+%s" % (self.default_x, self.default_y, x_offset, y_offset))
        self.panel.sash_place(0, self.default_x / 4, 0)

    def init_menu(self):
        menu_bar = Menu(self.parent)
        file_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Login", command=lambda: LoginDialog(self.parent))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=lambda: self.on_close())
        help_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Guide", command=lambda: None)  # TODO
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

    def init_ui(self):

        self.parent.title(self.title)

        frame = Frame(self)

        self.panel = PanedWindow(frame, orient=HORIZONTAL, relief=RAISED, borderwidth=1, showhandle=True)
        self.panel.pack(fill=BOTH, side=LEFT, expand=True)

        scrollbar = Scrollbar(frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        frame.pack(fill=BOTH, expand=True)

        self.messages = Text(self.panel, bg="gray12", fg="gray93", wrap=WORD,
                             yscrollcommand=scrollbar.set)  # when yview change, change position of scrollbar
        scrollbar.config(command=self.messages.yview)  # when scrollbar change, change yview of text widget
        self.messages.bind("<Key>", lambda e: "break")  # make readonly  http://bit.ly/2erqllU  http://bit.ly/2ersn5y

        self.users = Listbox(self.panel, bg="gray12", selectforeground="white",
                             exportselection=False,  # ensure selection even when clicking outside http://bit.ly/2fQb8Qq
                             selectbackground="turquoise")
        self.users.bind("<<ListboxSelect>>", self.listbox_select_callback)  # http://bit.ly/2erzieI
        _last_bg, _last_fg = [], []
        for name in dummy_names:
            self.users.insert(0, name)  # opposite of END
            _fg = random.choice(list(self.colors.difference(_last_fg)))
            _last_fg = [_fg]
            _bg = random.choice(list(self.colors.difference(_last_fg+_last_bg)))  # ensure different colors each row
            _last_bg = [_bg]
            self.users.itemconfig(0, {'fg': _fg, 'bg': _bg})
            self._default_user_colors[name] = {'fg': _fg, 'bg': _bg}
            self.messages.tag_config(name, background=_bg, foreground=_fg)

        self.panel.add(self.users)
        self.panel.add(self.messages)

        message_label = Label(self, text="Enter Message:")
        self.message_entry = Entry(self, bg="gray99")
        message_label.pack(side=LEFT)
        self.message_entry.pack(side=RIGHT, fill=X, expand=True)  # expand entire x free space

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
        self.messages.tag_config(self._listbox_current_select, background="turquoise", foreground="white")
        self._listbox_previous_select = self._listbox_current_select

    def message_entry_callback(self, evt):
        new = self.message_entry.get()
        if new:
            self.add_message(self.this_user, new)
            self.message_entry.delete(0, END)

    def add_message(self, name, message):
        line = "<%s> %s %s\n\n" % (name, datetime.datetime.now().strftime("%I:%M:%S %p"), message)
        self.messages.insert("1.0", line)
        self.messages.tag_add(name, "1.0", "1.%s" % (len(name)+14))  # additional len for time and <>


def main():
    queue = Queue()
    kill = Queue()
    p = Process(target=dummy_server_process, args=(queue, kill))
    p.start()

    root = Tk()
    app = GUI(root, queue, kill, "EChatr - Encrypted Chat System")
    app.set_centered_geometry()
    root.mainloop()


if __name__ == '__main__':
    main()
