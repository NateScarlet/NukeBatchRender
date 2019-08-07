渲染任务
====================

每个工程文件对应一个渲染任务，同一工程文件可能存在多个渲染任务。

数据结构
------------------

hash

    类型: string

    文件哈希值，使用 sha256 算法。

mtime

    类型: Date

    文件修改日期，以最后一次见到的修改日期为准。

priority

    类型: number

    优先级，低于 0 代表任务搁置。

started

    类型: Date | undefined

    任务开始时间。

finished

    类型: Date | undefined

    任务结束时间。

error_count

    类型: number

    出错次数。

progress

    类型: number

    渲染进度， 0 到 1 。
