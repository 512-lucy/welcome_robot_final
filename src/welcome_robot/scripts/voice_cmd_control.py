#!/usr/bin/env python3
# voice_cmd_control.py
# 订阅 /voice/stt 话题，NLU意图实体解析，发布 /cmd_vel 控制机器人
import rospy
import re
import time
from geometry_msgs.msg import Twist
from std_msgs.msg import String

# ================= NLU解析函数 =================
num_map = {
    "一":1, "二":2, "三":3, "四":4, "五":5,
    "1":1, "2":2, "3":3, "4":4, "5":5
}

def nlu_parse(text):
    action = None
    duration = 0.5  # 默认0.5秒，比如“右转一下”
    if re.search(r"向前|前进", text):
        action = "forward"
    elif re.search(r"后退|向后", text):
        action = "backward"
    elif re.search(r"左转|向左", text):
        action = "left"
    elif re.search(r"右转|向右", text):
        action = "right"
    else:
        return None, None
    # 提取时间实体
    match = re.search(r"([一二三四五12345]+)秒", text)
    if match:
        num_str = match.group(1)
        if num_str in num_map:
            duration = num_map[num_str]
    return action, duration

# ================= 机器人运动函数 =================
def robot_move(action, duration):
    pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
    twist = Twist()
    linear_speed = 0.2
    angular_speed = 0.3
    if action == "forward":
        twist.linear.x = linear_speed
    elif action == "backward":
        twist.linear.x = -linear_speed
    elif action == "left":
        twist.angular.z = angular_speed
    elif action == "right":
        twist.angular.z = -angular_speed
    else:
        rospy.loginfo("未知动作")
        return
    rospy.loginfo(f"执行指令：{action}，持续 {duration} 秒")
    start = time.time()
    while time.time() - start < duration and not rospy.is_shutdown():
        pub.publish(twist)
    # 停止
    stop_twist = Twist()
    pub.publish(stop_twist)
    rospy.loginfo("运动结束，机器人停止")

# ================= 订阅回调函数 =================
def stt_callback(msg):
    text = msg.data
    rospy.loginfo(f"收到ASR文本：{text}")
    action, dur = nlu_parse(text)
    if action is not None:
        robot_move(action, dur)
    else:
        rospy.loginfo("不是移动指令，忽略")

if __name__ == "__main__":
    rospy.init_node("voice_nlu_control_node")
    # 订阅ASR输出话题 /voice/stt
    rospy.Subscriber("/voice/stt", String, stt_callback)
    rospy.loginfo("NLU控制节点已启动，等待语音指令...")
    rospy.spin()
