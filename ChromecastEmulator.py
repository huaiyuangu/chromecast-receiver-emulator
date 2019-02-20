import json
import tornado.websocket
import tornado.ioloop
import threading

CLIENTS_INDEX = 0
HANDLERS = {}


class MessageHandler(tornado.websocket.WebSocketHandler):

    def initialize(self):
        self.namespace = {
            'con': 'urn:x-cast:com.google.cast.tp.connection',
            'receiver': 'urn:x-cast:com.google.cast.receiver',
            'sender': 'urn:x-cast:com.google.cast.sender',
            'RECEIVER_STATUS': 'urn:x-cast:com.google.cast.sse',
            'cast': 'urn:x-cast:com.google.cast.media',
            'heartbeat': 'urn:x-cast:com.google.cast.tp.heartbeat',
            'message': 'urn:x-cast:com.google.cast.player.message',
            'media': "urn:x-cast:com.google.cast.media",
            'system': "urn:x-cast:com.google.cast.system",
        }
        self.app_ns = 'urn:x-cast:com.hulu.plus'
        self.app_id = '52CF632F'
        self.requestId = 1

        global CLIENTS_INDEX
        self.sender_id = '%s:sender-0' % CLIENTS_INDEX

    def check_origin(self, origin):
        return True

    def open(self, *args, **kwargs):

        global CLIENTS_INDEX
        print 'websocket client connected:', CLIENTS_INDEX, self.request.path
        if self.request.path == '/sender':
            self.write_message({'senderId': self.sender_id})
            HANDLERS[self.sender_id].append(self)
            CLIENTS_INDEX += 1
        elif self.request.path == '/v2/ipc':
            HANDLERS[self.sender_id] = [self]

    def on_message(self, message):

        # print 'ws:\n', message
        m = json.loads(message)
        data = json.loads(m['data'])
        if 'type' in data:
            self.handle_platform_msg(m, data)
        elif 'event_type' in data:
            self.handle_app_msg(message, m['senderId'], data['event_type'])
        else:
            print 'unhandled msg', data

    def handle_app_msg(self, m, senderId, event_type):
        if self.request.path == '/sender':
            if event_type not in ('start', 'playback_update'):
                print ('app --> receiver', m)
            HANDLERS[senderId][0].write_message(m)
        else:
            if event_type not in ('start', 'playback_update'):
                print ('receiver --> app:', m)
            HANDLERS[senderId][1].write_message(m)

    def handle_platform_msg(self, m, data):
        if data['type'] == 'startheartbeat':
            pass
        elif data['type'] == 'ready':
            self.sender_register()
        elif data['type'] == 'MEDIA_STATUS':
            pass
        elif data['type'] == 'sender':
            self.handle_receiver_msg(data)
        else:
            print 'unknown msg type', data

    def handle_receiver_msg(self, data):

        HANDLERS[data['from']].write_message(data['msg'])

    def get_status(self):
        data = {'namespace': self.app_ns,
                'data': {"event_type": "GET_STATUS",
                        "requestId": self.requestId}
                }
        self.requestId += 1
        self.write_message(json.dumps(data))

    def sender_register(self):
        data = {"data": "{\"senderId\":\"%s\",\"type\":\"senderconnected\",\"userAgent\":\"\"}" % self.sender_id,
         "namespace": "urn:x-cast:com.google.cast.system", "senderId": "SystemSender"}
        self.write_message(json.dumps(data))

    def send_license(self):
        data = {"data":"{\"type\":\"license\",\"value\":\"http://playready.directtaps.net/pr/svc/rightsmanager.asmx\"}",
                "namespace": "urn:x-cast:com.google.cast.sample.mediaplayer",
                "senderId":self.sender_id}
        self.write_message(json.dumps(data))

    def ping_receivers(self):
        ping = {"type": "PING",
                "requestId": self.requestId,
                "namespace": "urn:x-cast:com.google.cast.system"
                }
        self.requestId += 1
        self._msg_to_receivers(json.dumps(ping))

    def send_pong(self):
        pong = {'namespace': self.namespace['heartbeat'],
                'data': {"type": "PONG" }}
        self.write_message(json.dumps(pong))

    def send_status(self):
        print ("Sending status")
        data = {'namespace': self.namespace['receiver'], 'data':{
            'status': {'volume': {'muted': False, 'stepInterval': 0.05000000074505806, 'controlType': 'attenuation', 'level': 1.0},
                       'applications': [{'displayName': 'Backdrop', 'statusText': '',
                                         'transportId': 'f43550a8-1fac-41f9-84c5-1d69d8abe427',
                                         'isIdleScreen': True,
                                         'sessionId': 'f43550a8-1fac-41f9-84c5-1d69d8abe427',
                                         'namespaces': [{'name': self.app_ns}],
                                         # 'namespaces': [{'name': 'urn:x-cast:com.google.cast.sse'}],
                                         'appId': 'E8C28D3C'}]},
            'type': 'RECEIVER_STATUS',
            'requestId': 1
            }
                }
        self.write_message(json.dumps(data))

    def _load_app(self):
        data = {'data':{"event_type": "LOAD",
                "currentTime": 0,
                "media": {"contentId": "https://player.xxxx.com/chromecast_curiosity.html",
                          "streamType": "BUFFERED",
                          "contentType": "video/mp4",
                          "metadata": {}}, "customData": {},
                            "sessionId": "6e5468aa-950f-48b3-951f-84f163ec20f6",
                            "requestId": self.requestId, "autoplay": True},
                "senderId": self.sender_id,
                'namespace': self.app_ns
                }
        self.write_message(json.dumps(data))

    def start_video(self, entity, user_token):
        self._load_app()
        start_data = {
              "data": {
                "autoplay": {
                  "autoplay": "on"
                },
                "captions_language": "en",
                "device_ad_id": "17abd158-1812-4d45-a9c5-941588176787",
                "eab_id": entity['bundle']['eab_id'],
                "entity": entity,
                "latitude": 34.011163,
                "limit_ad_tracking": False,
                "longitude": -118.493892,
                "offset_msec": -1,
                "show_prerolls": True,
                "user_token": user_token,
                "volume": 0
        }
        self.requestId += 1
        self.write_message({
            'data': json.dumps(start_data),
            'namespace': self.app_ns,
            'senderId': self.sender_id
            })

    def launch_app(self, appId):
        """
        todo launch chrome automatically
        :param appId:
        :return:
        """
        status = self.get_app_status()
        # open browser by selenium
        self.start_browser(self.url, status, None, {})

        self.set_app_status(status)

    def _msg_to_receivers(self, message):
        """write message to another client"""
        for key, value in self.application.sockets.items():
            value.ws_connection.write_message(message)

    def on_close(self):
        pass

# emulate websocket server like chromecast key
class ChromecastRunThread(threading.Thread):
    """
    check all resource pool status and store in database
    """

    def __init__(self, name):
        super(ChromecastRunThread, self).__init__(name=name)
        self.name = name
        self.master = None

        self._stop = threading.Event()
        self.setDaemon(True)

    def stop(self):
        print 'to stop chromecast server....'
        self._stop.set()

    def stopped(self):
        print 'chromecast server stopped!'
        return self._stop.isSet()

    def run(self):
        """
        start one proxy in background with specific port
        :param port:
        :param addon:
        :return:
        """
        application = tornado.web.Application([
            (r'/v2/ipc', MessageHandler),
            (r'/sender', MessageHandler)
        ])
        application.listen(8008)
        tornado.ioloop.IOLoop.instance().start()
        print 'exiting from chromecast running thread...'


if __name__ == "__main__":
    application = tornado.web.Application([
        (r'/v2/ipc', MessageHandler),
        (r'/sender', MessageHandler)
    ])
    application.listen(8008)
    tornado.ioloop.IOLoop.instance().start()
