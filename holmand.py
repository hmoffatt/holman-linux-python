#!/usr/bin/env python3

import os
import sys
import time
import socket
import json
from threading import Thread
from argparse import ArgumentParser
import holman

tap_timer_manager = None

class TapTimerPrintListener(holman.TapTimerListener):
    """
    An implementation of ``TapTimerListener`` that prints each event.
    """
    def __init__(self, tap_timer):
        self.tap_timer = tap_timer

    def started_connecting(self):
        self.print("connecting...")

    def connect_succeeded(self):
        self.print("connected")

    def connect_failed(self, error):
        self.print("connect failed: " + str(error))

    def started_disconnecting(self):
        self.print("disconnecting...")

    def disconnect_succeeded(self):
        self.print("disconnected")

    def timer_written(self):
        self.print("timer written")

    def print(self, string):
        print("Holman tap timer " + self.tap_timer.mac_address + " " + string)

class TapTimerTestListener(TapTimerPrintListener):
    def __init__(self, tap_timer, auto_reconnect=False, auto_start=None, auto_exit=False):
        super().__init__(tap_timer)
        self.auto_reconnect = auto_reconnect
        self.auto_start = auto_start
        self.auto_exit = auto_exit

    def connect_failed(self, error):
        super().connect_failed(error)
        tap_timer_manager.stop()
        sys.exit(0)

    def disconnect_succeeded(self):
        super().disconnect_succeeded()

        if self.auto_reconnect:
            # Reconnect as soon as Holman was disconnected
            print("Disconnected, reconnecting...")
            self.tap_timer.connect()
        else:
            tap_timer_manager.stop()
            sys.exit(0)

    def connect_succeeded(self):
        super().connect_succeeded()
        if self.auto_start is not None:
            if self.auto_start == 0:
                self.tap_timer.stop()
            else:
                self.tap_timer.start(self.auto_start)
            self.auto_start = None

    def timer_written(self):
        super().timer_written()
        if self.auto_exit:
            self.print('exiting')
            tap_timer_manager.stop()


class TapTimerManagerPrintListener(holman.TapTimerManagerListener):
    def tap_timer_discovered(self, tap_timer):
        print("Discovered Holman tap timer", tap_timer.mac_address)


def main():
    arg_parser = ArgumentParser(description="Holman Tap Timer Control Daemon")
    arg_parser.add_argument(
        '--adapter',
        default='hci0',
        help="Name of Bluetooth adapter, defaults to 'hci0'")
    arg_parser.add_argument(
        '--socket',
        default='/run/holman.sock',
        help="Path to control socket, defaults to '/run/holman.sock'")
    args = arg_parser.parse_args()

    global tap_timer_manager
    tap_timer_manager = holman.TapTimerManager(adapter_name=args.adapter)
    manager_thread = Thread(target = tap_timer_manager.run, daemon = True)

    tap_timers = {}

    try:
        os.unlink(args.socket)
    except IOError:
        pass

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(args.socket)

    try:
        manager_thread.start()

        while True:
            message, address = sock.recvfrom(4096)
            try:
                data = json.loads(message.decode('utf-8'))
                print(data)

                mac = data['mac']
                tap_timer = tap_timers.get(mac)

                if tap_timer is None:
                    tap_timer = holman.TapTimer(mac_address=mac, manager=tap_timer_manager)
                    tap_timer.listener = TapTimerTestListener(tap_timer=tap_timer)
                    tap_timers[mac] = tap_timer
                    tap_timer.connect()

                if not tap_timer.is_connected():
                    tap_timer.connect()

                tap_timer.start(data['runtime'])

            except KeyboardInterrupt:
                break

            except Exception as e:
                raise e

    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
