"""No windows or BLE: virtual time and in-memory rendering only."""
import heapq
import unittest
from unittest.mock import Mock
from mr3_overlay import VolumeOverlay, render_overlay, overlay_position


class Scheduler:
    def __init__(self):
        self.time = 0.0
        self.queue = []
        self.pending = {}
        self.counter = 0
    def bind(self,*args,**kwargs): pass
    def after(self,ms,callback):
        self.counter += 1
        token = self.counter
        self.pending[token] = callback
        heapq.heappush(self.queue,(self.time+ms/1000,token))
        return token
    def after_cancel(self,token): self.pending.pop(token,None)
    def advance(self,seconds):
        end = self.time+seconds
        while self.queue and self.queue[0][0] <= end:
            self.time,token = heapq.heappop(self.queue)
            callback = self.pending.pop(token,None)
            if callback: callback()
        self.time = end


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.root = Scheduler()
        self.surface = Mock(work_area=lambda:(-1920,0,0,1040))
        self.overlay = VolumeOverlay(self.root,lambda:self.surface,lambda:self.root.time)

    def test_first_notification_has_true_volume_and_stops_scheduling(self):
        self.overlay.show(13)
        self.assertEqual(self.overlay.level,13)
        self.root.advance(.2)
        self.assertEqual(self.overlay.opacity,1)
        self.assertEqual(len(self.root.pending),1)  # Only expiry; no animation loop while static.
        self.root.advance(2)
        self.assertFalse(self.overlay.visible)
        self.assertEqual(self.root.pending,{})

    def test_new_value_extends_expiry_and_overrides_fade(self):
        self.overlay.show(13)
        self.root.advance(2.05)
        self.assertGreater(self.overlay.opacity,0)
        self.assertLess(self.overlay.opacity,1)
        self.overlay.show(20)
        self.root.advance(.2)
        self.assertEqual((self.overlay.value,self.overlay.level,self.overlay.opacity),(20,20,1))
        self.root.advance(1.6)
        self.assertTrue(self.overlay.visible)
        self.root.advance(.5)
        self.assertFalse(self.overlay.visible)
        self.assertEqual(self.root.pending,{})

    def test_hide_and_close_cancel_every_callback(self):
        self.overlay.show(0)
        self.overlay.hide()
        self.assertEqual(self.root.pending,{})
        self.overlay.show(30)
        self.overlay.close()
        self.root.advance(5)
        self.surface.close.assert_called_once()
        self.assertEqual(self.root.pending,{})
        self.overlay.show(12)
        self.assertFalse(self.overlay.visible)

    def test_failed_native_creation_does_not_leave_timers(self):
        self.overlay.factory = Mock(side_effect=OSError('simulated allocation failure'))
        with self.assertLogs(level='ERROR'):
            self.overlay.show(13)
        self.assertFalse(self.overlay.visible)
        self.assertEqual(self.root.pending,{})

    def test_failed_paint_does_not_schedule_expiry_or_keep_visible_state(self):
        self.surface.paint.side_effect = OSError('simulated GDI failure')
        with self.assertLogs(level='ERROR'):
            self.overlay.show(13)
        self.assertFalse(self.overlay.visible)
        self.assertEqual(self.root.pending,{})

    def test_monitor_placement_respects_negative_coordinates_and_taskbar(self):
        x,y = overlay_position((-1920,0,0,1040),(356,88),1)
        self.assertEqual(x,-1138)
        self.assertEqual(y+88,1022)

    def test_rgba_rendering_has_transparent_corners_and_valid_native_bytes(self):
        for scale in (1,1.5,2):
            for value in (0,13,30):
                image = render_overlay(value,scale=scale)
                self.assertEqual(image.size,(round(356*scale),round(88*scale)))
                self.assertEqual(image.getpixel((0,0))[3],0)
                self.assertGreater(image.getpixel((round(170*scale),round(30*scale)))[3],240)
                self.assertEqual(len(image.convert('RGBa').tobytes('raw','BGRa')),image.width*image.height*4)


if __name__ == '__main__': unittest.main()
