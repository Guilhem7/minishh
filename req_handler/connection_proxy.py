import sys
from req_handler.sessions import Session

class ConnectionProxy:
    """ConnectionProxy is a class proxying the access to the different messages queues of a Connection object"""
    def add_msg(self, session, msg):
        if(session.is_waiting()):
            session.get_answer_queue().put(msg.decode("utf-8", "ignore"))

        elif(isinstance(session, Session)):
            if(session.connection.is_active):
                sys.stdout.write(msg.decode("utf-8", "ignore"))
                sys.stdout.flush()

            else:
                session.connection.get_queue().put(msg.decode("utf-8", "ignore"))

