"""
TCP Command Server for freedvtnc2-lfm

Provides runtime control of the modem via ASCII commands on port 8002.
See PROTOCOL.md for full specification.
"""

import socket
import threading
import logging
from typing import Optional, Callable
import argparse

logger = logging.getLogger(__name__)


class CommandServer:
    """
    TCP server that accepts ASCII commands to control the modem.

    Commands: MODE, VOLUME, FOLLOW, STATUS, LEVELS, PTT TEST, CLEAR, SAVE, PING
    """

    def __init__(
        self,
        modem_tx,
        output_device,
        input_device,
        options: argparse.Namespace,
        port: int = 8002,
        address: str = "0.0.0.0"
    ):
        self.modem_tx = modem_tx
        self.output_device = output_device
        self.input_device = input_device
        self.options = options
        self.port = port
        self.address = address
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

        # Valid modes (imported from modem module)
        from .modem import Modems
        self.valid_modes = [m.name for m in Modems]

    def start(self):
        """Start the command server in a background thread."""
        if self.running:
            logger.warning("CommandServer already running")
            return

        self.running = True
        self._thread = threading.Thread(target=self._server_loop, daemon=True)
        self._thread.start()
        logger.info(f"CommandServer started on {self.address}:{self.port}")

    def stop(self):
        """Stop the command server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("CommandServer stopped")

    def _server_loop(self):
        """Main server loop - accepts connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.address, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Allow periodic check of self.running

            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    logger.debug(f"CommandServer connection from {addr}")
                    handler = threading.Thread(
                        target=self._handle_connection,
                        args=(conn, addr),
                        daemon=True
                    )
                    handler.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"CommandServer accept error: {e}")
        except Exception as e:
            logger.error(f"CommandServer error: {e}")
        finally:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass

    def _handle_connection(self, conn: socket.socket, addr):
        """Handle a single client connection."""
        conn.settimeout(None)  # No timeout for client connections
        buffer = ""

        try:
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break

                buffer += data.decode('utf-8', errors='ignore')

                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        response = self._process_command(line)
                        conn.send(f"{response}\n".encode('utf-8'))
        except Exception as e:
            logger.debug(f"CommandServer connection error: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
            logger.debug(f"CommandServer connection closed from {addr}")

    def _process_command(self, command: str) -> str:
        """Process a single command and return response."""
        parts = command.upper().split(None, 1)  # Split on whitespace, max 2 parts
        if not parts:
            return "ERROR Empty command"

        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        try:
            if cmd == "PING":
                return "OK PONG"

            elif cmd == "MODE":
                return self._cmd_mode(arg)

            elif cmd == "VOLUME":
                return self._cmd_volume(arg)

            elif cmd == "FOLLOW":
                return self._cmd_follow(arg)

            elif cmd == "STATUS":
                return self._cmd_status()

            elif cmd == "LEVELS":
                return self._cmd_levels()

            elif cmd == "PTT":
                if arg == "TEST":
                    return self._cmd_ptt_test()
                return "ERROR Unknown PTT command. Use: PTT TEST"

            elif cmd == "CLEAR":
                return self._cmd_clear()

            elif cmd == "SAVE":
                return self._cmd_save()

            else:
                return f"ERROR Unknown command: {cmd}"

        except Exception as e:
            logger.error(f"CommandServer error processing '{command}': {e}")
            return f"ERROR {str(e)}"

    def _cmd_mode(self, arg: str) -> str:
        """Handle MODE command."""
        if not arg:
            # Query current mode
            return f"OK MODE {self.modem_tx.modem.modem_name}"

        mode = arg.upper()
        if mode not in self.valid_modes:
            return f"ERROR Invalid mode. Valid: {', '.join(self.valid_modes)}"

        self.modem_tx.set_mode(mode)
        self.options.mode = mode
        logger.info(f"Mode changed to {mode}")
        return f"OK MODE {mode}"

    def _cmd_volume(self, arg: str) -> str:
        """Handle VOLUME command."""
        if not arg:
            # Query current volume
            return f"OK VOLUME {self.options.output_volume}"

        try:
            volume = float(arg)
            self.output_device.db = volume
            self.options.output_volume = volume
            logger.info(f"Volume changed to {volume} dB")
            return f"OK VOLUME {volume}"
        except ValueError:
            return "ERROR Invalid volume (must be number in dB)"

    def _cmd_follow(self, arg: str) -> str:
        """Handle FOLLOW command."""
        if not arg:
            # Query current follow state
            state = "ON" if self.options.follow else "OFF"
            return f"OK FOLLOW {state}"

        arg = arg.upper()
        if arg == "ON":
            self.options.follow = True
            logger.info("Follow mode enabled")
            return "OK FOLLOW ON"
        elif arg == "OFF":
            self.options.follow = False
            logger.info("Follow mode disabled")
            return "OK FOLLOW OFF"
        else:
            return "ERROR Invalid follow state. Use: ON or OFF"

    def _cmd_status(self) -> str:
        """Handle STATUS command."""
        mode = self.modem_tx.modem.modem_name
        volume = self.options.output_volume
        follow = "ON" if self.options.follow else "OFF"
        ptt = "ON" if getattr(self.output_device, 'ptt', False) else "OFF"
        channel = "BUSY" if getattr(self.output_device, 'inhibit', False) else "CLEAR"

        return f"OK STATUS MODE={mode} VOLUME={volume} FOLLOW={follow} PTT={ptt} CHANNEL={channel}"

    def _cmd_levels(self) -> str:
        """Handle LEVELS command."""
        try:
            rx_level = self.input_device.input_level
            return f"OK LEVELS RX={rx_level:.1f}"
        except Exception as e:
            return f"ERROR Could not read levels: {e}"

    def _cmd_ptt_test(self) -> str:
        """Handle PTT TEST command."""
        try:
            import pydub.generators

            sin_wave = pydub.generators.Sine(
                440,
                sample_rate=self.modem_tx.modem.sample_rate,
                bit_depth=16,
            ).to_audio_segment(2000, volume=-6)
            sin_wave.set_channels(1)

            self.output_device.write_raw(sin_wave.raw_data)
            logger.info("PTT test triggered")
            return "OK PTT TEST started"
        except Exception as e:
            return f"ERROR PTT test failed: {e}"

    def _cmd_clear(self) -> str:
        """Handle CLEAR command."""
        try:
            self.output_device.clear()
            with self.output_device.send_queue_lock:
                self.output_device.send_queue = []
            logger.info("TX buffer cleared")
            return "OK CLEAR"
        except Exception as e:
            return f"ERROR Clear failed: {e}"

    def _cmd_save(self) -> str:
        """Handle SAVE command."""
        try:
            from pathlib import Path
            import configargparse

            path = str(Path.home() / ".freedvtnc2.conf")
            with open(path, "w") as f:
                f.write(
                    configargparse.DefaultConfigFileParser().serialize({
                        key.replace("_", "-"): str(value) if value is not None else ""
                        for key, value in vars(self.options).items()
                        if key != "c"
                    })
                )
            logger.info(f"Config saved to {path}")
            return f"OK SAVE {path}"
        except Exception as e:
            return f"ERROR Save failed: {e}"
