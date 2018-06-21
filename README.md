# 使用方法:

1.  到[发布页面](https://github.com/NateScarlet/NukeBatchRender/releases)下载 zip 包
2.  解压 zip 包到你存放 nuke 插件的文件夹
3.  运行文件夹中的`安装.bat`
4.  安装依赖或使用独立包 (见下方)
5.  打开 nuke 菜单 - 工具 - 批渲染

## 使用独立包(运行时脱离 nuke 环境):

1.  到[发布页面](https://github.com/NateScarlet/NukeBatchRender/releases)下载最新预构建包或者自己构建
2.  在插件文件夹中新建`dist`文件夹放入得到的构建包

## 安装依赖

在命令行中运行以下命令

```shell
cd {你的Nuke安装文件夹}
python -m pip install pipenv
python -m pipenv install --system --deploy
```

## 如果需要序列转 mov

安装[ffmpeg](https://ffmpeg.org/) 或者使用独立包(内含`ffmpeg`)

## 构建独立包

### 准备依赖的 exe

依赖的 exe 文件全部放到[./lib/batchrender/bin](./lib/batchrender/bin)中

#### `winactive_by_pid.exe`

_windows 下需要,
缺少此文件会在重复运行时不能自动激活已运行的窗口_

安装[AutoHotKey](https://www.autohotkey.com/)

在[./lib/batchrender/bin/winactive_by_pid.ahk](./lib/batchrender/bin/winactive_by_pid.ahk)的右键菜单中点击`Complie Script`

#### `ffmpeg.exe`

_缺少此文件会在没安装`ffmpeg`的电脑上无法序列转 mov_

到[ffmpeg](https://ffmpeg.org/)官网下载

### 构建

需要[pipenv](https://docs.pipenv.org/)

```shell
cd {源代码目录}
pipenv install -d
pipenv run build.py
```

构建好的可执行程序会位于`dist`文件夹中
