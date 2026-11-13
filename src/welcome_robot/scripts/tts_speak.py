#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import String
import websocket
import json
import base64
import hmac
import hashlib
from urllib.parse import urlencode, urlparse
from datetime import datetime
import threading
import pyaudio
 
# ===================== 讯飞密钥（和ASR/星火同一个app） =====================
APPID = "XXX"
API_KEY = "XXX"
API_SECRET = "XXX"
 
# TTS配置
TTS_WSS_URL = "wss://tts-api.xfyun.cn/v2/tts"
VOICE = "x4_yezi"        # 发音人：小燕；更多看讯飞文档
SPEED = 50               # 语速0-100
PITCH = 50               # 音调0-100
VOLUME = 50              # 音量0-100
SAMPLE_RATE = 16000      # 输出pcm采样率16000
# =========================================================================
 
class XfyunOnlineTTS:
    def __init__(self):
        self.appid = APPID
        self.api_key = API_KEY
        self.api_secret = API_SECRET
        self._play_lock = threading.Lock()
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=1024
        )
 
    def _build_auth_url(self, wss_url):
        parsed = urlparse(wss_url)
        host = parsed.netloc
        path = parsed.path
        date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        hmac_obj = hmac.new(self.api_secret.encode('utf-8'), signature_origin.encode('utf-8'), hashlib.sha256)
        signature = base64.b64encode(hmac_obj.digest()).decode('utf-8')
        auth_raw = (
            f'api_key="{self.api_key}",algorithm="hmac-sha256",'
            f'headers="host date request-line",signature="{signature}"'
        )
        authorization = base64.b64encode(auth_raw.encode('utf-8')).decode('utf-8')
        params = {
            "authorization": authorization,
            "date": date,
            "host": host
        }
        return f"{wss_url}?{urlencode(params)}"
 
    def synthesize(self, text):
        if not self._play_lock.acquire(blocking=False):
            rospy.logwarn("TTS正在播放，忽略本次请求")
            return
        try:
            auth_url = self._build_auth_url(TTS_WSS_URL)
            ws_reply_done = threading.Event()
            err_msg = None
 
            def on_open(ws):
                payload = {
                    "common": {"app_id": self.appid},
                    "business": {
                        "aue": "raw",
                        "vcn": VOICE,
                        "speed": SPEED,
                        "pitch": PITCH,
                        "volume": VOLUME,
                        "auf": f"audio/L16;rate={SAMPLE_RATE}",
                        "tte": "UTF8"
                    },
                    "data": {
                        "status": 0,
                        "text": base64.b64encode(text.encode("utf-8")).decode("utf-8")
                    }
                }
                ws.send(json.dumps(payload))
 
            def on_message(ws, msg):
                nonlocal err_msg
                try:
                    data = json.loads(msg)
                except Exception:
                    rospy.logerr(f"TTS收到非JSON消息: {msg[:500]}")
                    err_msg = "TTS返回非JSON数据"
                    ws.close()
                    ws_reply_done.set()
                    return
 
                rospy.logdebug(f"TTS原始返回: {json.dumps(data, ensure_ascii=False)[:500]}")
 
                # 兼容两种返回结构
                if "header" in data:
                    code = data["header"].get("code", -1)
                    message = data["header"].get("message", "")
                    payload = data.get("payload", {})
                    audio_block = payload.get("audio", {})
                else:
                    code = data.get("code", -1)
                    message = data.get("message", "")
                    audio_block = data.get("data", {})
 
                if code != 0:
                    err_msg = f"TTS错误 {code}: {message}"
                    rospy.logerr(err_msg)
                    ws.close()
                    ws_reply_done.set()
                    return
 
                audio_b64 = audio_block.get("audio", "")
                if audio_b64:
                    try:
                        pcm_bytes = base64.b64decode(audio_b64)
                        self.stream.write(pcm_bytes)
                    except Exception as e:
                        rospy.logerr(f"TTS音频解码/播放失败: {e}")
                else:
                    rospy.logwarn(f"TTS返回帧无音频数据: {json.dumps(data, ensure_ascii=False)[:300]}")
 
                status = audio_block.get("status", -1)
                if status == 2:
                    ws.close()
                    ws_reply_done.set()
 
            def on_error(ws, error):
                nonlocal err_msg
                err_msg = f"WebSocket连接错误: {error}"
                rospy.logerr(err_msg)
                ws_reply_done.set()
 
            def on_close(ws, close_status_code, close_msg):
                rospy.logdebug(f"TTS WebSocket关闭, code={close_status_code}, msg={close_msg}")
                ws_reply_done.set()
 
            ws_app = websocket.WebSocketApp(
                auth_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            th = threading.Thread(target=ws_app.run_forever, daemon=True)
            th.start()
            ws_reply_done.wait(timeout=20)
            if err_msg:
                rospy.logerr(err_msg)
        except Exception as e:
            rospy.logerr(f"TTS合成异常 {str(e)}")
        finally:
            self._play_lock.release()
 
 
class XfyunTTSNode:
    def __init__(self):
        self.tts_engine = XfyunOnlineTTS()
        rospy.Subscriber("/tts_say", String, self.callback, queue_size=2)
        rospy.loginfo("✅讯飞在线TTS节点就绪，订阅话题：/tts_say")
 
    def callback(self, msg):
        text = msg.data.strip()
        if not text:
            return
        rospy.loginfo(f"TTS待播报文本：{text}")
        threading.Thread(target=self.tts_engine.synthesize, args=(text,), daemon=True).start()
 
 
if __name__ == '__main__':
    rospy.init_node("xfyun_online_tts_node")
    node = XfyunTTSNode()
    rospy.spin()
