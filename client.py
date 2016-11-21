import socket, select, sys, commands, binascii, os, getpass, Queue, threading, time
from Crypto.Cipher import ARC4
from curses import wrapper
from ui import ChatUI


key = '82aaee3b0f5c1e12' 

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

class StoppableQueueThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""
    def __init__(self, ui, outBox):
        threading.Thread.__init__(self)
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self.ui = ui
        self.outBox = outBox
    
    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet() 

class threadReadFromServer(StoppableQueueThread):
    
    def run(self):        
        ui = self.ui
        global clientSock      
        
        inputList = [clientSock]
        while not self._stop.isSet():
            self._lock.acquire()         
            try:
                readable, writeable, exceptional = select.select(inputList, [], inputList, SELECT_TIMEOUT)
                if readable:
                    cmd, cmdId, recBuf = myRecv(clientSock, key)
                    if cmd == CHAT:
                        ui.chatbuffer_add(recBuf)
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
    
#..
def myRecv(recvSock, key):
        
    
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
def main(stdscr):
    
    cmd = ''
    host = '127.0.0.1'
    port = 8080
    bufLen = 0 
    outBox = Queue.Queue(0)
    global clientSock


    clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # clear screen and set ui
        stdscr.clear()
        ui = ChatUI(stdscr)      
        
        # connect to server
        clientSock.connect((host, port))
        ui.chatbuffer_add("Connected to: " + host)

        # authenticates users to remote service
        username = ui.wait_input("Username: ")
        
        # send username 
        header = "%4s%4s%16s%16s" % (USERNAME, 0,  binascii.crc32(username),  len(username))
        mySend(header, username, clientSock, key)                
        cmd, cmdId, recBuf = myRecv(clientSock, key)
        
        # no results from the server to indicate weather it's a valid username by design
        if(cmd == USERNAME):
            
            password = ui.wait_input("Password: ")
            header = "%4s%4s%16s%16s" % (PASSWD, 0,  binascii.crc32(password),  len(password))
            mySend(header, password, clientSock, key)                
            #get response back from server 
            cmd, cmdId, recBuf = myRecv(clientSock, key)
        
        # if we authenticated, awesome otherwise die    
        if(recBuf == 'OK'):
            ui.chatbuffer_add("Successfully Logged in")
        else:
            clientSock.close()
            sys.exit(-1)
        
        # client is now authenticated
        ui.userlist.append(username)
        ui.redraw_userlist()
    
        # start thread to send and recv messages
        serverReader = threadReadFromServer(ui, outBox)       
        serverReader.start()            
    
        # process user input
        while True:
        
            userInput = ui.wait_input("> ")
            if(userInput == "/quit"):
                ui.chatbuffer_add("[*] Client Terminating")
                header = "%4s%4s%16s%16s" % (EXIT, 0,  binascii.crc32('aaaa'),  len('aaaa'))
                mySend(header, 'aaaa', clientSock, key)                 
                doShutdown(clientSock, serverReader)

            elif(userInput == "/help"):
                ui.chatbuffer_add("--- Supported Commands ---")
                ui.chatbuffer_add(" /help - this menu")
                ui.chatbuffer_add(" /quit - quits ")
            else:
                userInput = "< " + username + " > " + userInput
                header = "%4s%4s%16s%16s" % (CHAT, 0,  binascii.crc32(userInput),  len(userInput))
                mySend(header, userInput, clientSock, key)                
           
    except socket.gaierror, e:
        print "Error connecting to server: %s" % e
        sys.exit(1)
    except KeyboardInterrupt:
        ui.chatbuffer_add("[*] Client Terminating")
        
      
    
wrapper(main)
