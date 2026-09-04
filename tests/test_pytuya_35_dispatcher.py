import asyncio
import unittest

from custom_components.localtuya import pytuya


class TestTuya35Dispatcher(unittest.TestCase):
    KEY = b"0123456789abcdef"
    IV1 = b"abcdefghijkl"
    IV2 = b"mnopqrstuvwx"

    @staticmethod
    def _dispatcher(version, key, received):
        return pytuya.MessageDispatcher(
            "test-device-123456",
            received.append,
            version,
            key,
            False,
        )

    def _6699_status_frame(self, seqno, iv, state):
        payload = (
            b'{"dps":{"1":'
            + (b"true" if state else b"false")
            + b"}}"
        )

        msg = pytuya.TuyaMessage(
            seqno,
            pytuya.STATUS,
            0,
            payload,
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            iv,
        )

        return pytuya.pack_message(
            msg,
            hmac_key=self.KEY,
        )

    def test_6699_fragmented_frame_waits_for_complete_packet(self):
        received = []
        dispatcher = self._dispatcher(
            3.5,
            self.KEY,
            received,
        )

        frame = self._6699_status_frame(
            10,
            self.IV1,
            True,
        )

        split = 23

        dispatcher.add_data(frame[:split])

        self.assertEqual(received, [])
        self.assertEqual(
            dispatcher.buffer,
            frame[:split],
        )

        dispatcher.add_data(frame[split:])

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].seqno, 10)
        self.assertEqual(received[0].cmd, pytuya.STATUS)
        self.assertEqual(
            received[0].payload,
            b'{"dps":{"1":true}}',
        )
        self.assertEqual(dispatcher.buffer, b"")

    def test_6699_frame_split_across_many_tcp_chunks(self):
        received = []
        dispatcher = self._dispatcher(
            3.5,
            self.KEY,
            received,
        )

        frame = self._6699_status_frame(
            15,
            self.IV1,
            True,
        )

        chunks = (
            frame[:2],
            frame[2:7],
            frame[7:19],
            frame[19:31],
            frame[31:47],
            frame[47:],
        )

        for chunk in chunks[:-1]:
            dispatcher.add_data(chunk)
            self.assertEqual(received, [])

        dispatcher.add_data(chunks[-1])

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].seqno, 15)
        self.assertEqual(
            received[0].payload,
            b'{"dps":{"1":true}}',
        )
        self.assertEqual(dispatcher.buffer, b"")

    def test_6699_multiple_frames_in_single_tcp_chunk(self):
        received = []
        dispatcher = self._dispatcher(
            3.5,
            self.KEY,
            received,
        )

        frame1 = self._6699_status_frame(
            20,
            self.IV1,
            True,
        )
        frame2 = self._6699_status_frame(
            21,
            self.IV2,
            False,
        )

        dispatcher.add_data(frame1 + frame2)

        self.assertEqual(
            [msg.seqno for msg in received],
            [20, 21],
        )
        self.assertEqual(
            received[0].payload,
            b'{"dps":{"1":true}}',
        )
        self.assertEqual(
            received[1].payload,
            b'{"dps":{"1":false}}',
        )
        self.assertEqual(dispatcher.buffer, b"")

    def test_55aa_fragmented_frame_still_works(self):
        received = []
        dispatcher = self._dispatcher(
            3.3,
            self.KEY,
            received,
        )

        # A received 55AA frame contains a four-byte
        # return code before the actual payload.
        msg = pytuya.TuyaMessage(
            30,
            pytuya.STATUS,
            0,
            b"\x00\x00\x00\x00"
            b'{"dps":{"1":true}}',
            0,
            True,
        )

        frame = pytuya.pack_message(msg)

        split = 12

        dispatcher.add_data(frame[:split])

        self.assertEqual(received, [])

        dispatcher.add_data(frame[split:])

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].seqno, 30)
        self.assertEqual(
            received[0].payload,
            b'{"dps":{"1":true}}',
        )
        self.assertEqual(dispatcher.buffer, b"")


if __name__ == "__main__":
    unittest.main()


class TestTuya35GlobalSequence(unittest.IsolatedAsyncioTestCase):
    KEY = b"0123456789abcdef"

    @staticmethod
    def _dispatcher():
        return pytuya.MessageDispatcher(
            "test-device-123456",
            lambda msg: None,
            3.5,
            TestTuya35GlobalSequence.KEY,
            False,
        )

    async def test_35_response_can_use_different_seqno(self):
        dispatcher = self._dispatcher()

        waiter = asyncio.create_task(
            dispatcher.wait_for(
                10,
                pytuya.DP_QUERY_NEW,
                timeout=0.05,
            )
        )

        # Allow wait_for() to register its listener.
        await asyncio.sleep(0)

        response = pytuya.TuyaMessage(
            700,
            pytuya.DP_QUERY_NEW,
            0,
            b'{"dps":{"1":true}}',
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            b"abcdefghijkl",
        )

        dispatcher._dispatch(response)

        result = await waiter

        self.assertIs(result, response)

    async def test_35_single_waiter_can_accept_different_response_command(self):
        dispatcher = self._dispatcher()

        waiter = asyncio.create_task(
            dispatcher.wait_for(
                20,
                pytuya.DP_QUERY_NEW,
                timeout=0.05,
            )
        )

        await asyncio.sleep(0)

        # Some devices answer a query with STATUS while also
        # using their own global sequence counter.
        response = pytuya.TuyaMessage(
            701,
            pytuya.STATUS,
            0,
            b'{"dps":{"1":false}}',
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            b"abcdefghijkl",
        )

        dispatcher._dispatch(response)

        result = await waiter

        self.assertIs(result, response)

    async def test_35_does_not_guess_between_multiple_waiters(self):
        dispatcher = self._dispatcher()

        waiter1 = asyncio.create_task(
            dispatcher.wait_for(
                30,
                pytuya.DP_QUERY_NEW,
                timeout=0.05,
            )
        )
        waiter2 = asyncio.create_task(
            dispatcher.wait_for(
                31,
                pytuya.CONTROL_NEW,
                timeout=0.05,
            )
        )

        await asyncio.sleep(0)

        response = pytuya.TuyaMessage(
            702,
            pytuya.STATUS,
            0,
            b'{"dps":{"1":true}}',
            0,
            True,
            pytuya.PREFIX_6699_VALUE,
            b"abcdefghijkl",
        )

        dispatcher._dispatch(response)

        self.assertIsInstance(
            dispatcher.listeners[30],
            asyncio.Semaphore,
        )
        self.assertIsInstance(
            dispatcher.listeners[31],
            asyncio.Semaphore,
        )

        waiter1.cancel()
        waiter2.cancel()

        for waiter in (waiter1, waiter2):
            try:
                await waiter
            except asyncio.CancelledError:
                pass
