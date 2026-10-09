import unittest

class SemanticMediaContract(unittest.TestCase):
    def test_segments_keep_nonmatches_as_breaks_and_use_source_time(self):
        from vision_app.semantic_media import build_segments
        rows=[{'frame_id':i,'time_s':t,'ranking':[{'id':'0','label':'杯子','score':s}]} for i,(t,s) in enumerate([(0,.3),(.2,.4),(.4,.1),(.6,.5),(4,.6)])]
        result=build_segments(rows,.25,gap_s=1,padding_s=.1,duration=5)
        self.assertEqual(len(result),3)
        self.assertEqual([x['frame_ids'] for x in result],[[0,1],[3],[4]])
        self.assertEqual(result[0]['start_s'],0)
        self.assertAlmostEqual(result[0]['end_s'],.3)
    def test_each_description_has_its_own_interval(self):
        from vision_app.semantic_media import build_segments
        rows=[{'frame_id':0,'time_s':2,'ranking':[{'id':'0','label':'杯子','score':.4},{'id':'1','label':'有人','score':.5}]}]
        result=build_segments(rows,.25,duration=3)
        self.assertEqual({r['label'] for r in result},{'杯子','有人'})
