#!/usr/bin/env python3

import sys
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
    arg_parser = ArgumentParser(description="Holman Tap Timer Demo")
    arg_parser.add_argument(
        '--adapter',
        default='hci0',
        help="Name of Bluetooth adapter, defaults to 'hci0'")
    arg_commands_group = arg_parser.add_mutually_exclusive_group(required=True)
    arg_commands_group.add_argument(
        '--discover',
        action='store_true',
        help="Lists all nearby Holman tap timers")
    arg_commands_group.add_argument(
        '--known',
        action='store_true',
        help="Lists all known Holman tap timers")
    arg_commands_group.add_argument(
        '--connect',
        metavar='address',
        type=str,
        help="Connect to a Holman tap timer with a given MAC address")
    arg_commands_group.add_argument(
        '--auto',
        metavar='address',
        type=str,
        help="Connect and automatically reconnect to a Holman tap timer with a given MAC address")
    arg_commands_group.add_argument(
        '--disconnect',
        metavar='address',
        type=str,
        help="Disconnect a Holman tap timer with a given MAC address")

    arg_run_group = arg_parser.add_mutually_exclusive_group(required=False)
    arg_run_group.add_argument(
        '--run',
        default=None,
        metavar='MINUTES',
        type=int,
        help="Run the timer for the specified number of minutes")
    arg_run_group.add_argument(
        '--stop',
        action='store_const',
        const=True,
        default=False,
        help="Stop the timer")
    args = arg_parser.parse_args()

    global tap_timer_manager
    tap_timer_manager = holman.TapTimerManager(adapter_name=args.adapter)

    if args.run is not None and not (args.connect or args.auto):
        arg_parser.error('--run can only be used with --auto or --connect.')
        return

    if args.stop is not None and not (args.connect or args.auto):
        arg_parser.error('--run can only be used with --auto or --connect.')
        return

    run_time = 0 if args.stop else args.run
    auto_exit = run_time is not None

    if args.discover:
        tap_timer_manager.listener = TapTimerManagerPrintListener()
        tap_timer_manager.start_discovery()
    if args.known:
        for tap_timer in tap_timer_manager.tap_timers():
            print("[%s] %s" % (tap_timer.mac_address, tap_timer.alias()))
        return
    elif args.connect:
        tap_timer = holman.TapTimer(mac_address=args.connect, manager=tap_timer_manager)
        tap_timer.listener = TapTimerTestListener(tap_timer=tap_timer, auto_start=run_time, auto_exit=auto_exit)
        tap_timer.connect()
    elif args.auto:
        tap_timer = holman.TapTimer(mac_address=args.auto, manager=tap_timer_manager)
        tap_timer.listener = TapTimerTestListener(tap_timer=tap_timer, auto_reconnect=True, auto_start=run_time, auto_exit=auto_exit)
        tap_timer.connect()
    elif args.disconnect:
        tap_timer = holman.TapTimer(mac_address=args.disconnect, manager=tap_timer_manager)
        tap_timer.disconnect()
        return

    if not auto_exit:
        print("Terminate with Ctrl+C")
    try:
        tap_timer_manager.run()
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
