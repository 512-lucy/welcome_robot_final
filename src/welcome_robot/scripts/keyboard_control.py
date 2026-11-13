#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
from geometry_msgs.msg import Twist
import sys, select, termios, tty

msg = """
---------------------------
控制Spark机器人：
w : 前进
s : 后退
a : 左转
d : 右转
空格 : 停止
q : 退出
---------------------------
"""
moveBindings = {
        'w':(0.2,0),
        's':(-0.2,0),
        'a':(0,0.4),
        'd':(0,-0.4),
        ' ':(0,0)
}

def getKey():
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

if __name__=="__main__":
    settings = termios.tcgetattr(sys.stdin)
    rospy.init_node('keyboard_ctrl')
    pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
    twist = Twist()
    print(msg)
    try:
        while(1):
            key = getKey()
            if key in moveBindings.keys():
                twist.linear.x = moveBindings[key][0]
                twist.angular.z = moveBindings[key][1]
                pub.publish(twist)
            elif key == 'q':
                break
            else:
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                pub.publish(twist)
    except Exception as e:
        print(e)
    finally:
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        pub.publish(twist)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
