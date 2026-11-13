# 迎宾导游机器人（ROS1 Noetic）
## 项目简介
基于ROS1 Noetic开发的智能迎宾机器人，集成人脸检测、语音识别ASR、语音合成TTS、讯飞星火大模型对话、多点自主导航功能，可用于展厅迎宾导览场景。
本项目代码仅支持ROS1，不兼容ROS2。

## 实现功能
- 人脸检测迎宾：摄像头识别到人脸，自动播报欢迎语
- 语音交互：语音识别转文字，调用讯飞星火大模型智能对话，TTS语音朗读回答
- 语音控制运动：识别语音指令，控制机器人前进、后退、转向
- 多点导航迎宾：识别访客后，依次前往A、B参观点，完成导览后自动返回待机home点
- 键盘手动遥控：支持w/a/s/d键盘控制机器人移动，用于演示模式
- 导航超时容错：导航失败时可切换手动遥控，保证答辩演示流畅

## 技术栈
- 开发环境：ROS Noetic（Ubuntu 20.04）
- 视觉：OpenCV 人脸检测
- 语音：讯飞开放平台 WebSocket API（ASR + TTS）
- 大模型：讯飞星火大模型
- 导航：move_base 自主导航
- 开发语言：Python3

## 项目目录
spark_noetic/
└── src/
├── face_detector      # 人脸检测节点
├── multi_nav          # 多点导航节点
└── welcome_robot      # 语音 ASR/TTS、大模型对话、键盘控制节点


## 启动说明
一共开启3个独立终端

终端1：底层导航（底盘 + D435 + spark_map地图 + amcl + move_base+RViz）
cd ~/spark_noetic
source devel/setup.bash
roslaunch spark_navigation amcl_demo_lidar_rviz.launch camera_type_tel:=d435 lidar_type_tel:=ydlidar_g6

终端 2：启动 D435 深度相机
roslaunch realsense2_camera rs_camera.launch enable_color:=true enable_depth:=true

终端 3：启动人脸检测、导航调度、语音全套业务节点
cd ~/spark_noetic
source devel/setup.bash
roslaunch welcome_robot all_in_one_demo.launch

## 注意事项

- 需要自行配置讯飞 APPID、API_KEY、API_SECRET
- 导航点位需要在 RViz 中采集，修改 multi_nav 内坐标
- 编译命令：
catkin_make
source devel/setup.bash
