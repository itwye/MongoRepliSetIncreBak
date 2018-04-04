#!/usr/bin/env python
# -*- encoding:utf-8 -*-
##########################################################
# Purpose:
#       write data to mongodb for test purpose,so that to test 
# +     it's backup and incremental backup functions.
#
# Functions:
#       (1) batch write data to mongodb
#       (2) write single data to mongodb
# 
# Write by itwye in 20180331
#     
##########################################################

import sys
import ast
import time
import random

try:
    from pymongo import MongoClient
    from pymongo import InsertOne
except ImportError,e:
    print("Please install pymongo package.")
    sys.exit(1)


class writeToMongo(object):

    def __init__(self,mserver,mport,mdb,mcol,args):

        self.mserver = mserver
        self.mport = mport
        self.mdb = mdb
        self.mcol = mcol

        try:
            funObj = getattr(self,args[0])
        except AttributeError:
            print "Don't find the %s function in this script"%args[0]
            showUsage()
            sys.exit(1)
        else:
            funObj(args[1:])

    def batch(self,args):

        # ------------------------
        # number: the number of data to write each time  
        # times: write serveal times
        # ------------------------

        try:
            number = int(args[0])
            times = int(args[1])
        except Exception,e:
            print "Parameter does not meet the requirements,Error is %s"%e
            showUsage()
            sys.exit(1)

        mo = MongoClient(self.mserver,self.mport,maxPoolSize=None)
        mdbo = mo[self.mdb]

        tstart = time.time() 
        
        for n in xrange(0,times):
            cache = []
            for i in xrange(0,number):
                username = ''.join([chr(random.randint(97,122)) for _ in range(8)])
                passwd = ''.join([str(random.randint(0,9)) for i in range(3)])
                cache.append(InsertOne({'username':username,'passwd':passwd}))
            mdbo[self.mcol].bulk_write(cache)

        print "Spend time : %s"%(time.time() - tstart)

    def single(self,args):

        # ------------------------
        # document: a json data
        # ------------------------

        try:
            mdoc = args[0]
            #mdoc = eval(mdoc)
            mdoc = ast.literal_eval('%s'%mdoc)
        except Exception,e:
            print "Parameter does not meet the requirements,Error is %s"%e
            showUsage()
            sys.exit(1)

        mo = MongoClient(self.mserver,self.mport,maxPoolSize=None)
        mdbo = mo[self.mdb]

        tstart = time.time()
        mdbo[self.mcol].insert_one(mdoc)
        print "Spend time : %s"%(time.time() - tstart)


def showUsage():

    print """
---------------- Usage Help ---------------  
(1) batch write:  
    usage: %s batch $number $times 
    examp: %s batch 10000 5 

(2) single write: 
    usage: %s single $document 
    examp: %s single '{"name" : "john", "gender" : "male", "age": 25}'
------------------- End -------------------
"""%(sys.argv[0],sys.argv[0],sys.argv[0],sys.argv[0])



# ------------- Main -----------------
if __name__ == "__main__":

    mserver = "127.0.0.1"
    mport = 27017
    mdb = "mydb"
    mcol = "mycol"

    try:
        writeToMongo(mserver,mport,mdb,mcol,sys.argv[1:])
    except Exception,e:
        print "Exception error is %s"%e
        showUsage()

    sys.exit(0)













