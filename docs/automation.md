# 每日自动化

本项目可以用一个长期运行的 Python 命令完成每日流程：

- 采集卡带回收价。
- 生成报表图片和小红书发布包。
- 通过 Android 手机和 ADB 发布到小红书。
- 按需启动本地网页管理 UI。

## 首次配置 Android 手机

安装依赖：

```bash
pip install -r requirements.txt
```

连接已开启 USB 调试的 Android 手机，并确保手机上的小红书已登录。然后检查设备状态：

```bash
python main.py xhs-adb-doctor
```

如果连接了多台设备，使用 `adb devices` 看到的序列号指定设备：

```bash
python main.py xhs-adb-doctor --device ANDROID_SERIAL
```

## 启动每日自动化

一个命令即可启动每日采集、随机发布窗口和本地管理 UI：

```bash
python main.py auto --ui
```

当前默认配置等价于：

```bash
python main.py auto --ui --fetch-time 11:50 --publish-time 12:00-12:10
```

进程需要一直运行。进程关闭后，定时任务不会继续执行。

## 手动测试命令

立即执行采集并生成发布包：

```bash
python main.py auto-fetch
```

立即通过 Android 发布当天发布包：

```bash
python main.py auto-publish
```

只在 Android 小红书里填写内容，不点击最终发布按钮：

```bash
python main.py xhs-adb-publish
```

填写并点击发布：

```bash
python main.py xhs-adb-publish --publish
```

## 注意事项

- 每天会在发布窗口内随机选择一个分钟执行发布。
- 进程启动或恢复后会补做当天已经到期的任务。
- 发布会等待当天已到期的采集任务成功完成。
- ADB 截图默认写入 `data/runtime/adb-xhs/`。
- 发布过程中保持手机亮屏并解锁。
