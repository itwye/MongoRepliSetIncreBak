#!/usr/bin/env python
# -*- encoding:utf-8 -*-
##########################################################
# Purpose:
#       mongodb full backup and incremental backup
#
# Steps:
#       (1) first mongodb full backup
#       (2) if have already done a mongodb full backup ,
# +         just do an incremental bakcup 
# 
# Write by itwye in 20180402
#     
##########################################################


import os
import sys
import pickle
import logging
import subprocess
import logging.handlers


class mongoBackup(object):

    def __init__(self,bak_dir,lock_file_path,log_path,logger):

        self.bak_dir = bak_dir
        self.state_file_path = self.bak_dir + os.sep + "state.obj"
        self.lock_file_path = lock_file_path
        self.log_path = log_path
        self.incre_bak_dir = self.bak_dir + os.sep + "incredump"
        self.logger = logger

        self.is_fulldump = False

    def mongoBackup(self):

        if os.path.isfile(self.lock_file_path):

            self.logger.warning("有其它进程正在备份，退出!")
            sys.exit(1)

        else:

            # 创建锁

            subprocess.call("touch %s"%self.lock_file_path,shell=True)

            if os.path.isfile(self.state_file_path):
                
                self.logger.info("准备进行增量备份......")
                self.mongoIncreBackup()

            else:
 
                self.logger.info(" \n \
                ################################## \n \
                                                   \n \
                准备进行全备份.......                \n \
                                                   \n \
                ################################## \n \
                                ")

                self.is_fulldump = True
                self.mongoPreFullBackup()
                self.mongoFullBackup()
 

    def mongoPreFullBackup(self):

        # 清理环境

        # ------------------------
        # 创建dump空目录, 用mongorestore恢复时需要它，原因未知！
        # 创建oplog目录, 后面用来装log bson文件.
        # ------------------------
    
        subprocess.call("cd %s && mkdir dump && mkdir oplog"%self.bak_dir,shell=True)

        # ------------------------
        # 有时用"mongodump --oplog"备份时，不能生成oplog.bson或者为空(当备份时没有数据写往mongodb会出现这种情况)，没有oplog.bson就不能得到
        # 后面增量备份需要的起始时间戳, 所以为防止出现这种情况, 在全备份前，查询local.oplog.rs集合找到最后那条oplog的时间戳作为后面增量备份
        # 的起始时间戳,这样虽然在后面mongorestore恢复时有重复的部分,但oplog是幂等的，多次导入不会重复。
        # (如全备份有生成oplog.bson则取oplog.bson最后log的时间戳)
        # ------------------------

        returnresult = subprocess.Popen("mongo  --quiet --norc local oplog-last-timestamp.js",shell=True,stdout=subprocess.PIPE)

        ts = eval(returnresult.stdout.readlines()[0].strip("\n"))["position"]["$timestamp"]
        t = ts["t"]
        i = ts["i"]

        self.writeTsObj(t,i)


    def mongoFullBackup(self):

        subprocess.call("mongodump --oplog -o %s >> %s 2>&1 "%(self.bak_dir+os.sep+"fulldump",self.log_path),shell=True)

        # 检查是否有生成oplog.bson

        first_oplog_path = self.bak_dir+os.sep+"fulldump"+os.sep+"oplog.bson"

        if os.path.isfile(first_oplog_path) and os.path.getsize(first_oplog_path):

            # 解析oplog.bson获取最后一条log的时间戳.

            t,i = self.parseBsonGetLastLogTs(first_oplog_path)

            # 将时间戳写入state.obj , 后面的增量备份基于该时间戳进行.

            self.writeTsObj(t,i)

            # 移动生成的oplog.bson到新的目录并重命名

            self.mvAndRenameOplogFile(first_oplog_path)
    

    def mongoIncreBackup(self):

        # 取本次增量备份起始时间戳

        t,i = self.readTsObj()

        subprocess.call("mongodump --out %s --db local --collection oplog.rs --query \{ts\ :\ \{\ \$gte\ :\ \{\ \$timestamp\ :\ \{\ t\ :\ %s,\ i\ :\ %s\ \}\ \}\ \}\} >> %s 2>&1"%(self.incre_bak_dir,t,i,self.log_path),shell=True,stdout=subprocess.PIPE)

        incre_oplog_path = self.incre_bak_dir + os.sep + "local" + os.sep + "oplog.rs.bson"

        if os.path.isfile(incre_oplog_path) and os.path.getsize(incre_oplog_path):

            # 取生成的增量oplog最后一条log时间戳作为下一次增量备份起始时间戳,并写入state.obj

            t,i = self.parseBsonGetLastLogTs(incre_oplog_path)
            self.writeTsObj(t,i)
     
            # 移动本次增量log到oplog目录

            self.mvAndRenameOplogFile(incre_oplog_path)

            # 移除本次增量备份生成的目录

            subprocess.call("rm -rf %s"%self.incre_bak_dir,shell=True)


    def mvAndRenameOplogFile(self,source_file):

        if self.is_fulldump:

            # 如全备份有生成oplog.bson, 那移动到oplog目录,并命名为1.oplog.bson

            subprocess.call("mv %s %s"%(source_file,self.bak_dir+os.sep+"oplog"+os.sep+"1.oplog.bson"),shell=True)
        
        else:
            
            # 移动oplog.bson到oplog目录,并扫描oplog目录依序命名文件。

            if len(os.listdir(self.bak_dir+os.sep+"oplog")) == 0:
                subprocess.call("mv %s %s"%(source_file,self.bak_dir+os.sep+"oplog"+os.sep+"1.oplog.bson"),shell=True)
            else:
                num = int([i.split(".")[0] for i in os.listdir(self.bak_dir+os.sep+"oplog")][-1])+1
                subprocess.call("mv %s %s"%(source_file,self.bak_dir+os.sep+"oplog"+os.sep+"%s.oplog.bson"%num),shell=True)
   

    def parseBsonGetLastLogTs(self,bson_file_path):

        # 解析oplog bson文件，得到最后一条的log的时间戳.

        # 方案1：解析慢,对小的bson文件可行，实测，30MB 内含18万条log的bson文件，花费5秒左右!

        returnresult = subprocess.Popen("bsondump --quiet  %s | tail -1"%bson_file_path,shell=True,stdout=subprocess.PIPE)

        last_log = eval(returnresult.stdout.readlines()[0].strip("\n"))

        t = last_log["ts"]["$timestamp"]["t"]
        i = last_log["ts"]["$timestamp"]["i"]

        return t , i


    def writeTsObj(self,t,i):

        pobj = {"t":t,"i":i}

        with open(self.state_file_path,"w") as f:
            pickle.dump(pobj,f)


    def readTsObj(self):

        with open(self.state_file_path) as f:

            pobj = pickle.load(f)

            return pobj["t"],pobj["i"]


#------ logging --------

def GetLog(logfile,logflag,loglevel="debug"):
    logger = logging.Logger(logflag)
    hdlr = logging.handlers.RotatingFileHandler(logfile, maxBytes = 5*1024*1024, backupCount = 5)
    formatter = logging.Formatter("%(asctime)s -- [ %(name)s ] -- %(levelname)s -- %(message)s")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)    
    if loglevel == "debug": 
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger        


# ----- main ----------

if __name__ == "__main__":

    if len(sys.argv[1:]) == 0:
        print "请指定备份目录!,退出!"
        sys.exit(1)
    else:
        bak_dir = sys.argv[1]
        lock_file_path = "/tmp/block.lock"
        log_path = "/var/log/mongo_backup.log"

        try:
            subprocess.call("mkdir -p %s"%bak_dir,shell=True)
            logger = GetLog(log_path,"MongoIncrBak")
            mongo_bak_obj = mongoBackup(bak_dir,lock_file_path,log_path,logger)
            mongo_bak_obj.mongoBackup()
        finally:
            subprocess.call("rm -f %s"%lock_file_path,shell=True)




        











