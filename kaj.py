# -*- coding: utf-8 -*-

import random

# Packages for integrations
import pylast
from bs4 import BeautifulSoup
import requests

mozilla_agent = 'Mozilla/5.0 (Platform; Security; OS-or-CPU; Localization; rv:1.4) Gecko/20030624 Netscape/7.1 (ax)'

def hltv_get_astralis_matches():
    # First retrieve the match page for Astralis (team id 6665)
    page = BeautifulSoup(requests.get('https://www.hltv.org/matches?team=6665',
                                      headers={'User-Agent': mozilla_agent}).text, "lxml")
    matches = page.find('div', {'class': 'upcoming-matches'})
    if not matches:
        return None
    all_matches = []
    for matchday in matches.find_all('div', {'class': 'match-day'}):
        links = matchday.find_all('a')
        matchdaymatches = matchday.find_all('table', {'class': 'table'})
        for link, matchdaymatch in zip(links, matchdaymatches):
            match_obj = {}
            match_obj['link'] = 'https://hltv.org' + link.attrs['href']
            match_obj['date'] = matchday.find('span', {'class': 'standard-headline'}).text
            match_obj['time'] = matchdaymatch.find('div', {'class': 'time'}).text
            teams = matchdaymatch.find_all('div', {'class': 'team'})
            match_obj['opp'] = teams[0].text if 'Astralis' in teams[1] else teams[1].text
            match_obj['map'] = matchdaymatch.find('div', {'class': 'map-text'}).text

            all_matches.append(match_obj)

    return all_matches


def make_astralis_msg(match_obj):
    return "{0}, {1} - Mod {2} - Map/boX: {3} ({4})".format(
        match_obj['date'],
        match_obj['time'],
        match_obj['opp'],
        match_obj['map'],
        match_obj['link']
    )


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
    msg_max = 1000

    # Initialize everything needed for the bot.
    def __init__(self, bot_id, slack_token, default_channel, lastfm_token, lastfm_secret):
        self.id = bot_id
        self.token = slack_token
        self.def_chan = default_channel

        # Initialize commands
        self.cmds_full = {  # Commands that match entire line
            "hej": self.cmd_hej,
            "musikstatus": self.cmd_lfm,
            "astralis_next": self.cmd_astralis_next,
            "astralis_all": self.cmd_astralis_all
        }
        self.cmds_contain = {  # Commands that match part of line
            "plantagebaronen": self.cmd_pb,
        }
        self.cmds_react = {  # Commands for reactions
            "kmi": self.cmd_kmi,
        }

        # Initialize last.fm stuff
        self.lfm_net = pylast.LastFMNetwork(api_key=lastfm_token, api_secret=lastfm_secret)
        self.lfm_users = ['zeraz', 'daxiee', 'asgerbj', 'predr', 'pb_hogl', 'nemauen']

    # Command that returns list of songs being listened to
    def cmd_lfm(self, cmd):
        msg = ''
        for user in self.lfm_users:
            user_obj = self.lfm_net.get_user(user)
            track = user_obj.get_now_playing()
            if track:
                msg = msg + user + " lytter til: " + str(track.artist) +\
                        " - " + str(track.title)
                msg = msg + "\n"
        return msg

    def cmd_hej(self, cmd):
        if 'name' not in cmd:
            return "Hmm.. Noget gik galt med hej kommandoen :("
        return "Hej " + random.choice(self.adj) + " " + cmd['name']

    def cmd_pb(self, cmd):
        return random.choice(self.pb1) + random.choice(self.pb2)

    def cmd_kmi(self, cmd):
        return "Haha {0}, {1} synes vist lige du skal :kmi:'e".format(cmd['name2'], cmd['name'])

    # Search/replace command
    def cmd_s(self, s, r):
        for (name, msg) in self.messages[::-1]:
            if s in msg:
                return "<" + name + "> " + msg.replace(s, r)
        return None

    # Whenever a message is posted. Do this
    def msg(self, cmd):
        if cmd['content'][0:2] == 's/' or cmd['name'] == 'kaj':
            return
        self.messages.append((cmd['name'], cmd['content']))
        if len(self.messages) > self.msg_max:
            self.messages.pop(0)

    def cmd_hello(self, cmd):
        return ":kaj: Hej med dig jeg hedder Kaj! :kaj:"

    def cmd_edited(self, cmd):
        return "Hov hov, {0}, sidder du og retter din besked :kmi:".format(cmd['name'])

    def cmd_astralis_next(self, cmd):
        ast_matches = hltv_get_astralis_matches()
        if not ast_matches:
            return 'Jeg kunne ikke finde nogen Astralis kampe'
        return make_astralis_msg(ast_matches[0])

    def cmd_astralis_all(self, cmd):
        ast_matches = hltv_get_astralis_matches()
        if not ast_matches:
            return 'Jeg kunne ikke finde nogen Astralis kampe'
        return '\n'.join(map(make_astralis_msg, ast_matches))
