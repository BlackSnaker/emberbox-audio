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

    def test_frequent_small_waves_overlap_thaw_without_exceeding_live_budget(self):
        for width,height in ((320,230),(460,430),(1920,1080)):
            model=SnowShower(4);model.start(width,height,frequent=True)
            shelves=[('cover',12,width-12,100)]
            emissions=[];previous=0;overlap=False
            for frame in range(60*52):
                dots=model.advance(frame/60,shelves)
                if model.spawned>previous:
                    emissions.append(frame/60)
                    if frame/60>5 and any(d[2]<0 for d in dots):overlap=True
                    previous=model.spawned
                self.assertLessEqual(len(dots),model.cap,'Frequency must not increase peak snow density')
            self.assertGreaterEqual(len(emissions),model.batch*2)
            gaps=[b-a for a,b in zip(emissions,emissions[1:]) if b-a>1]
            self.assertTrue(gaps);self.assertLessEqual(max(gaps),8.5)
            self.assertTrue(overlap,'New flakes should arrive while older snow is still thawing')
            self.assertFalse(model.finished,'Frequent mode must not insert a long wait for all deposits to thaw')
            model.duration=model.age
            model.advance(model.age+32,shelves)
            self.assertTrue(model.finished);self.assertFalse(model.flakes)

    def test_monitor_sleep_does_not_replay_missed_waves(self):
        model=SnowShower(4);model.start(1920,1080,frequent=True)
        model.advance(0,[]);before=model.spawned
        model.advance(24*3600,[])
        self.assertLessEqual(model.spawned,before+1)
        self.assertLessEqual(len(model.flakes),1)



class SnowClockTests(unittest.TestCase):
    def test_high_refresh_displays_only_advance_snow_at_sixty_hz(self):
        from winter_snow_model import SnowClock
        for rate in (60,120,144,165,240):
            clock=SnowClock();times=[i/rate for i in range(rate*3)]
            updates=sum(clock.due(t) for t in times)
            self.assertLessEqual(abs(updates-180),1,(rate,updates))

    def test_clock_jitter_does_not_halve_sixty_hz_animation(self):
        from winter_snow_model import SnowClock
        clock=SnowClock()
        times=[i/60+(.0007 if i%2 else -.0007) for i in range(120)]
        self.assertGreaterEqual(sum(clock.due(t) for t in times),119)
        self.assertFalse(clock.due(times[-1]))

    def test_resume_and_slower_displays_do_not_replay_frames(self):
        from winter_snow_model import SnowClock
        clock=SnowClock();self.assertTrue(clock.due(100.))
        self.assertTrue(clock.due(1000.));self.assertFalse(clock.due(1000.))
        self.assertTrue(clock.due(10.))
        clock.reset();self.assertEqual(sum(clock.due(i/30) for i in range(60)),60)


class SnowDamageTests(unittest.TestCase):
    def test_only_moving_footprints_are_invalidated(self):
        from types import SimpleNamespace
        from winter_snow import WinterSnow
        calls=[]
        area=SimpleNamespace(get_allocated_width=lambda:1920,get_allocated_height=lambda:1080,
                             queue_draw_area=lambda *rect:calls.append(rect))
        snow=SimpleNamespace(area=area)
        still=(100.,100.,-4.,.5,1.);old=(900.,400.,2.,.5,2.);new=(901.,401.,2.,.5,2.)
        WinterSnow.invalidate(snow,[still,old],[still,new])
        self.assertEqual(len(calls),1,'Overlapping footprints must share one small damage request')
        self.assertLess(snow.damage_pixels,200,'Snow must never invalidate a fullscreen GL surface')
        calls.clear();WinterSnow.invalidate(snow,[still,new],[still,new])
        self.assertFalse(calls);self.assertEqual(snow.damage_pixels,0)

    def test_footprints_are_clipped_to_the_widget(self):
        from types import SimpleNamespace
        from winter_snow import WinterSnow
        calls=[]
        area=SimpleNamespace(get_allocated_width=lambda:320,get_allocated_height=lambda:230,
                             queue_draw_area=lambda *rect:calls.append(rect))
        snow=SimpleNamespace(area=area)
        WinterSnow.invalidate(snow,[],[(0.,0.,2.,.5,2.),(500.,500.,2.,.5,2.)])
        self.assertEqual(calls,[(0,0,4,4)])
