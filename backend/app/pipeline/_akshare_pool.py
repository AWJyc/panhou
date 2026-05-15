"""把所有 akshare 调用串行化到一条专用线程。

部分 akshare 美股端点（stock_us_hist 等）走 mini_racer（V8 引擎）做反爬解码，
V8 isolate 在跨线程并发初始化时会触发 partition_address_space FATAL 直接把进程
带崩。让一条线程独占 akshare，整个进程都安全。

代价：akshare 调用之间没有并行（每次 ~2-5s 串起来）。这些都是每日一次的定时
任务，可接受。
"""

import asyncio
import concurrent.futures
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="akshare")


async def run_akshare(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))
