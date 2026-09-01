# ADB 小红书发布

ADB 发布会通过 `uiautomator2` 直接操作 Android 手机上的小红书 App。每日自动发布和手动发布测试都走这条路径。

## 要求

- Android 手机已开启 USB 调试。
- 手机上已安装小红书并登录。
- 已安装 `requirements.txt` 中的 Python 依赖。
- 已通过 `python main.py publish-pack` 或 `python main.py auto-fetch` 生成发布包。

## 检查设备

```powershell
python main.py xhs-adb-doctor
```

如果连接了多台设备，指定设备序列号：

```powershell
python main.py xhs-adb-doctor --device ANDROID_SERIAL
```

如果 `adb` 不在 `PATH` 中，传入完整路径：

```powershell
python main.py xhs-adb-doctor --adb-path "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
```

## 生成发布包

```powershell
python main.py publish-pack
```

发布包包含 `manifest.json` 和 `caption.txt`。图片不会重复复制到发布目录，`manifest.json` 会直接引用报表目录里的图片。

## 只填写内容

下面的命令会上传图片并填写标题、正文和话题，但不会点击最终发布按钮：

```powershell
python main.py xhs-adb-publish --device ANDROID_SERIAL
```

## 正式发布

确认填写流程正常后，再加上 `--publish`：

```powershell
python main.py xhs-adb-publish --device ANDROID_SERIAL --publish
```

## 更替已发布笔记图片

下面的命令会默认打开小红书个人主页，进入最新/置顶的第一篇笔记，把当天发布包里的新图片追加到图片编辑器最后，再删除前面的旧图片：

```powershell
python main.py xhs-adb-replace-latest-images --device ANDROID_SERIAL
```

不加 `--submit` 时，脚本会停在编辑后的笔记页面并保留手机相册里的新图，方便检查。确认流程正常后，加上 `--submit` 保存已发布笔记，保存后会删除这次推送到手机的照片目录：

```powershell
python main.py xhs-adb-replace-latest-images --device ANDROID_SERIAL --submit
```

默认删除的旧图数量等于新图数量。如果旧笔记的图片数量不同，显式指定：

```powershell
python main.py xhs-adb-replace-latest-images --device ANDROID_SERIAL --old-image-count 3 --submit
```

## 使用建议

- 发布过程中保持手机解锁。
- 脚本会先把图片推送到手机上的专用相册，再在小红书里选择图片。
- 更替图片时，脚本默认编辑个人主页第一篇笔记；请确保第一篇就是要更替的笔记。
- 截图和诊断文件默认写入 `data/runtime/adb-xhs/`，也可以用 `--output-dir` 指定目录。
- 如果手机分辨率或小红书页面布局变化，发布前重新运行 `xhs-adb-doctor` 检查。
