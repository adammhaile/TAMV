#!/usr/bin/env python2
# Test console for webhooks interface
#
# Copyright (C) 2020  Kevin O'Connor <kevin@koconnor.net>
# Modified by Nanotech in April 2021 to be used for Klipper communications
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import sys, os, socket, fcntl, select, json, errno, time

class KlipperAPI:
    _socketAddress = ''
    _webhook_socket = ''
    id = -1
    pt = 0
    
    def __init__(self,uds_filename):
        # Socket Creation
        self._socketAddress = uds_filename
        self._webhook_socket = self.webhook_socket_create(uds_filename)
        self.poll = select.poll()
        self.poll.register(self._webhook_socket, select.POLLIN | select.POLLHUP)
        # Keyboard Implementation
        self.kbd_fd = sys.stdin.fileno()
        set_nonblock(self.kbd_fd)
        self.kbd_data = self.socket_data = ""
        self.pt = 4
    
    def webhook_socket_create(self, uds_filename):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.setblocking(0)
        #sys.stderr.write("Waiting for connect to %s\n" % (uds_filename,))
        while 1:
            try:
                sock.connect(uds_filename)
            except socket.error as e:
                if e.errno == errno.ECONNREFUSED:
                    time.sleep(0.1)
                    continue
                sys.stderr.write("Unable to connect socket %s [%d,%s]\n"
                                 % (uds_filename, e.errno,
                                    errno.errorcode[e.errno]))
                sys.exit(-1)
            break
        #sys.stderr.write("Connection.\n")
        return sock
    
    def get_socket_address(self):
        return self._socketAddress
    
    def increment_id(self):
        self.id += 1
    
    def get_last_id(self):
        return self.id
    
    def format_status_request(self, id):
        return '{"id": '+str(id)+', "method": "info", "params": {}}'
    
    def format_gcode_request(self, id, gcodeInput):
        return '{"id": '+str(id)+', "method": "gcode/script", "params": {"script": "'+str(gcodeInput)+'"}}'
        
    def format_position_request(self, id):
        return '{"id": '+str(id)+', "method": "objects/query", "params": {"objects": {"gcode_move": ["gcode_position"]}}}'
    
    def format_abs_position_request(self, id):
        return '{"id": '+str(id)+', "method": "objects/query", "params": {"objects": {"toolhead": ["position"]}}}'
    
    def format_current_tool_request(self, id):
        return '{"id": '+str(id)+', "method": "objects/query", "params": {"objects": {"toolhead": ["extruder"]}}}'
    
    def format_objects_list(self, id):
        return '{"id": '+str(id)+', "method": "objects/list"}'
    
    def wait_for_response(self):
        wait = True
        while(wait):
            res = self.poll.poll(1.)
            for fd, event in res:
                return self.get_socket()
                wait = False
    
    def get_socket(self):
        data = self._webhook_socket.recv(4096)
        if not data:
            sys.stderr.write("Socket closed\n")
            sys.exit(0)
        if b'\x03' in data:
            parts = data.split(b'\x03')
        else:
            parts = data
        self.socket_data = parts.pop()
        for line in parts:
            return line
            #currently only returns the first line
    
    def send_status_request(self, id):
        request = self.format_status_request(id)
        try:
            m = json.loads(request)
            cm = json.dumps(m, separators=(',', ':'))
            #sys.stdout.write("SEND: %s\n" % (cm,))
            cm=cm.encode()
            self._webhook_socket.send(b"%s\x03" % (cm,))
        except:
            sys.stderr.write("ERROR: Unable to parse data\n")
    
    def get_status(self):
        self.increment_id()
        self.send_status_request(self.id)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'result' in j:
            j = j['result']['state']
            return str(j)
    
    def get_config_location(self):
        self.increment_id()
        self.send_status_request(self.id)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'result' in j:
            j = j['result']['config_file']
            return str(j)
    
    def send_gcode_request(self, id,  line):
        request = self.format_gcode_request(id,line)
        try:
            m = json.loads(request)
            cm = json.dumps(m, separators=(',', ':'))
            #sys.stdout.write("SEND: %s\n" % (cm,))
            cm=cm.encode()
            self._webhook_socket.send(b"%s\x03" % (cm,))
        except:
            sys.stderr.write("ERROR: Unable to parse data\n")
    
    def get_gcode(self, line):
        # Check for G10 Override
        if 'G10 ' in line or 'g10 ' in line:
            return self.G10_Override(line)
        self.increment_id()
        self.send_gcode_request(self.id, line)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'error' in j:
            j = j['error']['message']
            return 'error: '+str(j)
        elif 'result' in j:
            return 'GCode Sent Successfully'
    
    def send_position_request(self, id):
        request = self.format_position_request(id)
        try:
            m = json.loads(request)
            cm = json.dumps(m, separators=(',', ':'))
            #sys.stdout.write("SEND: %s\n" % (cm,))
            cm=cm.encode()
            self._webhook_socket.send(b"%s\x03" % (cm,))
        except:
            sys.stderr.write("ERROR: Unable to parse data\n")
    
    def get_position(self, axis=None):
        self.increment_id()
        self.send_position_request(self.id)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'error' in j:
            j = j['error']['message']
            return 'error: '+str(j)
        elif 'result' in j:
            j = j['result']['status']['gcode_move']['gcode_position']
            x = j[0]
            y = j[1]
            z = j[2]
            e = j[3]
            if axis == 'x' or axis == 'X':
                return x
            elif axis == 'y' or axis == 'Y':
                return y
            elif axis == 'z' or axis == 'Z':
                return z
            elif axis == 'e' or axis == 'S':
                return e
            else:
                return str('X'+str(x)+' Y'+str(y)+' Z'+str(z)+' E'+str(e))
        return ''
    
    def send_abs_position_request(self, id):
        request = self.format_abs_position_request(id)
        try:
            m = json.loads(request)
            cm = json.dumps(m, separators=(',', ':'))
            #sys.stdout.write("SEND: %s\n" % (cm,))
            cm=cm.encode()
            self._webhook_socket.send(b"%s\x03" % (cm,))
        except:
            sys.stderr.write("ERROR: Unable to parse data\n")
    
    def get_abs_position(self, axis=None):
        self.increment_id()
        self.send_abs_position_request(self.id)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'error' in j:
            j = j['error']['message']
            return 'error: '+str(j)
        elif 'result' in j:
            j = j['result']['status']['toolhead']['position']
            x = j[0]
            y = j[1]
            z = j[2]
            e = j[3]
            if axis == 'x' or axis == 'X':
                return x
            elif axis == 'y' or axis == 'Y':
                return y
            elif axis == 'z' or axis == 'Z':
                return z
            elif axis == 'e' or axis == 'S':
                return e
            else:
                return str('X'+str(x)+' Y'+str(y)+' Z'+str(z)+' E'+str(e))
        return ''
    
    def send_current_tool_request(self, id):
        request = self.format_current_tool_request(id)
        try:
            m = json.loads(request)
            cm = json.dumps(m, separators=(',', ':'))
            #sys.stdout.write("SEND: %s\n" % (cm,))
            cm=cm.encode()
            self._webhook_socket.send(b"%s\x03" % (cm,))
        except:
            sys.stderr.write("ERROR: Unable to parse data\n")
    
    def get_current_tool(self, axis=None):
        # Currently only supports up to 4 extruders. Add more if needed
        self.increment_id()
        self.send_current_tool_request(self.id)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'error' in j:
            j = j['error']['message']
            return 'error: '+str(j)
        elif 'result' in j:
            j = j['result']['status']['toolhead']['extruder']
            if j == 'extruder':
                return 0
            elif j == 'extruder1':
                return 1
            elif j == 'extruder2':
                return 2
            elif j == 'extruder3':
                return 3
            else:
                return -1
        return -1
    
    def get_tool_offset(self, tool_num=None):
        self.config_location = self.get_config_location()
        if tool_num is None:
            tool_num = self.get_current_tool()
        search_text = '[gcode_macro T'+ str(tool_num) + ']'
        if 'printer.cfg' in self.config_location:
            self.config_location = self.config_location.replace('printer.cfg', 'TOOLS.cfg')
        try:
            offset_x = 'null'
            offset_y = 'null'
            offset_z = 'null'
            with open(self.config_location, 'r') as file:
                line = file.readline()
                while line != '':
                    if search_text in line:
                        line = file.readline()
                        if 'gcode:' in line:
                            line = file.readline()
                            elements = line.split()
                            for i, elem in enumerate(elements):
                                if 'OFFSET_X=' in elem:
                                    offset_x = elem.replace('OFFSET_X=', '')
                                elif 'OFFSET_Y=' in elem:
                                    offset_y = elem.replace('OFFSET_Y=', '')
                                elif 'OFFSET_Z=' in elem:
                                    offset_z = elem.replace('OFFSET_Z=', '')
                    else:
                        line = file.readline()
            offset_list = [offset_x, offset_y, offset_z]
            return offset_list
        except:
            return -1
    
    def set_tool_offset(self, tool_num, newX=None, newY=None, newZ=None):
        current_offset = self.get_tool_offset(tool_num)
        self.config_location = self.get_config_location()
        search_text = '[gcode_macro T'+ str(tool_num) + ']'
        if 'printer.cfg' in self.config_location:
            self.config_location = self.config_location.replace('printer.cfg', 'TOOLS.cfg')
        try:
            offset_x = None
            offset_y = None
            offset_z = None
            with open(self.config_location, 'r') as file:
                fullFile = file.readlines()
            with open(self.config_location, 'r') as file:
                filelineIndex = 0
                line = file.readline()
                while line != '':
                    if search_text in line:
                        line = file.readline(); filelineIndex += 1
                        if 'gcode:' in line:
                            line = file.readline(); filelineIndex += 1
                            elements = line.split()
                            for i, elem in enumerate(elements):
                                if 'OFFSET_X=' in elem:
                                    offset_x = i
                                elif 'OFFSET_Y=' in elem:
                                    offset_y = i
                                elif 'OFFSET_Z=' in elem:
                                    offset_z = i
                            if newX is None:
                                newX = current_offset[0]
                            if newY is None:
                                newY = current_offset[1]
                            if newZ is None:
                                newZ = current_offset[2]
                            elements[offset_x] = 'OFFSET_X=' + str(newX)
                            elements[offset_y] = 'OFFSET_Y=' + str(newY)
                            elements[offset_z] = 'OFFSET_Z=' + str(newZ)
                            newLine = '\t'
                            for i in range(len(elements)):
                                newLine = newLine + str(elements[i])
                                if i is not len(elements) - 1:
                                    newLine = newLine + " "
                                else:
                                    newLine = newLine + "\n"
                            fullFile[filelineIndex] = newLine
                            #print('newLine: ' + newLine)
                    else:
                        line = file.readline(); filelineIndex += 1
            with open(self.config_location, 'w') as file:
                file.writelines(fullFile)
                #print(fullFile)
        except:
            print('Failed to store tool offset')
    
    def G10_Override(self, line):
        try:
            toolNum = -1
            xVal = None
            yVal = None
            zVal = None
            for i, item in enumerate(line.split()):
                if "P" in item:
                    toolNum = item.replace('P', '')
                elif "p" in item:
                    toolNum = item.replace('p', '')
                elif "X" in item:
                    xVal = item.replace('X', '')
                elif "x" in item:
                    xVal = item.replace('x', '')
                elif "Y" in item:
                    yVal = item.replace('Y', '')
                elif "y" in item:
                    yVal = item.replace('y', '')
                elif "Z" in item:
                    zVal = item.replace('Z', '')
                elif "z" in item:
                    zVal = item.replace('z', '')
            self.set_tool_offset(toolNum, xVal, yVal, zVal)
            return 'G10 Values Set Successfully'
        except:
            return "ERROR: Unable to parse G10 data"
    
    def send_num_extruders_request(self, id):
        request = self.format_objects_list(id)
        try:
            m = json.loads(request)
            cm = json.dumps(m, separators=(',', ':'))
            #sys.stdout.write("SEND: %s\n" % (cm,))
            cm=cm.encode()
            self._webhook_socket.send(b"%s\x03" % (cm,))
        except:
            sys.stderr.write("ERROR: Unable to parse data\n")
    
    def get_num_extruders(self):
        # Currently only supports up to 4 extruders. Add more if needed
        self.increment_id()
        self.send_num_extruders_request(self.id)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'error' in j:
            j = j['error']['message']
            return 'error: '+str(j)
        elif 'result' in j:
            j = j['result']['objects']
            count = 0
            if 'extruder' in j: count += 1
            if 'extruder1' in j: count += 1
            if 'extruder2' in j: count += 1
            if 'extruder3' in j: count += 1
            return(count)
    
    def get_config_directory(self):
        self.increment_id()
        self.send_status_request(self.id)
        j = json.loads(self.wait_for_response())
        if str(j['id']) != str(self.id):
            return 'error: Incorrect ID returned'
        if 'error' in j:
            j = j['error']['message']
            return 'error: '+str(j)
        elif 'result' in j:
            j = j['result']['config_file']
            return(str(j))
    
    def run_gcode_kbd(self):
        self.poll.register(sys.stdin, select.POLLIN | select.POLLHUP)
        queryText = 'Enter GCode to send to printer, or type exit:'
        print(queryText)
        while 1:
            res = self.poll.poll(1000.)
            for fd, event in res:
                if fd == self.kbd_fd:
                    keyboardEntry = os.read(self.kbd_fd, 4096)
                    keyboardEntry = keyboardEntry.decode().split('\n')
                    for line in keyboardEntry:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if line == 'exit':
                            exit(0)
                        try:
                            print(self.get_gcode(line))
                        except:
                            if not 'G10 ' in line and not 'g10 ' in line:
                                sys.stderr.write("ERROR: Unable to parse line\n")
                else:
                    print(self.get_socket())
                    print(queryText)
    
    # DuetWebAPI Cross Functions
    def printerType(self):
        return(self.pt)
    
    def getCoords(self):
        pos = self.get_position()
        xVal = 0.0
        yVal = 0.0
        zVal = 0.0
        eVal = 0.0
        for i, item in enumerate(pos.split()):
            if "X" in item:
                xVal = round(float(item.replace('X', '')),3)
            elif "Y" in item:
                yVal = round(float(item.replace('Y', '')),3)
            elif "Z" in item:
                zVal = round(float(item.replace('Z', '')),3)
            elif "E" in item:
                eVal = round(float(item.replace('E', '')),6)
        return ({'X':xVal,'Y':yVal,'Z':zVal,'E':eVal})
    
    def getCoordsAbs(self):
        pos = self.get_abs_position()
        xVal = 0.0
        yVal = 0.0
        zVal = 0.0
        eVal = 0.0
        for i, item in enumerate(pos.split()):
            if "X" in item:
                xVal = round(float(item.replace('X', '')),3)
            elif "Y" in item:
                yVal = round(float(item.replace('Y', '')),3)
            elif "Z" in item:
                zVal = round(float(item.replace('Z', '')),3)
            elif "E" in item:
                eVal = round(float(item.replace('E', '')),6)
        return ({'X':xVal,'Y':yVal,'Z':zVal,'E':eVal})
    
    def getLayer(self): # Not currently used
        return 0
    
    def getG10ToolOffset(self,tool):
        to = self.get_tool_offset(tool)
        xVal = round(float(to[0]),3)
        yVal = round(float(to[1]),3)
        zVal = round(float(to[2]),3)
        return ({'X':xVal,'Y':yVal,'Z':zVal})
    
    def getNumExtruders(self):
        return int(self.get_num_extruders())
    
    def getNumTools(self):
        return int(self.get_num_extruders())
    
    def getStatus(self):
        return self.get_status()
    
    def gCode(self,command):
        if self.get_gcode(command) is 'GCode Sent Successfully':
            return 0
        else:
            return -1
    
    def gCodeBatch(self,commands):
        for command in commands:
            if not 'GCode Sent Successfully' in self.get_gcode(command):
                return -1
    
    def getFilenamed(self,filename): # Not currently used
        return ''
    
    def getTemperatures(self): # Not currently used
        return ''
    
    def checkDuet2RRF3(self):
        return False
    
    def getCurrentTool(self):
        return 0 # Needs updating
    
    def getHeaters(self): # Not currently used
        return ''
    
    def isIdle(self):
        if 'ready' in self.get_status():
            return True
        else:
            return False

# Set a file-descriptor as non-blocking
def set_nonblock(fd):
    fcntl.fcntl(fd, fcntl.F_SETFL
                , fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
