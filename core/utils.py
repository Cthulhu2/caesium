import time
from typing import List


def separate(fetch_list, step=20):  # type: (List, int) -> List
    for x in range(0, len(fetch_list), step):
        yield fetch_list[x:x + step]


def scroll_thumb_size(length, scroll_view):  # type: (int, int) -> int
    return max(1, min(scroll_view,
                      int(scroll_view * scroll_view / length + 0.49)))


def scroll_thumb_pos(length, scroll_pos, scroll_view, thumb_size):
    # type: (int, int, int, int) -> int
    available_track = scroll_view - thumb_size
    thumb_pos = int((scroll_pos / (length - scroll_view))
                    * available_track + 0.49)
    return max(0, min(available_track, thumb_pos))


def msgn_status(msgids, msgn, width):  # type: (List[str], int, int) -> str
    total = len(msgids)
    remains = total - msgn - 1
    if width >= 80:
        return "Сообщение %d из %d (%d осталось)" % (msgn + 1, total, remains)
    return "%d/%d [%d]" % (msgn + 1, total, remains)


def msg_strftime(msg_time_sec, width):  # type: (str, int) -> str
    if not str.isdigit(msg_time_sec):
        return ""
    msg_time_sec = time.gmtime(int(msg_time_sec))
    if width >= 80:
        return time.strftime("%d %b %Y %H:%M UTC", msg_time_sec)
    return time.strftime("%d.%m.%y %H:%M", msg_time_sec)


def msg_strfsize(size_bytes):  # type: (int) -> str
    if size_bytes < 1024:
        return str(size_bytes) + " B"
    return str(format(size_bytes / 1024, ".2f")) + " KiB"
