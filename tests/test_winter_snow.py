"""Snow motion is bounded, attaches to real edges and fully thaws at rest."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from winter_snow_model import SnowShower,MAX_FLAKES


class SnowTests(unittest.TestCase):
    def test_landing_soft_thaw_and_bounded_showers(self):
        for width,height in ((320,230),(460,430),(1920,1080)):
            model=SnowShower(4);model.start(width,height)
            shelves=[('cover',width*.25,width*.75,100),('console',20,width-20,height-50)]
            max_count=0;landed=False
            for frame in range(60*48):
                dots=model.advance(frame/60,shelves);max_count=max(max_count,len(dots))
                landed=landed or any(dot[2]<0 for dot in dots)
                self.assertTrue(all(0<=d[3]<=1 for d in dots))
            self.assertTrue(landed);self.assertLessEqual(max_count,MAX_FLAKES)
            self.assertLessEqual(model.spawned,model.cap);self.assertTrue(model.finished)
            self.assertFalse(model.flakes);self.assertFalse(model.previous)

    def test_settled_snow_follows_edge_geometry_then_disappears_with_it(self):
        model=SnowShower(9);model.start(460,400)
        shelves=[('cover',20,440,100)]
        for frame in range(600):
            dots=model.advance(frame/60,shelves)
            landed=[d for d in dots if d[2]<0]
            if landed:break
        self.assertTrue(landed)
        x,y=landed[0][:2]
        shifted=model.advance(frame/60,[('cover',40,460,140)])
        new=[d for d in shifted if d[2]<0][0]
        self.assertAlmostEqual(new[0],x+20);self.assertAlmostEqual(new[1],y+40)
        cleared=model.advance(frame/60,[])
        self.assertFalse(any(d[2]<0 for d in cleared),'No floating deposits after changing pages')

    def test_flight_positions_are_independent_of_refresh_rate(self):
        a=SnowShower(2);b=SnowShower(2);a.start(460,500);b.start(460,500)
        for frame in range(61):a.advance(frame/60,[])
        for frame in range(145):b.advance(frame/144,[])
        first=a.advance(1.,[]);second=b.advance(1.,[])
        self.assertEqual(first,second,'Refresh-rate jitter must not alter snow flight')

    def test_snow_cap_morph_and_melt_are_continuous(self):
        model=SnowShower(4);model.start(460,400)
        shelves=[('edge',1,459,80)]
        for frame in range(600):
            model.advance(frame/60,shelves)
            landed=next((f for f in model.flakes if f.landed>=0),None)
            if landed:break
        self.assertIsNotNone(landed)
        first=model.advance(model.age,shelves)[0]
        self.assertAlmostEqual(first[4],landed.size,places=4)
        t=landed.landed+landed.hold
        normal=model.advance(t,shelves)
        before=next(d for d in normal if abs(d[0]-first[0])<.001 and d[2]<0)
        middle=model.advance(t+landed.thaw*.5,shelves)
        fading=next(d for d in middle if abs(d[0]-first[0])<.001 and d[2]<0)
        self.assertGreater(before[3],fading[3]);self.assertAlmostEqual(fading[3],before[3]*.5,places=4)
