import unittest


class RecentInferenceFpsTests(unittest.TestCase):
    def test_startup_wait_is_excluded_and_ten_results_replace_old_history(self):
        from vision_app.recent_fps import RecentFps
        rate=RecentFps()
        rate.add(100)
        self.assertEqual(rate.value(),0)
        for i in range(1,11):rate.add(100+i*.5)
        self.assertAlmostEqual(rate.value(),2.)
        for i in range(1,11):rate.add(105+i*.25)
        self.assertAlmostEqual(rate.value(),4.)
        self.assertEqual(rate.samples,10)

    def test_fps_uses_total_elapsed_not_average_of_instantaneous_rates(self):
        from vision_app.recent_fps import RecentFps
        rate=RecentFps()
        for stamp in (10.,10.1,10.5):rate.add(stamp)
        self.assertEqual(rate.value(),0.)
        for stamp in (10.75,11.,11.25,11.5,11.75,12.,12.25,12.5):rate.add(stamp)
        self.assertAlmostEqual(rate.value(),4.)
        rate.clear()
        self.assertEqual(rate.samples,0)
        self.assertEqual(rate.value(),0)
        rate.add(200.)
        self.assertEqual(rate.value(),0)

    def test_board_status_does_not_divide_by_startup_or_idle_time(self):
        import threading,time
        from types import SimpleNamespace
        from vision_app.board_agent import Agent
        from vision_app.recent_fps import RecentFps
        rate=RecentFps()
        for i in range(11):rate.add(100+i*.25)
        agent=Agent.__new__(Agent)
        agent.contract={'contract_id':'test'}
        agent.lock=threading.RLock();agent.camera=SimpleNamespace(started=time.monotonic(),frames=0,gaps=0,error=None,width=1280,height=720,fps=30)
        agent.queries=SimpleNamespace(get=lambda:None);agent.cpu=SimpleNamespace(status=lambda:{'current_khz':1200000})
        agent.r5=None;agent.r5_error=None;agent.performance={};agent.first_result_at=100;agent.last_result_at=102.25
        agent.inference_count=11;agent.inference_started=1;agent.inference_state='RUNNING';agent.inference_error=None
        agent.max_in_flight=4;agent.config={};agent.threshold=.17;agent.delivery_drops=0;agent.serial_metrics={}
        agent.recent_fps=rate
        self.assertAlmostEqual(agent.status()['inference']['fps'],4.)
