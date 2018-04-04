#!/usr/bin/env python
# -*- encoding:utf-8 -*-
##########################################################
# Purpose:
#       mongodb restore by mongodb full backup and mongodb 
# +     incremental backup
#
# Steps:
#       (1) mongodb restore by mongodb full backup
#       (2) mongodb restore by mongodb incremental backup
# 
# Write by itwye in 20180402
#     
##########################################################

import os
import sys
import subprocess

class mongoRestore(object):

    def __init__(self,bak_dir):

        self.bak_dir = bak_dir
        self.fulldump_dir = self.bak_dir+os.sep+"fulldump"
        self.oplog_dir = self.bak_dir+os.sep+"oplog"

    def mongoRestore(self):

        self.mongoFullRestore()
        self.mongoIncreRestore()

    def mongoFullRestore(self):

        print "----- 开始还原全备份 ------"

        print "shi : %s/"%self.fulldump_dir
        subprocess.call("mongorestore --drop --dir=%s/"%self.fulldump_dir,shell=True)

    def mongoIncreRestore(self):

        # 当前目录创建dump空目录, 不然增量还原会出错，原因未知！
        subprocess.call("mkdir dump",shell=True)

        print "----- 开始还原各个增量备份 -----"

        oplog_file_list = os.listdir(self.oplog_dir)

        print "=以下增量备份按顺序还原!="
        print oplog_file_list

        for oplog in oplog_file_list:

            print "=还原[%s]="%(self.oplog_dir+os.sep+oplog)
            subprocess.call("mongorestore  --oplogReplay  --oplogFile=%s"%(self.oplog_dir+os.sep+oplog),shell=True)

# -------- main -----------

if __name__ == "__main__":

    if len(sys.argv[1:]) == 0:
        print "请指定备份文件所在目录,退出!"
        sys.exit(1)
    else:
        bak_dir = sys.argv[1]
        if os.path.isdir("%s"%bak_dir+os.sep+"fulldump") and os.path.isdir("%s"%bak_dir+os.sep+"oplog"):
            print "备份文件存在，满足条件，准备开始还原!"
            mongo_res_obj = mongoRestore(bak_dir)
            mongo_res_obj.mongoRestore()
        else:
            print "该目录下不存在相关备份文件，无法还原,退出！"
            sys.exit(1)

