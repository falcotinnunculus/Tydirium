from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import sys, os
from threading import Thread
from time import sleep
from datetime import datetime, timedelta
#import cgi
import discord
from discord.ext import tasks


HOST_NAME = ""
PORT = 7216
PIETT_TOKEN = os.environ['PIETT_TOKEN']
PATIENCE = timedelta(minutes=10, seconds=0)
HTTP_TIMEOUT = 10 # in seconds
REFRESH_TIME = 10 # in seconds
SERVER_LIFETIME = 300 # in seconds
CMD_LEADER = "Admiral,"


class ControllPanel(BaseHTTPRequestHandler):
    code_blue = -1
    last_update = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #  self.code_blue = -1

    def do_POST(self):
        print("I got POST")
        def acceptPost():
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                #  ctype, pdict = cgi.parse_header(self.headers.get('Content-Type'))
                body = self.rfile.read()
                ControllPanel.code_blue = ControllPanel.parseAsExpected(body)
                ControllPanel.last_update = datetime.now()
                output = ""
                self.wfile.write(output.encode())
                print("Received code:", ControllPanel.code_blue)
            except:
                self.send_error(404, "{}".format(sys.exc_info()[0]))
                print(sys.exc_info())
        serveThread = Thread(target=acceptPost, args={})
        serveThread.start()
        serveThread.join(timeout=HTTP_TIMEOUT)

    @staticmethod
    def parseAsExpected(body):
        body = str(body)
        if body[0] == 'b' and body[1] == body[-1] == '\'':
            return int(body[2:-1])
        else:
            return -1


def startControllPanel(panel):
    print("Server started http://%s:%s" % (HOST_NAME, PORT))
    try:
        while True:
            th = Thread(target=panel.serve_forever)
            th.start()
            th.join(timeout=SERVER_LIFETIME)
    except KeyboardInterrupt:
        panel.server_close()
        print("Server stopped.")


class FirmusPiett(discord.Client):
    class Communicate:
        def __init__(self):
            self._communicates = [
                ({"type" : discord.ActivityType.watching, "name" : "Koło zamknięte. Nakazuję odwrót!"},
                 {"type" : discord.ActivityType.watching, "name" : "Koło otware. Utrzymujcie kurs i prędkość"}),
                ({"type" : discord.ActivityType.listening, "name" : "Knockin' On Koło's Door"},
                 {"type" : discord.ActivityType.listening, "name" : "Baby It's Cold Outside"})
            ]
            self._status = {
                -1: discord.Status.invisible,
                0 : discord.Status.do_not_disturb,
                1 : discord.Status.online
            }
            self._currentlyUsed = 0

        def setCurrent(self, idx):
            if idx < 0 or idx > len(self._communicates):
                raise IndexError("no such communicate")
            self._currentlyUsed = idx

        def get(self, state):
            state = int(state) if 0 <= int(state) <= 1 else -1
            response = {"status": self._status[state]}
            if state < 0:
                response["activity"] = None
            else:
                response["activity"] = discord.Activity(**self._communicates[self._currentlyUsed][state])
            return response


    def __init__(self):
        super().__init__()
        #  self._panel = panel
        self._last_code = -1
        self._communicate = FirmusPiett.Communicate()

    @tasks.loop(seconds=REFRESH_TIME)
    async def refreshStatus(self):
        now = datetime.now()
        if ControllPanel.last_update is not None and \
           (now - ControllPanel.last_update) > PATIENCE:
            ControllPanel.code_blue = -1
        if self._last_code != ControllPanel.code_blue:
            self._last_code = ControllPanel.code_blue
            presence = self._communicate.get(self._last_code)
            await self.change_presence(**presence)
        print("Current code:", self._communicate._currentlyUsed, "/", self._last_code)

    async def on_ready(self):
        try:
            self.refreshStatus.start()
            print('We have logged in as {0.user}'.format(self))
        except:
            pass
        presence = self._communicate.get(self._last_code)
        await self.change_presence(**presence)

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith(CMD_LEADER):
            await self.execute_order(message.content[len(CMD_LEADER):], message.channel)

    async def execute_order(self, cmd, channel):
        HELP = "help"
        NEW_CODE = "new code"
        REPORT = "report"
        cmd = cmd.strip()
        if cmd.startswith(HELP):
            await self.print_help(cmd[len(HELP):], channel)
        elif cmd.startswith(NEW_CODE):
            await self.new_code(cmd[len(NEW_CODE):], channel)
        elif cmd.startswith(REPORT):
            await self.report(cmd[len(REPORT):], channel)
        else:
            await self.bad_command(channel)

    async def print_help(self, cmd, channel):
        cmd = cmd.strip()
        if cmd != "" and cmd != "!" and cmd != ".":
            await self.bad_command(channel)
        ans = "Calm down, Sir, I'm here.\n" \
              "You can ask me for `report` to see current state of the door " \
              "and last time when it was updated.\n" \
              "You can also order me to `new code n`, so I would display " \
              "the state of the door in different ways."
        await channel.send(ans)

    async def new_code(self, cmd, channel):
        cmd = cmd.strip()
        try:
            cmd = int(cmd)
            if 0 <= cmd < len(self._communicate._communicates):
                self._communicate.setCurrent(cmd)
                self._last_code = -1
                await channel.send("Yes Sir! Code {}".format(cmd))
            else:
                await channel.send("Sir, code {} is out of the protocol!".format(cmd))
        except:
            await self.bad_command(channel)
        
    async def report(self, cmd, channel):
        cmd = cmd.strip()
        if cmd != "" and cmd != "!" and cmd != ".":
            await self.bad_command(channel)
        await self.refreshStatus()
        ans = ""
        if self._last_code == 0:
            ans += "Sir, according to our intelligence the door is closed.\n"
        elif self._last_code == 1:
            ans += "Sir, according to our intelligence the door is open.\n"
        else:
            ans += "Sir, despite many Bothans died, we have not determined the state of the door.\n"
        if ControllPanel.last_update is None:
            ans += "We haven't received any information from them yet."
        else:
            ans += "Last update from Tydirium was received "
            ans += ControllPanel.last_update.strftime("%d.%m.%Y at %H:%M:%S.")
        await channel.send(ans)
        
    async def bad_command(self, channel):
        await channel.send("We have some communication disruption, Sir. Please repeat.")




if __name__ == "__main__":
    server = HTTPServer((HOST_NAME, PORT), ControllPanel)
    server_thread = Thread(target=startControllPanel, args={server})
    server_thread.start()

    piett = FirmusPiett()
    piett.run(PIETT_TOKEN)

    server_thread.join()

