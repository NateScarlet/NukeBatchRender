# usr/bin/env python
# -*- coding=UTF-8 -*-
# Nuke Batch Render
# Version 2.2
'''
REM load py script from bat
@ECHO OFF & CHCP 936 & CLS
REM Read ini
REM Won't support same variable name in diffrent block
FOR /F "usebackq eol=; tokens=1,* delims==" %%a IN ("%~dp0path.ini") DO (
    IF NOT "%%b"=="" (
        SET "%%a=%%b"
    )
)

CALL :getPythonPath %NUKE%
START "NukeBatchRender" %PYTHON% %0 %*
IF %ERRORLEVEL% == 0 (
    GOTO :EOF
) ELSE (
    ECHO.
    ECHO **ERROR** - NUKE path in path.ini not Correct.
    ECHO.
    EXPLORER path.ini
    PAUSE & GOTO :EOF
)
GOTO :EOF

:getPythonPath
SET "PYTHON="%~dp1python.exe""
GOTO :EOF
'''
import os
import sys
import re
import logging
import logging.handlers
import shutil
import time
import datetime
import io
from subprocess import call, Popen, PIPE

VERSION = 2.2
prompt_codec = 'gbk'
script_codec = 'UTF-8'
LOG_FILENAME = u'Nuke批渲染.log'
render_time = time.strftime('%y%m%d_%H%M')
autoclose = None

def forceSingleInstance():
    call(u'TASKKILL /FI "IMAGENAME eq 自动关闭崩溃提示.exe"'.encode(prompt_codec), stdout=PIPE, stderr=PIPE)
    time.sleep(0.1)
    if os.path.exists(LOG_FILENAME):
        try:
            new_name = LOG_FILENAME + render_time
            os.rename(LOG_FILENAME, new_name)
            os.rename(new_name, LOG_FILENAME)  
        except WindowsError:
            print('**提示** 已经在运行另一个渲染了, 可以直接添加新文件到此文件夹。不要运行多个。'.decode(script_codec).encode(prompt_codec))
            pause()
            exit()

def print_(obj):
    print(str(obj).decode(script_codec).encode(prompt_codec))

def pause():
    call('PAUSE', shell=True)

class CommandLineUI(object):

    ini_path = dict.fromkeys(['EP', 'IMAGE_FOLDER', 'NUKE', 'PROJECT', 'SCENE', 'SERVER'])

    isLowPriority = False
    isHibernate = False
    isProxyRender = False
    isCont = False
    
    def __init__(self):
        call(u'CHCP 936 & TITLE Nuke批渲染_v{} & CLS'.format(VERSION).encode(prompt_codec), shell=True)
        self.readIni()

    def askScheme(self):    
        print_('\n方案1:\t\t\t制作模式(默认) - 流畅, 出错直接跳过\n'
               '方案2:\t\t\t午间模式 - 全速, 出错继续渲\n'
               '方案3:\t\t\t夜间模式 - 全速, 出错继续渲, 完成后休眠\n'
               '方案4:\t\t\t代理模式 - 流畅, 出错继续渲, 输出代理尺寸\n'
               '\nCtrl+C\t直接退出\n')
               
        try:
            choice = call(u'CHOICE /C 1234 /T 15 /D 1 /M "选择方案"'.encode(prompt_codec))
        except KeyboardInterrupt:
            exit()

        if choice == 1:
            self.isLowPriority = True
            logger.info('用户选择:\t制作模式')
        elif choice == 2:
            self.isCont = True
            logger.info('用户选择:\t午间模式')
        elif choice == 3:
            self.isCont = True
            self.isHibernate = True
            logger.info('用户选择:\t夜间模式')
        elif choice == 4:
            self.isCont = True
            self.isProxyRender = True
            self.isLowPriority = True
            logger.info('用户选择:\t代理模式')
        else:
            exit()
        print('')
        
    def readIni(self, ini_file='path.ini'):
        with open(ini_file, 'r') as ini_file:
            for line in ini_file.readlines():
                result = re.match('^([^;].*)=(.*)', line)
                if result:
                    var_name = result.group(1)
                    var_value = result.group(2)
                    self.ini_path[var_name] = var_value
                    logger.debug('{}: {}'.format(var_name, var_value))
        print('')

class NukeBatchRender(CommandLineUI):
    def __init__(self, dir=None):
        super(NukeBatchRender, self).__init__()

        self.error_file_list = []
        if not dir:
            self.dir = os.getcwd()
        logger.debug(u'工作目录: {}'.format(self.dir))

        if not self.getFileList():
            print_('**警告** 没有可渲染文件')
            logger.info(u'用户尝试在没有可渲染文件的情况下运行')
            pause()
            logger.info('<退出>')
            exit()

    def __call__(self):
        while self.getFileList():
            self.batchRender()

    def getFileList(self):
        mtime = lambda file: os.path.getmtime(self.dir + '\\' + file.decode(script_codec). encode(prompt_codec))

        file_list = list(i for i in os.listdir(self.dir) if i.endswith('.nk'))
        if file_list:
            file_list.sort(key=mtime, reverse=False)

            # log and stdout
            print_('将渲染以下文件:')
            for file in file_list:
                print_('\t\t\t{}'.format(file))
                logger.debug (u'发现文件:\t{}'.format(file))
            print_('总计:\t{}\n'.format(len(file_list)))
            logger.debug(u'总计:\t{}'.format(len(file_list)))

        self.file_list = file_list
        return file_list
    
    def batchRender(self):
        if not self.file_list:
            logger.warning(u'没有找到可渲染文件')
            return False
        
        self.setSwitch()

        logger.info('{:-^50s}'.format('<开始批渲染>'))
        for file in self.file_list:
            self.render(file)

        logger.info('<结束批渲染>')

    def render(self, file):
        if not os.path.exists(file):
            return False

        start_time = datetime.datetime.now()
        logger.info(u'{}: 开始渲染'.format(file))
        print_('## [{}/{}]\t{}'.format(self.file_list.index(file) + 1, len(self.file_list), file))
        
        # Lock file
        locked_file = self.lockFile(file)
        
        # Call nuke
        cmd = ' '.join(i for i in [self.ini_path['NUKE'], '-x', self.proxy_switch, self.priority_swith, self.cont_switch, '"{}"'.format(locked_file)] if i)
        logger.debug(u'命令: {}'.format(cmd))
        proc = Popen(cmd, stderr=PIPE)
        
        # Catch stderr
        while proc.poll() == None:
            stderr_data = proc.stderr.readline()
            if stderr_data:
                sys.stderr.write(stderr_data)
                if re.match(r'\[.*\] Warning: (.*)', stderr_data):
                    logger.warning(stderr_data)
                else:
                    logger.error(self.getErrorValue(stderr_data))
        
        # Catch returncode
        returncode = proc.returncode
        if returncode:
            self.error_file_list.append(file)
            count = self.error_file_list.count(file)
            logger.error('{}: 渲染出错 第{}次'.format(file, count))
            if count >= 3:
                logger.error('{}: 连续渲染错误超过3次,不再进行重试。'.format(file))
            elif os.path.exists(file):
                os.remove(locked_file)
            else:
                os.rename(locked_file, file)
            returncode_text = '退出码: {}'.format(returncode)
        else:
            if not self.isProxyRender:
                os.remove(locked_file)
            returncode_text = '正常退出'
        
        # Total time logging
        end_time = datetime.datetime.now()
        total_seconds = (end_time-start_time).total_seconds()
        logger.info('{}: 结束渲染 耗时 {} {}'.format(file, self.secondsToStr(total_seconds),  returncode_text))

        return returncode

    def lockFile(self, file):
        locked_file = file + '.lock'
        file_archive_folder = 'ArchivedRenderFiles\\' + render_time
        file_archive_dest = '\\'.join([file_archive_folder, file])

        shutil.copyfile(file, locked_file)
        if not os.path.exists(file_archive_folder):
            os.makedirs(file_archive_folder)
        if os.path.exists(file_archive_dest):
            time_text = datetime.datetime.fromtimestamp(os.path.getctime(file_archive_dest)).strftime('%M%S_%f')
            alt_file_archive_dest = file_archive_dest + '.' + time_text
            if os.path.exists(alt_file_archive_dest):
                os.remove(file_archive_dest)
            else:
                os.rename(file_archive_dest, alt_file_archive_dest)
        shutil.move(file, file_archive_dest)
        return locked_file
    
    def unlockFiles(self):
        locked_file = list(i for i in os.listdir(self.dir) if i.endswith('.nk.lock'))
        if locked_file:
            print_('**提示** 检测到上次遗留的.nk.lock文件, 将自动解锁') 
            logger.info('检测到.nk.lock文件')
            for file in locked_file:
                unlocked_name = os.path.splitext(file)[0]
                if not os.path.exists(unlocked_name):
                    try:
                        os.rename(file, unlocked_name)
                        logger.info('解锁: {}'.format(file))
                    except WindowsError:
                        print_('**错误** 其他程序占用文件: {}'.format(file))
                        logger.error('其他程序占用文件: {}'.format(file))
                        pause()
                        logger.info('<退出>')
                        exit()   
                else:
                    os.remove(file)
                    logger.info('因为有更新的文件, 移除: {}'.format(file))
            print('')
    
    def getErrorValue(self, str):
        ret = str.strip('\r\n')
        ret = re.sub(r'\[.*?\] ERROR: (.+)', r'\1', ret)
        ret = ret.replace('Read error: No such file or directory', '读取错误: 找不到文件或路径')
        ret = ret.replace('Missing input channel', '输入通道丢失')
        ret = ret.replace('There are no active Write operators in this script', '此脚本中没有启用任何Write节点')
        ret = re.sub(r'(.+?: )Error reading LUT file\. (.+?: )unable to open file\.', r'\1读取LUT文件出错。 \2 无法打开文件', ret)
        ret = re.sub(r'(.+?: )Error reading pixel data from image file (".*")\. Scan line (.+?) is missing\.', r'\1自文件 \2 读取像素数据错误。扫描线 \3 丢失。', ret)
        ret = re.sub(r'(.+?: )Error reading pixel data from image file (".*")\. Early end of file: read (.+?) out of (.+?) requested bytes.', r'\1自文件 \2 读取像素数据错误。过早的文件结束符: 读取了 \4 数据中的 \3 。', ret)
        return ret
    
    def setSwitch(self):
        self.proxy_switch = '-p' if self.isProxyRender else '-f'
        self.priority_swith = '-c 8G --priority low' if self.isLowPriority else ''
        self.cont_switch = '--cont' if self.isCont else ''

    def afterRender(self):
        if os.path.exists('afterRender.bat'):
            call('afterRender.bat')

    def ignoreError(self):
        global autoclose
        if os.path.exists(u'自动关闭崩溃提示.exe'.encode(prompt_codec)):
            autoclose = Popen(u'自动关闭崩溃提示.exe'.encode(prompt_codec))
            
    def hiber(self):
        if self.isHibernate:
            choice = call(u'CHOICE /t 15 /d y /m "即将自动休眠"'.encode(prompt_codec))
            if choice == 2:
                pause()
            else:
                logger.info('<计算机进入休眠模式>')
                print_('[{}]\t计算机进入休眠模式'.format(time.strftime('%H:%M:%S')))
                call(['SHUTDOWN', '/h'])
        else:
            choice = call(u'CHOICE /t 15 /d y /m "此窗口将自动关闭"'.encode(prompt_codec))
            if choice == 2:
                pause()

    def secondsToStr(self, seconds):
        ret = ''
        hour = int(seconds // 3600)
        minute = int(seconds % 3600 // 60)
        seconds = seconds % 60
        if hour:
            ret += '{}小时'.format(hour)
        if minute:
            ret += '{}分钟'.format(minute)
        ret += '{}秒'.format(seconds)
        return ret


class Logger(object):
    LOG_LEVEL = logging.INFO

    def __init__(self):
        self.rotateLog()
        self.setLogger()

    def rotateLog(self):
        if os.path.exists(LOG_FILENAME):
            if os.stat(LOG_FILENAME).st_size > 10000:
                logname = os.path.splitext(LOG_FILENAME)[0]
                if os.path.exists(u'{}.{}.log'.format(logname, 5)):
                    os.remove(u'{}.{}.log'.format(logname, 5))
                for i in range(5)[:0:-1]:
                    old_name = u'{}.{}.log'.format(logname, i)
                    new_name = u'{}.{}.log'.format(logname, i+1)
                    if os.path.exists(old_name):
                        os.rename(old_name, new_name)
                os.rename(LOG_FILENAME, u'{}.{}.log'.format(logname, 1))

    def setLogger(self):
        global logger
        global logfile
        logfile = open(LOG_FILENAME, 'a')
        logger = logging.getLogger(__name__)
        logger.setLevel(self.LOG_LEVEL)
        handler = logging.FileHandler(LOG_FILENAME)
        formatter = logging.Formatter('[%(asctime)s]\t%(levelname)10s:\t%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.info('{:-^100s}'.format('<启动>'))

def main():
    os.chdir(os.path.dirname(__file__))
    forceSingleInstance()
    Logger()
    raise RuntimeError
    render = NukeBatchRender()
    render.unlockFiles()
    render.askScheme()
    render.ignoreError()
    render()
    render.afterRender()
    render.hiber()

    logger.info('<退出>')
    exit()

if __name__ == '__main__':
    try:
        main()
    except SystemExit as e:
        Popen('EXPLORER {}'.format(LOG_FILENAME.encode(prompt_codec)))
        if autoclose:
            autoclose.kill()
        exit(e)
    except:
        import traceback
        traceback.print_exc(file=logfile)
        traceback.print_exc()
        pause()
        logger.error('本程序报错')