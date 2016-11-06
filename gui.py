#!/usr/bin/python
# -*- coding: utf-8 -*-

from Tkinter import *
import tkMessageBox
from multiprocessing import Process, Queue
from Queue import Empty
import random
import datetime
import time


dummy_names = ["Dachelle", "David", "Himel", "John", "Julia", "Robert", "Sally", "Trisha"]

lorem_ipsum = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et " \
              "dolore magna aliqua Ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip " \
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


class GUI(Frame):

    colors = {'red', 'blue', 'green', 'orange', 'purple', 'yellow', 'teal', 'pink', 'grey'}

    def __init__(self, parent, queue, kill, default_x, default_y, title):
        Frame.__init__(self, parent)

        # init args
        self.parent = parent
        self.queue = queue
        self.kill = kill  # temp
        self.title = title
        self.default_x = default_x
        self.default_y = default_y

        # declare widgets
        self.messages = None
        self.message_entry = None

        # user info
        self.this_user = dummy_names[0]

        # init widgets
        self.init_menu()
        self.init_ui()

        parent.protocol("WM_DELETE_WINDOW", self.on_close)  # http://bit.ly/2fPXjRS
        self.task_loop()

    def on_close(self):
        self.kill.put(True)  # kill dummy server
        self.parent.destroy()

    def task_loop(self):
        try:
            incoming = self.queue.get_nowait()
            self.add_message(*incoming)
        except Empty:
            pass
        finally:
            self.parent.after(10, self.task_loop)  # update gui event loop

    def set_centered_geometry(self, x, y):
        x_offset = (self.parent.winfo_screenwidth() - x) / 2
        y_offset = (self.parent.winfo_screenheight() - y) / 2
        self.parent.geometry("%sx%s+%s+%s" % (x, y, x_offset, y_offset))

    def init_menu(self):
        menu_bar = Menu(self.parent)
        file_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=lambda: self.on_close())
        help_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(
            label="About",
            command=lambda: tkMessageBox.showinfo("About "+self.title,
                                                  message="Backend: David Nadwodny\n"
                                                          "Frontend: Himel Das\n"
                                                          "Manager: Dachelle Robinson\n"
                                                          u"\n\u00a9 2016 UMUC CMSC 495 7980"
                                                  )
        )
        self.parent.config(menu=menu_bar)

    def init_ui(self):

        self.set_centered_geometry(self.default_x, self.default_y)

        self.parent.title(self.title)

        panel = PanedWindow(self, orient=HORIZONTAL, relief=RAISED, borderwidth=1, showhandle=True)
        panel.pack(fill=BOTH, expand=True)

        self.messages = Text(panel, bg="gray12", fg="gray93", wrap=WORD)

        users = Listbox(panel, bg="gray12")
        _last_bg, _last_fg = [], []
        for name in dummy_names:
            users.insert(0, name)  # opposite of END
            _fg = random.choice(list(self.colors.difference(_last_fg)))
            _last_fg = [_fg]
            _bg = random.choice(list(self.colors.difference(_last_fg+_last_bg)))  # ensure different colors each row
            _last_bg = [_bg]
            users.itemconfig(0, {'fg': _fg, 'bg': _bg})
            self.messages.tag_config(name, background=_bg, foreground=_fg)

        panel.add(users)
        panel.add(self.messages)
        panel.sash_place(0, self.default_x/4, 0)

        self.pack(fill=BOTH, expand=True)

        message_label = Label(self, text="Enter Message:")
        self.message_entry = Entry(self)
        message_label.pack(side=LEFT)
        self.message_entry.pack(side=RIGHT, fill=X, expand=True)  # expand entire x free space

        # bind widgets to callbacks
        self.message_entry.bind("<Return>", self.message_entry_callback)

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
    app = GUI(root, queue, kill, 640, 480, "Crypto Chat")
    root.mainloop()


if __name__ == '__main__':
    main()
