from bisect import bisect_left, bisect_right
from operator import itemgetter
from datetime import datetime
from typing import List, Dict, Any


def data_filter_with_binary_search(
    data: List[Dict[str, Any]],
    from_dt: datetime,
    to_dt: datetime,
    epsilon_ms: float = 100,
) -> List[Dict[str, Any]]:
    if not data:
        return []

    low_bound = from_dt.timestamp() - (epsilon_ms / 1000.0)
    high_bound = to_dt.timestamp() + (epsilon_ms / 1000.0)

    get_ts = itemgetter("timestamp")

    left = bisect_left(data, low_bound, key=get_ts)
    right = bisect_right(data, high_bound, key=get_ts)

    return data[left:right]
