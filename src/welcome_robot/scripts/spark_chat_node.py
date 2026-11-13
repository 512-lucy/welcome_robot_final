#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from std_msgs.msg import String, Bool
import requests
import json

# =========和你讯飞APP保持一致，拷贝vosk_spark_chat.py里面配置=========
APPID = "XXX"
APIKey = "XXX"
APISecret = "XXX"
SPARK_URL = "https://spark-api-open.xf-yun.com/v1/chat/completions"
SPARK_MODEL = "4.0Ultra"

class SparkChatNode:
    def __init__(self):
        rospy.init_node("spark_chat_node")
        # 上电默认：mode2 迎宾模式
        self.work_mode = "mode2"
        # 人脸防重复播报标记，避免持续人脸循环播报欢迎语
        self.face_greet_flag = False

        # 订阅语音识别输出结果话题
        rospy.Subscriber("/asr_result", String, self.asr_callback, queue_size=1)
        # 订阅人脸检测话题 Bool True=检测到人脸
        rospy.Subscriber("/face_detected", Bool, self.face_callback, queue_size=1)
        # 订阅外部话题切换模式（保留原功能，兼容rostopic/其他节点控制）
        rospy.Subscriber("/set_work_mode", String, self.mode_switch_callback, queue_size=1)

        # 发布给TTS播报
        self.tts_pub = rospy.Publisher("/tts_say", String, queue_size=2)
        rospy.loginfo("✅星火大模型对话节点就绪，等待语音识别输入")
        rospy.loginfo(f"✅上电默认工作模式：{self.work_mode}【mode2=迎宾；mode1=纯对话】")

    # 复制自 vosk_spark_chat.py 获取星火回答
    def get_spark_reply(self, text):
        try:
            r = requests.post(
                SPARK_URL,
                headers={"Authorization": f"Bearer {APIKey}:{APISecret}",
                         "Content-Type": "application/json"},
                json={"model": SPARK_MODEL,
                      "messages": [{"role": "user", "content": text}]},
                timeout=30)
            d = r.json()
        except Exception as e:
            rospy.logerr(f"星火网络异常：{e}")
            return None
        if r.status_code != 200 or d.get("code") not in (None,0):
            rospy.logerr(f"星火API错误 {r.status_code} {json.dumps(d,ensure_ascii=False)[:200]}")
            return None
        try:
            return d["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    # 复制vosk_spark_chat.py本地兜底，网络不通时回复
    def local_fallback(self, text):
        t = text.strip()
        if any(k in t for k in ("你好","您好","嗨","在吗")):
            return "你好，我是迎宾机器人助手。"
        if "时间" in t or "几点" in t:
            from datetime import datetime as _dt
            return "现在时间是" + _dt.now().strftime("%H点%M分") + "。"
        if "再见" in t or "拜拜" in t:
            return "再见，很高兴和你聊天。"
        return f"我听到你说：{t}。"

    def asr_callback(self, msg):
        user_text = msg.data.strip()
        if not user_text:
            return
        rospy.loginfo(f"👂用户语音识别文本：{user_text}")

        # =========【新增：口述语音口令判断，优先处理模式切换指令】=========
        lower_text = user_text.lower()
        if "切换成模式2" in lower_text:
            self._set_mode("mode1")
            self.tts_pub.publish(String(data="已经切换到模式2，现在为语音对话模式"))
            return
        if "切换成模式1" in lower_text:
            self._set_mode("mode2")
            self.tts_pub.publish(String(data="已经切换到模式1，现在为迎宾模式"))
            return

        # ----下面完全是你原来的逻辑，没有改动----
        reply = self.get_spark_reply(user_text)
        if reply is None:
            rospy.logwarn("星火调用失败，启用本地兜底回复")
            reply = self.local_fallback(user_text)
        rospy.loginfo(f"🤖大模型回答：{reply}")
        self.tts_pub.publish(String(data=reply))

    # 内部统一设置模式函数，重置人脸标记 + 打日志
    def _set_mode(self, target_mode):
        self.work_mode = target_mode
        self.face_greet_flag = False
        rospy.loginfo(f"🔄工作模式切换 → {self.work_mode}")

    # 外部ROS话题切换回调（保留原有逻辑不变）
    def mode_switch_callback(self, msg):
        cmd = msg.data.strip().lower()
        if cmd in ("mode1","mode2"):
            self._set_mode(cmd)
        else:
            rospy.logwarn(f"未知模式指令:{cmd}，请发送 mode1 / mode2")

    # 人脸检测回调
    def face_callback(self, msg):
        face_detected = msg.data
        # 只有 mode2（迎宾模式）才会处理人脸问候
        if self.work_mode != "mode2":
            return

        if face_detected:
            if not self.face_greet_flag:
                rospy.loginfo("👤检测到人脸，播报欢迎光临")
                self.tts_pub.publish(String(data="你好，欢迎光临"))
                self.face_greet_flag = True
        else:
            # 人脸离开画面，重置标记，下次来人再次问候
            self.face_greet_flag = False

if __name__ == "__main__":
    try:
        node = SparkChatNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("spark_chat_node 退出")
