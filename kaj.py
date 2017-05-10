# -*- coding: utf-8 -*-

# Ny og bedre Lotte!!! :)
# Basic framework from
# https://www.fullstackpython.com/blog/build-first-slack-bot-python.html

import sys  

# Ensure utf8 encoding
reload(sys)  
sys.setdefaultencoding('utf8')

import os
import time
import random
from datetime import datetime

# Nice packages to have
from slackclient import SlackClient
import pylast
#import spotipy

import kaj_conf as kc

class KajBot:
    # For random messages
    adj = ["søde", "smukke", "seje", "flotte", "kloge"]
    pb1 = ["erimitage", "garage", "apanage"]
    pb2 = ["kanonen", "ekskursionen", "instruktionen", "eksplosionen", 
           "ekspansionen"]

    # For last seen
    users = {}

    # For search/replace
    messages = []
    msg_max  = 1000

    # Initialize everything needed for the bot.
    def __init__(self, ID, TOKEN, DEF_CHAN):
        self.id       = ID
        self.token    = TOKEN
        self.def_chan = DEF_CHAN
        self.init_cmds()
        self.init_lfm()

    # Initialize last.fm usage
    def init_lfm(self):
        self.lfm_net = pylast.LastFMNetwork(api_key=kc.LFM_KEY,
                api_secret=kc.LFM_SCRT)
        self.lfm_users = ['zeraz', 'daxiee', 'asgerbj', 'predr', 'pb_hogl',
                'nemauen']
#        self.spfy = spotipy.Spotify()

    # Initialize command function pointers
    def init_cmds(self):
        self.cmds_full = { # Commands that match entire line
            "hej" : self.cmd_hej,
            "musikstatus" : self.cmd_lfm,
        }
        self.cmds_contain = { # Commands that match part of line
            "plantagebaronen" : self.cmd_pb,
        }
        self.cmds_react = { # Commands for reactions
            "kmi" : self.cmd_kmi,
        }
        self.cmds_startswith = {
            "hvornår har du sidst set" : self.cmd_seen,
        }

    def cmd_seen(self,cmd):
        msg = 'Det ved jeg sørme ikke :kaj:'
        name = cmd['content'].split("hvornår har du sidst set")[1].strip().lower()
        val = slack_client.api_call("users.list",presence=True)
        if val and val['ok']:
            for user in val['members']:
                if user['name'] == name:
                    if user['presence'] == 'active':
                        msg = name + " er her da lige nu! :kaj:"
                    elif user['id'] in self.users:
                        msg = "Sidst jeg så " + name + " var: " + \
                                str(self.users[user['id']])
                    else:
                        msg = "Jeg har ikke set " + name + " siden jeg" + \
                            " sidst blev genstartet"
                    break
        return msg

    # Command that returns list of songs being listened to
    def cmd_lfm(self, cmd):
        msg = ''
        for user in self.lfm_users:
            user_obj = self.lfm_net.get_user(user)
            track = user_obj.get_now_playing()
            if track:
                msg = msg + user + " lytter til: " + str(track.artist) +\
                        " - " + str(track.title)
# Spotify links. Not wanted :(
#                res = self.spfy.search(q='artist:' + str(track.artist) +\
#                        " title:" + str(track.title), type='track', limit=1)
#                if len(res['tracks']['items']) > 0:
#                    msg = msg + " (" +\
#                    res['tracks']['items'][0]['external_urls']['spotify'] +\
#                    ")"
                msg = msg + "\n"
        return msg

    def cmd_hej(self, cmd):
        if 'name' not in cmd:
            return "Hmm.. Noget gik galt med hej kommandoen :("
        return "Hej " + random.choice(self.adj) + " " + cmd['name']

    def cmd_pb(self, cmd):
        return random.choice(self.pb1) + random.choice(self.pb2)

    def cmd_kmi(self, cmd):
        return "Haha " + cmd['name2'] + ", " + cmd['name'] + \
                " synes vist lige du skal :kmi:'e"

    # Search/replace command
    def cmd_s(self, s, r):
        for (name,msg) in self.messages[::-1]:
            if s in msg:
                return "<" + name + "> " + msg.replace(s,r)
        return None

    # Whenever a message is posted. Do this
    def msg(self, cmd):
        if cmd['content'][0:2] == 's/' or cmd['name'] == 'Kaj':
            return
        self.messages.append((cmd['name'], cmd['content']))
        if (len(self.messages) > self.msg_max):
            self.messages.pop(0)

    def cmd_presence(self,cmd):
        if cmd['content'] == 'active':
            if cmd['user'] == self.id:
                return "Hej med dig, jeg hedder Kaj! :kaj:"
        if cmd['content'] == 'away':
            self.users[cmd['user']] = datetime.now()
        return None

# Command handler
def handle_command(command, Bot):
#    print("Received command: " + str(command))
    AT_BOT = "<@" + Bot.id + ">"
    done = False
    response = None
    if 'channel' not in command:
        command['channel'] = Bot.def_chan
    if not done and command['type'] == 'message':
        Bot.msg(command)
        # If targeted at the bot
        if AT_BOT in command['content']:
            text = command['content'].split(AT_BOT)[1].strip().lower()
            if text in Bot.cmds_full: # Check full command
                response = Bot.cmds_full[text](command)
            else: # Check starts-with command
                response = "Det forstår jeg ikke :("
                for t,f in Bot.cmds_startswith.items():
                    if text.startswith(t):
                        response = f(command)
                        break
        elif command['content'][0:2] == 's/': # search/replace
            response = "Noget gik galt med din s/"
            parts = command['content'].split('/')
            if (len(parts) == 4):
                response = Bot.cmd_s(parts[1], parts[2])
        else:
            for t,f in Bot.cmds_contain.items():
                if t in command['content']:
                    response = f(command)
        if response:
            done = True

    if not done and command['type'] == 'reaction':
        if command['content'] in Bot.cmds_react:
            response = Bot.cmds_react[command['content']](command)

    if not done and command['type'] == 'presence_change':
        response = Bot.cmd_presence(command)

    if response:
        slack_client.api_call("chat.postMessage",
                channel=command['channel'],
                text=response,
                as_user=True)


def parse_slack_output(slack_rtm_output):
    # Parses the slack RTM output and returns a tuple of the useful parts.
    # Returns a list of commands to consider.
    # Returned command contains the following fields (for now):
    # - type (obvious)
    # - user (User who triggered the even)
    # - content (content of event, e.g. the actual text, reaction, etc.)
    # - channel (channel event happened in. We want to respond here)
    # - name (Name of user who triggered the event)
    # - name2 (Name of target of event, i.e. person who was reacted to)
    rtm_list = slack_rtm_output
    cmds = []
    if rtm_list and len(rtm_list) > 0:
        for event in rtm_list:
            try:
                if not event or not 'type' in event:
                    continue
                # Several different events
                command = {'type' : None}
    #            print(event)
    #            print

                # A regular message to a channel (hopefully)
                # We want to return just the regular info.
                if event['type'] == 'message' and 'subtype' not in event and\
                        'channel' in event:
                    command['type']    = 'message'
                    command['user']    = event['user']
                    command['content'] = event['text']
                    command['channel'] = event['channel']
                    # Try to find the username as well.
                    val = slack_client.api_call("users.info",user=command['user'])
                    command['name']    = '<ukendt navn>'
                    if val.get('ok'):
                        command['name'] = val.get('user').get('name')
                # A reaction was added.
                if event['type'] == 'reaction_added' and 'item' in event and\
                        'channel' in event['item']:
                    command['type']    = 'reaction'
                    command['content'] = event['reaction']
                    command['channel'] = event['item']['channel']
                    val = slack_client.api_call("users.info",
                            user=event['item_user'])
                    command['name2'] = '<ukendt navn>'
                    if val.get('ok'):
                        command['name2'] = val.get('user').get('name')
                    val = slack_client.api_call("users.info",
                            user=event['user'])
                    command['name'] = '<ukendt navn>'
                    if val.get('ok'):
                        command['name'] = val.get('user').get('name')
                # Presence changed
                if event['type'] == 'presence_change':
                    command['type']    = event['type']
                    command['user']    = event['user']
                    command['content'] = event['presence']
                    val = slack_client.api_call("users.info",user=command['user'])
                    command['name']    = '<ukendt navn>'
                    if val.get('ok'):
                        command['name'] = val.get('user').get('name')
                cmds.append(command)
            except ConnectionError as e:
                print("Connection error happened: {0}".format(e))
    return cmds


# Main stuff.
# Creates a loop parsing messages, passing the messages to handle_command
if __name__ == "__main__":
    # instantiate Slack & Twilio clients
    slack_client = SlackClient(kc.BOT_TOKEN)
    kaj        = KajBot(kc.BOT_ID, kc.BOT_TOKEN, kc.DEF_CHAN)

    READ_WEBSOCKET_DELAY = 0.2 # Delay between reading in seconds
    if slack_client.rtm_connect():
        print("Kaj! connected and running!")
        while True:
            try:
                cmds = parse_slack_output(slack_client.rtm_read())
                for cmd in cmds:
                    handle_command(cmd, kaj)
                time.sleep(READ_WEBSOCKET_DELAY)
            except WebSocketConnectionClosedException as e:
                print("Connection error happened: {)}".format(e))
                slack_client.rtm_connect()
    else:
        print("Connection failed. Invalid Slack token or bot ID?")


