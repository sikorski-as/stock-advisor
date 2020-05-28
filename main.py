import asyncio
import threading
from concurrent.futures.thread import ThreadPoolExecutor

import websockets

import config
from interface_agent import InterfaceAgent


def main():
    interface_agent = InterfaceAgent(f"interface_agent@{config.domain}", "interface_agent")
    thread1 = threading.Thread(target=interface_agent.start)
    thread1.start()
    start_server = websockets.serve(interface_agent.hello, "127.0.0.1", 10001)
    loop = asyncio.get_event_loop()
    p = ThreadPoolExecutor(2)
    loop.run_until_complete(start_server)
    loop.run_forever()

    interface_agent.stop()


if __name__ == '__main__':
    main()