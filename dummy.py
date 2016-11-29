import random
import time
from Queue import Empty

dummy_names = ["Dachelle", "David", "Himel", "John", "Julia", "Robert", "Sally", "Trisha"]  # for experimenting only

lorem_ipsum = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et " \
              "dolore magna aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip " \
              "ex ea commodo consequat duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore " \
              "eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident sunt in culpa qui officia " \
              "deserunt mollit anim id est laborum".split(" ")  # for experimenting only


def dummy_server_process(queue, kill_queue):  # for experimenting only
    while 1:
        fragments = random.sample(lorem_ipsum, random.choice(range(1, 15)))
        fragments[0] = fragments[0].capitalize()
        message = " ".join(fragments)
        message += (random.choice(["!", "?", "."]))
        print "dummy server: %s" % message
        queue.put([random.choice(dummy_names[1:]), message])
        time.sleep(random.choice(range(1, 5)))

        try:
            if kill_queue.get_nowait():
                print "dummy server killed!"
                break
        except Empty:
            pass


colors = {'red', 'blue', 'green', 'orange', 'purple', 'yellow', 'teal', 'pink', 'grey'}
