"""Hand-authored score timelines catch false splitting and false joining."""
import unittest
from vision_app.semantic_media import build_segments


def rows(scores, step=.1):
    return [dict(frame_id=i, time_s=round(i*step, 6),
                 ranking=[dict(id='0', label='杯子', score=s)])
            for i, s in enumerate(scores)]


class Continuity(unittest.TestCase):
    def test_small_dip_keeps_one_interval_and_only_strong_frame_ids(self):
        data=rows([.24]*8+[.15]*3+[.24]*8)
        result=build_segments(data,.2,padding_s=0)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['frame_ids'],list(range(8))+list(range(11,19)))
        self.assertEqual(result[0]['start_s'],0)
        self.assertAlmostEqual(result[0]['end_s'],1.8)

    def test_real_absence_splits_and_does_not_include_waiting_tail(self):
        result=build_segments(rows([.24]*8+[.1]*15+[.24]*8),.2,padding_s=0)
        self.assertEqual(len(result),2)
        self.assertAlmostEqual(result[0]['end_s'],.7)
        self.assertAlmostEqual(result[1]['start_s'],2.3)

    def test_weak_continuation_cannot_extend_forever(self):
        result=build_segments(rows([.24]*8+[.19]*35),.2,padding_s=0)
        self.assertEqual(len(result),1)
        self.assertLessEqual(result[0]['end_s'],.7)

    def test_isolated_spike_is_candidate_not_exportable_segment(self):
        from vision_app.temporal_segments import segment_report
        result=segment_report(rows([.1]*5+[.28]+[.1]*10),.2,padding_s=0)
        self.assertEqual(result['segments'],[])
        self.assertEqual(result['candidates'][0]['frame_ids'],[5])

    def test_user_threshold_changes_enter_and_internal_continue(self):
        data=rows([.22]*8+[.19]*4+[.22]*8)
        self.assertEqual(len(build_segments(data,.2)),1)
        self.assertEqual(build_segments(data,.25),[])

    def test_missing_results_are_not_bridged_as_negative_scores(self):
        data=rows([.24]*8)+[dict(frame_id=8,time_s=.8,ranking=[])]+rows([.24]*8)
        for i,row in enumerate(data[9:]):row.update(frame_id=i+9,time_s=round(i*.1+.9,6))
        self.assertEqual(len(build_segments(data,.2,padding_s=0)),2)

    def test_four_fps_uses_seconds_instead_of_video_frame_count(self):
        data=rows([.24]*4+[.1]*2+[.24]*4,step=.25)
        self.assertEqual(len(build_segments(data,.2,padding_s=0)),1)

    def test_all_descriptions_keep_their_own_state(self):
        data=rows([.24]*20)
        for i,row in enumerate(data):
            row['ranking'].append(dict(id='1',label='有人',score=.26 if i>=10 else .1))
        result=build_segments(data,.2,padding_s=0)
        self.assertEqual([(x['label'],x['start_s']) for x in result],[('杯子',0),('有人',1.)])

    def test_incremental_and_batch_have_identical_boundaries(self):
        from vision_app.temporal_segments import SegmentTracker,segment_report
        data=rows([.24]*8+[.15]*3+[.24]*8+[.1]*10+[.3])
        tracker=SegmentTracker(.2)
        for row in data:tracker.add(row)
        self.assertEqual(tracker.report(duration=3.),segment_report(data,.2,duration=3.))

    def test_disabled_optimization_preserves_original_single_frame_hits(self):
        result=build_segments(rows([.1,.3,.1]),.2,continuity=False)
        self.assertEqual(result[0]['frame_ids'],[1])

