#!/usr/bin/env python
import socket
import sys
import os
import socket, select, sys, traceback, binascii, re, commands, time, os, threading, ssl, getopt
from Crypto.Cipher import ARC4
from Crypto.Hash import SHA256



# build buffer for binary protocol 
#-  cmd -   cmdid    crc     sizeOfmsg   msg 
#   32bits  32bits   128bits  32bits     varies (indicated by sizeOfmsg) 
# 
#
# id = 32bit int
# size = 32bit int (16 char)
# checksum  = crc32 value (16 char)
# msg = data 

# secrets dictionary that holds database after reading

secrets = {}
"""
>>> p = SHA256.new()
>>> p.update("hello")
>>> p.hexdigest()
'2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
>>>
"""

key = '82aaee3b0f5c1e12' 

# Protocol Constants

HEADER_SIZE = 40 
NET_BUF_SIZE = 1024
ERROR = -1
USERNAME = 1
PASSWD = 2
CHAT = 3
EXIT = 4
USERLIST = 5
NOT_IMPLEMENTED = -1 
SELECT_TIMEOUT = 2
DEBUG = 0
VERBOSE = 0 

socketList = []
 

def usage():
    """
       Prints usage of the server if the appropriate number of arguments isn't passed from the command
       line. 
    """
    
    print("Usage: python sslServer.py -p <port> \n"
          "                           -d  Toggles Debug   \n"
          "                           -v  Toggles Verbosity   ")
    sys.exit(0)
def readSecretsDb():
    """ 
       Opens up secrets.db in local directory that holds username and password hashes in comma separated values
       and reads them into the global secrets dictionary used to authenticate users 
    """
    try:
        f = open("secrets.db", "r")
        for line in f:
            ar = line.split(",", 1)
            secrets[ar[0]] = ar[1].rstrip()    
        f.close()
        if(DEBUG):
            for k, v in secrets.iteritems():
                print "[Debug] readSecretsDb: user: " + k  + ", value: " + v 
            return len(secrets)
        return len(secrets)
        
    except(IOError):
        print "[Error] problem opening secrets.db"
        return(0)
    
def processHeader(msg):
    
    pCmd = msg[0:4]
    pCmdId = msg[4:8]
    pCrc = msg[8:24]
    pSize = msg[24:40]
    return (int(pCmd), int(pCmdId), int(pCrc), int(pSize)) 
    
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

    cmd = int(header[0:4])
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
        if DEBUG:
            print "[Debug] myRecv(): Waiting for header  " 
        readable, writeable, exceptional = select.select(inputList, outputList, inputList, 0)
        if readable:
            print "[Debug] myRecv(): socket is readable" 
            
            while(bufRec < HEADER_SIZE):
                headerBuf += recvSock.recv(NET_BUF_SIZE)
                bufRec = len(headerBuf)
            # fix up buffer in case we read past the header (which we probably did)
            if(bufRec > HEADER_SIZE):
                buf = headerBuf[HEADER_SIZE:]
                headerBuf = headerBuf[:HEADER_SIZE]                
                offset = len(buf)
            cmd, cmdId, crc, size = processHeader(norc4(headerBuf, key))
            if DEBUG:  
                print "[Debug] Header for header recv is Command:" + str(cmd) + " Command Id:" + str(cmdId) + " CRC:" + str(crc) + " size:" + str(size)   
                print "[Debug] bufRec is " + str(bufRec) 
            notRead = False
            #bufRec = 0
            #bufLen = size
            # deal with small message
            if size != len(buf):
                print("size is: " + str(size) + " bufferlength is: " + str(len(buf)))
             #   while bufRec < bufLen:
              #      print "."
               #     buf += recvSock.recv(NET_BUF_SIZE)
                #    bufRec = len(buf)                        
                 #   if bufRec == 0:
                  #      raise RuntimeError("[!] Error: myRecv Error")          
        else:
            if DEBUG:
                print "[Debug] Waiting for header from client. "    
            continue        

    # decrypt
    #buf = norc4(buf,key)
    # test crc 
    #recvCrc = binascii.crc32(buf)
    if DEBUG:
        if crc != recvCrc:
            print "[!] Error: CRC Checksum Error"
    return cmd, cmdId, buf
    
#...
def inputOutputThread(lSocket):
    if(DEBUG or VERBOSE):
        print "[Debug] inputOutputThread: Start"

    while True:
        if not socketList:
            continue
        buf = ''
        readable, writeable, exceptional = select.select(socketList, [], [], SELECT_TIMEOUT)
        print "[Debug] inputOutputThread: Thread select loop"
        if(readable):
            for clientSock in readable:
                print "[Debug] inputOutputThread: clientSock is readable"
                try:
                    cmd, cmdId, buf = myRecv(clientSock, key)
                except (socket.error):  # fixed - this causes inputOutputThread to crash after a while
                    socketList.remove(clientSock)
                if(cmd == CHAT):
                    for s in socketList:
                        header = "%4s%4s%16s%16s" % (CHAT, 0,  binascii.crc32(buf),  len(buf))
                        mySend(header, buf, s, key)
                elif(cmd == EXIT):
                    print "[Debug] got Exit from client"
                    socketList.remove(clientSock)
                    #clientSock.shutdown(socket.SHUT_RDWR)
                    #clientSock.close()
                    # update user list
                else:
                    print "[Debug] inputOutputThread:  non-chat returned from myRecv. cmd " + str(cmd) + " buf: " + buf
                
    
def main():
    
    port = ''  
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:hvd", ["help"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print str(err)  
        usage()
    for o, a in opts:
        if o == "-v":
            VERBOSE = 1
            print "- Verbose mode inititated"
        elif o == "-d":
            DEBUG = 1
            print "- Debug mode inititated"
            
        elif o in ("-h", "--help"):
            usage()
        elif o in ("-p", "--port"):
            port = int(a)
            if(port > 65535 or port < 1):
                usage()
        else:
            usage()
            
    # ...    
    if(port == ''):
        print("[Error] Please set port!")
        usage()
    
    
    print("[------ Starting Server ------]")
    print("- Loading secrets database")
    numUsers = readSecretsDb()
    if(not numUsers):
        print("[Error] No users in secrets.db, have you added any users?")
        sys.exit(-1)
    print("- Loaded " + str(numUsers) + " Users")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    s = ssl.wrap_socket(s, server_side=True, certfile="echatr.crt", keyfile="echatr.key")    
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', port))
    s.listen(100)

    clientReaderWriter = threading.Thread(target=inputOutputThread, args=(s,))    
 
    clientReaderWriter.start()            

    while 1:
        try:
            clientsock, clientaddr = s.accept()
            print "[*] Accepted Connection"
            print "[*] Client Connected From: ", clientsock.getpeername() 
            # check pass on new client sock. 
            cmd, cmdId, buf = myRecv(clientsock, key)
            print buf
            if(cmd == USERNAME):
                username = buf
                print '[Debug] username is ' + username
                header = "%4s%4s%16s%16s" % (USERNAME, 0,  binascii.crc32(username),  len(username))
                mySend(header, username, clientsock, key)                
            else:
                print("[?] Expected username got " + cmd)
                clientsock.close()
            cmd, cmdId, buf = myRecv(clientsock, key)
            if(cmd == PASSWD):
                password = buf
                if DEBUG:
                    print("[?] Passwd sent " + password)
            if(secrets.has_key(username)):
                p = SHA256.new()
                p.update(password)

                if DEBUG:
                    print "\n---\n"
                    print "Username is " + username
                    print "Hash of sent password is " + p.hexdigest()
                    print "Hash of saved secret is " + secrets[username]
                    print "\n---\n"
                                   
                if(p.hexdigest() == secrets[username]):
                    print "[!] Password Accepted for " + username
                    header = "%4s%4s%16s%16s" % (PASSWD, 0,  binascii.crc32("OK"),  len("OK"))
                    mySend(header, "OK", clientsock, key) 
                else:
                    print "[!] Password Rejected for " + username
                    header = "%4s%4s%16s%16s" % (PASSWD, 0,  binascii.crc32("BADPAS"),  len("BADPAS"))
                    mySend(header, "BADPAS", clientsock, key)
                    clientsock.close()
            else:
                print "[!] No such user " + username
                header = "%4s%4s%16s%16s" % (PASSWD, 0,  binascii.crc32("BADPAS"),  len("BADPAS"))
                mySend(header, "BADPAS", clientsock, key)
                clientsock.close()
                            
            # add client sock to be monitored for input / output
            socketList.append(clientsock)
                        
                
        except KeyboardInterrupt:
            print "[*] Server Terminating"
            s.shutdown(socket.SHUT_RDWR)
            s.close()
            sys.exit(2)
        except:
            traceback.print_exc()
            continue

if __name__ == "__main__":
    main()