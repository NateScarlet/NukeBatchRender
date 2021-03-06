# Nuke 批渲染

![界面](./pic/batchrender-0.15.4_2019-02-18_14-58-25.png)

## 功能

- [x] 带优先级的渲染队列
- [x] 渲染完成后命令
- [x] 监控文件夹并自动开始渲染
- [x] 错误自动降低优先级以稍后重试
- [x] 如果渲染的是序列可以自动跳过已经渲染好的帧, 然后利用 ffmpeg 序列转视频
- [x] 基于历史数据的剩余时间估计
- [ ] 多机同时渲染同一文件夹
- [ ] 覆盖 Nuke 工程设置
- [ ] Nuke 预合成支持
- [ ] Web 远程控制

## 使用方法

1. 到[发布页面](https://github.com/NateScarlet/NukeBatchRender/releases)下载 zip 包
2. 解压 zip 包到你存放 nuke 插件的文件夹
3. 运行文件夹中的`安装.bat`
4. 打开 nuke 菜单 - _工具_ - _批渲染_

### 构建

项目现在使用 Appveyor 持续构建并部署到[发布页面](https://github.com/NateScarlet/NukeBatchRender/releases)

如果想要自己构建或者不是 windows 系统请参考 [appveyor.yml](./appveyor.yml)
