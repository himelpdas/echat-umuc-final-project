#!/usr/bin/python
# -*- coding: utf-8 -*-

from Tkinter import *
import random


class GUI(Frame):

    colors = {'red', 'blue', 'green', 'orange', 'purple', 'yellow', 'teal', 'pink', 'grey'}

    def __init__(self, parent, default_x, default_y):
        Frame.__init__(self, parent)

        self.parent = parent
        self.default_x = default_x
        self.default_y = default_y

        self.set_centered_geometry(640, 480)

        self.init_menu()
        self.init_ui()

    def set_centered_geometry(self, x, y):
        x_offset = (self.parent.winfo_screenwidth() - x) / 2
        y_offset = (self.parent.winfo_screenheight() - y) / 2
        self.parent.geometry("%sx%s+%s+%s" % (x, y, x_offset, y_offset))

    def init_menu(self):
        menu_bar = Menu(self.parent)
        file_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=lambda: self.quit())
        help_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        self.parent.config(menu=menu_bar)

    def init_ui(self):

        self.parent.title("Crypto")

        panel = PanedWindow(self, orient=HORIZONTAL, relief=RAISED, borderwidth=1, showhandle=True)
        panel.pack(fill=BOTH, expand=1)

        users = Listbox(panel)
        _last_bg, _last_fg = [], []
        for item in ["Dachelle", "David", "Himel", "John", "Robert", "Sally", "Trisha"]:
            users.insert(0, item)  # opposite of END
            _fg = random.choice(list(self.colors.difference(_last_fg)))
            _last_fg = [_fg]
            _bg = random.choice(list(self.colors.difference(_last_fg+_last_bg)))  # ensure different colors each row
            _last_bg = [_bg]
            users.itemconfig(0, {'fg': _fg, 'bg': _bg})

        messages = Text(panel)

        panel.add(users)
        panel.add(messages)
        panel.sash_place(0, self.default_x/3, 0)

        self.pack(fill=BOTH, expand=True)

        label = Label(self, text="Enter Message:")
        line_edit = Entry(self)
        label.pack(side=LEFT)
        line_edit.pack(side=RIGHT, fill=X, expand=True)  # expand entire x free space


def main():

    root = Tk()
    app = GUI(root, 640, 480)
    root.mainloop()


if __name__ == '__main__':
    main()
