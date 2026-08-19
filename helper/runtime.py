"""Shepherd runtime: one-shot RPC plus a dedicated subscribe reader."""

import sys
import time
from threading import Event, Lock, Thread

from helper.events import build_subscriptions, pane_ids_from_snapshot
from helper.ipc import HelperIPC
from helper.normalize import Normalizer
from helper.protocol import ProtocolError, is_invalidation_push
from helper.rpc import RpcClient, RpcDisconnected, RpcError, RpcTimeout
from helper.socket_path import resolve_socket_path
from helper.subscribe import SubscribeError, SubscribeSession


def _diag(message):
    sys.stderr.write("Helper: %s\n" % message)
    sys.stderr.flush()


class Helper:
    def __init__(
        self,
        socket_path=None,
        debounce_s=0.1,
        recv_timeout=0.2,
        rpc_timeout=5.0,
        backoff_initial=1.0,
        backoff_max=30.0,
        infile=None,
        outfile=None,
        rpc_client=None,
        subscribe_session=None,
    ):
        self.socket_path = socket_path or resolve_socket_path()
        self.debounce_s = debounce_s
        self.recv_timeout = recv_timeout
        self.rpc_timeout = rpc_timeout
        self.backoff_initial = backoff_initial
        self.backoff_max = backoff_max
        self.rpc = rpc_client or RpcClient(self.socket_path, recv_timeout=recv_timeout, rpc_timeout=rpc_timeout)
        self.subscribe = subscribe_session or SubscribeSession(
            self.socket_path, recv_timeout=recv_timeout, ack_timeout=rpc_timeout
        )
        self.normalizer = Normalizer()
        self.ipc = HelperIPC(self, infile=infile, outfile=outfile)
        self.stop_event = Event()
        self.generation = 0
        self.connected = False
        self.last_state = None
        self.last_pane_ids = ()
        self._reader_thread = None
        self._debounce_thread = None
        self._debounce_lock = Lock()
        self._debounce_deadline = None
        self._rebuild_subscribe = False
        self._reader_alive = Event()
        self._thread_errors = []
        self.reconnect_backoff = backoff_initial

    @property
    def running(self):
        return not self.stop_event.is_set()

    def run(self):
        self.stop_event.clear()
        self.ipc.start()
        try:
            while self.running:
                try:
                    self._session_loop()
                except (OSError, RpcDisconnected, RpcTimeout, RpcError, SubscribeError, ProtocolError) as exc:
                    _diag("session ended")
                    self._on_session_failure()
                    self._interruptible_backoff()
                    continue
                except Exception:
                    _diag("session error")
                    self._on_session_failure()
                    self._interruptible_backoff()
                    continue
                if self.running:
                    self._on_session_failure()
                    self._interruptible_backoff()
        finally:
            self._shutdown_session()
            self.ipc.stop()
            self.ipc.join()

    def stop(self):
        self.stop_event.set()
        self.subscribe.close()

    def focus_agent(self, pane_id):
        return self.rpc.agent_focus(pane_id)

    def refresh_snapshot(self, reason="invalidation"):
        generation = self.generation
        if self.stop_event.is_set():
            return None
        snapshot = self.rpc.snapshot()
        if self.stop_event.is_set() or generation != self.generation:
            return None
        state = self.normalizer.normalize_snapshot(snapshot)
        self.last_state = state
        self.connected = True
        self.reconnect_backoff = self.backoff_initial
        self.ipc.send_state(state, connection="connected", stale=False)
        pane_ids = pane_ids_from_snapshot(snapshot)
        if pane_ids != self.last_pane_ids and reason != "bootstrap":
            self.last_pane_ids = pane_ids
            self._rebuild_subscribe = True
            self.subscribe.close()
        else:
            self.last_pane_ids = pane_ids
        return snapshot

    def note_connection_lost(self):
        self.connected = False
        if self.last_state:
            self.ipc.send_state(self.last_state, connection="disconnected", stale=True)

    def schedule_invalidation(self):
        if self.stop_event.is_set():
            return
        with self._debounce_lock:
            self._debounce_deadline = time.monotonic() + self.debounce_s
            if self._debounce_thread is not None and self._debounce_thread.is_alive():
                return
            thread = Thread(target=self._debounce_loop, name="shepherd-debounce", daemon=False)
            self._debounce_thread = thread
            thread.start()

    def _session_loop(self):
        self.generation += 1
        self._rebuild_subscribe = False
        snapshot = self.refresh_snapshot(reason="bootstrap")
        if snapshot is None:
            raise RpcDisconnected("bootstrap snapshot failed")
        self._open_subscribe(self.last_pane_ids)
        self._run_reader()
        while self.running and self._rebuild_subscribe:
            self._rebuild_subscribe = False
            self._join_reader()
            if not self.running:
                return
            self._open_subscribe(self.last_pane_ids)
            self._run_reader()

    def _open_subscribe(self, pane_ids):
        subscriptions = build_subscriptions(pane_ids)
        self.subscribe.open(subscriptions)

    def _run_reader(self):
        self._reader_alive.set()
        thread = Thread(target=self._reader_loop, name="shepherd-subscribe", daemon=False)
        self._reader_thread = thread
        thread.start()
        thread.join()
        self._reader_thread = None

    def _join_reader(self):
        thread = self._reader_thread
        if thread is not None:
            thread.join(timeout=2.0)

    def _reader_loop(self):
        try:
            while self.running and not self._rebuild_subscribe:
                classified_list = self.subscribe.recv_classified()
                if classified_list is None:
                    continue
                if classified_list == "EOF":
                    return
                for classified in classified_list:
                    self._handle_subscribe_message(classified)
        except ProtocolError:
            _diag("invalid subscribe frame")
            return
        except Exception as exc:
            self._thread_errors.append(exc)
            _diag("subscribe reader error")
            return
        finally:
            self._reader_alive.clear()

    def _handle_subscribe_message(self, classified):
        kind = classified.get("kind")
        if is_invalidation_push(classified):
            self.schedule_invalidation()
            return
        if kind == "unknown":
            _diag("unrecognized subscribe frame")
            return
        _diag("unexpected subscribe envelope")

    def _debounce_loop(self):
        try:
            while self.running:
                with self._debounce_lock:
                    deadline = self._debounce_deadline
                if deadline is None:
                    return
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    self.stop_event.wait(timeout=remaining)
                    continue
                with self._debounce_lock:
                    if time.monotonic() < (self._debounce_deadline or 0):
                        continue
                    self._debounce_deadline = None
                if self.stop_event.is_set():
                    return
                generation = self.generation
                try:
                    self.refresh_snapshot(reason="debounce")
                except (OSError, RpcDisconnected, RpcTimeout, RpcError, ProtocolError):
                    _diag("debounced snapshot failed")
                    self.subscribe.close()
                    return
                if generation != self.generation:
                    return
                return
        except Exception as exc:
            self._thread_errors.append(exc)

    def _on_session_failure(self):
        self.connected = False
        self.generation += 1
        self.subscribe.close()
        if self.last_state:
            self.ipc.send_state(self.last_state, connection="disconnected", stale=True)
        else:
            self.ipc.send_state({"agents": [], "counts": {"total": 0}}, connection="disconnected", stale=True)

    def _interruptible_backoff(self):
        delay = self.reconnect_backoff
        self.reconnect_backoff = min(self.reconnect_backoff * 2, self.backoff_max)
        self.stop_event.wait(timeout=delay)

    def _shutdown_session(self):
        self.subscribe.close()
        self._join_reader()
        thread = self._debounce_thread
        if thread is not None:
            thread.join(timeout=2.0)
