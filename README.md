> ### mongodb replica set backup and incremental backup

    mongodb原生提供了全备份工具mongodump，没有提供增量备份工具(cloud manager等收费的除外)，
    
    出于实验目的，尝试用自写脚本+"mongodump"+"mongorestore"来实现增量备份和还原，经测试可以做到(未做严格测试)，
    
    注：本测试在mongodb 3.6.2 下进行, 是对mongodb replica set进行的增量备份和还原。
    
> #### 环境说明

    (1) mongodump需支持"--oplog"选项
    
    (2) mongorestore需支持"--oplogFile"选项,即需要mongorestore版本 >= 3.4
    
    (3) 为便于脚本执行, 我将mongod都监听在0.0.0.0上
    
    (4) mongodb测试库:mydb,集合:mycol
    
> #### 原理

> ##### 备份
    
    (1) 用户给定干净的空备份目录
    
    (2) 针对该空目录，第一次做全备份，也仅做一次全备份 (mongodump --oplog -o fulldump/)
        - 全备份前，查找local.oplog.rs最后一条log的时间戳保存到state.obj
        - 全备份后，如有生成oplog.bson,则取其最后一条log的时间戳覆盖到state.obj，作为下次增量备份的起始
          时间戳，如没有生成oplog.bson,则就用全备份前的保存到state.obj的时间戳作为下次增量备份的起始.
    
    (3) 全备份已做，后续都是增量备份 
    
    (4) 开始增量备份，取state.obj中起始时间戳,基于此到local.oplog.rs查找大于等于该事件戳的log，保存并按序命名。
        取本次得到的oplog的最后log的时间戳覆盖到state.obj.
    
    (5) 重复(4)
    
> ##### 还原

    (1) 用户给定有备份文件的目录
    
    (2) 还原先前备份的“全备份” (mongorestore  --dir=fulldump/)
    
    (3) 按顺序还原各个增量备份 (mongorestore  --oplogReplay  --oplogFile=oplog/1.oplog.bson)

> #### 测试过程

> ##### (1) 往mongodb写测试数据

```
./writeTestDataToMongo.py batch 10000 2
./writeTestDataToMongo.py single '{"name" : "itwye", "gender" : "male", "age": 18}'  #特征数据便于后期验证
```

> ##### (2) 全备份

```
./mongoIncreBackup.py  /tmp/mongodb_backup/
```
查找/var/log/mongo_backup.log看对应日志
```
2018-04-04 15:26:13,593 -- [ MongoIncrBak ] -- INFO --
                 ##################################
                 准备进行全备份.......
                 ##################################
2018-04-04T15:26:13.675+0800    writing admin.system.version to
2018-04-04T15:26:13.676+0800    done dumping admin.system.version (1 document)
2018-04-04T15:26:13.676+0800    writing mydb.mycol to
2018-04-04T15:26:13.714+0800    done dumping mydb.mycol (20001 documents)
2018-04-04T15:26:13.715+0800    writing captured oplog to
2018-04-04T15:26:15.080+0800            dumped 1 oplog entry
```
 
> ##### (3) 往mongodb写测试数据

```
./writeTestDataToMongo.py batch 10000 20
```

> ##### (4) 增量备份 

前一步写了10000*20条数据,本次增量备份花费时间较多

```
./mongoIncreBackup.py  /tmp/mongodb_backup/  #注意还是/tmp/mongodb_backup/目录。
```
```
2018-04-04 15:35:45,238 -- [ MongoIncrBak ] -- INFO -- 准备进行增量备份......
2018-04-04T15:35:45.254+0800    writing local.oplog.rs to
2018-04-04T15:35:46.395+0800    done dumping local.oplog.rs (200058 documents)
```

> ##### (5) 往mongodb写测试数据

```
./writeTestDataToMongo.py single '{"name" : "lisi", "gender" : "male", "age": 21}'
```

> ##### (6) 增量备份 

```
./mongoIncreBackup.py  /tmp/mongodb_backup/  #注意还是/tmp/mongodb_backup/目录。
```
```
2018-04-04 15:42:18,651 -- [ MongoIncrBak ] -- INFO -- 准备进行增量备份......
2018-04-04T15:42:18.663+0800    writing local.oplog.rs to
2018-04-04T15:42:19.548+0800    done dumping local.oplog.rs (40 documents)
```

> ##### (7) 查看mydb.mycol现有多少数据

    截止目前总共往mydb.mycol写了: 10000*2+1+10000*20+1 = 220002
    
```
itwyetest:PRIMARY> use mydb;
switched to db mydb
itwyetest:PRIMARY> db.mycol.find().count()
220002
```

> ##### (8) 删除mydb库

```
itwyetest:PRIMARY> use mydb;
switched to db mydb
itwyetest:PRIMARY> db.dropDatabase()
{
        "dropped" : "mydb",
        "ok" : 1,
        "operationTime" : Timestamp(1522828344, 2),
        "$clusterTime" : {
                "clusterTime" : Timestamp(1522828344, 2),
                "signature" : {
                        "hash" : BinData(0,"AAAAAAAAAAAAAAAAAAAAAAAAAAA="),
                        "keyId" : NumberLong(0)
                }
        }
}
itwyetest:PRIMARY>
```

> ##### (9) 还原

```
./mongoIncreRestore.py /tmp/mongodb_backup/
```
```
[root@secondary scripts]# ./mongoIncreRestore.py /tmp/mongodb_backup/
备份文件存在，满足条件，准备开始还原!
----- 开始还原全备份 ------
2018-04-04T15:53:58.419+0800    preparing collections to restore from
2018-04-04T15:53:58.420+0800    reading metadata for mydb.mycol from /tmp/mongodb_backup/fulldump/mydb/mycol.metadata.json
2018-04-04T15:53:58.434+0800    restoring mydb.mycol from /tmp/mongodb_backup/fulldump/mydb/mycol.bson
2018-04-04T15:53:58.843+0800    no indexes to restore
2018-04-04T15:53:58.843+0800    finished restoring mydb.mycol (20001 documents)
2018-04-04T15:53:58.844+0800    done
mkdir: cannot create directory ‘dump’: File exists
----- 开始还原各个增量备份 -----
=以下增量备份按顺序还原!=
['1.oplog.bson', '2.oplog.bson', '3.oplog.bson']
=还原[/tmp/mongodb_backup//oplog/1.oplog.bson]=
2018-04-04T15:53:58.861+0800    using default 'dump' directory
2018-04-04T15:53:58.862+0800    preparing collections to restore from
2018-04-04T15:53:58.863+0800    replaying oplog
2018-04-04T15:53:58.863+0800    done
=还原[/tmp/mongodb_backup//oplog/2.oplog.bson]=
2018-04-04T15:53:58.876+0800    using default 'dump' directory
2018-04-04T15:53:58.877+0800    preparing collections to restore from
2018-04-04T15:53:58.878+0800    replaying oplog
2018-04-04T15:54:01.873+0800    oplog  829KB
2018-04-04T15:54:04.873+0800    oplog  1.64MB
2018-04-04T15:54:07.873+0800    oplog  2.50MB
2018-04-04T15:54:10.873+0800    oplog  3.31MB
2018-04-04T15:54:13.873+0800    oplog  4.10MB
2018-04-04T15:54:16.873+0800    oplog  4.87MB
2018-04-04T15:54:19.874+0800    oplog  5.64MB
2018-04-04T15:54:22.873+0800    oplog  6.44MB
2018-04-04T15:54:25.873+0800    oplog  7.20MB
2018-04-04T15:54:28.873+0800    oplog  7.95MB
2018-04-04T15:54:31.874+0800    oplog  8.70MB
2018-04-04T15:54:34.873+0800    oplog  9.45MB
2018-04-04T15:54:37.873+0800    oplog  10.2MB
2018-04-04T15:54:40.873+0800    oplog  11.0MB
2018-04-04T15:54:43.873+0800    oplog  11.8MB
2018-04-04T15:54:46.873+0800    oplog  12.6MB
2018-04-04T15:54:49.873+0800    oplog  13.4MB
2018-04-04T15:54:52.873+0800    oplog  14.2MB
2018-04-04T15:54:55.873+0800    oplog  14.9MB
2018-04-04T15:54:58.873+0800    oplog  15.7MB
2018-04-04T15:55:01.873+0800    oplog  16.4MB
2018-04-04T15:55:04.874+0800    oplog  17.2MB
2018-04-04T15:55:07.873+0800    oplog  18.0MB
2018-04-04T15:55:10.873+0800    oplog  18.7MB
2018-04-04T15:55:13.874+0800    oplog  19.5MB
2018-04-04T15:55:16.873+0800    oplog  20.2MB
2018-04-04T15:55:19.873+0800    oplog  21.0MB
2018-04-04T15:55:22.873+0800    oplog  21.8MB
2018-04-04T15:55:25.873+0800    oplog  22.5MB
2018-04-04T15:55:28.873+0800    oplog  23.3MB
2018-04-04T15:55:31.873+0800    oplog  24.1MB
2018-04-04T15:55:34.873+0800    oplog  24.8MB
2018-04-04T15:55:37.873+0800    oplog  25.6MB
2018-04-04T15:55:40.873+0800    oplog  26.4MB
2018-04-04T15:55:43.873+0800    oplog  27.2MB
2018-04-04T15:55:46.873+0800    oplog  27.9MB
2018-04-04T15:55:49.874+0800    oplog  28.7MB
2018-04-04T15:55:52.873+0800    oplog  29.5MB
2018-04-04T15:55:55.873+0800    oplog  30.2MB
2018-04-04T15:55:58.873+0800    oplog  31.0MB
2018-04-04T15:56:01.873+0800    oplog  31.8MB
2018-04-04T15:56:04.873+0800    oplog  32.5MB
2018-04-04T15:56:07.873+0800    oplog  33.3MB
2018-04-04T15:56:10.304+0800    oplog  34.0MB
2018-04-04T15:56:10.304+0800    done
=还原[/tmp/mongodb_backup//oplog/3.oplog.bson]=
2018-04-04T15:56:10.325+0800    using default 'dump' directory
2018-04-04T15:56:10.325+0800    preparing collections to restore from
2018-04-04T15:56:10.327+0800    replaying oplog
2018-04-04T15:56:10.328+0800    done
[root@secondary scripts]#
```

> ##### (10) 验证

    查看现在mydb.mycol集合条目

```
itwyetest:PRIMARY> use mydb;
switched to db mydb
itwyetest:PRIMARY> db.mycol.find().count()
220002
itwyetest:PRIMARY>
```

    查看mydb.mycol最后一条数据

```
itwyetest:PRIMARY>
itwyetest:PRIMARY> db.mycol.find().sort({"_id":-1}).limit(1)
{ "_id" : ObjectId("5ac4818355f307058461c318"), "gender" : "male", "age" : 21, "name" : "lisi" }
```
    
    还原后，数据条目220002条正确, 最后一条数据也正确！



