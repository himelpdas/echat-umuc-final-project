import socket, select, sys, commands, binascii, os, getpass, Queue, threading, time
from Crypto.Cipher import ARC4
#from curses import wrapper
#from ui import ChatUI


key = '82aaee3b0f5c1e12' 
DEBUG = 1

#Constants
HEADER_SIZE = 40
NET_BUF_SIZE = 1024
ERROR = -1
USERNAME = 1
PASSWD = 2
CHAT = 3
EXIT = 4
USERLIST = 5

NOT_IMPLEMENTED = -1 
FILE_MAGIC_NUM = 1024 
SELECT_TIMEOUT = 2

#inBox = Queue.Queue(0)
clientSock = ''
temp_user_list = []  # David this is just a temporary way to add new users to the chat

class StoppableQueueThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""
    # def __init__(self, ui, outBox):
    def __init__(self, down_queue):
        threading.Thread.__init__(self)
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self.down_queue = down_queue

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

class threadReadFromServer(StoppableQueueThread):

    def run(self):
        global clientSock
        global temp_user_list

        inputList = [clientSock]
        while not self._stop.isSet():
            self._lock.acquire()
            try:
                readable, writeable, exceptional = select.select(inputList, [], inputList, SELECT_TIMEOUT)
                if readable:  # no need to iterate since we can assume there is just one connection
                    cmd, cmdId, recBuf = myRecv(clientSock, key)
                    if cmd == CHAT:
                        user, message = recBuf[1:].split(">")
                        user = user.strip()
                        message = message.strip()
                        if DEBUG:
                            print "[Debug] User: %s - Wrote: %s" % (user, message)
                        self.down_queue.put(["message", user, message])  # add a new message to GUI
                        if user not in temp_user_list:
                            self.down_queue.put(["user", user, 1])  # instruct GUI to add a new user
                            temp_user_list.append(user)

            finally:
                self._lock.release()

#...
def processHeader(msg):

    pCmd = msg[0:4]
    pCmdId = msg[4:8]
    pCrc = msg[8:24]
    pSize = msg[24:40]
    return (int(pCmd), int(pCmdId), int(pCrc), int(pSize))

#...
def buildHeader(userInput):

    cmd = ''
    cmdId = 0
    crc = 0
    size = 0
    msg = ''

    # !exit is for exit
    if(userInput.startswith('!exit')):
        cmd = EXIT
        cmdId = 0
        msg = ''
        size = 0
        crc = binascii.crc32(msg)
    # !help prints the old help.
    elif(userInput.startswith('!help')):
        printHelp()
    # chat message
    else:
        cmd = CHAT
        cmdId = 0
        msg = userInput
        size = len(msg)
        crc = binascii.crc32(msg)

    return (cmdGood, cmd, cmdId, crc, size, msg)
#...
def rc4Enc(msg, key):

    enc = ARC4.new(key)
    msg = enc.encrypt(msg)
    return(msg)

#...
def rc4Dec(msg, key):

    dec = ARC4.new(key)
    msg = dec.encrypt(msg)
    return(msg)

#...
def norc4(msg, key):
    # for testing
    return(msg)
#...
def mySend(header, msg, sendSock, key):

    totalSent = 0
    bufLen = len(msg)

    #header = rc4Enc(header, key)
    #msg = rc4Enc(msg, key)
    msg = header + msg

    # select lists
    inputList = []
    outputList = []
    notSent = True
    outputList.append(sendSock)

    while notSent:
        readable, writeable, exceptional = select.select(inputList, outputList, outputList, 0)
        if writeable:
            while totalSent < bufLen:
                sent = sendSock.send(msg[totalSent:])
                if sent == 0:
                    raise RuntimeError("[!] Error: mySend Error")
                totalSent += sent
                # use buffering
                if(bufLen > FILE_MAGIC_NUM):
                    print "Send Status: " + str(totalSent) + " of " + str(bufLen)
            notSent = False
    return


def myRecv(recvSock, key):  # Himel's note: this is probably where down_queue can be used (client to gui communication)


    # get header / split
    bufRec = 0
    headerBuf = ''
    buf = ''
    recvCrc = ''
    notRead = True

    # select lists
    inputList = []
    outputList = []
    inputList.append(recvSock)

    # get header
    while notRead:
        #print "[Debug] Waiting for header"
        readable, writeable, exceptional = select.select(inputList, outputList, inputList, SELECT_TIMEOUT)
        if readable:
            while(bufRec < HEADER_SIZE):
                headerBuf += recvSock.recv(NET_BUF_SIZE)
                bufRec = len(headerBuf)
            # fix up buffer in case we read past the header (which we probably did)
            if(bufRec > HEADER_SIZE):
                buf = headerBuf[HEADER_SIZE:]
                headerBuf = headerBuf[:HEADER_SIZE]
                offset = len(buf)
                print "[Debug] offset from header is " + str(offset)
            cmd, cmdId, crc, size = processHeader(norc4(headerBuf, key))
            print "[Debug] Header for header recv is Command:" + str(cmd) + " Command Id:" + str(cmdId) + " CRC:" + str(crc) + " size:" + str(size)
            notRead = False
            bufRec = 0
            bufLen = size
            # deal with small messages
            if size != len(buf):
                while bufRec < bufLen:
                    buf += recvSock.recv(NET_BUF_SIZE)
                    bufRec = len(buf)
                    if bufRec == 0:
                        raise RuntimeError("[!] Error: myRecv Error")
            print "[Debug] size recv()'d from previous header: " + str(bufRec)
        else:
            print "[Debug] Waiting for header from server. "

    # decrypt
    buf = norc4(buf,key)
    # test crc
    recvCrc = binascii.crc32(buf)
    if crc != recvCrc:
        print "[!] Error: CRC Checksum Error"
    return cmd, cmdId, buf

#...
def doShutdown(tSock, wThread):

    # set flag for threads
    try:
        wThread.stop()
        wThread.join(5)
        tSock.shutdown(socket.SHUT_WR)
        tSock.close()
        sys.exit(2)
    except socket.error:
        tSock.close()
        sys.exit(3)

#...
# def main(stdscr):
def main(up_queue, down_queue):

    down_queue.put(["message", "EChatr", "Started EChatr Client Process (ID %s)" % os.getpid()])
    down_queue.put(["system", os.getpid(), "client_pid"])

    cmd = ''
    host = '127.0.0.1'
    port = 8080
    bufLen = 0
    outBox = Queue.Queue(0)
    global clientSock


    clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # clear screen and set ui
        # stdscr.clear()
        # ui = ChatUI(stdscr)

        # authenticates users to remote service

        # connect to server
        clientSock.connect((host, port))
        # ui.chatbuffer_add("Connected to: " + host)
        down_queue.put(["message", "EChatr", "Connected to: " + host])
        # username = ui.wait_input("Username: ")  # before ui.py removal
        # username = raw_input("Username: ")  # after ui.py removal
        username, password = up_queue.get()  # after gui.py integration  # block here to wait for username from GUI
        if "/quit" in [username, password]:
            down_queue.put(["message", "EChatr", "Quitting!"])
            clientSock.close()
            sys.exit(-1)

        # send username
        header = "%4s%4s%16s%16s" % (USERNAME, 0,  binascii.crc32(username),  len(username))
        mySend(header, username, clientSock, key)
        cmd, cmdId, recBuf = myRecv(clientSock, key)

        # no results from the server to indicate weather it's a valid username by design
        if(cmd == USERNAME):

            # password = ui.wait_input("Password: ")  # before ui.py removal
            # password = raw_input("Password: ")  # after ui.py removal
            header = "%4s%4s%16s%16s" % (PASSWD, 0,  binascii.crc32(password),  len(password))
            mySend(header, password, clientSock, key)
            #get response back from server
            cmd, cmdId, recBuf = myRecv(clientSock, key)

        # if we authenticated, awesome otherwise die
        if(recBuf == 'OK'):
            down_queue.put(["message", "EChatr", "Successfully logged in!"])
            # client is now authenticated
            # ui.userlist.append(username) #TODO
            down_queue.put(["user", username, 1])  # 1 for add -1 for remove
            down_queue.put(["system", username, "login_success"])  # 1 for add -1 for remove
            temp_user_list.append(username)
            down_queue.put(["system", "message_entry", "enable_widget"])
            # ui.redraw_userlist()
        else:
            clientSock.close()  # socket file descriptor appears to get destroyed
            down_queue.put(["message", "EChatr", "Authentication Error: Login failed!"])
            gui_client_quit_countdown(5, up_queue, down_queue, lambda: sys.exit(1), None, post="Try logging in again!")

        # start thread to send and recv messages
        serverReader = threadReadFromServer(down_queue)
        serverReader.start()            
    
        # process user input
        while True:
        
            name, message = up_queue.get()
            if message == "/quit":
                header = "%4s%4s%16s%16s" % (EXIT, 0,  binascii.crc32('aaaa'),  len('aaaa'))
                mySend(header, 'aaaa', clientSock, key)
                gui_client_quit_countdown(0, up_queue, down_queue, lambda: doShutdown(clientSock, serverReader), None,
                                          post="Process stopped.")

            elif message == "/exit":
                gui_client_quit_countdown(3, up_queue, down_queue, lambda: sys.exit(0), "app_shutdown",
                                          pre="The EChatr Application will shutdown.",
                                          post="Application shutting down.")  # shutdown application

            elif message == "/help":
                down_queue.put(["system", "show_help_messages", "run_method"])

            else:
                userInput = "< " + name + " > " + message
                header = "%4s%4s%16s%16s" % (CHAT, 0,  binascii.crc32(userInput),  len(userInput))
                mySend(header, userInput, clientSock, key)  # Fixed - David it looks like the server is not getting this
           
    except (socket.gaierror, socket.error), e:
        down_queue.put(["message", "EChatr", "Connection Error: %s." % e])
        gui_client_quit_countdown(5, up_queue, down_queue, lambda: sys.exit(1), "client_restart",
                                  post="Reconnecting...")

    except Exception, e:
        down_queue.put(["message", "EChatr", "Fatal Error: %s." % e])
        gui_client_quit_countdown(10, up_queue, down_queue, lambda: sys.exit(4), "app_shutdown",
                                  pre="The EChatr Application will shutdown.")  # shutdown application


def gui_client_quit_countdown(seconds_to_kill, up_queue, down_queue, quit_callback, command, pre=None, post=None):
    if pre:
        down_queue.put(["message", "EChatr", pre])

    if command:
        down_queue.put(["system", seconds_to_kill * 1000, command])

    seconds_string = ""
    if seconds_to_kill:
        seconds_string = " in %s seconds.." % seconds_to_kill

    down_queue.put(["message", "EChatr",
                    "Quitting EChatr Client Process (ID %s)%s." % (os.getpid(), seconds_string)])

    while seconds_to_kill != 0:
        try:  # if GUI quits before countdown, then quit this process immediately
            if "/quit" == up_queue.get(True, 1):  # instead of using time.sleep(1), which can lead to race
                break
        except Queue.Empty:
            pass
        seconds_to_kill -= 1
        if seconds_to_kill % 2 == 0:
            down_queue.put(["message", "EChatr", "%s... %s..." % (seconds_to_kill + 1, seconds_to_kill)])

    if post:
        down_queue.put(["message", "EChatr", post])

    # prevent anything from messing up the queue during Echatr Client Process reset
    down_queue.put(["system", "message_entry", "disable_widget"])

    quit_callback()

# wrapper(main)
if __name__ == "__main__":
    pass
