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

NOT_IMPLEMENTED = -1 
FILE_MAGIC_NUM = 1024 
SELECT_TIMEOUT = 2


outBox = Queue.Queue(0)
inBox = Queue.Queue(0)



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
def threadReadFromServer(tSock, ui):
    print "Hi from the socket reader"    
    inputList = [tSock]
    while True:
        readable, writeable, exceptional = select.select(inputList, [], inputList, SELECT_TIMEOUT)
        if readable:
            cmd, cmdId, recBuf = myRecv(tSock, key)
            if cmd == CHAT:
                ui.chatbuffer_add(recBuf)
#...
def threadWriter(tSock, ui, userName):
    print "Hi from the socket writer"
    while True:
        while outBox.not_empty:
            #print "sending" + item
            item = "<" + userName + "> " + outBox.get() 
            header = "%4s%4s%16s%16s" % (CHAT, 0,  binascii.crc32(item),  len(item))
            mySend(header, item, tSock, key)
            time.sleep(1)
            
#...

def main(stdscr):
    
    cmd = ''
    host = '127.0.0.1'
    port = 8080
    bufLen = 0 
    
    # select lists
    inputList = []
    outputList = []

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # clear screen and set ui
        stdscr.clear()
        ui = ChatUI(stdscr)      
        
        # connect to server
        s.connect((host, port))
        ui.chatbuffer_add("Connected to: " + host)

        # authenticates users to remote service
        username = ui.wait_input("Username: ")
        
        # send username 
        header = "%4s%4s%16s%16s" % (USERNAME, 0,  binascii.crc32(username),  len(username))
        mySend(header, username, s, key)                
        cmd, cmdId, recBuf = myRecv(s, key)
        
        # no results from the server to indicate weather it's a valid username by design
        if(cmd == USERNAME):
            
            password = ui.wait_input("Password: ")
            header = "%4s%4s%16s%16s" % (PASSWD, 0,  binascii.crc32(password),  len(password))
            mySend(header, password, s, key)                
            #get response back from server 
            cmd, cmdId, recBuf = myRecv(s, key)
        if(recBuf == 'OK'):
            ui.chatbuffer_add("Successfully Logged in")
        else:
            s.close()
            sys.exit(-1)
        
        ui.userlist.append(username)
        ui.redraw_userlist()
    
        # start threads     
        serverReader = threading.Thread(target=threadReadFromServer, args=(s, ui))    
        clientWriter = threading.Thread(target=threadWriter, args=(s, ui, username))
    
        serverReader.start()            
        clientWriter.start()        
    
        while True:
        
            userInput = ui.wait_input("> ")
            if(userInput == "/quit"):
                ui.chatbuffer_add("[*] Client Terminating")
                s.shutdown(socket.SHUT_RDWR)
                sys.exit(2) 
            elif(userInput == "/help"):
                ui.chatbuffer_add("--- Supported Commands ---")
                ui.chatbuffer_add(" /help - this menu")
                ui.chatbuffer_add(" /quit - quits ")
            else:
                outBox.put(userInput)

           
    except socket.gaierror, e:
        print "Error connecting to server: %s" % e
        sys.exit(1)
    except KeyboardInterrupt:
        ui.chatbuffer_add("[*] Client Terminating")
        s.shutdown(socket.SHUT_RDWR)
        sys.exit(2)    
    s.shutdown(socket.SHUT_RDWR)
    s.close()
    sys.exit(0)    
    


wrapper(main)
