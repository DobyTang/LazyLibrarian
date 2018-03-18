#  This file is part of LazyLibrarian.
#  It is just used to talk JSON to the Deluge WebUI
#  A separate library lib.deluge_client is used to talk to the Deluge daemon
#  Lazylibrarian is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#  Lazylibrarian is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
#  along with LazyLibrarian.  If not, see <http://www.gnu.org/licenses/>.
# Parts of this file are a part of SickRage.
# Author: Mr_Orange <mr_orange@hotmail.it>
# URL: http://code.google.com/p/sickbeard/
# Adapted for Headphones by <noamgit@gmail.com>
# URL: https://github.com/noam09
#

from __future__ import unicode_literals

import json
import os
import re
import time
import traceback
from base64 import b64encode

try:
    import requests
except ImportError:
    import lib.requests as requests

import lazylibrarian
from lazylibrarian import logger
from lazylibrarian.formatter import check_int
from lazylibrarian.common import setperm
from lib.six import PY2

delugeweb_auth = {}
delugeweb_url = ''
deluge_verify_cert = False
headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}


def addTorrent(link, data=None):
    try:
        result = {}
        retid = False

        if link and link.startswith('magnet:'):
            logger.debug('Deluge: Got a magnet link: %s' % link)
            result = {'type': 'magnet',
                      'url': link}
            retid = _add_torrent_magnet(result)

        elif link and link.startswith('http'):
            logger.debug('Deluge: Got a URL: %s' % link)
            result = {'type': 'url',
                      'url': link}
            retid = _add_torrent_url(result)

            """
            user_agent = 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)
                          Chrome/41.0.2243.2 Safari/537.36'
            headers = {'User-Agent': user_agent}
            torrentfile = ''
            logger.debug('Deluge: Trying to download (GET)')
            try:
                r = requests.get(link, headers=headers)
                if r.status_code == 200:
                    logger.debug('Deluge: 200 OK')
                    torrentfile = r.text
                    #for chunk in r.iter_content(chunk_size=1024):
                    #    if chunk: # filter out keep-alive new chunks
                    #        torrentfile = torrentfile + chunk
                else:
                    logger.debug('Deluge: Trying to GET %s returned status %d' % (link, r.status_code))
                    return False
            except Exception as e:
                logger.debug('Deluge: Download failed: %s' % str(e))
            if 'announce' not in torrentfile[:40]:
                logger.debug('Deluge: Contents of %s doesn\'t look like a torrent file' % link)
                return False
            # Extract torrent name from .torrent
            try:
                logger.debug('Deluge: Getting torrent name length')
                name_length = int(re.findall('name([0-9]*)\:.*?\:', torrentfile)[0])
                logger.debug('Deluge: Getting torrent name')
                name = re.findall('name[0-9]*\:(.*?)\:', torrentfile)[0][:name_length]
            except Exception as e:
                logger.debug('Deluge: Could not get torrent name, getting file name')
                # get last part of link/path (name only)
                name = link.split('\\')[-1].split('/')[-1]
                # remove '.torrent' suffix
                if name[-len('.torrent'):] == '.torrent':
                    name = name[:-len('.torrent')]
            logger.debug('Deluge: Sending Deluge torrent with name %s and content [%s...]' % (name, torrentfile[:40]))
            result = {'type': 'torrent',
                        'name': name,
                        'content': torrentfile}
            retid = _add_torrent_file(result)
            """
        # elif link.endswith('.torrent') or data:
        elif link:
            if data:
                logger.debug('Deluge: Getting .torrent data')
                torrentfile = data
            else:
                logger.debug('Deluge: Getting .torrent file')
                with open(link, str('rb')) as f:
                    torrentfile = f.read()
            # Extract torrent name from .torrent
            try:
                logger.debug('Deluge: Getting torrent name length')
                name_length = int(re.findall('name([0-9]*):.*?:', torrentfile)[0])
                logger.debug('Deluge: Getting torrent name')
                name = re.findall('name[0-9]*:(.*?):', torrentfile)[0][:name_length]
            except (re.error, IndexError, TypeError):
                logger.debug('Deluge: Could not get torrent name, getting file name')
                # get last part of link/path (name only)
                name = link.split('\\')[-1].split('/')[-1]
                # remove '.torrent' suffix
                if name[-len('.torrent'):] == '.torrent':
                    name = name[:-len('.torrent')]
            logger.debug('Deluge: Sending Deluge torrent with name %s and content [%s...]' % (name, torrentfile[:40]))
            result = {'type': 'torrent',
                      'name': name,
                      'content': torrentfile}
            retid = _add_torrent_file(result)

        else:
            logger.error('Deluge: Unknown file type: %s' % link)

        if retid:
            logger.info('Deluge: Torrent sent to Deluge successfully  (%s)' % retid)
            if lazylibrarian.CONFIG['DELUGE_LABEL']:
                labelled = setTorrentLabel(result)
                logger.debug('Deluge label returned: %s' % labelled)
            return retid
        else:
            logger.info('Deluge returned status %s' % retid)
            return False

    except Exception as err:
        logger.error(str(err))
        if lazylibrarian.LOGLEVEL > 2:
            formatted_lines = traceback.format_exc().splitlines()
            logger.error('; '.join(formatted_lines))


def getTorrentFolder(torrentid):
    logger.debug('Deluge: Get torrent folder name')
    if not any(delugeweb_auth):
        _get_auth()

    try:
        post_data = json.dumps({"method": "web.get_torrent_status",
                                "params": [
                                    torrentid,
                                    ["total_done"]
                                ],
                                "id": 22})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)

        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)
        total_done = json.loads(response.text)['result']['total_done']

        tries = 0
        while total_done == 0 and tries < 10:
            tries += 1
            time.sleep(5)
            response = requests.post(delugeweb_url, data=post_data,
                                     verify=deluge_verify_cert, cookies=delugeweb_auth, headers=headers)
            total_done = json.loads(response.text)['result']['total_done']

        post_data = json.dumps({"method": "web.get_torrent_status",
                                "params": [
                                    torrentid,
                                    [
                                        "name",
                                        "save_path",
                                        "total_size",
                                        "num_files",
                                        "message",
                                        "tracker",
                                        "comment"
                                    ]
                                ],
                                "id": 23})

        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)

        # save_path = json.loads(response.text)['result']['save_path']
        name = json.loads(response.text)['result']['name']

        return name
    except Exception as err:
        logger.debug('Deluge %s: Could not get torrent folder name: %s' % (type(err).__name__, str(err)))


def removeTorrent(torrentid, remove_data=False):
    if not any(delugeweb_auth):
        _get_auth()

    logger.debug('Deluge: Removing torrent %s' % str(torrentid))
    post_data = json.dumps({"method": "core.remove_torrent", "params": [torrentid, remove_data], "id": 25})
    if PY2:
        post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
    response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                             verify=deluge_verify_cert, headers=headers)
    result = json.loads(response.text)['result']

    return result


def _get_auth():
    logger.debug('Deluge: Authenticating...')
    global delugeweb_auth, delugeweb_url, headers, deluge_verify_cert
    delugeweb_auth = {}
    timeout = check_int(lazylibrarian.CONFIG['HTTP_TIMEOUT'], 30)

    delugeweb_cert = lazylibrarian.CONFIG['DELUGE_CERT']
    delugeweb_host = lazylibrarian.CONFIG['DELUGE_HOST']
    delugeweb_port = check_int(lazylibrarian.CONFIG['DELUGE_PORT'], 0)
    if not delugeweb_host or not delugeweb_port:
        logger.error('Invalid delugeweb host or port, check your config')
        return None

    delugeweb_password = lazylibrarian.CONFIG['DELUGE_PASS']

    if not delugeweb_host.startswith("http://") and not delugeweb_host.startswith("https://"):
        delugeweb_host = 'http://%s' % delugeweb_host

    if delugeweb_host.endswith('/'):
        delugeweb_host = delugeweb_host[:-1]

    delugeweb_host = "%s:%s" % (delugeweb_host, delugeweb_port)

    if delugeweb_cert is None or delugeweb_cert.strip() == '':
        deluge_verify_cert = False
        logger.debug('Deluge: FYI no SSL certificate configured')
    else:
        deluge_verify_cert = delugeweb_cert
        delugeweb_host = delugeweb_host.replace('http:', 'https:')
        logger.debug('Deluge: Using certificate %s, host is now %s' % (deluge_verify_cert, delugeweb_host))

    delugeweb_url = delugeweb_host + '/json'

    post_data = json.dumps({"method": "auth.login",
                            "params": [delugeweb_password],
                            "id": 1})
    if PY2:
        post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
    try:
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth, timeout=timeout,
                                 verify=deluge_verify_cert, headers=headers)
    except requests.ConnectionError:
        try:
            logger.debug('Deluge: Connection failed, let\'s try HTTPS just in case')
            response = requests.post(delugeweb_url.replace('http:', 'https:'), data=post_data, timeout=timeout,
                                     cookies=delugeweb_auth, verify=deluge_verify_cert, headers=headers)
            # If the previous line didn't fail, change delugeweb_url for the rest of this session
            logger.error('Deluge: Switching to HTTPS, certificate won\'t be verified NO CERTIFICATE WAS CONFIGURED')
            delugeweb_url = delugeweb_url.replace('http:', 'https:')
        except Exception as e:
            logger.error('Deluge: Authentication failed: %s' % str(e))
            if lazylibrarian.LOGLEVEL > 2:
                formatted_lines = traceback.format_exc().splitlines()
                logger.error('; '.join(formatted_lines))
            return None
    except Exception as err:
        logger.error('Deluge %s: auth.login returned %s' % (type(err).__name__, str(err)))
        if lazylibrarian.LOGLEVEL > 2:
            formatted_lines = traceback.format_exc().splitlines()
            logger.error('; '.join(formatted_lines))
        return None

    auth = json.loads(response.text)["result"]
    if auth is False:
        auth_error = json.loads(response.text)["error"]
        logger.debug('Deluge: Authentication result: %s, Error: %s' % (auth, auth_error))
        return None

    delugeweb_auth = response.cookies

    post_data = json.dumps({"method": "web.connected",
                            "params": [],
                            "id": 10})
    if PY2:
        post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
    try:
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)
    except Exception as err:
        logger.debug('Deluge %s: web.connected returned %s' % (type(err).__name__, str(err)))
        delugeweb_auth = {}
        return None

    connected = json.loads(response.text)['result']
    connected_error = json.loads(response.text)['error']
    logger.debug('Deluge: Connection result: %s, Error: %s' % (connected, connected_error))

    if not connected:
        post_data = json.dumps({"method": "web.get_hosts",
                                "params": [],
                                "id": 11})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        try:
            response = requests.post(delugeweb_url, data=post_data, verify=deluge_verify_cert,
                                     cookies=delugeweb_auth, headers=headers)
        except Exception as err:
            logger.debug('Deluge %s: web.get_hosts returned %s' % (type(err).__name__, str(err)))
            delugeweb_auth = {}
            return None

        delugeweb_hosts = json.loads(response.text)['result']
        if not delugeweb_hosts or len(delugeweb_hosts) == 0:
            logger.error('Deluge: WebUI does not contain daemons')
            delugeweb_auth = {}
            return None

        post_data = json.dumps({"method": "web.connect",
                                "params": [delugeweb_hosts[0][0]],
                                "id": 11})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        try:
            _ = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                              verify=deluge_verify_cert, headers=headers)
        except Exception as err:
            logger.debug('Deluge %s: web.connect returned %s' % (type(err).__name__, str(err)))
            delugeweb_auth = {}
            return None

        post_data = json.dumps({"method": "web.connected",
                                "params": [],
                                "id": 10})

        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        try:
            response = requests.post(delugeweb_url, data=post_data, verify=deluge_verify_cert,
                                     cookies=delugeweb_auth, headers=headers)
        except Exception as err:
            logger.debug('Deluge %s: web.connected returned %s' % (type(err).__name__, str(err)))
            delugeweb_auth = {}
            return None

        connected = json.loads(response.text)['result']

        if not connected:
            logger.error('Deluge: WebUI could not connect to daemon')
            delugeweb_auth = {}
            return None

    return auth


def _add_torrent_magnet(result):
    logger.debug('Deluge: Adding magnet')
    if not any(delugeweb_auth):
        _get_auth()
    try:
        post_data = json.dumps({"method": "core.add_torrent_magnet",
                                "params": [result['url'], {}],
                                "id": 2})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)
        result['hash'] = json.loads(response.text)['result']
        msg = 'Deluge: Response was %s' % str(json.loads(response.text)['result'])
        logger.debug(msg)
        if 'was None' in msg:
            logger.error('Deluge: Adding magnet failed: Is the WebUI running?')
        return json.loads(response.text)['result']
    except Exception as err:
        logger.error('Deluge %s: Adding magnet failed: %s' % (type(err).__name__, str(err)))


def _add_torrent_url(result):
    logger.debug('Deluge: Adding URL')
    if not any(delugeweb_auth):
        _get_auth()

    try:
        post_data = json.dumps({"method": "core.add_torrent_url",
                                "params": [result['url'], {}],
                                "id": 2})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)

        result['hash'] = json.loads(response.text)['result']
        msg = 'Deluge: Response was %s' % str(json.loads(response.text)['result'])
        logger.debug(msg)
        if 'was None' in msg:
            logger.error('Deluge: Adding torrent URL failed: Is the WebUI running?')
        return json.loads(response.text)['result']
    except Exception as err:
        logger.error('Deluge %s: Adding torrent URL failed: %s' % (type(err).__name__, str(err)))
        return False


def _add_torrent_file(result):
    logger.debug('Deluge: Adding file')
    if not any(delugeweb_auth):
        _get_auth()
    try:
        # content is torrent file contents that needs to be encoded to base64
        post_data = json.dumps({"method": "core.add_torrent_file",
                                "params":
                                    [result['name'] + '.torrent', b64encode(result['content'].encode('utf8')), {}],
                                "id": 2})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)
        result['hash'] = json.loads(response.text)['result']
        msg = 'Deluge: Response was %s' % str(json.loads(response.text)['result'])
        logger.debug(msg)
        if 'was None' in msg:
            logger.error('Deluge: Adding torrent file failed: Is the WebUI running?')
        return json.loads(response.text)['result']
    except UnicodeDecodeError:
        try:
            # content is torrent file contents that needs to be encoded to base64
            # this time let's try leaving the encoding as is
            logger.debug('Deluge: There was a decoding issue, let\'s try again')
            post_data = json.dumps({"method": "core.add_torrent_file",
                                    "params": [result['name'].decode('utf8') + '.torrent',
                                               b64encode(result['content']), {}],
                                    "id": 22})
            response = requests.post(delugeweb_url, data=post_data.encode('utf-8'), cookies=delugeweb_auth,
                                     verify=deluge_verify_cert, headers=headers)
            result['hash'] = json.loads(response.text)['result']
            logger.debug('Deluge: Response was %s' % str(json.loads(response.text)))
            return json.loads(response.text)['result']
        except Exception as e:
            logger.error('Deluge: Adding torrent file failed after decode: %s' % str(e))
            if lazylibrarian.LOGLEVEL > 2:
                formatted_lines = traceback.format_exc().splitlines()
                logger.error('; '.join(formatted_lines))
            return False
    except Exception as err:
        logger.error('Deluge %s: Adding torrent file failed: %s' % (type(err).__name__, str(err)))
        if lazylibrarian.LOGLEVEL > 2:
            formatted_lines = traceback.format_exc().splitlines()
            logger.error('; '.join(formatted_lines))
        return False


def setTorrentLabel(result):
    logger.debug('Deluge: Setting label')
    label = lazylibrarian.CONFIG['DELUGE_LABEL']

    if not any(delugeweb_auth):
        _get_auth()

    if ' ' in label:
        logger.error('Deluge: Invalid label. Label can\'t contain spaces - replacing with underscores')
        label = label.replace(' ', '_')
    if label:
        # check if label already exists and create it if not
        post_data = json.dumps({"method": 'label.get_labels',
                                "params": [],
                                "id": 3})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)
        labels = json.loads(response.text)['result']

        if labels:
            if label not in labels:
                try:
                    logger.debug('Deluge: %s label doesn\'t exist in Deluge, let\'s add it' % label)
                    post_data = json.dumps({"method": 'label.add',
                                            "params": [label],
                                            "id": 4})
                    if PY2:
                        post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
                    _ = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                      verify=deluge_verify_cert, headers=headers)
                    logger.debug('Deluge: %s label added to Deluge' % label)
                except Exception as err:
                    logger.error('Deluge %s: Setting label failed: %s' % (type(err).__name__, str(err)))
                    if lazylibrarian.LOGLEVEL > 2:
                        formatted_lines = traceback.format_exc().splitlines()
                        logger.error('; '.join(formatted_lines))

            # add label to torrent
            post_data = json.dumps({"method": 'label.set_torrent',
                                    "params": [result['hash'], label],
                                    "id": 5})
            if PY2:
                post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
            response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                     verify=deluge_verify_cert, headers=headers)
            logger.debug('Deluge: %s label added to torrent' % label)
            return not json.loads(response.text)['error']
        else:
            logger.debug('Deluge: Label plugin not detected')
            return False
    else:
        logger.debug('Deluge: No Label set')
        return True


def setSeedRatio(result):
    logger.debug('Deluge: Setting seed ratio')
    if not any(delugeweb_auth):
        _get_auth()

    ratio = None
    if result['ratio']:
        ratio = result['ratio']

    if ratio:
        post_data = json.dumps({"method": "core.set_torrent_stop_at_ratio",
                                "params": [result['hash'], True],
                                "id": 5})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        _ = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                          verify=deluge_verify_cert, headers=headers)
        post_data = json.dumps({"method": "core.set_torrent_stop_ratio",
                                "params": [result['hash'], float(ratio)],
                                "id": 6})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)

        return not json.loads(response.text)['error']

    return True


def setTorrentPath(result):
    logger.debug('Deluge: Setting download path')
    if not any(delugeweb_auth):
        _get_auth()

    dl_dir = lazylibrarian.CONFIG['DELUGE_DIR']

    if dl_dir:
        post_data = json.dumps({"method": "core.set_torrent_move_completed",
                                "params": [result['hash'], True],
                                "id": 7})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        _ = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                          verify=deluge_verify_cert, headers=headers)

        if not os.path.isdir(dl_dir):
            logger.debug('Deluge: %s directory doesn\'t exist, let\'s create it' % dl_dir)
            try:
                os.makedirs(dl_dir)
                setperm(dl_dir)
            except OSError as e:
                logger.debug("Error creating directory %s, %s" % (dl_dir, e))

        post_data = json.dumps({"method": "core.set_torrent_move_completed_path",
                                "params": [result['hash'], dl_dir],
                                "id": 8})
        if PY2:
            post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
        response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                                 verify=deluge_verify_cert, headers=headers)

        return not json.loads(response.text)['error']

    return True


def setTorrentPause(result):
    logger.debug('Deluge: Pausing torrent')
    if not any(delugeweb_auth):
        _get_auth()

    post_data = json.dumps({"method": "core.pause_torrent",
                            "params": [[result['hash']]],
                            "id": 9})
    if PY2:
        post_data = post_data.encode(lazylibrarian.SYS_ENCODING)
    response = requests.post(delugeweb_url, data=post_data, cookies=delugeweb_auth,
                             verify=deluge_verify_cert, headers=headers)

    return not json.loads(response.text)['error']


def checkLink():
    logger.debug('Deluge: Checking connection')
    msg = "Deluge: Connection successful"
    auth = _get_auth()
    if not auth:
        msg = "Deluge: Connection FAILED\nCheck debug log"
    logger.debug(msg)
    return msg
