#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
import base64
import hmac
import hashlib
from urllib.parse import urlencode
import sounddevice as sd
import websocket
import rospy
from std_msgs.msg import String
from datetime import datetime

# ===================== 讯飞鉴权信息 =====================
APPID = "XXX"
API_KEY = "XXX"
API_SECRET = "XXX"
# =======================================================

class Xfyun_asr():
    def __init__(self):
        # 生成讯飞鉴权wss地址
        self.ws_url = self._build_auth_url()
        self.ws_xf = websocket.create_connection(self.ws_url)
        # ROS发布器：voice/stt 给语音底盘控制
        self.pub = rospy.Publisher('voice/stt', String, queue_size=10)
        # 新增：/asr_result 给星火大模型对话节点
        self.asr_result_pub = rospy.Publisher('/asr_result', String, queue_size=10)

        # 获取默认麦克风
        self.input_dev_num = sd.query_hostapis()[0]['default_input_device']
        if self.input_dev_num == -1:
            rospy.logfatal('No input device found')
            raise ValueError('No input device found, device number == -1')
        self.samplerate = 16000
        self.asr()

    def _build_auth_url(self):
        """讯飞V2 IAT鉴权链接生成"""
        host = "iat-api.xfyun.cn"
        uri = "/v2/iat"
        date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        sign_origin = f"host: {host}\ndate: {date}\nGET {uri} HTTP/1.1"
        hmac_obj = hmac.new(API_SECRET.encode(), sign_origin.encode(), hashlib.sha256)
        sign = base64.b64encode(hmac_obj.digest()).decode()
        auth_raw = f'api_key="{API_KEY}",algorithm="hmac-sha256",headers="host date request-line",signature="{sign}"'
        auth = base64.b64encode(auth_raw.encode()).decode()
        params = {"authorization": auth, "date": date, "host": host}
        return f"wss://{host}{uri}?{urlencode(params)}"

    def send_start_params(self):
        """发送会话初始化帧（移除wpgs参数）"""
        req = {
            "common": {"app_id": APPID},
            "business": {
                "domain": "iat",
                "language": "zh_cn",
                "accent": "mandarin",
                "vad_eos": 2000
            },
            "data": {
                "status": 0,
                "format": "audio/L16;rate=16000",
                "audio": ""
            }
        }
        body = json.dumps(req)
        try:
            self.ws_xf.send(body, websocket.ABNF.OPCODE_TEXT)
        except Exception:
            pass
        rospy.loginfo("send START frame:" + body)

    def send_audio_frame(self, pcm_data):
        """发送持续音频流（status=1 中间帧）"""
        req = {
            "data": {
                "status": 1,
                "format": "audio/L16;rate=16000",
                "audio": base64.b64encode(pcm_data).decode()
            }
        }
        body = json.dumps(req)
        try:
            self.ws_xf.send(body, websocket.ABNF.OPCODE_TEXT)
        except Exception:
            pass

    def send_finish(self):
        """发送结束帧（status=2，告知服务端语音结束）"""
        req = {
            "data": {
                "status": 2,
                "format": "audio/L16;rate=16000",
                "audio": ""
            }
        }
        body = json.dumps(req)
        try:
            self.ws_xf.send(body, websocket.ABNF.OPCODE_TEXT)
        except Exception:
            pass
        rospy.loginfo("send FINISH frame")

    def callback(self, indata, frames, time, status):
        """音频回调：直接转发pcm，和百度代码逻辑完全一致"""
        if status:
            print(status, file=sys.stderr)
        try:
            self.send_audio_frame(bytes(indata))
        except Exception:
            pass

    def asr(self):
        try:
            # RawInputStream 配置，讯飞标准40ms帧长 blocksize=640
            with sd.RawInputStream(samplerate=self.samplerate, blocksize=640,
                                   device=self.input_dev_num, dtype='int16',
                                   channels=1, callback=self.callback):
                self.send_start_params()
                rospy.loginfo("讯飞在线语音识别开始监听!")
                full_text = ""
                while not rospy.is_shutdown():
                    # 无timeout参数，兼容低版本websocket-client
                    result = self.ws_xf.recv()
                    # 增加空报文防护，避免JSONDecodeError崩溃
                    if not result:
                        continue
                    result_data = json.loads(result)
                    if result_data["code"] != 0:
                        rospy.logerr(f"讯飞错误: {result_data['message']}")
                        continue
                    data = result_data["data"]
                    res = data["result"]
                    seg_text = ""
                    for ws_item in res["ws"]:
                        for cw in ws_item["cw"]:
                            seg_text += cw["w"]
                    # 实时打印中间识别文字
                    rospy.loginfo_throttle(2, f"实时识别片段: {seg_text}")
                    full_text += seg_text
                    # ls==True 代表当前一轮语音识别完成
                    if res["ls"]:
                        rospy.loginfo(f"【完整STT结果】{full_text}")
                        # 发布给语音底盘控制
                        self.pub.publish(String(data=full_text))
                        # 新增：同时发布给星火大模型对话节点
                        self.asr_result_pub.publish(String(data=full_text))

                        full_text = ""
                        # 服务端判定语音结束，重建连接开启新一轮识别
                        if data["status"] == 2:
                            rospy.loginfo("服务端判定语音结束，等待下一轮说话")
                            self.ws_xf.close()
                            self.ws_url = self._build_auth_url()
                            self.ws_xf = websocket.create_connection(self.ws_url)
                            self.send_start_params()
        except Exception as e:
            rospy.logerr(f"ASR异常: {type(e).__name__}: {str(e)}")
        except KeyboardInterrupt:
            rospy.loginfo("Stopping xfyun asr node...")
            print("node terminated")

if __name__ == '__main__':
    try:
        rospy.init_node('xfyun_asr', anonymous=False)
        rec = Xfyun_asr()
    except (KeyboardInterrupt, rospy.ROSInterruptException) as e:
        rospy.logfatal("Error occurred! Stopping xfyun asr node...")
        print("node terminated")
