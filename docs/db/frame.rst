渲染帧
===========================

记录渲染过的帧。

数据结构
-------------------

finished

    类型: Date

    渲染完成时间。

file_hash

    类型: string

    工程文件哈希值。

frame

    类型: number

    帧编号

elapsed

    类型: number

    渲染耗时。

output

    类型: string | undefined

    输出文件，多帧可指向同一个文件(视频)。
