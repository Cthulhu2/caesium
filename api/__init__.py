from dataclasses import dataclass


@dataclass
class MsgMetadata:
    msgid: str
    tags: str
    echo: str
    date: int
    fr: str
    addr: str
    to: str
    subj: str

    @staticmethod
    def from_list(msgid, msg):
        return MsgMetadata(msgid=msgid,
                           tags=msg[0],
                           echo=msg[1],
                           date=int(msg[2]),
                           fr=msg[3],
                           addr=msg[4],
                           to=msg[5],
                           subj=msg[6])
