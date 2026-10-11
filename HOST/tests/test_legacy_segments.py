import unittest
from vision_app.semantic_media import build_segments

class LegacySegments(unittest.TestCase):
    def test_disabled_mode_preserves_negative_breaks_and_padding(self):
        rows=[dict(frame_id=i,time_s=t,ranking=[dict(id='0',label='杯子',score=s)]) for i,(t,s) in enumerate([(0,.3),(.2,.4),(.4,.1),(.6,.5),(4,.6)])]
        result=build_segments(rows,.25,gap_s=1,padding_s=.1,duration=5,continuity=False)
        self.assertEqual([x['frame_ids'] for x in result],[[0,1],[3],[4]])
        self.assertAlmostEqual(result[0]['end_s'],.3)
    def test_disabled_mode_keeps_simultaneous_descriptions(self):
        result=build_segments([dict(frame_id=0,time_s=2,ranking=[dict(id='0',label='杯子',score=.4),dict(id='1',label='有人',score=.5)])],.25,duration=3,continuity=False)
        self.assertEqual({r['label'] for r in result},{'杯子','有人'})
