#!/usr/bin/env python
import rospy
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from std_msgs.msg import Bool, String   # 新增导入String

# ==========点位：home待机点、A参观点、B参观点============
Point_home = [-0.8607707596452842, -0.458118738296885, 0.0, 0.0, 0.0, -0.8995888022041945, 0.43673789273295566]
Point_A = [-2.529348872087504, -3.582366513362758, 0.0, 0.0, 0.0, -0.7104657860702972, 0.7037317435099221]
Point_B = [-1.1867471706630088, -3.554981674613556, 0.0, 0.0, 0.0, 0.6041984213071596, 0.796833021966473]
class MultiNavTrigger:
    def __init__(self):
        rospy.init_node("multi_nav_node")
        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        rospy.loginfo("等待move_base服务...")
        self.client.wait_for_server()
        rospy.loginfo("move_base连接成功，待机等待人脸触发")

        # 订阅人脸检测话题
        rospy.Subscriber("/face_detected", Bool, self.face_callback)
        self.task_running = False # 任务锁，防止重复触发导航

        # =========新增：TTS播报发布器，和人脸节点用同一个话题=========
        self.tts_pub = rospy.Publisher("/tts_say", String, queue_size=3)

    def send_nav_goal(self, pose_array, wait_sec=20):
        rospy.loginfo(f"🚀下发导航目标 x={pose_array[0]:.3f}, y={pose_array[1]:.3f}")
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = pose_array[0]
        goal.target_pose.pose.position.y = pose_array[1]
        goal.target_pose.pose.position.z = pose_array[2]
        goal.target_pose.pose.orientation.x = pose_array[3]
        goal.target_pose.pose.orientation.y = pose_array[4]
        goal.target_pose.pose.orientation.z = pose_array[5]
        goal.target_pose.pose.orientation.w = pose_array[6]

        self.client.send_goal(goal)
        finished = self.client.wait_for_result(rospy.Duration(wait_sec))
        state = self.client.get_state()
        if finished and state == 3:
            rospy.loginfo("✅到达目标点")
            return True
        else:
            rospy.logwarn("❌导航失败或者超时，取消目标")
            self.client.cancel_goal()
            return False

    def face_callback(self, msg):
        # 检测到人，并且当前没有任务在跑
        if msg.data is True and self.task_running is False:
            rospy.loginfo("👤检测到人，启动迎宾导航任务！")
            self.client.cancel_all_goals()   # 清除move_base里面残留导航目标
            self.task_running = True

            # 1.前往A参观点，到达停留3秒
            self.send_nav_goal(Point_A)
            rospy.sleep(3)
            # 2.前往B参观点，到达停留3秒
            self.send_nav_goal(Point_B)
            rospy.sleep(3)
            # 返回home待机点位
            self.send_nav_goal(Point_home)

            rospy.loginfo("一轮迎宾任务完成，回到待机，等待下一位访客")
            # =========新增：语音播报这句话=========
            self.tts_pub.publish(String(data="一轮迎宾任务完成，回到待机，等待下一位访客"))

            self.task_running = False

if __name__ == "__main__":
    try:
        nav = MultiNavTrigger()
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("导航节点退出")
