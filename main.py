from interface_agent import InterfaceAgent


def main():
    interface_agent = InterfaceAgent("interface_agent@127.0.0.1", "interface_agent")
    interface_agent.start()

    interface_agent.stop()


if __name__ == '__main__':
    main()