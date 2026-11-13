#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import numpy as np
import cv2
import rospy
from std_msgs.msg import Bool, String
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError

def draw_str(dst, target, s):
    x, y = target
    cv2.putText(dst, s, (x+1, y+1), cv2.FONT_HERSHEY_PLAIN, 1.0, (0, 0, 0), thickness = 2, lineType=cv2.LINE_AA)
    cv2.putText(dst, s, (x, y), cv2.FONT_HERSHEY_PLAIN, 1.0, (255, 255, 255), lineType=cv2.LINE_AA)

class Facedetect():
    def __init__(self):
        self.bridge = CvBridge()
        self.image_sub = rospy.Subscriber("/camera/color/image_raw", Image, self.callback)
        # 发布人脸检测话题 True=检测到人 False=无人
        self.face_pub = rospy.Publisher("/face_detected", Bool, queue_size=5)
        # 发布TTS播报文本话题
        self.tts_pub = rospy.Publisher("/tts_say", String, queue_size=3)

        # ==========新增：防重复播报冷却==========
        self.greet_cooldown = rospy.Duration(8.0)   # 8秒冷却，8秒内不会重复播报
        self.last_greet_time = rospy.Time(0)

    def detect(self, img, cascade):
        rects = cascade.detectMultiScale(img, scaleFactor=1.3, minNeighbors=4, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)
        if len(rects) == 0:
            return []
        rects[:, 2:] += rects[:, :2]
        return rects

    def draw_rects(self, img, rects, color):
        for x1, y1, x2, y2 in rects:
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

    def callback(self, data):
        try:
            image = self.bridge.imgmsg_to_cv2(data, "bgr8")
        except CvBridgeError as e:
            print(e)
            return

        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt.xml")
        nested = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        rects = self.detect(gray, cascade)
        vis = image.copy()
        self.draw_rects(vis, rects, (0, 255, 0))

        if not nested.empty():
            for x1, y1, x2, y2 in rects:
                roi = gray[y1:y2, x1:x2]
                vis_roi = vis[y1:y2, x1:x2]
                subrects = self.detect(roi.copy(), nested)
                self.draw_rects(vis_roi, subrects, (255, 0, 0))

        now = rospy.Time.now()
        # 发布人脸状态
        if len(rects) > 0:
            self.face_pub.publish(Bool(data=True))
            # 判断冷却时间，只有超过冷却时间才播报一次欢迎
            if now - self.last_greet_time > self.greet_cooldown:
                self.tts_pub.publish(String(data="你好，欢迎光临"))
                self.last_greet_time = now
            draw_str(vis, (20, 20), "Face Detected!")
        else:
            self.face_pub.publish(Bool(data=False))
            draw_str(vis, (20, 20), "No Face")

        cv2.imshow('facedetect', vis)
        cv2.waitKey(1)

def main():
    rospy.init_node('facedetector', anonymous=True)
    Facedetect()
    try:
        rospy.spin()
    except KeyboardInterrupt:
        print("Shutting down")
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
