# 朋辈辅学机器人简介
### 机器人任务
#### 课程提醒机器人
* 周五 - 周日 上午 8 点自动检测当日课程
  * 有课，输出当日课程和调课消息，并设置当天课程提醒（课程前15分钟开课提醒，课程结束后发反馈问卷）
  * 没课，输出早安消息
* 每周日晚上 20:00 发送课程反馈问卷

#### 答疑机器人
* 每周五 18:00 发送一次答疑提问链接
* 每天下午 16:00 - 22:00 为群内答疑时间
  * 每隔 10 分钟检测一次提问列表，如果有新提问则提问小钉发送消息


### 测试
##### 课程提醒机器人
1. 没课时能够正常输出早安信息 √
2. 有课时能否输出当日课程信息 √
3. 能否在课程开始 15 分钟前自动提醒 √
4. 有调课时能否正常输出调课信息 √
5. 能否正常发送反馈问卷 √

##### 提问机器人
1. 能否正常发送答疑链接 √
2. 能否每隔 10 分钟检测是否有新的提问并发送 √


## 使用说明
#### 文件组织
* 出于数据保护，本工程的 config, input, log 文件夹中的内容没有上传，可在服务器工程目录下查看
* config 文件夹内包含课程提醒机器人和问题机器人的配置文件，具体说明请看 samples 文件夹内两个 config 内的说明
* input 文件夹内包含程序运行时需要用到的数据，数据格式请见 sample 内相应文件中的说明
* log 文件夹内包含程序运行时两个机器人的日志信息
* src 为代码文件夹

#### 如何运行
```shell
# 每次运行前请确保 input/shift.csv, input/timetable.csv 数据正确
# 并确保 config/course_reminder_bot.config 中单双周配置正确
# input/shift.csv 需要手动输入调课信息，格式参考 sample
# input/timetable.csv 可以由排课表通过 src/utils/timetable2csv.py 生成
# 排课表格式参考 sample，需要本地 scp 到服务器上
# 生成后需要手动将生成的 timetable.csv 移动到 input 文件夹下相应位置
scp [local_path] pbfx@[host]:/home/pbfx/input.xlsx  # 本地
cd ~/DingBot/src/utils
python timetable2csv.py --input /home/pbfx/input.xlsx --output /home/pbfx/input/timetable.csv

# 由于 ssh 运行程序时一旦退出 ssh 连接，相关进程就会被 kill，所以需要使用 tmux 来启动
# 具体可参考 https://askubuntu.com/questions/8653/how-to-keep-processes-running-after-ending-ssh-session
tmux
cd ~/DingBot  # 切换工作目录
conda activate pbfx  # 激活环境
python -m src.main  # 运行程序
# ctrl+b 唤醒 tmux 后按 d 可以退出，此时可以正常 exit 断开连接

# kill 相关进程
ps -aux | grep pbfx | grep main
kill -9 [PID]

# 运行测试
python -m src.main --test

# 若存在 package 缺失
conda(pip) install pipreqs
pipreqs --encoding=utf8 ~/DingBot  # 检测依赖包
conda(pip) install -r ~/DingBot/requirements.txt  # 安装依赖包
```
