from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
import av
from PIL import Image
from vision_app.semantic_media import export_segments


class GroupedExport(unittest.TestCase):
    def test_same_description_is_one_video_with_source_interval_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'input.mp4'
            with av.open(str(source),'w') as c:
                stream=c.add_stream('mpeg4',rate=4);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
                for i in range(12):
                    frame=av.VideoFrame.from_image(Image.new('RGB',(64,64),'blue' if 4<=i<8 else 'red'))
                    frame.pts=i;frame.time_base=Fraction(1,4)
                    for packet in stream.encode(frame):c.mux(packet)
                for packet in stream.encode():c.mux(packet)
            segments=[dict(query_id='0',label='红色',start_s=0.,end_s=.75,frame_ids=[0],best_score=.3),
                      dict(query_id='1',label='蓝色',start_s=1.,end_s=1.75,frame_ids=[4],best_score=.4),
                      dict(query_id='0',label='红色',start_s=2.,end_s=2.75,frame_ids=[8],best_score=.5)]
            result=export_segments(source,segments,Path(d)/'clips',group_by_query=True)
            self.assertEqual(len(result),2)
            red=next(x for x in result if x['query_id']=='0')
            self.assertEqual([(p['source_start_s'],p['source_end_s']) for p in red['source_intervals']],[(0.,.75),(2.,2.75)])
            self.assertAlmostEqual(red['source_intervals'][1]['output_start_s'],.75,places=2)
            with av.open(red['path']) as c:
                frames=list(c.decode(video=0));self.assertGreaterEqual(len(frames),6)
                for frame in frames:
                    r,g,b=frame.to_image().getpixel((32,32));self.assertGreater(r,b+100)

