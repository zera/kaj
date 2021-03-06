import time
from json import JSONDecodeError

from slackclient import SlackClient
from slackclient.server import SlackConnectionError
from websocket._exceptions import WebSocketConnectionClosedException

from kaj import KajBot
from kaj_config import KAJ_DEFAULT_CHANNEL, KAJ_LASTFM_SECRET, KAJ_LASTFM_TOKEN, KAJ_SLACK_TOKEN, KAJ_ID

import logging
logger = logging.getLogger('kajlogger')
logger.setLevel(logging.DEBUG)

READ_WEBSOCKET_DELAY = 0.4  # Delay between reading in seconds
CONNECTION_RETRY_DELAY = 1
CONNECTION_RETRY_LIMIT = 10


def slack_get_username(slack_client, user_id):
    name = '<ukendt_navn>'
    try:
        logger.debug("Seding slack API call: {0}, {1}".format(
            "users.info",
            user_id)
        )
        val = slack_client.api_call("users.info", user=user_id)
        if val.get('ok'):
            name = val.get('user').get('name')
    except JSONDecodeError as err:
        logger.error('Got a JSON DecodeError while retrieving username: {0}'.format(err))
    return name


def handle_command(command, bot, slack_client):
    AT_BOT = "<@" + bot.id + ">"
    done = False
    response = None
    if 'channel' not in command:
        command['channel'] = bot.def_chan
    if not done and command['type'] == 'message':
        bot.msg(command)
        # If targeted at the bot
        if AT_BOT in command['content']:
            text = command['content'].split(AT_BOT)[1].strip().lower()
            if text in bot.cmds_full:  # Check full command
                response = bot.cmds_full[text](command)
        elif command['content'][0:2] == 's/':  # search/replace
            response = "Noget gik galt med din s/"
            parts = command['content'].split('/')
            if len(parts) == 4:
                response = bot.cmd_s(parts[1], parts[2])
        else:
            for t, f in bot.cmds_contain.items():
                if t in command['content']:
                    response = f(command)
        if response:
            done = True

    if not done and command['type'] == 'reaction':
        if command['content'] in bot.cmds_react:
            response = bot.cmds_react[command['content']](command)

    if not done and command['type'] == 'hello':
        response = bot.cmd_hello(command)

    if not done and command['type'] == 'message_changed':
        response = bot.cmd_edited(command)

    if response:
        logger.debug("Seding slack API call: {0}, {1}, {2}".format(
            "chat.postMessage",
            command['channel'],
            response)
        )
        slack_client.api_call("chat.postMessage",
                              channel=command['channel'],
                              text=response,
                              as_user=True)


def parse_slack_output(slack_rtm_output, slack_client):
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
    if not rtm_list:
        return []
    logger.debug("rtm_list: {0}".format(rtm_list))
    cmds = []
    if rtm_list and len(rtm_list) > 0:
        for event in rtm_list:
            try:
                if not event or 'type' not in event:
                    continue
                # Several different events
                command = {'type': None}

                # A regular message to a channel (hopefully)
                # We want to return just the regular info.
                if event['type'] == 'message' and 'subtype' not in event and\
                        'channel' in event:
                    command['type'] = 'message'
                    command['user'] = event['user']
                    command['content'] = event['text']
                    command['channel'] = event['channel']
                    # Try to find the username as well.
                    command['name'] = slack_get_username(slack_client, command['user'])
                # A reaction was added.
                if event['type'] == 'reaction_added' and 'item' in event and\
                        'channel' in event['item']:
                    command['type'] = 'reaction'
                    command['content'] = event['reaction']
                    command['channel'] = event['item']['channel']
                    command['name2'] = slack_get_username(slack_client, event['item_user'])
                    command['name'] = slack_get_username(slack_client, event['user'])
                # This event is sent to the bot when it goes online
                if event['type'] == 'hello':
                    command['type'] = 'hello'
                # This event is sent if a user edits his/her message
                if event['type'] == 'message' and 'subtype' in event and event['subtype'] == 'message_changed'\
                        and 'attachments' not in event['message']:  # We ignore messages with attachments.
                    command['type'] = 'message_changed'
                    command['user'] = event['message']['user']
                    command['channel'] = event['channel']
                    # Try to find the username as well.
                    command['name'] = slack_get_username(slack_client, command['user'])
                # Finally add the command to the list of KajBot-commands
                cmds.append(command)
            except ConnectionError as e:
                logger.critical("Connection error happened: {0}".format(e))
    return cmds


# Main stuff.
# Creates a loop parsing messages, passing the messages to handle_command
if __name__ == "__main__":
    logger.info("Initializing Kaj Bot")
    kaj_client = SlackClient(KAJ_SLACK_TOKEN)
    kaj = KajBot(KAJ_ID, KAJ_SLACK_TOKEN, KAJ_DEFAULT_CHANNEL, KAJ_LASTFM_TOKEN, KAJ_LASTFM_SECRET)

    logger.info("Initialized bot. Running main loop with delay {0}".format(READ_WEBSOCKET_DELAY))
    while True:
        if kaj_client.server.connected:
            try:
                kaj_cmds = parse_slack_output(kaj_client.rtm_read(), kaj_client)
                if kaj_cmds:
                    logger.info("Commands: {0}".format(kaj_cmds))
                for cmd in kaj_cmds:
                    handle_command(cmd, kaj, kaj_client)
                time.sleep(READ_WEBSOCKET_DELAY)
            except WebSocketConnectionClosedException as e:
                logger.critical("Connection error happened: {0}".format(e))
            except SlackConnectionError as e:
                logger.critical("Connection error happened: {0}".format(e))
            except TimeoutError as e:
                logger.critical("Timeout error happened: {0}".format(e))
        else:
            delay = CONNECTION_RETRY_DELAY
            for i in range(CONNECTION_RETRY_LIMIT):
                time.sleep(delay)
                logger.info('Connecting, try {0}/{1}'.format(i, CONNECTION_RETRY_LIMIT))
                if kaj_client.rtm_connect():
                    logger.info('Connection succeeded')
                    break
                else:
                    logger.error('Connection retry {0}/{1} failed!'.format(i, CONNECTION_RETRY_LIMIT))
                delay *= 2
            else:
                logger.critical('Failed after limit reconnect attempts. Perhaps invalid slack token?')
                break
    logger.critical('Shutting down main loop')